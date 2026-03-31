#!/usr/bin/env python3
"""
sanity_check_coverage.py — Validate data coverage for Stratford-upon-Avon.

Cross-references our dataset against external sources to find:
1. Restaurants found externally but missing from our data
2. Non-restaurants that shouldn't be in our rankings
3. Data quality metrics

Uses Google Places API to search for restaurants near Stratford.

Requires:
    GOOGLE_PLACES_API_KEY environment variable

Reads:  stratford_establishments.json
Writes: stratford_sanity_report.json
"""

import difflib
import json
import os
import sys
import time

import requests

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
INPUT_PATH = os.path.join(REPO_ROOT, "stratford_establishments.json")
OUTPUT_PATH = os.path.join(REPO_ROOT, "stratford_sanity_report.json")

GOOGLE_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")

# Stratford-upon-Avon centre coordinates
STRATFORD_LAT = 52.1917
STRATFORD_LNG = -1.7083

PLACES_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"
PLACES_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"


def normalise(name):
    """Normalise name for matching."""
    import re
    name = name.lower().strip()
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def fuzzy_match_score(name1, name2):
    return difflib.SequenceMatcher(None, normalise(name1), normalise(name2)).ratio()


def search_google_nearby(lat, lng, radius_m=8000, place_type="restaurant"):
    """Search Google Places Nearby for restaurants."""
    if not GOOGLE_API_KEY:
        return []

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.formattedAddress,"
            "places.rating,places.userRatingCount,places.types"
        ),
    }
    body = {
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": radius_m,
            }
        },
        "includedTypes": [place_type],
        "maxResultCount": 20,
        "languageCode": "en",
        "regionCode": "GB",
    }

    try:
        resp = requests.post(PLACES_NEARBY_URL, headers=headers, json=body, timeout=15)
        resp.raise_for_status()
        return resp.json().get("places", [])
    except requests.RequestException as e:
        print(f"  Google Nearby search error: {e}")
        return []


def search_google_text(query):
    """Search Google Places by text query."""
    if not GOOGLE_API_KEY:
        return []

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.formattedAddress,"
            "places.rating,places.userRatingCount,places.types"
        ),
    }
    body = {
        "textQuery": query,
        "languageCode": "en",
        "regionCode": "GB",
    }

    try:
        resp = requests.post(PLACES_TEXT_URL, headers=headers, json=body, timeout=15)
        resp.raise_for_status()
        return resp.json().get("places", [])
    except requests.RequestException as e:
        print(f"  Google Text search error: {e}")
        return []


def check_non_food(establishments):
    """
    Identify establishments that look like non-food businesses.
    Returns list of suspects with classification confidence score.
    """
    non_food_indicators = {
        "sports_club", "church", "place_of_worship", "insurance_agency",
        "real_estate_agency", "miniature_golf_course", "gym", "fitness_center",
    }
    non_food_names = {
        "slimming world", "football club", "golf club", "aston martin",
        "nfu mutual", "baptist church", "horse sanctuary",
    }
    food_types = {"restaurant", "cafe", "food", "bar", "pub",
                  "meal_takeaway", "bakery", "coffee_shop"}

    suspects = []
    for key, record in establishments.items():
        name = (record.get("n") or "").lower()
        gty = set(record.get("gty", []) or [])
        fsa_r = record.get("r")

        is_suspect = False
        reason = ""
        confidence = 0.0

        # Check Google types
        if gty & non_food_indicators and not gty & food_types:
            is_suspect = True
            reason = f"google_types: {gty & non_food_indicators}"
            confidence = 0.8

        # Check names
        for nf in non_food_names:
            if nf in name:
                is_suspect = True
                reason = f"name_match: {nf}"
                confidence = 0.9
                break

        # Reduce confidence if FSA rating suggests food service
        if is_suspect and fsa_r is not None:
            try:
                if int(fsa_r) >= 3:
                    # Has good FSA rating — might actually serve food
                    confidence *= 0.6
                    reason += " (but FSA 3+ — may serve food)"
            except (ValueError, TypeError):
                pass

        # Food keywords in name increase doubt about exclusion
        food_kw = {"cafe", "caff", "restaurant", "kitchen", "catering",
                   "lunch", "coffee", "tea", "food", "bistro", "grill"}
        if is_suspect and any(fk in name for fk in food_kw):
            confidence *= 0.5
            reason += " (food keyword in name)"

        if is_suspect:
            suspects.append({
                "fhrsid": key,
                "name": record.get("n", ""),
                "postcode": record.get("pc", ""),
                "reason": reason,
                "fsa_rating": fsa_r,
                "google_types": list(gty)[:5],
                "classification_confidence": round(confidence, 2),
                "needs_manual_review": confidence < 0.6,
            })

    return suspects


