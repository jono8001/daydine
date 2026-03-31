#!/usr/bin/env python3
"""
classify_remaining.py — Tier 3 category classifier (web lookup fallback).

For establishments still categorised as 'Other' after Google type matching
(Tier 1) and name keyword matching (Tier 2), this script performs web
lookups to determine the business type.

Reads stratford_rcs_scores.csv, finds rows with category='Other',
searches for each business online, and writes updated categories to
stratford_category_overrides.json.

Usage:
    python .github/scripts/classify_remaining.py

The overrides file can be merged into the scoring pipeline by loading
it in rcs_scoring_stratford.py and applying overrides before CSV output.

Status: STUB — not yet implemented. Requires web search API access
(e.g. Brave Search API, Perplexity API, or Google Custom Search).
"""

import csv
import json
import os
import sys


def load_unclassified(csv_path):
    """Load establishments still categorised as 'Other'."""
    unclassified = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("category") == "Other":
                unclassified.append({
                    "fhrsid": row["fhrsid"],
                    "name": row["business_name"],
                    "postcode": row["postcode"],
                })
    return unclassified


def web_classify(name, postcode):
    """
    Look up a restaurant online and determine its category.

    TODO: Implement using one of:
    - Brave Search API: search "{name} {postcode} restaurant type"
    - Google Custom Search: similar query
    - Direct URL check: try common patterns like tripadvisor.co.uk/Restaurant_Review-*
    - Perplexity API: ask "What type of restaurant is {name} in {postcode}?"

    Returns (category, confidence) or (None, 0) if not found.
    """
    # STUB — return None until implemented
    return None, 0


def main():
    csv_path = "stratford_rcs_scores.csv"
    overrides_path = "stratford_category_overrides.json"

    if not os.path.exists(csv_path):
        print(f"ERROR: {csv_path} not found")
        sys.exit(1)

    unclassified = load_unclassified(csv_path)
    print(f"Found {len(unclassified)} establishments still categorised as 'Other'")

    if not unclassified:
        print("Nothing to classify — all establishments have categories.")
        return

    # Load existing overrides
    overrides = {}
    if os.path.exists(overrides_path):
        with open(overrides_path, "r", encoding="utf-8") as f:
            overrides = json.load(f)
        print(f"Loaded {len(overrides)} existing overrides")

    classified = 0
    for item in unclassified:
        fhrsid = item["fhrsid"]
        if fhrsid in overrides:
            continue  # already classified

        category, confidence = web_classify(item["name"], item["postcode"])
        if category:
            overrides[fhrsid] = {
                "category": category,
                "category_source": "web_lookup",
                "confidence": confidence,
                "name": item["name"],
            }
            classified += 1
            print(f"  {item['name']} -> {category} (confidence: {confidence})")

    # Save overrides
    with open(overrides_path, "w", encoding="utf-8") as f:
        json.dump(overrides, f, indent=2, ensure_ascii=False)

    print(f"\nClassified: {classified}, Total overrides: {len(overrides)}")
    print(f"Saved to {overrides_path}")


if __name__ == "__main__":
    main()
