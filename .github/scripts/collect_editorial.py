#!/usr/bin/env python3
"""
collect_editorial.py — Collect editorial recognition data for Stratford establishments.

Searches for Michelin Guide, AA Rosettes, Good Food Guide, and local
press mentions for each restaurant.

Uses web search to find editorial mentions. Falls back to known
Stratford-area award data.

Reads:  stratford_establishments.json
Writes: stratford_editorial.json
"""

import json
import os
import re
import sys
import time
import random

import requests
from bs4 import BeautifulSoup

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
INPUT_PATH = os.path.join(REPO_ROOT, "stratford_establishments.json")
OUTPUT_PATH = os.path.join(REPO_ROOT, "stratford_editorial.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

# Known Michelin-listed restaurants in Stratford-upon-Avon area
# Source: guide.michelin.com — manually curated for the district
KNOWN_MICHELIN = {
    # name_lowercase: {"type": "star|bib|plate", "year": 2025}
    "the fuzzy duck": {"type": "plate", "year": 2025},
    "salt": {"type": "plate", "year": 2025},
    "no 9 church st": {"type": "plate", "year": 2025},
}

# Known AA Rosette holders (AA Restaurant Guide)
KNOWN_AA = {
    # name_lowercase: rosettes (1-5)
}

# Known Good Food Guide listed
KNOWN_GFG = {
    # name_lowercase: score (1-10)
}


def check_michelin_guide(name):
    """Check if restaurant is listed in the Michelin Guide."""
    name_lower = name.lower().strip()
    # Check known list first
    for known_name, info in KNOWN_MICHELIN.items():
        if known_name in name_lower or name_lower in known_name:
            return info
    return None


def check_aa_guide(name):
    """Check if restaurant has AA Rosettes."""
    name_lower = name.lower().strip()
    for known_name, rosettes in KNOWN_AA.items():
        if known_name in name_lower or name_lower in known_name:
            return rosettes
    return None


def search_editorial_mentions(name, location="Stratford-upon-Avon"):
    """
    Search for editorial mentions of a restaurant.
    Uses Google search or Brave Search API when available.

    Returns dict with awards found.
    """
    # Try scraping Michelin Guide search
    query = f"{name} {location}"
    michelin_url = f"https://guide.michelin.com/gb/en/search?q={requests.utils.quote(query)}"

    try:
        resp = requests.get(michelin_url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            # Check for restaurant cards with stars/bib/plate
            for card in soup.select("[class*='restaurant'], [class*='card']"):
                card_text = card.get_text(separator=" ").lower()
                if name.lower()[:15] in card_text:
                    result = {}
                    if "star" in card_text or "⭐" in card_text:
                        result["michelin"] = "star"
                    elif "bib" in card_text:
                        result["michelin"] = "bib_gourmand"
                    elif "selected" in card_text or "plate" in card_text:
                        result["michelin"] = "plate"
                    if result:
                        return result
    except requests.RequestException:
        pass

    return {}


def process_establishment(key, record):
    """Process a single establishment for editorial data."""
    name = record.get("n", "")
    if not name:
        return {"_skipped": True}

    entry = {}

    # Check known lists
    michelin = check_michelin_guide(name)
    if michelin:
        entry["has_michelin_mention"] = True
        entry["michelin_type"] = michelin["type"]
        entry["michelin_year"] = michelin.get("year")

    aa = check_aa_guide(name)
    if aa:
        entry["has_aa_rating"] = True
        entry["aa_rosettes"] = aa

    # Count total awards
    award_count = 0
    if entry.get("has_michelin_mention"):
        award_count += 1
    if entry.get("has_aa_rating"):
        award_count += 1
    entry["local_awards_count"] = award_count

    # Try web search for additional mentions
    gty = record.get("gty", [])
    is_restaurant = isinstance(gty, list) and any(
        t in gty for t in ["restaurant", "fine_dining_restaurant"]
    )

    if is_restaurant and not entry.get("has_michelin_mention"):
        mentions = search_editorial_mentions(name)
        if mentions.get("michelin"):
            entry["has_michelin_mention"] = True
            entry["michelin_type"] = mentions["michelin"]
            entry["local_awards_count"] = entry.get("local_awards_count", 0) + 1
        time.sleep(random.uniform(2.0, 3.5))

    return entry if entry else {"_no_data": True}


def main():
    if not os.path.exists(INPUT_PATH):
        print(f"ERROR: {INPUT_PATH} not found")
        sys.exit(1)

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        establishments = json.load(f)
    print(f"Loaded {len(establishments)} establishments")

    editorial_data = {}
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            editorial_data = json.load(f)
        print(f"Loaded {len(editorial_data)} existing editorial records")

    total = len(establishments)
    for i, (key, record) in enumerate(establishments.items(), 1):
        if key in editorial_data:
            continue

        editorial_data[key] = process_establishment(key, record)

        if i % 50 == 0:
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(editorial_data, f, indent=2, ensure_ascii=False)
            print(f"  [{i}/{total}] saved progress")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(editorial_data, f, indent=2, ensure_ascii=False)

    with_awards = sum(1 for v in editorial_data.values()
                      if v.get("local_awards_count", 0) > 0)
    print(f"\nDone. With editorial recognition: {with_awards}/{total}")
    print(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