def check_fsa_reconciliation():
    """Compare our establishment count against FSA API total for LA 320."""
    import requests as req
    FSA_URL = "https://api.ratings.food.gov.uk/Establishments"
    FSA_HEADERS = {"x-api-version": "2", "accept": "application/json"}
    try:
        params = {"localAuthorityId": 320, "pageSize": 1}
        resp = req.get(FSA_URL, params=params, headers=FSA_HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.json().get("meta", {}).get("totalCount", 0)
    except Exception:
        return None


def main():
    if not os.path.exists(INPUT_PATH):
        print(f"ERROR: {INPUT_PATH} not found")
        sys.exit(1)

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        establishments = json.load(f)

    our_names = {normalise(v.get("n", "")) for v in establishments.values()}
    print(f"Our dataset: {len(establishments)} establishments")

    report = {
        "our_count": len(establishments),
        "missing_from_our_data": [],
        "non_food_suspects": [],
        "external_searches": [],
    }

    # Check for non-food businesses (with confidence scores)
    print("\nChecking for non-food businesses...")
    suspects = check_non_food(establishments)
    report["non_food_suspects"] = suspects
    print(f"  Found {len(suspects)} non-food suspects")
    needs_review = [s for s in suspects if s.get("needs_manual_review")]
    for s in suspects:
        flag = " ** NEEDS REVIEW" if s.get("needs_manual_review") else ""
        print(f"    {s['name']}: conf={s['classification_confidence']}{flag}")
    if needs_review:
        print(f"  {len(needs_review)} decisions need manual review (confidence < 0.6)")

    # FSA reconciliation
    print("\nChecking FSA reconciliation...")
    fsa_total = check_fsa_reconciliation()
    if fsa_total:
        gap_pct = abs(fsa_total - len(establishments)) / fsa_total * 100
        report["fsa_reconciliation"] = {
            "fsa_total": fsa_total,
            "our_total": len(establishments),
            "gap_pct": round(gap_pct, 1),
            "warning": gap_pct > 5,
        }
        print(f"  FSA total: {fsa_total}, ours: {len(establishments)}, gap: {gap_pct:.1f}%")
        if gap_pct > 5:
            print(f"  WARNING: DATA_GAP — {gap_pct:.1f}% difference")
    else:
        print("  Could not reach FSA API for reconciliation")

    # Search Google Places for restaurants we might be missing
    if GOOGLE_API_KEY:
        print("\nSearching Google Places for restaurants near Stratford...")

        queries = [
            "best restaurants Stratford-upon-Avon",
            "top rated restaurants Stratford-upon-Avon",
            "fine dining Stratford-upon-Avon",
            "wine bar Stratford-upon-Avon",
            "pub food Stratford-upon-Avon",
            "cafe Stratford-upon-Avon",
            "Indian restaurant Stratford-upon-Avon",
            "Italian restaurant Stratford-upon-Avon",
            "Chinese restaurant Stratford-upon-Avon",
            "takeaway Stratford-upon-Avon",
            "brunch Stratford-upon-Avon",
        ]

        # Also search for specific known restaurants that should be in data
        known_names = [
            "The Vintner Stratford-upon-Avon",
            "The Dirty Duck Stratford-upon-Avon",
            "Baraset Barn Stratford-upon-Avon",
            "The Rooftop Restaurant RSC Stratford",
            "Boston Tea Party Stratford-upon-Avon",
            "Osteria Da Gino Stratford-upon-Avon",
            "Grace & Savour Stratford-upon-Avon",
            "The Golden Bee Wetherspoon Stratford",
            "Caffeine & Machine Stratford",
        ]
        queries.extend(known_names)

        all_external = {}
        for query in queries:
            print(f"  Searching: {query}")
            results = search_google_text(query)
            for place in results:
                pid = place.get("id", "")
                if pid not in all_external:
                    all_external[pid] = {
                        "name": place.get("displayName", {}).get("text", ""),
                        "address": place.get("formattedAddress", ""),
                        "rating": place.get("rating"),
                        "reviews": place.get("userRatingCount"),
                        "types": place.get("types", [])[:5],
                    }
            time.sleep(1)

        # Also do a nearby search
        print("  Searching: Nearby restaurants (8km radius)")
        nearby = search_google_nearby(STRATFORD_LAT, STRATFORD_LNG)
        for place in nearby:
            pid = place.get("id", "")
            if pid not in all_external:
                all_external[pid] = {
                    "name": place.get("displayName", {}).get("text", ""),
                    "address": place.get("formattedAddress", ""),
                    "rating": place.get("rating"),
                    "reviews": place.get("userRatingCount"),
                    "types": place.get("types", [])[:5],
                }

        print(f"  Found {len(all_external)} unique external restaurants")

        # Cross-reference
        missing = []
        for pid, ext in all_external.items():
            ext_norm = normalise(ext["name"])
            best_score = max(
                (fuzzy_match_score(ext["name"], v.get("n", ""))
                 for v in establishments.values()),
                default=0
            )
            if best_score < 0.6:
                missing.append({
                    "name": ext["name"],
                    "address": ext["address"],
                    "rating": ext["rating"],
                    "reviews": ext["reviews"],
                    "best_match_score": round(best_score, 2),
                })

        report["missing_from_our_data"] = sorted(
            missing, key=lambda x: x.get("reviews") or 0, reverse=True
        )
        print(f"  Missing from our data: {len(missing)} restaurants")
        for m in missing[:10]:
            print(f"    {m['name']} ({m.get('reviews', '?')} reviews, "
                  f"rating {m.get('rating', '?')})")

    else:
        print("\nNo GOOGLE_PLACES_API_KEY — skipping external search")

    # Save report
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nSaved sanity report to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
