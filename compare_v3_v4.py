#!/usr/bin/env python3
"""
compare_v3_v4.py — Side-by-side V3.4 vs V4 comparison artifacts

Reads existing V3.4 outputs (stratford_rcs_scores.csv) and freshly-computed V4
outputs (stratford_rcs_v4_scores.json) and writes:

    stratford_v3_v4_comparison.csv       per-venue side-by-side
    stratford_v3_v4_distribution.json    aggregate stats for both models
    stratford_v3_v4_movers.json          top movers, drops, staybes
    stratford_v3_v4_sanity.json          sanity checks

The markdown assessment at docs/DayDine-V4-Scoring-Comparison.md is authored
separately.

Reason-for-change classification is heuristic — a single primary_reason plus
a list of reason_tags. Definitions:
    sentiment_removal       V3.4 sentiment_score moved its rank; V4 does not.
    google_de_overweight    V3.4 google_tier_score high; V4 customer shrunk.
    low_evidence_gating     V4 class is Directional-C or Profile-only-D.
    penalty_logic           V4 applied a cap or CH penalty V3.4 did not.
    missing_source_disc.    Few sources present; V3.4 renormalised up.
    entity_ambiguity        V4 entity_match != confirmed.
    shrinkage_low_counts    Low Google/TA counts; V4 shrinkage pulled score.
"""
from __future__ import annotations

import csv
import json
import os
import statistics
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
V3_CSV    = os.path.join(HERE, "stratford_rcs_scores.csv")
V4_JSON   = os.path.join(HERE, "stratford_rcs_v4_scores.json")
RECORDS   = os.path.join(HERE, "stratford_establishments.json")
OUT_CSV   = os.path.join(HERE, "stratford_v3_v4_comparison.csv")
OUT_DIST  = os.path.join(HERE, "stratford_v3_v4_distribution.json")
OUT_MOVE  = os.path.join(HERE, "stratford_v3_v4_movers.json")
OUT_SANE  = os.path.join(HERE, "stratford_v3_v4_sanity.json")


def _load_v3() -> dict[str, dict[str, Any]]:
    with open(V3_CSV, newline="", encoding="utf-8") as f:
        return {row["fhrsid"]: row for row in csv.DictReader(f)}


def _load_v4() -> dict[str, dict[str, Any]]:
    with open(V4_JSON, encoding="utf-8") as f:
        return json.load(f)


def _load_records() -> dict[str, dict[str, Any]]:
    with open(RECORDS, encoding="utf-8") as f:
        return json.load(f)


def _f(x: Any) -> float | None:
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _classify_reasons(v3: dict[str, Any], v4: dict[str, Any],
                       rec: dict[str, Any]) -> tuple[str, list[str]]:
    tags: list[str] = []

    v3_final = _f(v3.get("rcs_final"))
    v4_final = _f(v4.get("rcs_v4_final"))
    delta = None if (v3_final is None or v4_final is None) else v4_final - v3_final

    v3_rank = v3.get("rcs_band") or ""
    v4_class = v4.get("confidence_class") or ""

    sentiment = _f(v3.get("sentiment_score"))
    red_flags = _f(v3.get("red_flag_count"))
    g_tier = _f(v3.get("google_tier_score"))
    sig_avail = _f(v3.get("signals_available")) or 0
    sig_total = _f(v3.get("signals_total")) or 40

    # Customer-platform data from V4 record
    platforms = (v4.get("components", {})
                 .get("customer_validation", {})
                 .get("platforms", {}))
    plat_count = len(platforms)
    google_n = (platforms.get("google") or {}).get("count", 0)
    ta_n = (platforms.get("tripadvisor") or {}).get("count", 0)

    # Sentiment_removal: V3.4 had non-trivial sentiment signal and V4 dropped
    if sentiment is not None and abs(sentiment) >= 0.5 and delta is not None and delta < -0.3:
        tags.append("sentiment_removal")
    if red_flags and red_flags >= 1 and delta is not None and delta < -0.3:
        tags.append("sentiment_removal")

    # Google de-overweight: V3.4 google tier >= 9 and V4 customer < 8
    cv_score = (v4.get("components", {})
                .get("customer_validation", {}).get("score"))
    if g_tier is not None and g_tier >= 9.0 and cv_score is not None and cv_score < 8.0:
        tags.append("google_de_overweight")

    # Low evidence gating
    if v4_class in {"Directional-C", "Profile-only-D"}:
        tags.append("low_evidence_gating")

    # Penalty logic: V4 has caps applied that V3.4 did not surface
    if v4.get("caps_applied") or v4.get("penalties_applied"):
        tags.append("penalty_logic")

    # Missing source discipline: few signals in V3, small number of platforms in V4
    coverage = sig_avail / sig_total if sig_total else 0
    if coverage < 0.35 and plat_count <= 1:
        tags.append("missing_source_discipline")

    # Entity ambiguity
    if v4.get("entity_match_status") != "confirmed":
        tags.append("entity_ambiguity")

    # Shrinkage on low counts
    if 0 < google_n < 30 or 0 < ta_n < 10:
        tags.append("shrinkage_low_counts")

    # Primary reason — priority order matches severity of explanation
    priority = [
        "low_evidence_gating",
        "penalty_logic",
        "entity_ambiguity",
        "sentiment_removal",
        "google_de_overweight",
        "shrinkage_low_counts",
        "missing_source_discipline",
    ]
    primary = next((t for t in priority if t in tags), "structural_shift")
    if not tags:
        tags = ["structural_shift"]
    return primary, tags


