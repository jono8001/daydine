#!/usr/bin/env python3
"""
fetch_stratford.py — Fetch Stratford-on-Avon establishments from Firebase RTDB.

Saves to stratford_establishments.json and stratford_establishments.csv.

Usage:
    python fetch_stratford.py
    python fetch_stratford.py --la "Newham"
"""

import argparse
import csv
import json
import os
import sys

import requests

FIREBASE_DB_URL = "https://recursive-research-eu-default-rtdb.europe-west1.firebasedatabase.app"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    parser = argparse.ArgumentParser(description="Fetch establishments from Firebase")
    parser.add_argument("--la", default="Stratford-on-Avon", help="Local authority name")
    args = parser.parse_args()

    url = f"{FIREBASE_DB_URL}/daydine/establishments.json"
    params = {"orderBy": '"la"', "equalTo": f'"{args.la}"'}

    print(f"Fetching establishments for LA: {args.la}")
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if not data:
        print("No establishments found.")
        sys.exit(1)

    print(f"Found {len(data)} establishments")

    # Save JSON
    json_path = os.path.join(SCRIPT_DIR, "stratford_establishments.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved to {json_path}")

    # Save CSV
    csv_path = os.path.join(SCRIPT_DIR, "stratford_establishments.csv")
    fields = ["_key", "n", "a1", "a2", "a3", "a4", "pc", "la", "bt",
              "rv", "r", "rd", "lat", "lng", "fhrsid", "gr", "grc", "gpl"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for key, record in data.items():
            row = {"_key": key}
            row.update(record)
            writer.writerow(row)
    print(f"Saved to {csv_path}")


if __name__ == "__main__":
    main()
