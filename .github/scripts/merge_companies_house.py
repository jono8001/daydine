#!/usr/bin/env python3
"""merge_companies_house.py — Merge Companies House data into establishments JSON."""

import json, os, sys


def main():
    est_path = "stratford_establishments.json"
    ch_path = "stratford_companies_house.json"

    if not os.path.exists(est_path):
        print(f"ERROR: {est_path} not found"); sys.exit(1)
    with open(est_path, "r", encoding="utf-8") as f:
        establishments = json.load(f)
    if not os.path.exists(ch_path):
        print(f"No Companies House data ({ch_path}), skipping"); return
    with open(ch_path, "r", encoding="utf-8") as f:
        ch_data = json.load(f)

    CH_FIELDS = [
        "ch_company_number", "ch_company_name", "ch_incorporated",
        "ch_status", "ch_accounts_due", "ch_accounts_overdue",
        "ch_last_accounts_filed", "ch_directors", "ch_insolvency",
        "director_changes_12m",
    ]

    merged = 0
    for key, ch in ch_data.items():
        if key not in establishments:
            continue
        # Skip entries that had no match
        if not ch.get("ch_company_number"):
            continue
        est = establishments[key]
        for field in CH_FIELDS:
            if field in ch:
                est[field] = ch[field]
        merged += 1

    with open(est_path, "w", encoding="utf-8") as f:
        json.dump(establishments, f, indent=2, ensure_ascii=False)
    print(f"Merged Companies House data for {merged}/{len(establishments)} establishments")


if __name__ == "__main__":
    main()
