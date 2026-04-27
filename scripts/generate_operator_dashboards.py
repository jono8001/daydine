#!/usr/bin/env python3
"""Generate static operator dashboard snapshots with monthly history.

MVP goal: make client screens repeatable and monitorable instead of hand-written.

Inputs:
- data/operator_dashboard_targets.json
- assets/rankings/<market>.json
- <source_prefix>_establishments.json
- <source_prefix>_rcs_v4_scores.json

Outputs:
- assets/operator-dashboards/<venue_slug>/<month>.json
- assets/operator-dashboards/<venue_slug>/latest.json
- assets/operator-dashboards/manifest.json

Every generated month is retained. latest.json points to the most recent month
and includes a history/time-series array so the client screen can show movement
over time.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
TARGETS_FILE = ROOT / "data" / "operator_dashboard_targets.json"
AREAS_FILE = ROOT / "data" / "ranking_areas.json"
OUT_DIR = ROOT / "assets" / "operator-dashboards"


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")


def norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def data_prefix_for_market(market_slug: str) -> str:
    areas = (read_json(AREAS_FILE, {"areas": []}) or {}).get("areas", [])
    for area in areas:
        if area.get("slug") == market_slug:
            if area.get("data_source_prefix"):
                return str(area["data_source_prefix"])
            slug = norm(area.get("slug"))
            la = norm(area.get("la_name"))
            if "stratford" in slug or "stratford" in la:
                return "stratford"
            if "leamington" in slug or "warwick" in la:
                return "leamington"
            return slugify(market_slug)
    return slugify(market_slug)


def all_ranking_rows(ranking: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen = set()
    for row in ranking.get("venues", []) or []:
        key = (norm(row.get("name")), norm(row.get("postcode")))
        rows.append(dict(row))
        seen.add(key)
    for group in ranking.get("category_rankings", []) or []:
        for row in group.get("venues", []) or []:
            key = (norm(row.get("name")), norm(row.get("postcode")))
            if key in seen:
                continue
            rows.append(dict(row))
            seen.add(key)
    return rows


def find_ranking_row(target: dict[str, Any], ranking: dict[str, Any]) -> dict[str, Any] | None:
    wanted_name = norm(target.get("venue"))
    wanted_pc = norm(target.get("postcode"))
    rows = all_ranking_rows(ranking)
    for row in rows:
        if norm(row.get("name")) == wanted_name and (not wanted_pc or norm(row.get("postcode")) == wanted_pc):
            return row
    for row in rows:
        row_name = norm(row.get("name"))
        if (wanted_name in row_name or row_name in wanted_name) and (not wanted_pc or norm(row.get("postcode")) == wanted_pc):
            return row
    return None


def find_fhrsid(target: dict[str, Any], establishments: dict[str, Any]) -> str | None:
    if target.get("fhrsid"):
        return str(target["fhrsid"])
    wanted_name = norm(target.get("venue"))
    wanted_pc = norm(target.get("postcode"))
    for fhrsid, row in establishments.items():
        names = [row.get("n"), row.get("public_name"), *(row.get("trading_names") or [])]
        if wanted_pc and norm(row.get("pc")) != wanted_pc:
            continue
        if any(norm(name) == wanted_name for name in names if name):
            return str(fhrsid)
    for fhrsid, row in establishments.items():
        names = [row.get("n"), row.get("public_name"), *(row.get("trading_names") or [])]
        if wanted_pc and norm(row.get("pc")) != wanted_pc:
            continue
        if any(wanted_name in norm(name) or norm(name) in wanted_name for name in names if name):
            return str(fhrsid)
    return None


def signed_gap(base: Any, other: Any) -> str:
    try:
        diff = float(other) - float(base)
        return f"{diff:+.3f}"
    except Exception:
        return "—"


def competitors(row: dict[str, Any], ranking: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    rows = [r for r in all_ranking_rows(ranking) if r.get("rank") is not None]
    rows.sort(key=lambda r: int(r.get("rank") or 9999))
    idx = next((i for i, r in enumerate(rows) if norm(r.get("name")) == norm(row.get("name")) and norm(r.get("postcode")) == norm(row.get("postcode"))), 0)
    window = rows[max(0, idx - 2):idx + 3]
    return [
        {
            "rank": r.get("rank"),
            "venue": r.get("name"),
            "category": r.get("category"),
            "rcs": r.get("rcs_final"),
            "gap": "you" if norm(r.get("name")) == norm(row.get("name")) and norm(r.get("postcode")) == norm(row.get("postcode")) else signed_gap(row.get("rcs_final"), r.get("rcs_final")),
        }
        for r in window[:limit]
    ]


def component_summary(key: str, comp: dict[str, Any]) -> str:
    if key == "trust_compliance":
        return "Compliance evidence from FHRS/FSA. This is a trust signal, not a food-quality score."
    if key == "customer_validation":
        platforms = comp.get("platforms", {}) or {}
        if len(platforms) <= 1:
            return "Single-platform evidence reduces confidence breadth even when rating strength is good."
        return "Multi-platform customer validation improves evidence breadth."
    if key == "commercial_readiness":
        return "Measures whether a guest can find, understand and act on the venue online."
    return "Component signal."


def score_components(score: dict[str, Any]) -> list[dict[str, Any]]:
    comps = score.get("components", {}) or {}
    labels = [
        ("trust_compliance", "Trust & Compliance"),
        ("customer_validation", "Customer Validation"),
        ("commercial_readiness", "Commercial Readiness"),
    ]
    result = []
    for key, label in labels:
        comp = comps.get(key, {}) or {}
        value = comp.get("score")
        if value is None:
            continue
        if key == "trust_compliance":
            evidence = f"FSA/FHRS present · {comp.get('signals_used', '—')} signals used"
        elif key == "customer_validation":
            platforms = comp.get("platforms", {}) or {}
            evidence = " · ".join(f"{name.title()} {p.get('count', '—')} reviews @ {p.get('raw', '—')}" for name, p in platforms.items()) or "Customer-platform evidence"
        elif key == "commercial_readiness":
            evidence = f"{comp.get('signals_used', '—')} commercial-readiness signals used"
        else:
            evidence = "Evidence present"
        result.append({
            "name": label,
            "score": round(float(value), 3),
            "summary": component_summary(key, comp),
            "evidence": evidence,
        })
    return result


def priorities(score: dict[str, Any], row: dict[str, Any]) -> list[dict[str, Any]]:
    comps = score.get("components", {}) or {}
    customer_platforms = (comps.get("customer_validation", {}) or {}).get("platforms", {}) or {}
    commercial = comps.get("commercial_readiness", {}) or {}
    output = []
    if len(customer_platforms) <= 1:
        output.append({
            "title": "Add or strengthen a second legitimate customer-platform listing",
            "target": "Customer Validation",
            "why": "The dashboard currently sees only one customer-platform family, which weakens confidence breadth.",
            "action": "Claim, clean or strengthen a suitable second listing such as TripAdvisor, OpenTable or another legitimate booking/review platform where appropriate.",
            "expected_upside": "Improves evidence breadth and may strengthen confidence class over time.",
        })
    try:
        commercial_score = float(commercial.get("score") or 0)
    except Exception:
        commercial_score = 0
    if commercial_score < 8:
        output.append({
            "title": "Reduce booking/contact friction",
            "target": "Commercial Readiness",
            "why": "Commercial Readiness is below the top band, so there may be visible friction in the customer path.",
            "action": "Check that website, menu, opening hours, phone and booking/reservation links are obvious and current on public profiles.",
            "expected_upside": "Improves customer-path confidence and reduces guest drop-off.",
        })
    output.append({
        "title": "Protect rank in the local score cluster",
        "target": "Ranking stability",
        "why": f"The venue is currently ranked #{row.get('rank', '—')} and nearby venues may be separated by small score gaps.",
        "action": "Monitor review-count movement, listing accuracy and any inspection changes monthly.",
        "expected_upside": "Protects public visibility and gives early warning of competitor movement.",
    })
    return output[:3]


def monthly_tracking(row: dict[str, Any], ranking: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"label": "Overall rank", "value": f"#{row.get('rank', '—')} of {ranking.get('total_venues', '—')}", "meaning": row.get("public_visibility_label") or "Tracked market record"},
        {"label": "Category rank", "value": f"#{row.get('category_rank', '—')}", "meaning": row.get("category_visibility_label") or "Category tracking"},
        {"label": "DayDine RCS", "value": str(row.get("rcs_final", "—")), "meaning": "Current baseline for future movement"},
        {"label": "Monthly movement", "value": row.get("movement") or "Baseline", "meaning": "Future snapshots can show up/down movement"},
    ]


def evidence(est: dict[str, Any], score: dict[str, Any]) -> dict[str, Any]:
    customer = ((score.get("components", {}) or {}).get("customer_validation", {}) or {}).get("platforms", {}) or {}
    google = customer.get("google", {}) if isinstance(customer, dict) else {}
    return {
        "fhrsid": str(est.get("id") or est.get("fhrsid") or ""),
        "fsa_rating": est.get("r") or est.get("fsa_rating_value"),
        "last_inspection_date": str(est.get("rd") or "")[:10],
        "google_rating": google.get("raw") or est.get("gr"),
        "google_review_count": google.get("count") or est.get("grc"),
        "google_place_id": est.get("gpid"),
        "website_present": bool(est.get("web") or est.get("web_url")),
        "menu_online": bool(est.get("menu") or est.get("menu_url")),
        "opening_hours": "present" if est.get("goh") else "unknown",
        "direct_booking_contact_observed": bool(est.get("reservable") or est.get("phone")),
    }


def tracking_status(row: dict[str, Any]) -> str:
    rank = row.get("rank")
    cat_rank = row.get("category_rank")
    if rank and int(rank) <= 30:
        return "Strong public visibility; protect position and monitor nearby score clusters."
    if cat_rank and int(cat_rank) <= 30:
        return "Category-visible venue; improve evidence breadth and monitor route to overall top 30."
    return "Tracked market record; focus on the highest-evidence gaps before using this as a sales claim."


def commercial_impact(score: dict[str, Any]) -> dict[str, str]:
    commercial_score = (((score.get("components", {}) or {}).get("commercial_readiness", {}) or {}).get("score"))
    try:
        value = float(commercial_score)
    except Exception:
        value = 0.0
    if value >= 8.5:
        monthly = "Low immediate friction"
        annual = "Protect existing demand capture"
    elif value >= 7:
        monthly = "£250 – £760"
        annual = "£3,000 – £9,120"
    else:
        monthly = "£500 – £1,500"
        annual = "£6,000 – £18,000"
    return {
        "confidence": "Low",
        "monthly_revenue_impact": monthly,
        "annual_projection": annual,
        "cost_band": "£200 – £1,000",
        "payback_window": "1 – 3 months",
        "wording_guardrail": "Directional estimate only. Exact numbers require internal cover and spend data.",
    }


def watch_list() -> list[str]:
    return [
        "Overall rank movement",
        "Category-rank movement",
        "Review-count movement",
        "Emergence or loss of a second review/listing platform",
        "Public contact/booking path completeness",
        "Any FHRS re-inspection activity",
    ]


def month_record(snapshot: dict[str, Any]) -> dict[str, Any]:
    evidence_blob = snapshot.get("evidence", {}) or {}
    return {
        "month": snapshot.get("month"),
        "overall_rank": snapshot.get("headline", {}).get("overall_rank"),
        "category_rank": snapshot.get("headline", {}).get("category_rank"),
        "public_rcs": snapshot.get("scores", {}).get("public_rcs"),
        "operator_v4_score": snapshot.get("scores", {}).get("operator_v4_score"),
        "google_review_count": evidence_blob.get("google_review_count"),
        "confidence_class": snapshot.get("scores", {}).get("confidence_class"),
        "status": snapshot.get("status"),
    }


def compute_deltas(history: list[dict[str, Any]]) -> dict[str, Any]:
    if len(history) < 2:
        return {
            "overall_rank_delta": 0,
            "category_rank_delta": 0,
            "public_rcs_delta": 0,
            "review_count_delta": 0,
            "summary": "Baseline month — movement will appear after the next monthly snapshot.",
        }
    previous = history[-2]
    current = history[-1]
    def delta(key: str) -> Any:
        try:
            return round(float(current.get(key)) - float(previous.get(key)), 3)
        except Exception:
            return None
    def rank_delta(key: str) -> Any:
        try:
            # Positive means improvement in rank position.
            return int(previous.get(key)) - int(current.get(key))
        except Exception:
            return None
    r_delta = rank_delta("overall_rank")
    c_delta = rank_delta("category_rank")
    rcs_delta = delta("public_rcs")
    reviews_delta = delta("google_review_count")
    parts = []
    if r_delta is not None:
        parts.append(f"overall rank {'up' if r_delta > 0 else 'down' if r_delta < 0 else 'flat'} {abs(r_delta)}")
    if rcs_delta is not None:
        parts.append(f"RCS {rcs_delta:+.3f}")
    if reviews_delta is not None:
        parts.append(f"Google reviews {reviews_delta:+.0f}")
    return {
        "overall_rank_delta": r_delta,
        "category_rank_delta": c_delta,
        "public_rcs_delta": rcs_delta,
        "review_count_delta": reviews_delta,
        "summary": "; ".join(parts) if parts else "Movement unavailable for this period.",
    }


def load_existing_history(venue_slug: str) -> list[dict[str, Any]]:
    folder = OUT_DIR / venue_slug
    records = []
    if not folder.exists():
        return []
    for path in sorted(folder.glob("*.json")):
        if path.name == "latest.json":
            continue
        data = read_json(path, {}) or {}
        if data.get("month"):
            records.append(month_record(data))
    return records


def attach_history(snapshot: dict[str, Any]) -> dict[str, Any]:
    existing = [r for r in load_existing_history(snapshot["venue_slug"]) if r.get("month") != snapshot.get("month")]
    records = existing + [month_record(snapshot)]
    records = sorted(records, key=lambda r: str(r.get("month") or ""))
    snapshot["history"] = records
    snapshot["movement"] = compute_deltas(records)
    return snapshot


def build_dashboard(target: dict[str, Any], month: str) -> dict[str, Any]:
    market_slug = target["market"]
    prefix = data_prefix_for_market(market_slug)
    ranking = read_json(ROOT / "assets" / "rankings" / f"{market_slug}.json", {}) or {}
    establishments = read_json(ROOT / f"{prefix}_establishments.json", {}) or {}
    scores = read_json(ROOT / f"{prefix}_rcs_v4_scores.json", {}) or {}
    row = find_ranking_row(target, ranking)
    if not row:
        raise SystemExit(f"Could not find venue '{target.get('venue')}' in assets/rankings/{market_slug}.json")
    fhrsid = find_fhrsid(target, establishments)
    est = establishments.get(fhrsid, {}) if fhrsid else {}
    score = scores.get(fhrsid, {}) if fhrsid else {}
    category_total = next((c.get("total_venues") for c in ranking.get("category_rankings", []) if c.get("category") == row.get("category")), None)
    public_visibility = " · ".join(x for x in [row.get("public_visibility_label"), row.get("category_visibility_label")] if x)
    operator_score = score.get("rcs_v4_final", row.get("rcs_final"))
    try:
        operator_score = round(float(operator_score), 3)
    except Exception:
        operator_score = None
    snapshot = {
        "id": f"{target['venue_slug']}-{month}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "venue_slug": target["venue_slug"],
        "venue": row.get("name") or target.get("venue"),
        "also_trading_as": target.get("also_trading_as") or "",
        "market": ranking.get("display_name") or market_slug,
        "market_slug": market_slug,
        "category": row.get("category"),
        "month": month,
        "status": target.get("status", "draft"),
        "client_status": target.get("client_status", "draft"),
        "operator_email": target.get("operator_email", ""),
        "methodology": ranking.get("methodology_version"),
        "headline": {
            "overall_rank": row.get("rank"),
            "overall_total": ranking.get("total_venues"),
            "category_rank": row.get("category_rank"),
            "category_total": category_total,
            "public_visibility": public_visibility,
            "tracking_status": tracking_status(row),
        },
        "scores": {
            "public_rcs": row.get("rcs_final"),
            "operator_v4_score": operator_score,
            "confidence_class": score.get("confidence_class") or row.get("daydine_scoring_status") or "tracked",
            "rankable": bool(score.get("rankable", True)),
            "league_eligible": bool(score.get("league_table_eligible", True)),
            "entity_match": score.get("entity_match_status") or est.get("entity_match") or "unknown",
        },
        "components": score_components(score),
        "monthly_tracking": monthly_tracking(row, ranking),
        "nearest_competitors": competitors(row, ranking),
        "priorities": priorities(score, row),
        "commercial_impact": commercial_impact(score),
        "watch_list": watch_list(),
        "evidence": evidence(est, score),
        "source_report": target.get("source_report", ""),
        "download_report_url": target.get("source_report", ""),
    }
    return attach_history(snapshot)


def generate(month_override: str | None = None, venue_filter: str | None = None) -> dict[str, Any]:
    config = read_json(TARGETS_FILE, {"dashboards": [], "month": "2026-04"}) or {}
    month = month_override or config.get("month") or "2026-04"
    dashboards = []
    for target in config.get("dashboards", []) or []:
        if venue_filter and target.get("venue_slug") != venue_filter:
            continue
        snapshot = build_dashboard(target, month)
        folder = OUT_DIR / snapshot["venue_slug"]
        month_path = folder / f"{month}.json"
        latest_path = folder / "latest.json"
        write_json(month_path, snapshot)
        write_json(latest_path, snapshot)
        dashboards.append({
            "id": snapshot["id"],
            "venue_slug": snapshot["venue_slug"],
            "venue": snapshot["venue"],
            "market": snapshot["market"],
            "category": snapshot["category"],
            "month": snapshot["month"],
            "status": snapshot["status"],
            "client_status": snapshot["client_status"],
            "snapshot_url": f"/assets/operator-dashboards/{snapshot['venue_slug']}/{month}.json",
            "latest_url": f"/assets/operator-dashboards/{snapshot['venue_slug']}/latest.json",
            "dashboard_url": f"/operator/{snapshot['venue_slug']}",
            "source_report": snapshot.get("source_report", ""),
            "history_months": len(snapshot.get("history", [])),
            "notes": "Generated operator dashboard snapshot with retained monthly history.",
        })
    manifest = {
        "last_updated": datetime.now(timezone.utc).date().isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "month": month,
        "dashboards": sorted(dashboards, key=lambda d: (d["venue"].lower(), d["month"])),
    }
    write_json(OUT_DIR / "manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", help="Snapshot month, YYYY-MM")
    parser.add_argument("--venue", help="Optional venue_slug to generate only one dashboard")
    args = parser.parse_args()
    manifest = generate(args.month, args.venue)
    print(f"Generated {len(manifest['dashboards'])} operator dashboard snapshot(s) for {manifest['month']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
