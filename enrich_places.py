#!/usr/bin/env python3
"""
enrich_places.py — Enrich DayDine FSA establishments with Google Places data.

Reads establishments from Firebase RTDB for a given local authority,
matches each to a Google Place via the Places API (New), and writes
enriched fields back to Firebase.

Usage:
    python enrich_places.py --la "Camden"
    python enrich_places.py --la "Camden" --limit 5 --dry-run

Requires:
    pip install requests python-dotenv

Environment:
    GOOGLE_PLACES_API_KEY  — Google Places API key (in .env or env var)

Uses Firebase RTDB REST API (public read rules, no credentials needed for reads).
For writes, uses the RTDB REST API with no auth (relies on write rules being
temporarily enabled or uses firebase-admin when available).
"""

import argparse
import json
import os
import sys
import time
from urllib.parse import quote

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
FIREBASE_DB_URL = os.getenv(
    "FIREBASE_DATABASE_URL",
    "https://recursive-research-eu-default-rtdb.europe-west1.firebasedatabase.app",
)

PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Rate limiting: max 10 req/sec → sleep 0.1s between requests
RATE_LIMIT_DELAY = 0.1

# ---------------------------------------------------------------------------
# Firebase RTDB REST helpers
# ---------------------------------------------------------------------------
def firebase_admin_available():
    """Try to use firebase-admin if available and credentials exist."""
    try:
        import importlib
        firebase_admin = importlib.import_module("firebase_admin")
        creds_mod = importlib.import_module("firebase_admin.credentials")
        db_mod = importlib.import_module("firebase_admin.db")

        if firebase_admin._apps:
            return True

        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not creds_path:
            win_path = r"C:\Users\Jon Swaby\OneDrive\Documents\evidtrace-agents\firebase_credentials.json"
            if os.path.exists(win_path):
                creds_path = win_path

        if creds_path and os.path.exists(creds_path):
            cred = creds_mod.Certificate(creds_path)
            firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})
            return True
    except BaseException:
        pass
    return False


USE_ADMIN_SDK = False


def fb_read(path, params=None):
    """Read from Firebase RTDB via REST API."""
    url = f"{FIREBASE_DB_URL}/{path}.json"
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fb_update(path, data):
    """Write/update fields in Firebase RTDB via REST API or Admin SDK."""
    if USE_ADMIN_SDK:
        import importlib
        db_mod = importlib.import_module("firebase_admin.db")
        db_mod.reference(path).update(data)
    else:
        url = f"{FIREBASE_DB_URL}/{path}.json"
        resp = requests.patch(url, json=data, timeout=15)
        resp.raise_for_status()


# ---------------------------------------------------------------------------
# Google Places API (New) — Text Search
# ---------------------------------------------------------------------------
def search_place(name, address, postcode):
    """Search for a place using the Places API (New) Text Search."""
    query = f"{name}, {address}, {postcode}, UK"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": (
            "places.id,"
            "places.rating,"
            "places.userRatingCount,"
            "places.priceLevel,"
            "places.types,"
            "places.currentOpeningHours.weekdayDescriptions,"
            "places.regularOpeningHours.weekdayDescriptions"
        ),
    }
    body = {
        "textQuery": query,
        "languageCode": "en",
        "regionCode": "GB",
    }

    resp = requests.post(PLACES_SEARCH_URL, headers=headers, json=body, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    places = data.get("places", [])
    if not places:
        return None

    # Take the top result
    place = places[0]

    result = {"gid": place.get("id", "")}

    if "rating" in place:
        result["gr"] = place["rating"]
    if "userRatingCount" in place:
        result["grc"] = place["userRatingCount"]
    if "priceLevel" in place:
        result["gpl"] = place["priceLevel"]
    if "types" in place:
        result["gt"] = place["types"]

    # Opening hours — prefer regular, fall back to current
    hours = place.get("regularOpeningHours") or place.get("currentOpeningHours")
    if hours and "weekdayDescriptions" in hours:
        result["goh"] = hours["weekdayDescriptions"]

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    global USE_ADMIN_SDK

    parser = argparse.ArgumentParser(
        description="Enrich DayDine establishments with Google Places data"
    )
    parser.add_argument("--la", required=True, help="Local authority to process (exact match)")
    parser.add_argument("--dry-run", action="store_true", help="Search but don't write to Firebase")
    parser.add_argument("--limit", type=int, default=0, help="Max establishments to process (0=all)")
    args = parser.parse_args()

    if not GOOGLE_API_KEY:
        print("ERROR: GOOGLE_PLACES_API_KEY not set. Add it to .env or environment.")
        sys.exit(1)

    # Try firebase-admin first, fall back to REST API
    USE_ADMIN_SDK = firebase_admin_available()
    if USE_ADMIN_SDK:
        print("Using firebase-admin SDK for writes")
    else:
        print("Using Firebase REST API (firebase-admin not available)")

    # Query establishments for the given LA via REST API
    print(f"Fetching establishments for LA: {args.la}")
    data = fb_read("daydine/establishments", {
        "orderBy": '"la"',
        "equalTo": f'"{args.la}"',
    })

    if not data:
        print(f"No establishments found for LA '{args.la}'")
        sys.exit(0)

    entries = list(data.items())
    total = len(entries)
    print(f"Found {total} establishments")

    if args.limit > 0:
        entries = entries[: args.limit]
        print(f"Processing first {len(entries)} (--limit {args.limit})")

    enriched = 0
    skipped = 0
    failed = 0
    no_match = 0

    for i, (key, record) in enumerate(entries, 1):
        name = record.get("n", "")
        address = record.get("a", "")
        postcode = record.get("pc", "")

        # Skip if already enriched
        if record.get("gid"):
            skipped += 1
            if i % 50 == 0 or i == len(entries):
                print(f"  [{i}/{len(entries)}] skipped (already enriched): {name}")
            continue

        if not name:
            skipped += 1
            continue

        try:
            result = search_place(name, address, postcode)
            time.sleep(RATE_LIMIT_DELAY)

            if result is None:
                no_match += 1
                print(f"  [{i}/{len(entries)}] no match: {name}")
                continue

            if args.dry_run:
                print(f"  [{i}/{len(entries)}] DRY RUN match: {name} → gid={result.get('gid')}, "
                      f"gr={result.get('gr')}, grc={result.get('grc')}")
            else:
                fb_update(f"daydine/establishments/{key}", result)
                print(f"  [{i}/{len(entries)}] enriched: {name} → gr={result.get('gr')}, "
                      f"grc={result.get('grc')}")

            enriched += 1

        except requests.exceptions.HTTPError as e:
            failed += 1
            print(f"  [{i}/{len(entries)}] API error for {name}: {e}")
            # Back off on 429
            if e.response is not None and e.response.status_code == 429:
                print("  Rate limited — sleeping 10s")
                time.sleep(10)
        except Exception as e:
            failed += 1
            print(f"  [{i}/{len(entries)}] error for {name}: {e}")

    print()
    print(f"Done. Total: {len(entries)}, Enriched: {enriched}, "
          f"Skipped: {skipped}, No match: {no_match}, Failed: {failed}")


if __name__ == "__main__":
    main()