# ---------------------------------------------------------------------------
# Comparison CSV
# ---------------------------------------------------------------------------

COLS = [
    "fhrsid", "business_name", "category", "postcode",
    "v3_rank", "v3_final", "v3_band", "v3_confidence",
    "v4_final", "v4_class", "v4_rankable", "v4_league_eligible",
    "delta",
    "v4_trust", "v4_customer", "v4_commercial",
    "v4_platforms", "v4_reviews",
    "v3_sentiment", "v3_red_flags", "v3_google_tier",
    "v4_penalties", "v4_caps",
    "primary_reason", "reason_tags",
]


def build_comparison(v3: dict, v4: dict, records: dict) -> list[dict]:
    rows: list[dict] = []
    ids = set(v3) | set(v4)
    for fid in ids:
        a = v3.get(fid, {})
        b = v4.get(fid, {})
        rec = records.get(fid) or records.get(str(fid)) or {}
        v3_final = _f(a.get("rcs_final"))
        v4_final = _f(b.get("rcs_v4_final"))
        delta = None if (v3_final is None or v4_final is None) else round(v4_final - v3_final, 3)
        primary, tags = _classify_reasons(a, b, rec)
        comp = b.get("components", {})
        platforms = comp.get("customer_validation", {}).get("platforms", {})
        caps = "|".join(c.get("code", "") for c in b.get("caps_applied", []))
        pens = "|".join(p.get("code", "") for p in b.get("penalties_applied", []))
        rows.append({
            "fhrsid": fid,
            "business_name": a.get("business_name") or b.get("name") or rec.get("n"),
            "category": a.get("category", ""),
            "postcode": a.get("postcode") or rec.get("pc", ""),
            "v3_rank": a.get("rank", ""),
            "v3_final": v3_final,
            "v3_band": a.get("rcs_band", ""),
            "v3_confidence": a.get("confidence", ""),
            "v4_final": v4_final,
            "v4_class": b.get("confidence_class", ""),
            "v4_rankable": b.get("rankable", ""),
            "v4_league_eligible": b.get("league_table_eligible", ""),
            "delta": delta,
            "v4_trust": (comp.get("trust_compliance") or {}).get("score"),
            "v4_customer": (comp.get("customer_validation") or {}).get("score"),
            "v4_commercial": (comp.get("commercial_readiness") or {}).get("score"),
            "v4_platforms": "|".join(platforms.keys()),
            "v4_reviews": sum((p or {}).get("count", 0) for p in platforms.values()),
            "v3_sentiment": _f(a.get("sentiment_score")),
            "v3_red_flags": a.get("red_flag_count", ""),
            "v3_google_tier": _f(a.get("google_tier_score")),
            "v4_penalties": pens,
            "v4_caps": caps,
            "primary_reason": primary,
            "reason_tags": "|".join(tags),
        })
    # Sort by absolute delta descending (venues that moved most first), then
    # fallback to V4 score
    def sort_key(r):
        d = r.get("delta")
        return (-(abs(d) if d is not None else -1), -(r.get("v4_final") or 0))
    rows.sort(key=sort_key)
    return rows


