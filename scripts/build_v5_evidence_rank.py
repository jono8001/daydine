#!/usr/bin/env python3
"""Prototype DayDine V5 Evidence Rank outputs beside V4.

This is deliberately non-destructive: it reads existing V4/public ranking assets and
coverage certificates, then emits experimental V5 JSON under assets/v5/.

V5.0 goal:
- preserve V4 as the implemented baseline;
- add Evidence Confidence, DayDine Signal, Gap Signal and category-normalised ranks;
- avoid Tripadvisor/OpenTable dependency;
- keep exact internal heuristics out of public display.

Inputs reused from prior work:
- assets/rankings/<market>.json
- assets/coverage/<market>.json
- assets/market-readiness/<market>.json
- <prefix>_rcs_v4_scores.json, referenced from readiness files where available

Outputs:
- assets/v5/<market>.json
- assets/v5/index.json
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RANKINGS_DIR = ROOT / "assets" / "rankings"
READINESS_DIR = ROOT / "assets" / "market-readiness"
COVERAGE_DIR = ROOT / "assets" / "coverage"
OUT_DIR = ROOT / "assets" / "v5"
DEFAULT_MARKETS = ("stratford-upon-avon", "leamington-spa")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("&", "and").split())


def public_slug(value: str) -> str:
    return "-".join(norm(value).replace("'", "").replace("/", " ").split())


def score_to_band(score: float) -> str:
    if score >= 9.25:
        return "Very Strong"
    if score >= 8.75:
        return "Strong"
    if score >= 7.75:
        return "Good"
    if score >= 6.5:
        return "Developing"
    return "Weak"


def review_volume_band(n: int) -> str:
    if n >= 750:
        return "very_high"
    if n >= 250:
        return "high"
    if n >= 100:
        return "medium"
    if n >= 30:
        return "low"
    return "thin"


def evidence_confidence(v4_record: dict[str, Any] | None, review_count: int, coverage_status: str, ambiguous_market: bool) -> str:
    if not v4_record:
        return "Profile Only"
    if not v4_record.get("rankable", True):
        return "Profile Only"
    if v4_record.get("entity_match_status") not in (None, "confirmed", "probable"):
        return "Low"
    platforms = (v4_record.get("source_family_summary") or {}).get("customer_platforms") or []
    single_platform = len(platforms) <= 1
    if review_count >= 750 and coverage_status == "ready" and not ambiguous_market and not single_platform:
        return "Very High"
    if review_count >= 250 and not ambiguous_market:
        return "High" if not single_platform else "Medium"
    if review_count >= 100:
        return "Medium"
    if review_count >= 30:
        return "Low"
    return "Profile Only"


def gap_signal(rank: int | None, review_count: int, score: float) -> str:
    """Directional gap heuristic for V5.0.

    Positive gap = strong underlying score with lower public visibility.
    Negative gap = high public visibility with weaker support.
    """
    if rank is None:
        return "Neutral"
    if score >= 8.75 and review_count < 250 and rank > 20:
        return "Positive Gap"
    if score < 7.75 and review_count >= 750 and rank <= 30:
        return "Negative Gap"
    return "Neutral"


def daydine_signal(rank: int | None, category_rank: int | None, confidence: str, gap: str, review_count: int, score: float) -> str:
    if confidence == "Profile Only":
        return "Profile Only"
    if confidence == "Low":
        return "Under-Evidenced"
    if gap == "Positive Gap":
        return "Hidden Gem"
    if gap == "Negative Gap":
        return "Overexposed"
    if rank is not None and rank <= 10 and confidence in {"High", "Very High", "Medium"} and score >= 8.75:
        return "Proven Leader"
    if category_rank is not None and category_rank <= 3 and score >= 8.5:
        return "Specialist Pick"
    if review_count >= 750 and score >= 8.0:
        return "Established Favourite"
    return "Tracked Venue"


def flatten_ranking(ranking: dict[str, Any]) -> list[dict[str, Any]]:
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for category in ranking.get("category_rankings") or []:
        for venue in category.get("venues") or []:
            key = (norm(venue.get("name")), norm(venue.get("postcode")))
            current = seen.get(key)
            if current is None or (venue.get("rank") or 10**9) < (current.get("rank") or 10**9):
                item = dict(venue)
                item["category"] = item.get("category") or category.get("category")
                item["category_slug"] = category.get("slug")
                seen[key] = item
    return list(seen.values())


def v4_by_name(records: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {norm(row.get("name")): row for row in records.values() if isinstance(row, dict)}


def build_market(slug: str, now: str) -> dict[str, Any]:
    ranking = load_json(RANKINGS_DIR / f"{slug}.json")
    coverage = load_json(COVERAGE_DIR / f"{slug}.json") if (COVERAGE_DIR / f"{slug}.json").exists() else {}
    readiness = load_json(READINESS_DIR / f"{slug}.json") if (READINESS_DIR / f"{slug}.json").exists() else {}
    scores_path = ROOT / readiness.get("files", {}).get("scores", "")
    v4_scores = load_json(scores_path) if scores_path.exists() else {}
    scores_by_name = v4_by_name(v4_scores)
    ambiguous_market = bool((readiness.get("counts") or {}).get("duplicate_or_ambiguous_gpid_groups"))
    coverage_status = coverage.get("status") or readiness.get("status") or "warning"

    records = []
    category_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in flatten_ranking(ranking):
        name = item.get("name", "Unnamed venue")
        v4 = scores_by_name.get(norm(name))
        review_count = int((item.get("tie_break") or {}).get("review_volume") or 0)
        score = float(item.get("rcs_final") or (v4 or {}).get("rcs_v4_final") or 0.0)
        category = item.get("category") or "Uncategorised"
        rank = item.get("rank")
        category_rank = item.get("category_rank")
        confidence = evidence_confidence(v4, review_count, coverage_status, ambiguous_market)
        gap = gap_signal(rank, review_count, score)
        signal = daydine_signal(rank, category_rank, confidence, gap, review_count, score)
        record = {
            "venue_id": public_slug(f"{name}-{item.get('postcode','')}")[:120],
            "market_slug": slug,
            "canonical_name": name,
            "postcode": item.get("postcode"),
            "category": category,
            "v4_public_rank": rank,
            "v4_public_rcs": score,
            "v5_score_estimate": round(score, 3),
            "v5_score_band": score_to_band(score),
            "v5_overall_rank": None,
            "v5_category_rank": None,
            "evidence_confidence": confidence,
            "coverage_status": coverage_status,
            "entity_resolution_confidence": (v4 or {}).get("entity_match_status", "unknown"),
            "daydine_signal": signal,
            "daydine_gap_signal": gap,
            "review_volume_band": review_volume_band(review_count),
            "movement_30d": item.get("movement", "same"),
            "movement_previous_period": item.get("movement_delta", 0),
            "last_updated": now,
            "source_refresh_summary": {
                "v4_source": readiness.get("files", {}).get("scores"),
                "ranking_source": f"assets/rankings/{slug}.json",
                "coverage_certificate": f"assets/coverage/{slug}.json",
                "authorised_review_evidence": "Google rating/count where present in V4 source records",
                "tripadvisor_opentable_dependency": "none"
            },
            "public_intelligence_note": intelligence_note(signal, confidence, gap, rank, category_rank),
            "internal_diagnostics": {
                "review_count": review_count,
                "v4_confidence_class": (v4 or {}).get("confidence_class"),
                "source_family_summary": (v4 or {}).get("source_family_summary"),
                "v4_components": (v4 or {}).get("components"),
                "prototype_caveat": "V5.0 deterministic prototype derived from existing V4/public ranking assets; not yet public cutover output."
            }
        }
        records.append(record)
        category_groups[category].append(record)

    records.sort(key=lambda r: (-float(r["v5_score_estimate"]), str(r["canonical_name"]).lower()))
    for idx, record in enumerate(records, start=1):
        record["v5_overall_rank"] = idx
    for category_records in category_groups.values():
        category_records.sort(key=lambda r: (-float(r["v5_score_estimate"]), str(r["canonical_name"]).lower()))
        for idx, record in enumerate(category_records, start=1):
            record["v5_category_rank"] = idx

    public_records = [strip_internal(record) for record in records]
    return {
        "market_slug": slug,
        "market_name": ranking.get("display_name") or coverage.get("market_name") or slug,
        "generated_at": now,
        "status": "experimental",
        "methodology_version": "V5.0 deterministic Evidence Rank prototype",
        "v4_baseline_methodology": ranking.get("methodology_version"),
        "coverage_certificate_url": f"/assets/coverage/{slug}.json",
        "public_copy_guardrail": "Experimental V5 output. Do not claim Tripadvisor/OpenTable ingestion. Do not publish exact weights/formula.",
        "counts": {
            "records": len(records),
            "proven_leaders": sum(1 for r in records if r["daydine_signal"] == "Proven Leader"),
            "hidden_gems": sum(1 for r in records if r["daydine_signal"] == "Hidden Gem"),
            "overexposed": sum(1 for r in records if r["daydine_signal"] == "Overexposed"),
            "profile_only": sum(1 for r in records if r["daydine_signal"] == "Profile Only"),
        },
        "records": public_records,
        "internal_records": records,
    }


def intelligence_note(signal: str, confidence: str, gap: str, rank: int | None, category_rank: int | None) -> str:
    if signal == "Proven Leader":
        return "A strong position with a useful evidence base and low immediate visibility risk."
    if signal == "Hidden Gem":
        return "A strong underlying profile relative to current public visibility."
    if signal == "Overexposed":
        return "High public visibility relative to supporting evidence; treat claims carefully."
    if signal == "Specialist Pick":
        return "Particularly strong within its category or occasion context."
    if signal == "Under-Evidenced":
        return "Useful listing, but evidence remains thin or incomplete."
    if signal == "Profile Only":
        return "Listed for coverage, but not confidently ranked."
    return "Tracked within the local DayDine market with evidence confidence and category context."


def strip_internal(record: dict[str, Any]) -> dict[str, Any]:
    public = dict(record)
    public.pop("internal_diagnostics", None)
    return public


def main() -> None:
    parser = argparse.ArgumentParser(description="Build V5 Evidence Rank prototype outputs beside V4.")
    parser.add_argument("--markets", nargs="*", default=list(DEFAULT_MARKETS), help="Market slugs to process")
    args = parser.parse_args()

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    index_entries = []
    for slug in args.markets:
        market_output = build_market(slug, now)
        write_json(OUT_DIR / f"{slug}.json", market_output)
        index_entries.append(
            {
                "market_slug": slug,
                "market_name": market_output["market_name"],
                "status": market_output["status"],
                "methodology_version": market_output["methodology_version"],
                "records": market_output["counts"]["records"],
                "url": f"/assets/v5/{slug}.json",
                "coverage_certificate_url": market_output["coverage_certificate_url"],
            }
        )

    write_json(
        OUT_DIR / "index.json",
        {
            "generated_at": now,
            "status": "experimental",
            "total_markets": len(index_entries),
            "markets": index_entries,
        },
    )
    print(f"Wrote {len(index_entries)} V5 prototype market file(s) to {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
