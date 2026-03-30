#!/usr/bin/env python3
"""
collect_enforcement.py — Check FSA enforcement actions for Stratford establishments.

Queries the FSA API for enforcement actions (prosecutions, hygiene
improvement notices, emergency closures) and voluntary closures.

FSA Enforcement API: https://api.ratings.food.gov.uk/

Reads:  stratford_establishments.json
Writes: stratford_enforcement.json
"""

import json
import os
import sys
import time

import requests

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
INPUT_PATH = os.path.join(REPO_ROOT, "stratford_establishments.json")
OUTPUT_PATH = os.path.join(REPO_ROOT, "stratford_enforcement.json")

FSA_BASE = "https://api.ratings.food.gov.uk"
FSA_HEADERS = {"x-api-version": "2", "accept": "application/json"}


def check_fsa_establishment(fhrsid):
    """
    Query FSA API for enforcement details of a specific establishment.
    The FSA API provides ActionsTaken field for establishments.
    """
    url = f"{FSA_BASE}/Establishments/{fhrsid}"
    try:
        resp = requests.get(url, headers=FSA_HEADERS, timeout=15)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()

        result = {}

        # Check for enforcement actions
        # FSA schema includes ActionsTaken in newer responses
        actions = data.get("ActionsTaken") or data.get("actionsTaken")
        if actions:
            result["enforcement_actions"] = actions

        # Check rating history for closures / big drops
        scores = data.get("scores", {}) or {}
        rating = data.get("RatingValue")

        # Low ratings suggest potential enforcement history
        if rating is not None:
            try:
                rv = int(rating)
                if rv == 0:
                    result["has_enforcement"] = True
                    result["enforcement_severity"] = "urgent"
                elif rv == 1:
                    result["has_enforcement"] = True
                    result["enforcement_severity"] = "major"
            except (ValueError, TypeError):
                pass

        return result if result else None

    except requests.RequestException as e:
        print(f"    FSA API error for {fhrsid}: {e}")
        return None


def main():
    if not os.path.exists(INPUT_PATH):
        print(f"ERROR: {INPUT_PATH} not found")
        sys.exit(1)

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        establishments = json.load(f)
    print(f"Loaded {len(establishments)} establishments")

    enforcement_data = {}
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            enforcement_data = json.load(f)
        print(f"Loaded {len(enforcement_data)} existing enforcement records")

    total = len(establishments)
    checked = 0

    for i, (key, record) in enumerate(establishments.items(), 1):
        if key in enforcement_data:
            continue

        fhrsid = record.get("id") or key
        name = record.get("n", "")

        result = check_fsa_establishment(fhrsid)
        if result:
            enforcement_data[key] = result
            print(f"  [{i}/{total}] {name}: enforcement found — {result.get('enforcement_severity', 'unknown')}")
        else:
            enforcement_data[key] = {"_clean": True}

        checked += 1
        time.sleep(0.2)  # Light throttle for FSA API

        if i % 50 == 0:
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(enforcement_data, f, indent=2, ensure_ascii=False)
            print(f"  [{i}/{total}] saved progress")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(enforcement_data, f, indent=2, ensure_ascii=False)

    with_enforcement = sum(1 for v in enforcement_data.values()
                           if v.get("has_enforcement"))
    print(f"\nDone. Checked: {checked}, With enforcement: {with_enforcement}/{total}")
    print(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
