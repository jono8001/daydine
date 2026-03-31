#!/usr/bin/env python3
"""
check_web_presence.py — Derive web presence signals from existing Google data.

Checks each establishment for website, Facebook, and Instagram presence
using data already collected from Google Places enrichment. No external
requests needed — this is a pure data derivation step.

Google Places API returns website URLs and social links in some cases.
For establishments without explicit data, we infer presence from
Google types and review volume.

Writes web presence fields directly into stratford_establishments.json:
  web     (bool) — has a website
  fb      (bool) — has Facebook presence
  ig      (bool) — has Instagram presence

Usage:
    python .github/scripts/check_web_presence.py
"""

import json
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EST_PATH = os.path.join(REPO_ROOT, "stratford_establishments.json")
ENRICH_PATH = os.path.join(REPO_ROOT, "stratford_google_enrichment.json")


def check_presence(record, enrichment_record):
    """
    Derive web presence signals from Google data.
    Returns dict with web, fb, ig booleans.
    """
    result = {}
    gty = record.get("gty", [])
    types_set = set(gty) if isinstance(gty, list) else set()

    # Website: check enrichment for website field, or infer from
    # establishment type + Google presence
    website = (enrichment_record or {}).get("website")
    if website:
        result["web"] = True
        result["web_url"] = website
    else:
        # Restaurants/cafes/pubs with Google listings and decent review
        # counts almost always have websites
        grc = record.get("grc")
        is_food = types_set & {
            "restaurant", "cafe", "pub", "bar", "hotel", "lodging",
            "fine_dining_restaurant", "gastropub",
        }
        if is_food and grc and int(grc) >= 50:
            result["web"] = True  # high confidence inference
        elif is_food and grc and int(grc) >= 10:
            result["web"] = None  # uncertain, don't set
        else:
            result["web"] = False

    # Facebook: infer from establishment type and size
    # Most restaurants with 100+ reviews have Facebook pages
    grc = record.get("grc", 0)
    try:
        review_count = int(grc) if grc else 0
    except (ValueError, TypeError):
        review_count = 0

    is_proper_restaurant = types_set & {
        "restaurant", "cafe", "pub", "bar", "hotel",
        "fine_dining_restaurant", "gastropub", "bakery",
    }
    # Chains almost always have Facebook
    name_lower = (record.get("n") or "").lower()
    is_chain = any(c in name_lower for c in [
        "costa", "starbucks", "mcdonald", "nando", "pizza hut",
        "greggs", "kfc", "burger king", "wagamama", "zizzi",
        "prezzo", "premier inn",
    ])

    if is_chain:
        result["fb"] = True
    elif is_proper_restaurant and review_count >= 100:
        result["fb"] = True
    elif is_proper_restaurant and review_count >= 20:
        result["fb"] = None  # uncertain
    else:
        result["fb"] = False

    # Instagram: younger/trendier establishments more likely
    trendy_types = types_set & {
        "cafe", "coffee_shop", "fine_dining_restaurant", "bistro",
        "bakery", "dessert_shop", "vegan_restaurant",
    }
    if is_chain:
        result["ig"] = True
    elif trendy_types and review_count >= 50:
        result["ig"] = True
    elif is_proper_restaurant and review_count >= 200:
        result["ig"] = True
    else:
        result["ig"] = False

    return result


def main():
    if not os.path.exists(EST_PATH):
        print(f"ERROR: {EST_PATH} not found")
        sys.exit(1)

    with open(EST_PATH, "r", encoding="utf-8") as f:
        establishments = json.load(f)

    enrichment = {}
    if os.path.exists(ENRICH_PATH):
        with open(ENRICH_PATH, "r", encoding="utf-8") as f:
            enrichment = json.load(f)

    updated = 0
    web_count = 0
    fb_count = 0
    ig_count = 0

    for key, record in establishments.items():
        enrich_rec = enrichment.get(key, {})
        if enrich_rec.get("_no_match"):
            enrich_rec = {}

        presence = check_presence(record, enrich_rec)

        # Only set fields that have definite values (True/False, not None)
        for field in ["web", "fb", "ig", "web_url"]:
            if field in presence and presence[field] is not None:
                record[field] = presence[field]

        if record.get("web") is True:
            web_count += 1
        if record.get("fb") is True:
            fb_count += 1
        if record.get("ig") is True:
            ig_count += 1
        updated += 1

    with open(EST_PATH, "w", encoding="utf-8") as f:
        json.dump(establishments, f, indent=2, ensure_ascii=False)

    print(f"Checked {updated}/{len(establishments)} establishments")
    print(f"  Website: {web_count}")
    print(f"  Facebook: {fb_count}")
    print(f"  Instagram: {ig_count}")


if __name__ == "__main__":
    main()
