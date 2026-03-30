#!/usr/bin/env python3
"""
fetch_fsa_stratford.py — Fetch Stratford-on-Avon restaurants from the FSA API,
convert to DayDine Firebase format, and save as stratford_establishments.json.

FSA API docs: https://api.ratings.food.gov.uk/help
Stratford-on-Avon district: localAuthorityId=336
BusinessTypeId=1 = Restaurants/Cafe/Canteen
"""

import csv
import json
import os
import sys

import requests

FSA_URL = "https://api.ratings.food.gov.uk/Establishments"
HEADERS = {"x-api-version": "2", "accept": "application/json"}
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))


def fetch_fsa_establishments():
    """Fetch all restaurants for Stratford-on-Avon from FSA API."""
    params = {
        "localAuthorityId": 336,
        "BusinessTypeId": 1,
        "pageSize": 0,  # 0 = return all
    }
    print("Fetching from FSA API...")
    resp = requests.get(FSA_URL, params=params, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    establishments = data.get("establishments", [])
    print(f"Fetched {len(establishments)} establishments from FSA API")
    return establishments


def convert_to_firebase_format(fsa_records):
    """
    Convert FSA API records to DayDine Firebase format.

    FSA fields -> Firebase fields:
      BusinessName -> n
      AddressLine1 -> a1
      AddressLine2 -> a2
      AddressLine3 -> a3
      AddressLine4 -> a4
      PostCode -> pc
      LocalAuthorityName -> la
      BusinessType -> bt
      RatingValue -> rv / r
      RatingDate -> rd
      geocode.latitude -> lat
      geocode.longitude -> lng
      FHRSID -> fhrsid
      scores.Hygiene -> sh
      scores.Structural -> ss
      scores.ConfidenceInManagement -> sc
    """
    firebase_data = {}

    for i, est in enumerate(fsa_records):
        # Parse rating value — FSA returns string like "5", "4", "Exempt", etc.
        rv_raw = est.get("RatingValue", "")
        try:
            rv = int(rv_raw)
        except (ValueError, TypeError):
            rv = None  # "Exempt", "AwaitingInspection", etc.

        # Parse geocode
        geocode = est.get("geocode", {}) or {}
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

        # Parse sub-scores
        scores = est.get("scores", {}) or {}

        record = {
            "n": est.get("BusinessName", ""),
            "a1": est.get("AddressLine1", ""),
            "a2": est.get("AddressLine2", ""),
            "a3": est.get("AddressLine3", ""),
            "a4": est.get("AddressLine4", ""),
            "pc": est.get("PostCode", ""),
            "la": est.get("LocalAuthorityName", "Stratford-on-Avon"),
            "bt": est.get("BusinessType", ""),
            "rv": rv,
            "r": rv,
            "rd": est.get("RatingDate", ""),
            "lat": lat,
            "lng": lng,
            "fhrsid": est.get("FHRSID"),
            "sh": scores.get("Hygiene"),
            "ss": scores.get("Structural"),
            "sc": scores.get("ConfidenceInManagement"),
        }

        # Use FHRSID as key (matches Firebase pattern)
        key = str(est.get("FHRSID", i))
        firebase_data[key] = record

    return firebase_data


def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(data)} records to {path}")


def save_csv(data, path):
    fields = ["_key", "n", "a1", "a2", "a3", "a4", "pc", "la", "bt",
              "rv", "r", "rd", "lat", "lng", "fhrsid", "sh", "ss", "sc"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for key, record in data.items():
            row = {"_key": key}
            row.update(record)
            writer.writerow(row)
    print(f"Saved {len(data)} records to {path}")


def main():
    fsa_records = fetch_fsa_establishments()
    if not fsa_records:
        print("ERROR: No records returned from FSA API")
        sys.exit(1)

    firebase_data = convert_to_firebase_format(fsa_records)

    json_path = os.path.join(REPO_ROOT, "stratford_establishments.json")
    csv_path = os.path.join(REPO_ROOT, "stratford_establishments.csv")

    save_json(firebase_data, json_path)
    save_csv(firebase_data, csv_path)

    # Print summary
    ratings = {}
    for record in firebase_data.values():
        rv = record.get("rv")
        key = str(rv) if rv is not None else "Unrated"
        ratings[key] = ratings.get(key, 0) + 1
    print("\nRating distribution:")
    for r in sorted(ratings.keys()):
        print(f"  Rating {r}: {ratings[r]}")


if __name__ == "__main__":
    main()
