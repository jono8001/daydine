#!/usr/bin/env python3
"""Fetch Stratford-on-Avon establishments from Firebase RTDB."""

import json
import requests

url = "https://recursive-research-eu-default-rtdb.europe-west1.firebasedatabase.app/daydine/establishments.json"
params = {"orderBy": '"la"', "equalTo": '"Stratford-on-Avon"'}

print("Fetching from Firebase RTDB...")
resp = requests.get(url, params=params, timeout=60)
resp.raise_for_status()
data = resp.json()
print(f"Fetched {len(data)} establishments")

with open("stratford_establishments.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print("Saved stratford_establishments.json")

# Verify postcodes
cv_count = sum(1 for r in data.values() if r.get("pc", "").startswith("CV"))
print(f"CV postcodes: {cv_count} of {len(data)}")
