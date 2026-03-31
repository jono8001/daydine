#!/usr/bin/env python3
"""merge_enforcement.py — Merge enforcement data into establishments JSON."""

import json, os, sys

def main():
    est_path = "stratford_establishments.json"
    enf_path = "stratford_enforcement.json"

    if not os.path.exists(est_path):
        print(f"ERROR: {est_path} not found"); sys.exit(1)
    with open(est_path, "r", encoding="utf-8") as f:
        establishments = json.load(f)
    if not os.path.exists(enf_path):
        print(f"No enforcement data ({enf_path}), skipping"); return
    with open(enf_path, "r", encoding="utf-8") as f:
        enforcement = json.load(f)

    merged = 0
    for key, enf in enforcement.items():
        if key not in establishments or enf.get("_clean"):
            continue
        est = establishments[key]
        for field in ["has_enforcement", "enforcement_severity",
                       "enforcement_actions"]:
            if field in enf:
                est[field] = enf[field]
        merged += 1

    with open(est_path, "w", encoding="utf-8") as f:
        json.dump(establishments, f, indent=2, ensure_ascii=False)
    print(f"Merged enforcement data for {merged}/{len(establishments)} establishments")

if __name__ == "__main__":
    main()
