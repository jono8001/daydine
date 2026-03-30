#!/usr/bin/env python3
"""merge_editorial.py — Merge editorial/awards data into establishments JSON."""

import json, os, sys

def main():
    est_path = "stratford_establishments.json"
    ed_path = "stratford_editorial.json"

    if not os.path.exists(est_path):
        print(f"ERROR: {est_path} not found"); sys.exit(1)
    with open(est_path, "r", encoding="utf-8") as f:
        establishments = json.load(f)
    if not os.path.exists(ed_path):
        print(f"No editorial data ({ed_path}), skipping"); return
    with open(ed_path, "r", encoding="utf-8") as f:
        editorial = json.load(f)

    merged = 0
    for key, ed in editorial.items():
        if key not in establishments or ed.get("_no_data") or ed.get("_skipped"):
            continue
        est = establishments[key]
        for field in ["has_michelin_mention", "michelin_type", "has_aa_rating",
                       "aa_rosettes", "local_awards_count"]:
            if field in ed:
                est[field] = ed[field]
        merged += 1

    with open(est_path, "w", encoding="utf-8") as f:
        json.dump(establishments, f, indent=2, ensure_ascii=False)
    print(f"Merged editorial data for {merged}/{len(establishments)} establishments")

if __name__ == "__main__":
    main()
