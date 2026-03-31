#!/usr/bin/env python3
"""
augment_fsa_stratford.py — Augment Stratford data with ALL FSA establishments.

The Firebase RTDB only has a subset of FSA-registered establishments.
This script fetches ALL food-related business types from the FSA API
for Stratford-on-Avon district and merges any missing records.

Also checks a list of known important restaurants to ensure they're
included.

FSA LA ID for Stratford-on-Avon: 320
"""

import json
import os
import sys

import requests

FSA_URL = "https://api.ratings.food.gov.uk/Establishments"
FSA_HEADERS = {"x-api-version": "2", "accept": "application/json"}

# CORRECT FSA local authority ID for Stratford-on-Avon District Council
LA_ID = 320

# All food-related business types in the FSA system
FOOD_TYPES = [
    (1, "Restaurant/Cafe/Canteen"),
    (7, "Pub/bar/nightclub"),
    (14, "Takeaway/sandwich shop"),
    (7843, "Hotel/B&B/Guest House"),
]

# Known important restaurants that MUST be in the dataset
# If they're still missing after the FSA fetch, flag them
KNOWN_RESTAURANTS = [
    {"fhrsid": "503480", "name": "The Vintner", "postcode": "CV37 6EF"},
    {"fhrsid": None, "name": "The Dirty Duck", "postcode": "CV37 6BA"},
    {"fhrsid": None, "name": "The Rooftop Restaurant", "postcode": "CV37 6BB"},
    {"fhrsid": None, "name": "The Golden Bee", "postcode": "CV37 6QW"},
    {"fhrsid": None, "name": "Baraset Barn", "postcode": "CV35 9AA"},
    {"fhrsid": None, "name": "Boston Tea Party", "postcode": "CV37 6HJ"},
    {"fhrsid": None, "name": "Osteria Da Gino", "postcode": "CV37 6HJ"},
    {"fhrsid": None, "name": "Grace & Savour", "postcode": "CV37 6BA"},
    {"fhrsid": "503104", "name": "Simla Takeaway", "postcode": "CV37 6LE"},
]


def reconcile_fsa_count(la_id, our_count):
    """Check our count vs FSA total for data gap detection."""
    try:
        params = {"localAuthorityId": la_id, "pageSize": 1}
        resp = requests.get(FSA_URL, params=params, headers=FSA_HEADERS, timeout=15)
        resp.raise_for_status()
        fsa_total = resp.json().get("meta", {}).get("totalCount", 0)
        gap_pct = abs(fsa_total - our_count) / fsa_total * 100 if fsa_total > 0 else 0
        print(f"\nFSA reconciliation: FSA total={fsa_total}, ours={our_count}, gap={gap_pct:.1f}%")
        if gap_pct > 5:
            print(f"  WARNING: DATA_GAP — {gap_pct:.1f}% difference from FSA total")
        return {"fsa_total": fsa_total, "our_total": our_count,
                "gap_pct": round(gap_pct, 1), "warning": gap_pct > 5}
    except requests.RequestException as e:
        print(f"  FSA reconciliation check failed: {e}")
        return None