def write_csv(path: str, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------------------
# Distribution diagnostics
# ---------------------------------------------------------------------------

V3_BANDS = ["Excellent", "Good", "Generally Satisfactory",
            "Improvement Necessary", "Major Improvement", "Urgent Improvement"]
V4_CLASSES = ["Rankable-A", "Rankable-B", "Directional-C", "Profile-only-D"]


def _stats(vals: list[float]) -> dict[str, Any]:
    if not vals:
        return {"n": 0}
    return {
        "n": len(vals),
        "mean": round(statistics.mean(vals), 3),
        "median": round(statistics.median(vals), 3),
        "stdev": round(statistics.pstdev(vals), 3) if len(vals) > 1 else 0,
        "min": round(min(vals), 3),
        "max": round(max(vals), 3),
    }


def distribution(rows: list[dict]) -> dict[str, Any]:
    v3_scores = [r["v3_final"] for r in rows if r["v3_final"] is not None]
    v4_scores = [r["v4_final"] for r in rows if r["v4_final"] is not None]
    v4_ranked = [r["v4_final"] for r in rows
                 if r["v4_final"] is not None and r["v4_rankable"] is True]

    v3_band_counts = {b: 0 for b in V3_BANDS}
    for r in rows:
        b = r.get("v3_band") or ""
        if b in v3_band_counts:
            v3_band_counts[b] += 1

    v4_class_counts = {c: 0 for c in V4_CLASSES}
    for r in rows:
        c = r.get("v4_class") or ""
        if c in v4_class_counts:
            v4_class_counts[c] += 1

    # Cross-tab V3 band -> V4 class
    xtab: dict[str, dict[str, int]] = {b: {c: 0 for c in V4_CLASSES} for b in V3_BANDS}
    xtab["(no_v3_band)"] = {c: 0 for c in V4_CLASSES}
    for r in rows:
        b = r.get("v3_band") or "(no_v3_band)"
        c = r.get("v4_class") or ""
        if b in xtab and c in xtab[b]:
            xtab[b][c] += 1

    total = len(rows)
    v3_ranked_n = sum(1 for r in rows if r["v3_final"] is not None and r.get("v3_rank"))
    v4_rankable_n = sum(1 for r in rows if r["v4_rankable"] is True)
    v4_league_n = sum(1 for r in rows if r["v4_league_eligible"] is True)

    v3_top = v3_band_counts["Excellent"]
    v4_top = v4_class_counts["Rankable-A"]

    return {
        "total_venues": total,
        "v3": {
            "ranked": v3_ranked_n,
            "ranked_pct": round(100 * v3_ranked_n / total, 1) if total else 0,
            "scores": _stats(v3_scores),
            "band_distribution": {
                b: {"count": v3_band_counts[b],
                    "pct": round(100 * v3_band_counts[b] / total, 1) if total else 0}
                for b in V3_BANDS
            },
            "top_band_count": v3_top,
            "top_band_pct": round(100 * v3_top / total, 1) if total else 0,
        },
        "v4": {
            "rankable": v4_rankable_n,
            "rankable_pct": round(100 * v4_rankable_n / total, 1) if total else 0,
            "league_eligible": v4_league_n,
            "league_eligible_pct": round(100 * v4_league_n / total, 1) if total else 0,
            "scores_all": _stats(v4_scores),
            "scores_rankable_only": _stats(v4_ranked),
            "class_distribution": {
                c: {"count": v4_class_counts[c],
                    "pct": round(100 * v4_class_counts[c] / total, 1) if total else 0}
                for c in V4_CLASSES
            },
            "top_class_count": v4_top,
            "top_class_pct": round(100 * v4_top / total, 1) if total else 0,
        },
        "cross_tab_v3_band_to_v4_class": xtab,
    }


# ---------------------------------------------------------------------------
# Movers
# ---------------------------------------------------------------------------

def movers(rows: list[dict]) -> dict[str, Any]:
    with_delta = [r for r in rows if r["delta"] is not None]
    up = sorted(with_delta, key=lambda r: -r["delta"])[:20]
    down = sorted(with_delta, key=lambda r: r["delta"])[:20]
    dropped = [r for r in rows
               if r["v3_band"] in V3_BANDS[:3]
               and r["v4_class"] in {"Directional-C", "Profile-only-D"}]
    still_top = [r for r in rows
                 if r["v3_band"] == "Excellent" and r["v4_class"] in {"Rankable-A", "Rankable-B"}
                 and (r["v4_final"] or 0) >= 8.0]
    still_top.sort(key=lambda r: -(r["v4_final"] or 0))
    return {
        "top_20_risers": [_brief(r) for r in up],
        "top_20_fallers": [_brief(r) for r in down],
        "dropped_from_ranking": [_brief(r) for r in dropped],
        "still_top_under_both": [_brief(r) for r in still_top[:30]],
    }


def _brief(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "fhrsid": r["fhrsid"],
        "name": r["business_name"],
        "category": r["category"],
        "v3_final": r["v3_final"],
        "v3_band": r["v3_band"],
        "v4_final": r["v4_final"],
        "v4_class": r["v4_class"],
        "delta": r["delta"],
        "primary_reason": r["primary_reason"],
        "reason_tags": r["reason_tags"],
        "v4_reviews": r["v4_reviews"],
        "v4_platforms": r["v4_platforms"],
    }


# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------

HIGH_PROFILE_NAMES = [
    "Vintner", "Dirty Duck", "Opposition", "Rooftop", "Loxley",
    "Black Swan", "Stratford Manor", "Arden", "Church Street Townhouse",
    "No 9 Church Street", "Lambs", "Oscar's",
]


def sanity_checks(rows: list[dict]) -> dict[str, Any]:
    # Suspiciously high V4 with thin evidence
    suspiciously_high = sorted(
        [r for r in rows
         if r["v4_final"] is not None and r["v4_final"] >= 7.5
         and (r["v4_reviews"] or 0) < 30],
        key=lambda r: -(r["v4_final"] or 0),
    )[:20]

    # Now excluded from ranking but were in V3.4 rankings
    newly_excluded = [r for r in rows
                      if r["v3_final"] is not None and r.get("v3_rank")
                      and r["v4_rankable"] is not True]

    # Top band inflation check
    total_v4 = sum(1 for r in rows)
    rankable_v4 = sum(1 for r in rows if r["v4_rankable"] is True)
    in_top_half = sum(1 for r in rows
                      if r["v4_rankable"] is True
                      and (r["v4_final"] or 0) >= 8.0)

    # High-profile presence
    lower_names = {r["business_name"].lower() if r["business_name"] else "": r
                   for r in rows}
    high_profile_status = []
    for hp in HIGH_PROFILE_NAMES:
        hits = [r for n, r in lower_names.items() if n and hp.lower() in n]
        if hits:
            best = max(hits, key=lambda r: r.get("v4_final") or 0)
            high_profile_status.append({
                "query": hp, "match": best["business_name"],
                "v3_final": best["v3_final"], "v4_final": best["v4_final"],
                "v4_class": best["v4_class"],
                "v4_rankable": best["v4_rankable"],
            })
        else:
            high_profile_status.append({"query": hp, "match": None})

    return {
        "suspiciously_high_with_thin_evidence": [_brief(r) for r in suspiciously_high],
        "newly_excluded_from_ranking": [_brief(r) for r in newly_excluded],
        "top_band_inflation": {
            "total": total_v4,
            "rankable": rankable_v4,
            "rankable_with_final_ge_8": in_top_half,
            "pct_of_rankable_ge_8": round(100 * in_top_half / rankable_v4, 1)
                if rankable_v4 else 0,
        },
        "high_profile_presence": high_profile_status,
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> int:
    v3 = _load_v3()
    v4 = _load_v4()
    records = _load_records()
    rows = build_comparison(v3, v4, records)
    write_csv(OUT_CSV, rows)
    with open(OUT_DIST, "w", encoding="utf-8") as f:
        json.dump(distribution(rows), f, indent=2)
    with open(OUT_MOVE, "w", encoding="utf-8") as f:
        json.dump(movers(rows), f, indent=2)
    with open(OUT_SANE, "w", encoding="utf-8") as f:
        json.dump(sanity_checks(rows), f, indent=2)
    print(f"Wrote: {OUT_CSV}")
    print(f"Wrote: {OUT_DIST}")
    print(f"Wrote: {OUT_MOVE}")
    print(f"Wrote: {OUT_SANE}")
    print(f"Compared {len(rows)} venues")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
