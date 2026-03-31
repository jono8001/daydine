#!/usr/bin/env python3
"""
merge_enrichment.py — Merge Google enrichment data into establishments JSON.

Reads stratford_establishments.json and stratford_google_enrichment.json,
merges Google fields into the establishment records, and overwrites
stratford_establishments.json so the scoring pipeline picks them up.
"""

import json
import os
import sys


def main():
    est_path = "stratford_establishments.json"
    enrich_path = "stratford_google_enrichment.json"

    if not os.path.exists(est_path):
        print(f"ERROR: {est_path} not found")
        sys.exit(1)

    with open(est_path, "r", encoding="utf-8") as f:
        establishments = json.load(f)

    if not os.path.exists(enrich_path):
        print(f"No enrichment file found ({enrich_path}), skipping merge")
        return

    with open(enrich_path, "r", encoding="utf-8") as f:
        enrichment = json.load(f)

    merged = 0
    for key, google_data in enrichment.items():
        if key not in establishments:
            continue
        if google_data.get("_no_match"):
            continue

        # Merge Google fields into the establishment record
        for field in ["gr", "grc", "gpl", "gty", "gpc", "gpid", "goh", "g_reviews"]:
            if field in google_data:
                establishments[key][field] = google_data[field]
        merged += 1

    # Save merged data back
    with open(est_path, "w", encoding="utf-8") as f:
        json.dump(establishments, f, indent=2, ensure_ascii=False)

    print(f"Merged Google data for {merged}/{len(establishments)} establishments")

    # Print stats
    with_rating = sum(1 for v in establishments.values() if v.get("gr") is not None)
    with_reviews = sum(1 for v in establishments.values() if v.get("grc") is not None)
    with_photos = sum(1 for v in establishments.values() if v.get("gpc") is not None)
    print(f"  With Google rating: {with_rating}")
    print(f"  With review count:  {with_reviews}")
    print(f"  With photo count:   {with_photos}")


if __name__ == "__main__":
    main()
