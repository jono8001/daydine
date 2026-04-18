#!/usr/bin/env python3
"""
merge_tripadvisor.py — Merge TripAdvisor headline metadata into establishments.

Reads `stratford_tripadvisor.json` (produced by `consolidate_tripadvisor.py`)
and writes ONLY the headline-score fields into `stratford_establishments.json`:

    ta          — rating 0-5 (Customer Validation input, spec V4 §4)
    trc         — review count (Customer Validation input, spec V4 §4)
    ta_present  — boolean flag
    ta_url      — audit URL

Review text (`ta_reviews`), cuisine tags (`ta_cuisines`), ranking position,
and recency all stay in the side file. V4 headline scoring never consumes
review text (spec V4 §9) — keeping narrative fields out of
`stratford_establishments.json` prevents accidental ingestion downstream.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
ESTABLISHMENTS = os.path.join(REPO, "stratford_establishments.json")
TA_SIDE = os.path.join(REPO, "stratford_tripadvisor.json")

# Fields copied from the side file into establishments.json. Anything else
# is narrative/report-only and stays in the side file.
HEADLINE_FIELDS = ("ta", "trc", "ta_present", "ta_url")


def main() -> int:
    if not os.path.exists(ESTABLISHMENTS):
        print(f"ERROR: {ESTABLISHMENTS} not found", file=sys.stderr)
        return 1
    if not os.path.exists(TA_SIDE):
        print(f"No TripAdvisor side file ({TA_SIDE}); nothing to merge.")
        return 0

    with open(ESTABLISHMENTS, encoding="utf-8") as f:
        establishments = json.load(f)
    with open(TA_SIDE, encoding="utf-8") as f:
        ta_side = json.load(f)

    merged = 0
    skipped = 0
    for key, ta_entry in ta_side.items():
        if key.startswith("_"):  # _meta, _unmatched
            continue
        if key not in establishments:
            skipped += 1
            continue
        est = establishments[key]
        for fld in HEADLINE_FIELDS:
            if fld in ta_entry:
                est[fld] = ta_entry[fld]
        # Strip any legacy narrative fields that may have been merged by
        # earlier versions of this script. V4 does not read these and they
        # must not be in the scoring input.
        for legacy in ("ta_reviews", "ta_cuisines", "ta_recency",
                        "ta_price", "ta_ranking"):
            if legacy in est:
                del est[legacy]
        merged += 1

    with open(ESTABLISHMENTS, "w", encoding="utf-8") as f:
        json.dump(establishments, f, indent=2, ensure_ascii=False)

    with_ta = sum(1 for v in establishments.values() if v.get("ta") is not None)
    print(f"Merged TripAdvisor headline fields for {merged} venues "
          f"(skipped {skipped} unknown keys).")
    print(f"  Venues with ta rating after merge: "
          f"{with_ta}/{len(establishments)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
