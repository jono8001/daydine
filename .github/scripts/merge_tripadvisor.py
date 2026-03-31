#!/usr/bin/env python3
"""
merge_tripadvisor.py — Merge TripAdvisor data into establishments JSON.

Reads stratford_tripadvisor.json and merges ta (rating), trc (review count),
ta_url, ta_present, and ta_cuisines fields into stratford_establishments.json.
"""

import json
import os
import sys


def main():
    est_path = "stratford_establishments.json"
    ta_path = "stratford_tripadvisor.json"

    if not os.path.exists(est_path):
        print(f"ERROR: {est_path} not found")
        sys.exit(1)

    with open(est_path, "r", encoding="utf-8") as f:
        establishments = json.load(f)

    if not os.path.exists(ta_path):
        print(f"No TripAdvisor data found ({ta_path}), skipping merge")
        return

    with open(ta_path, "r", encoding="utf-8") as f:
        ta_data = json.load(f)

    merged = 0
    for key, ta_record in ta_data.items():
        if key not in establishments:
            continue
        if ta_record.get("_skipped") or ta_record.get("_no_match") or ta_record.get("_error"):
            continue

        est = establishments[key]

        # Merge TripAdvisor fields
        if ta_record.get("ta") is not None:
            est["ta"] = ta_record["ta"]
            est["ta_present"] = True
            merged += 1
        if ta_record.get("trc") is not None:
            est["trc"] = ta_record["trc"]
        if ta_record.get("ta_url"):
            est["ta_url"] = ta_record["ta_url"]
        if ta_record.get("ta_cuisines"):
            est["ta_cuisines"] = ta_record["ta_cuisines"]
        if ta_record.get("ta_price"):
            est["ta_price"] = ta_record["ta_price"]
        if ta_record.get("ta_reviews"):
            est["ta_reviews"] = ta_record["ta_reviews"]
        if ta_record.get("ta_ranking"):
            est["ta_ranking"] = ta_record["ta_ranking"]

    # Save merged data
    with open(est_path, "w", encoding="utf-8") as f:
        json.dump(establishments, f, indent=2, ensure_ascii=False)

    with_ta = sum(1 for v in establishments.values() if v.get("ta") is not None)
    print(f"Merged TripAdvisor data for {merged} establishments")
    print(f"  With TA rating: {with_ta}/{len(establishments)}")


if __name__ == "__main__":
    main()
