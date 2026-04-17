#!/usr/bin/env python3
"""
enrich_google_stratford.py — Enrich Stratford establishments with Google Places data.

Reads stratford_establishments.json, calls Google Places API (New) Text Search
for each establishment, and saves enrichment data to stratford_google_enrichment.json.

Requires:
    GOOGLE_PLACES_API_KEY environment variable
"""

import json
import math
import os
import sys
import time

import requests

GOOGLE_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")
PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Rate limit: ~10 req/sec max, use 0.15s to be safe
RATE_LIMIT_DELAY = 0.15


def search_place(name, address, postcode):
    """
    Search for a place using Google Places API (New) Text Search.
    Returns dict with Google data fields or None if not found.
    """
    query = f"{name}, {postcode}, UK"
    if address:
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
            "places.photos,"
            "places.reviews,"
            # Commercial Readiness customer-path fields (V4 spec §5)
            "places.websiteUri,"
            "places.nationalPhoneNumber,"
            "places.internationalPhoneNumber,"
            "places.reservable,"
            # Closure handling (V4 spec §7.4)
            "places.businessStatus,"
            "places.regularOpeningHours.weekdayDescriptions,"
            "places.currentOpeningHours.weekdayDescriptions"
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

    place = places[0]
    result = {"gpid": place.get("id", "")}

    if "rating" in place:
        result["gr"] = place["rating"]
    if "userRatingCount" in place:
        result["grc"] = place["userRatingCount"]
    if "priceLevel" in place:
        # API returns strings like "PRICE_LEVEL_MODERATE" etc.
        price_map = {
            "PRICE_LEVEL_FREE": 0,
            "PRICE_LEVEL_INEXPENSIVE": 1,
            "PRICE_LEVEL_MODERATE": 2,
            "PRICE_LEVEL_EXPENSIVE": 3,
            "PRICE_LEVEL_VERY_EXPENSIVE": 4,
        }
        result["gpl"] = price_map.get(place["priceLevel"], None)
    if "types" in place:
        result["gty"] = place["types"]
    if "photos" in place:
        result["gpc"] = len(place["photos"])  # photo count

    # --- Commercial Readiness signals (V4 §5) ---
    # Store the raw Google fields AND normalised short aliases so
    # downstream merge/scoring can pick either up.
    website_uri = place.get("websiteUri")
    if website_uri:
        result["websiteUri"] = website_uri
        result["web_url"] = website_uri

    nat_phone = place.get("nationalPhoneNumber")
    intl_phone = place.get("internationalPhoneNumber")
    if nat_phone:
        result["nationalPhoneNumber"] = nat_phone
    if intl_phone:
        result["internationalPhoneNumber"] = intl_phone
    if nat_phone or intl_phone:
        result["phone"] = nat_phone or intl_phone

    if "reservable" in place:
        # Places API returns a real bool here
        result["reservable"] = bool(place["reservable"])

    # --- Closure flag (V4 §7.4) ---
    if "businessStatus" in place:
        # API enum: OPERATIONAL | CLOSED_TEMPORARILY | CLOSED_PERMANENTLY
        result["business_status"] = place["businessStatus"]

    hours = place.get("regularOpeningHours") or place.get("currentOpeningHours")
    if hours and "weekdayDescriptions" in hours:
        result["goh"] = hours["weekdayDescriptions"]

    # Reviews — extract up to 5 most relevant
    reviews = place.get("reviews", [])
    if reviews:
        extracted = []
        for rev in reviews[:5]:
            entry = {}
            orig = rev.get("originalText") or rev.get("text")
            if orig:
                entry["text"] = orig.get("text", "") if isinstance(orig, dict) else str(orig)
            entry["rating"] = rev.get("rating")
            entry["time"] = rev.get("relativePublishTimeDescription", "")
            if entry.get("text"):
                extracted.append(entry)
        if extracted:
            result["g_reviews"] = extracted

    return result


def main():
    if not GOOGLE_API_KEY:
        print("ERROR: GOOGLE_PLACES_API_KEY not set")
        sys.exit(1)

    # Load establishments
    input_path = "stratford_establishments.json"
    if not os.path.exists(input_path):
        print(f"ERROR: {input_path} not found")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Loaded {len(data)} establishments")

    # Load existing enrichment data (to resume partial runs)
    output_path = "stratford_google_enrichment.json"
    enrichment = {}
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            enrichment = json.load(f)
        print(f"Loaded {len(enrichment)} existing enrichment records (resuming)")

    enriched = 0
    skipped = 0
    no_match = 0
    failed = 0
    total = len(data)

    for i, (key, record) in enumerate(data.items(), 1):
        name = record.get("n", "")
        address = record.get("a", "")
        postcode = record.get("pc", "")

        # Skip if already enriched
        if key in enrichment:
            skipped += 1
            continue

        if not name:
            skipped += 1
            continue

        try:
            result = search_place(name, address, postcode)
            time.sleep(RATE_LIMIT_DELAY)

            if result is None:
                no_match += 1
                print(f"  [{i}/{total}] no match: {name}")
                # Store empty so we don't re-query
                enrichment[key] = {"_no_match": True}
            else:
                enrichment[key] = result
                enriched += 1
                gr = result.get('gr', '-')
                grc = result.get('grc', 0)
                gpc = result.get('gpc', 0)
                print(f"  [{i}/{total}] {name} -> gr={gr} grc={grc} photos={gpc}")

        except requests.exceptions.HTTPError as e:
            failed += 1
            status = e.response.status_code if e.response is not None else '?'
            print(f"  [{i}/{total}] API error ({status}) for {name}: {e}")
            if e.response is not None and e.response.status_code == 429:
                print("  Rate limited — sleeping 10s")
                time.sleep(10)
            elif e.response is not None and e.response.status_code == 403:
                print("  API key invalid or quota exceeded — stopping")
                break
        except Exception as e:
            failed += 1
            print(f"  [{i}/{total}] error for {name}: {e}")

        # Save progress every 25 records
        if i % 25 == 0:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(enrichment, f, indent=2, ensure_ascii=False)
            print(f"  ... saved progress ({len(enrichment)} records)")

    # Final save
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(enrichment, f, indent=2, ensure_ascii=False)

    matched = sum(1 for v in enrichment.values() if not v.get("_no_match"))
    print(f"\nDone. Total: {total}, Enriched: {enriched}, "
          f"Skipped: {skipped}, No match: {no_match}, Failed: {failed}")
    print(f"Enrichment file: {len(enrichment)} records ({matched} with Google data)")
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
