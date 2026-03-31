#!/usr/bin/env python3
"""
augment_fsa_stratford.py — Fetch additional Stratford establishments from FSA API.

The Firebase RTDB only has BusinessTypeId=1 (Restaurant/Cafe/Canteen).
This script fetches types 7 (Pub/bar/nightclub) and 14 (Takeaway/sandwich shop)
from the FSA API and merges them into stratford_establishments.json.

This catches missing venues like wine bars, pubs with food, and takeaways.
"""

import json
import os
import sys

import requests

FSA_URL = "https://api.ratings.food.gov.uk/Establishments"
FSA_HEADERS = {"x-api-version": "2", "accept": "application/json"}

# Stratford-on-Avon District Council
LA_ID = 197

# Business types to fetch (not already in Firebase)
EXTRA_TYPES = [
    (7, "Pub/bar/nightclub"),
    (14, "Takeaway/sandwich shop"),
]


def fetch_fsa_type(la_id, business_type_id, type_name):
    """Fetch establishments of a specific type from FSA API."""
    params = {
        "localAuthorityId": la_id,
        "BusinessTypeId": business_type_id,
        "pageSize": 0,
    }
    print(f"Fetching FSA type {business_type_id} ({type_name})...")
    resp = requests.get(FSA_URL, params=params, headers=FSA_HEADERS, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    establishments = data.get("establishments", [])
    print(f"  Found {len(establishments)} establishments")
    return establishments


def convert_to_firebase_format(fsa_record):
    """Convert an FSA API record to our Firebase format."""
    rv_raw = fsa_record.get("RatingValue", "")
    try:
        rv = int(rv_raw)
    except (ValueError, TypeError):
        rv = None

    geocode = fsa_record.get("geocode", {}) or {}
    lat = geocode.get("latitude")
    lng = geocode.get("longitude")
    try:
        lat = float(lat) if lat else None
    except (ValueError, TypeError):
        lat = None
    try:
        lng = float(lng) if lng else None
    except (ValueError, TypeError):
        lng = None

    scores = fsa_record.get("scores", {}) or {}

    # Normalise FSA sub-scores (0=best, max=worst) to 0-10 (10=best)
    sh = scores.get("Hygiene")
    ss = scores.get("Structural")
    sm = scores.get("ConfidenceInManagement")
    if sh is not None:
        try:
            sh = round((25 - int(sh)) / 25 * 10, 1)
        except (ValueError, TypeError):
            sh = None
    if ss is not None:
        try:
            ss = round((25 - int(ss)) / 25 * 10, 1)
        except (ValueError, TypeError):
            ss = None
    if sm is not None:
        try:
            sm = round((20 - int(sm)) / 20 * 10, 1)
        except (ValueError, TypeError):
            sm = None

    return {
        "n": fsa_record.get("BusinessName", ""),
        "a": ", ".join(filter(None, [
            fsa_record.get("AddressLine1", ""),
            fsa_record.get("AddressLine2", ""),
            fsa_record.get("AddressLine3", ""),
        ])),
        "pc": fsa_record.get("PostCode", ""),
        "la": "Stratford-on-Avon",
        "r": rv,
        "rd": fsa_record.get("RatingDate", ""),
        "lat": lat,
        "lon": lng,
        "id": fsa_record.get("FHRSID"),
        "t": fsa_record.get("BusinessTypeId"),
        "sh": sh,
        "ss": ss,
        "sm": sm,
        "s": round(rv / 5 * 10, 1) if rv is not None else None,
    }


def main():
    est_path = "stratford_establishments.json"
    if not os.path.exists(est_path):
        print(f"ERROR: {est_path} not found")
        sys.exit(1)

    with open(est_path, "r", encoding="utf-8") as f:
        establishments = json.load(f)

    existing_ids = {str(v.get("id", k)) for k, v in establishments.items()}
    print(f"Existing: {len(establishments)} establishments ({len(existing_ids)} unique IDs)")

    added = 0
    for type_id, type_name in EXTRA_TYPES:
        fsa_records = fetch_fsa_type(LA_ID, type_id, type_name)
        for fsa_rec in fsa_records:
            fhrsid = str(fsa_rec.get("FHRSID", ""))
            if fhrsid in existing_ids:
                continue  # Already in dataset

            record = convert_to_firebase_format(fsa_rec)
            establishments[fhrsid] = record
            existing_ids.add(fhrsid)
            added += 1
            print(f"  + {record['n']} ({record['pc']}) [type {type_id}]")

    with open(est_path, "w", encoding="utf-8") as f:
        json.dump(establishments, f, indent=2, ensure_ascii=False)

    print(f"\nAdded {added} new establishments. Total: {len(establishments)}")


if __name__ == "__main__":
    main()
