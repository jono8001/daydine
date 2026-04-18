#!/usr/bin/env python3
"""
tripadvisor_coverage.py — Produce coverage stats for the Stratford trial.

Reads `stratford_tripadvisor.json` (consolidated side file) and
`stratford_establishments.json` and emits `stratford_tripadvisor_coverage.json`
summarising:

- total venues attempted (everything in establishments.json)
- matched to TripAdvisor
- unmatched (raw TA record exists but could not be mapped to a fhrsid)
- venues eligible for TA search but with no raw record attempted
- coverage %
- examples of successful matches
- examples of failures

"Eligible" means the establishment passes the existing non-food exclusion
filter used by the collector (`should_search` in collect_tripadvisor_apify.py).
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
ESTABLISHMENTS = os.path.join(REPO, "stratford_establishments.json")
TA_SIDE = os.path.join(REPO, "stratford_tripadvisor.json")
OUT = os.path.join(REPO, "stratford_tripadvisor_coverage.json")


def _is_food_eligible(record: dict) -> bool:
    """Mirror of `should_search()` in collect_tripadvisor_apify.py."""
    gty = record.get("gty") or []
    types = set(gty) if isinstance(gty, list) else set()
    non_food = {"sports_club", "church", "place_of_worship", "insurance_agency",
                "miniature_golf_course", "gym", "fitness_center"}
    if non_food & types and not (types & {"restaurant", "cafe", "food",
                                           "bar", "pub"}):
        return False
    name = (record.get("n") or "").lower()
    skip_names = ["slimming world", "football club", "golf club",
                  "aston martin", "nfu mutual", "baptist church",
                  "horse sanctuary"]
    if any(sn in name for sn in skip_names):
        return False
    return True


def main() -> int:
    if not os.path.exists(ESTABLISHMENTS):
        print(f"ERROR: {ESTABLISHMENTS} not found", file=sys.stderr)
        return 1

    with open(ESTABLISHMENTS, encoding="utf-8") as f:
        establishments = json.load(f)

    ta_side: dict = {}
    unmatched_raw: list = []
    if os.path.exists(TA_SIDE):
        with open(TA_SIDE, encoding="utf-8") as f:
            ta_side = json.load(f)
        unmatched_raw = ta_side.get("_unmatched", []) or []

    total = len(establishments)
    eligible = {k: v for k, v in establishments.items() if _is_food_eligible(v)}
    ineligible_count = total - len(eligible)

    matched_entries = {k: v for k, v in ta_side.items()
                        if not k.startswith("_") and v.get("ta") is not None}
    matched_keys = set(matched_entries.keys())

    # Venues eligible but no raw record attempted / landed
    not_attempted = [k for k in eligible.keys() if k not in matched_keys]

    def _pick_examples(ids, limit=10):
        out = []
        for k in ids[:limit]:
            rec = establishments.get(k) or {}
            out.append({
                "fhrsid": k,
                "name": rec.get("n"),
                "postcode": rec.get("pc"),
                "google_count": rec.get("grc"),
                "google_rating": rec.get("gr"),
            })
        return out

    successful_examples = []
    for k, entry in list(matched_entries.items())[:10]:
        rec = establishments.get(k) or {}
        successful_examples.append({
            "fhrsid": k,
            "name": rec.get("n"),
            "postcode": rec.get("pc"),
            "ta": entry.get("ta"),
            "trc": entry.get("trc"),
            "ta_url": entry.get("ta_url"),
            "match_method": entry.get("match", {}).get("method"),
            "match_confidence": entry.get("match", {}).get("confidence"),
        })

    coverage = {
        "generated_by": "tripadvisor_coverage.py",
        "total_establishments": total,
        "ineligible_non_food": ineligible_count,
        "eligible_for_ta_search": len(eligible),
        "matched_to_tripadvisor": len(matched_entries),
        "unmatched_raw_records": len(unmatched_raw),
        "eligible_not_attempted": len(not_attempted),
        "coverage_pct_of_eligible": round(
            100 * len(matched_entries) / len(eligible), 1)
            if eligible else 0,
        "coverage_pct_of_total": round(
            100 * len(matched_entries) / total, 1) if total else 0,
        "successful_matches_examples": successful_examples,
        "unmatched_raw_examples": unmatched_raw[:10],
        "not_attempted_examples_by_review_volume": _pick_examples(
            sorted(not_attempted,
                    key=lambda k: -(establishments.get(k, {}).get("grc") or 0)),
            limit=15,
        ),
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(coverage, f, indent=2)

    print(f"Wrote {OUT}")
    print(f"  total: {total}, eligible: {len(eligible)}, "
          f"matched: {len(matched_entries)} "
          f"({coverage['coverage_pct_of_eligible']}% of eligible)")
    print(f"  unmatched_raw: {len(unmatched_raw)}, "
          f"not_attempted: {len(not_attempted)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
