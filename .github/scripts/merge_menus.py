#!/usr/bin/env python3
"""merge_menus.py — Merge menu data into establishments JSON."""

import json, os, sys

def main():
    est_path = "stratford_establishments.json"
    menu_path = "stratford_menus.json"

    if not os.path.exists(est_path):
        print(f"ERROR: {est_path} not found"); sys.exit(1)
    with open(est_path, "r", encoding="utf-8") as f:
        establishments = json.load(f)
    if not os.path.exists(menu_path):
        print(f"No menu data ({menu_path}), skipping"); return
    with open(menu_path, "r", encoding="utf-8") as f:
        menu_data = json.load(f)

    merged = 0
    for key, md in menu_data.items():
        if key not in establishments or md.get("_no_data"):
            continue
        est = establishments[key]
        for field in ["has_menu_online", "dietary_options_count", "cuisine_tags_count",
                       "cuisine_tags", "menu_url", "price_range"]:
            if field in md:
                est[field] = md[field]
        merged += 1

    with open(est_path, "w", encoding="utf-8") as f:
        json.dump(establishments, f, indent=2, ensure_ascii=False)
    print(f"Merged menu data for {merged}/{len(establishments)} establishments")

if __name__ == "__main__":
    main()
