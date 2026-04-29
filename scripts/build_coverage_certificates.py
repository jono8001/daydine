#!/usr/bin/env python3
"""Build DayDine market coverage certificates from readiness outputs.

The first build phase needs coverage certificates for Stratford-upon-Avon and
Leamington Spa. This script makes those certificates repeatable instead of being
one-off hand-authored JSON files.

Inputs reused from prior work:
- assets/market-readiness/index.json
- assets/market-readiness/<market>.json
- data/ranking_areas.json, referenced only through readiness metadata

Outputs:
- assets/coverage/<market>.json
- assets/coverage/index.json
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
READINESS_DIR = ROOT / "assets" / "market-readiness"
COVERAGE_DIR = ROOT / "assets" / "coverage"
DEFAULT_MARKETS = ("stratford-upon-avon", "leamington-spa")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def display_month() -> str:
    # Existing V4/monthly artifacts are April 2026. Replace this later with
    # pipeline-run month once the monthly refresh runner owns certificate output.
    return "2026-04"


def certificate_from_readiness(readiness: dict[str, Any], now: str) -> dict[str, Any]:
    slug = readiness["market"]
    name = readiness.get("display_name", slug)
    counts = readiness.get("counts", {})
    files = readiness.get("files", {})
    total = int(counts.get("total_establishments") or 0)
    scored = int(counts.get("total_scored") or 0)
    rankable = int(counts.get("total_rankable") or 0)
    public_ranked = int(counts.get("total_public_ranking_venues") or 0)
    ambiguous = int(counts.get("duplicate_or_ambiguous_gpid_groups") or 0)
    known_missing = int(counts.get("known_missing_venues") or 0)
    active_missing = int(counts.get("active_known_missing_venues") or 0)
    directional_or_profile = max(scored - rankable, 0)

    public_summary = (
        f"Coverage: {public_ranked} public ranking venues shown from {total} establishments reviewed. "
        f"{rankable} venues are currently rankable in the wider source set. "
        f"Known missing active venues: {active_missing}. "
        f"Ambiguous Google Place groups: {ambiguous}."
    )

    ambiguity_summary: list[str] = []
    if ambiguous:
        ambiguity_summary.append(f"{ambiguous} duplicate/ambiguous Google Place group(s) recorded in readiness output.")
    if active_missing:
        ambiguity_summary.append(f"{active_missing} active known-missing venue blocker(s) remain for this market.")
    else:
        ambiguity_summary.append(f"No active known-missing venue blocker is currently recorded for {name}.")

    admin_next_actions = [
        "Review remaining ambiguous Google Place groups before paid-client use.",
        "Confirm prominent public dining venues are present or listed as known-missing with a resolution path.",
        "Expose the public coverage summary on the market ranking page before V5 public cutover.",
    ]

    known_missing_rows = []
    for row in readiness.get("known_missing_venues") or []:
        known_missing_rows.append(
            {
                "fhrsid": row.get("fhrsid"),
                "public_name": row.get("public_name") or row.get("fsa_name"),
                "status": row.get("status"),
                "note": row.get("resolved_note") or row.get("reason"),
            }
        )

    return {
        "certificate_id": f"{slug}_{display_month()}",
        "market_slug": slug,
        "market_name": name,
        "month": display_month(),
        "generated_at": now,
        "source_readiness_asset": f"/assets/market-readiness/{slug}.json",
        "source_ranking_asset": f"/assets/rankings/{slug}.json",
        "status": readiness.get("status", "warning"),
        "publish_decision": "public ranking live; certificate flags readiness warnings for admin review",
        "summary_public": public_summary,
        "counts": {
            "fsa_records_considered": total,
            "candidate_dining_venues": scored,
            "included_in_public_ranking": public_ranked,
            "rankable_venues": rankable,
            "directional_or_profile_venues": directional_or_profile,
            "known_missing_venues": known_missing,
            "active_known_missing_venues": active_missing,
            "ambiguous_entity_groups": ambiguous,
            "category_ranking_entries": int(counts.get("total_category_ranking_entries") or 0),
        },
        "known_missing_high_profile_venues": known_missing_rows,
        "ambiguity_summary": ambiguity_summary,
        "admin_next_actions": admin_next_actions,
        "source_files": {
            "area_config": files.get("area_config", "data/ranking_areas.json"),
            "establishments": files.get("establishments"),
            "scores": files.get("scores"),
            "ranking": files.get("ranking"),
            "readiness": f"assets/market-readiness/{slug}.json",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build DayDine coverage certificates from readiness outputs.")
    parser.add_argument("--markets", nargs="*", default=list(DEFAULT_MARKETS), help="Market slugs to certify")
    args = parser.parse_args()

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    certificates = []
    for slug in args.markets:
        readiness_path = READINESS_DIR / f"{slug}.json"
        readiness = load_json(readiness_path)
        cert = certificate_from_readiness(readiness, now)
        write_json(COVERAGE_DIR / f"{slug}.json", cert)
        certificates.append(
            {
                "certificate_id": cert["certificate_id"],
                "market_slug": cert["market_slug"],
                "market_name": cert["market_name"],
                "month": cert["month"],
                "status": cert["status"],
                "url": f"/assets/coverage/{slug}.json",
                "summary_public": cert["summary_public"],
            }
        )

    status = "ready" if all(c["status"] == "ready" for c in certificates) else "warning"
    write_json(
        COVERAGE_DIR / "index.json",
        {
            "generated_at": now,
            "status": status,
            "total_certificates": len(certificates),
            "certificates": certificates,
        },
    )
    print(f"Wrote {len(certificates)} coverage certificate(s) to {COVERAGE_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
