#!/usr/bin/env python3
"""
gbp_completeness.py — Google Business Profile completeness scorer.

Scores each establishment 0-10 based on how many GBP attributes are
populated from existing Google Places enrichment data.

Attributes checked:
  - Has rating (gr)
  - Has reviews (grc > 0)
  - Has photos (gpc > 0)
  - Has opening hours (goh)
  - Has price level (gpl)
  - Has place types (gty)
  - Has place ID (gpid)
  - Review count >= 10 (meaningful volume)
  - Review count >= 100 (strong presence)
  - Has website inferred (web)

Score = (attributes_present / 10) * 10, SCP 0.62

Reads:  stratford_establishments.json
Writes: Directly updates establishments with gbp_completeness field
"""

import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EST_PATH = os.path.join(REPO_ROOT, "stratford_establishments.json")


def score_gbp(record):
    """Score GBP completeness 0-10 based on populated attributes."""
    checks = 0
    total = 10

    # Has rating
    if record.get("gr") is not None:
        checks += 1

    # Has reviews
    grc = record.get("grc")
    if grc is not None and int(grc) > 0:
        checks += 1

    # Has photos
    gpc = record.get("gpc")
    if gpc is not None and int(gpc) > 0:
        checks += 1

    # Has opening hours
    goh = record.get("goh")
    if goh and isinstance(goh, list) and len(goh) > 0:
        checks += 1

    # Has price level
    if record.get("gpl") is not None:
        checks += 1

    # Has place types
    gty = record.get("gty")
    if gty and isinstance(gty, list) and len(gty) > 0:
        checks += 1

    # Has place ID
    if record.get("gpid"):
        checks += 1

    # Review volume >= 10
    try:
        if grc is not None and int(grc) >= 10:
            checks += 1
    except (ValueError, TypeError):
        pass

    # Review volume >= 100
    try:
        if grc is not None and int(grc) >= 100:
            checks += 1
    except (ValueError, TypeError):
        pass

    # Has website
    if record.get("web") is True:
        checks += 1

    return round(checks / total * 10, 1)


def main():
    if not os.path.exists(EST_PATH):
        print(f"ERROR: {EST_PATH} not found")
        sys.exit(1)

    with open(EST_PATH, "r", encoding="utf-8") as f:
        establishments = json.load(f)

    scored = 0
    total_score = 0
    for key, record in establishments.items():
        completeness = score_gbp(record)
        record["gbp_completeness"] = completeness
        scored += 1
        total_score += completeness

    with open(EST_PATH, "w", encoding="utf-8") as f:
        json.dump(establishments, f, indent=2, ensure_ascii=False)

    avg = total_score / scored if scored else 0
    high = sum(1 for v in establishments.values()
               if v.get("gbp_completeness", 0) >= 7)
    print(f"Scored GBP completeness for {scored} establishments")
    print(f"  Average: {avg:.1f}/10")
    print(f"  High completeness (7+): {high}")


if __name__ == "__main__":
    main()