def fetch_fsa_all(la_id):
    """Fetch ALL establishments for the LA from FSA API (no type filter)."""
    params = {
        "localAuthorityId": la_id,
        "pageSize": 0,  # 0 = return all
    }
    print(f"Fetching ALL FSA establishments for LA ID {la_id}...")
    resp = requests.get(FSA_URL, params=params, headers=FSA_HEADERS, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    establishments = data.get("establishments", [])
    print(f"  FSA API returned {len(establishments)} total establishments")
    return establishments


def fetch_fsa_type(la_id, business_type_id, type_name):
    """Fetch establishments of a specific type from FSA API."""
    params = {
        "localAuthorityId": la_id,
        "BusinessTypeId": business_type_id,
        "pageSize": 0,
    }
    print(f"  Fetching type {business_type_id} ({type_name})...")
    resp = requests.get(FSA_URL, params=params, headers=FSA_HEADERS, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    establishments = data.get("establishments", [])
    print(f"    Found {len(establishments)}")
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

    # Build address string
    addr_parts = [
        fsa_record.get("AddressLine1", ""),
        fsa_record.get("AddressLine2", ""),
        fsa_record.get("AddressLine3", ""),
        fsa_record.get("AddressLine4", ""),
    ]
    address = ", ".join(p for p in addr_parts if p)

    return {
        "n": fsa_record.get("BusinessName", ""),
        "a": address,
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
    existing_ids.update(establishments.keys())
    print(f"Existing: {len(establishments)} establishments ({len(existing_ids)} tracked IDs)")

    # Remove bad augment data (wrong LA — check for non-Stratford postcodes)
    bad_keys = []
    for k, v in establishments.items():
        pc = v.get("pc", "")
        # Stratford-on-Avon postcodes: CV37, CV35, CV36, CV47, B49, B50, B80, B94, B95
        stratford_prefixes = ("CV3", "CV4", "B49", "B50", "B80", "B94", "B95")
        if v.get("t") is None and pc and not pc.startswith(stratford_prefixes):
            bad_keys.append(k)

    if bad_keys:
        print(f"Removing {len(bad_keys)} incorrectly augmented records (wrong LA)")
        for k in bad_keys:
            del establishments[k]

    # Fetch all food-related types from FSA
    added = 0
    for type_id, type_name in FOOD_TYPES:
        fsa_records = fetch_fsa_type(LA_ID, type_id, type_name)
        for fsa_rec in fsa_records:
            fhrsid = str(fsa_rec.get("FHRSID", ""))
            if fhrsid in existing_ids:
                continue

            record = convert_to_firebase_format(fsa_rec)
            establishments[fhrsid] = record
            existing_ids.add(fhrsid)
            added += 1
            print(f"    + {record['n']} ({record['pc']}) [type {type_id}]")

    # Check known important restaurants
    print(f"\nChecking {len(KNOWN_RESTAURANTS)} known important restaurants...")
    still_missing = []
    for known in KNOWN_RESTAURANTS:
        found = False
        name_lower = known["name"].lower()

        # Check by FHRSID
        if known.get("fhrsid") and known["fhrsid"] in existing_ids:
            found = True

        # Check by name
        if not found:
            for v in establishments.values():
                if name_lower in v.get("n", "").lower():
                    found = True
                    break

        if not found:
            still_missing.append(known)
            print(f"  STILL MISSING: {known['name']} ({known['postcode']})")
        else:
            print(f"  OK: {known['name']}")

    # For still-missing known restaurants, try fetching by FHRSID directly
    for known in still_missing:
        fhrsid = known.get("fhrsid")
        if not fhrsid:
            continue
        try:
            url = f"https://api.ratings.food.gov.uk/Establishments/{fhrsid}"
            resp = requests.get(url, headers=FSA_HEADERS, timeout=15)
            if resp.status_code == 200:
                fsa_rec = resp.json()
                record = convert_to_firebase_format(fsa_rec)
                establishments[fhrsid] = record
                existing_ids.add(fhrsid)
                added += 1
                print(f"  ADDED by FHRSID: {record['n']} ({record['pc']})")
        except requests.RequestException as e:
            print(f"  Error fetching FHRSID {fhrsid}: {e}")

    with open(est_path, "w", encoding="utf-8") as f:
        json.dump(establishments, f, indent=2, ensure_ascii=False)

    print(f"\nAdded {added} new establishments. Removed {len(bad_keys)} bad records.")
    print(f"Total: {len(establishments)}")

    # Final check
    vintner = any("vintner" in v.get("n", "").lower() for v in establishments.values())
    print(f"Vintner present: {vintner}")

    # FSA reconciliation
    reconcile_fsa_count(LA_ID, len(establishments))


if __name__ == "__main__":
    main()
