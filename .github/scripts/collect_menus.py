#!/usr/bin/env python3
"""
collect_menus.py — Collect menu and offering data for Stratford establishments.

For each restaurant, attempts to find menu information from:
1. Google Places website URL (if available)
2. TripAdvisor cuisine tags (if collected)
3. Google place types for cuisine inference

Extracts: has_menu_online, dietary_options_count, cuisine_tags_count,
menu_url, price_range_text.

Usage:
    python .github/scripts/collect_menus.py

Reads:  stratford_establishments.json
Writes: stratford_menus.json
"""

import json
import os
import random
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
INPUT_PATH = os.path.join(REPO_ROOT, "stratford_establishments.json")
OUTPUT_PATH = os.path.join(REPO_ROOT, "stratford_menus.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

# Cuisine keywords to count from Google types, TA cuisines, and page text
CUISINE_KEYWORDS = {
    "british", "indian", "italian", "chinese", "thai", "japanese", "french",
    "mexican", "mediterranean", "turkish", "greek", "american", "asian",
    "vietnamese", "korean", "spanish", "seafood", "steakhouse", "vegan",
    "vegetarian", "pizza", "sushi", "tapas", "caribbean", "african",
    "middle eastern", "persian", "lebanese", "nepalese", "bangladeshi",
}

DIETARY_KEYWORDS = {
    "vegan", "vegetarian", "gluten-free", "gluten free", "halal", "kosher",
    "dairy-free", "dairy free", "nut-free", "nut free", "organic",
    "plant-based", "plant based", "coeliac", "celiac", "allergen",
}

MENU_KEYWORDS = {"menu", "food-menu", "food_menu", "our-food", "dishes",
                 "starters", "mains", "desserts", "a-la-carte"}


def extract_cuisine_count(record):
    """Count distinct cuisine tags from Google types and TA data."""
    cuisines = set()

    # From Google place types
    gty = record.get("gty", [])
    if isinstance(gty, list):
        for t in gty:
            t_lower = t.lower().replace("_", " ").replace(" restaurant", "")
            if t_lower in CUISINE_KEYWORDS:
                cuisines.add(t_lower)

    # From TripAdvisor cuisine tags
    ta_cuisines = record.get("ta_cuisines", [])
    if isinstance(ta_cuisines, list):
        for c in ta_cuisines:
            c_lower = c.lower().strip()
            if c_lower in CUISINE_KEYWORDS:
                cuisines.add(c_lower)

    return len(cuisines), list(cuisines)


def check_website_for_menu(url):
    """
    Check a restaurant website for menu presence and dietary options.
    Returns dict with has_menu, dietary_count, menu_url.
    """
    if not url:
        return None

    try:
        resp = requests.get(url, headers=HEADERS, timeout=10,
                            allow_redirects=True)
        resp.raise_for_status()
    except requests.RequestException:
        return None

    text = resp.text.lower()
    soup = BeautifulSoup(text, "html.parser")

    result = {"has_menu": False, "dietary_count": 0, "menu_url": None}

    # Check for menu links
    for link in soup.find_all("a", href=True):
        href = link.get("href", "").lower()
        link_text = link.get_text(strip=True).lower()
        if any(kw in href or kw in link_text for kw in MENU_KEYWORDS):
            result["has_menu"] = True
            full_url = href
            if href.startswith("/"):
                from urllib.parse import urljoin
                full_url = urljoin(url, href)
            result["menu_url"] = full_url
            break

    # Check page text for menu indicators
    if not result["has_menu"]:
        page_text = soup.get_text(separator=" ").lower()
        if any(kw in page_text for kw in ["our menu", "food menu", "view menu",
                                           "see our menu", "starters", "main course"]):
            result["has_menu"] = True

    # Count dietary options mentioned
    page_text = soup.get_text(separator=" ").lower()
    dietary_found = sum(1 for kw in DIETARY_KEYWORDS if kw in page_text)
    result["dietary_count"] = min(dietary_found, 10)

    return result


def infer_price_range(record):
    """Infer price range from Google price level or TA data."""
    gpl = record.get("gpl")
    ta_price = record.get("ta_price", "")

    if gpl is not None:
        try:
            level = int(gpl)
            return {0: "£", 1: "£", 2: "££", 3: "£££", 4: "££££"}.get(level, "££")
        except (ValueError, TypeError):
            pass

    if ta_price:
        pound_count = ta_price.count("£") or ta_price.count("$")
        if pound_count >= 3:
            return "£££"
        elif pound_count >= 2:
            return "££"
        elif pound_count >= 1:
            return "£"

    return None


def main():
    if not os.path.exists(INPUT_PATH):
        print(f"ERROR: {INPUT_PATH} not found")
        sys.exit(1)

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        establishments = json.load(f)
    print(f"Loaded {len(establishments)} establishments")

    # Resume support
    menu_data = {}
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            menu_data = json.load(f)
        print(f"Loaded {len(menu_data)} existing menu records (resuming)")

    processed = 0
    total = len(establishments)

    for i, (key, record) in enumerate(establishments.items(), 1):
        if key in menu_data:
            continue

        name = record.get("n", "")
        entry = {}

        # Cuisine tags from Google types + TA data
        cuisine_count, cuisine_list = extract_cuisine_count(record)
        if cuisine_count > 0:
            entry["cuisine_tags_count"] = cuisine_count
            entry["cuisine_tags"] = cuisine_list

        # Price range inference
        price = infer_price_range(record)
        if price:
            entry["price_range"] = price

        # Check website for menu (if we have a URL)
        # Google Places doesn't store website in our current fields,
        # but TA might have provided one. Also check ta_url.
        website = record.get("website") or record.get("web_url")
        if website:
            web_result = check_website_for_menu(website)
            if web_result:
                entry["has_menu_online"] = web_result["has_menu"]
                if web_result["menu_url"]:
                    entry["menu_url"] = web_result["menu_url"]
                if web_result["dietary_count"] > 0:
                    entry["dietary_options_count"] = web_result["dietary_count"]
                time.sleep(random.uniform(1.0, 2.0))

        # If no website, infer menu from TA/Google presence
        if "has_menu_online" not in entry:
            # Restaurants with TA pages or Google listings often have menus
            has_ta = record.get("ta") is not None
            has_google = record.get("gr") is not None
            gty = record.get("gty", [])
            is_restaurant = isinstance(gty, list) and any(
                t in gty for t in ["restaurant", "cafe", "pub", "bar",
                                   "meal_takeaway", "food"]
            )
            if is_restaurant and (has_ta or has_google):
                # Assume menu exists if it's a proper food establishment
                entry["has_menu_online"] = True

        menu_data[key] = entry if entry else {"_no_data": True}
        processed += 1

        if i % 50 == 0:
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(menu_data, f, indent=2, ensure_ascii=False)
            print(f"  [{i}/{total}] saved progress")

    # Final save
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(menu_data, f, indent=2, ensure_ascii=False)

    with_menu = sum(1 for v in menu_data.values() if v.get("has_menu_online"))
    with_cuisine = sum(1 for v in menu_data.values() if v.get("cuisine_tags_count", 0) > 0)
    print(f"\nDone. Processed: {processed}/{total}")
    print(f"  With menu: {with_menu}, With cuisines: {with_cuisine}")
    print(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
