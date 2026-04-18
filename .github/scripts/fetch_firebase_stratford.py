#!/usr/bin/env python3
"""Fetch Stratford-on-Avon establishments from Firebase RTDB.

Hardened so that an empty or null Firebase response (transient
backend issue, index missing, LA value drift) fails fast with a
clear diagnostic BEFORE overwriting the committed cache. The
scoring pipeline downstream cannot produce meaningful statistics
from zero rows; we'd rather surface the root cause here than hit
a StatisticsError later.
"""

import json
import os
import sys

import requests

URL = (
    "https://recursive-research-eu-default-rtdb.europe-west1.firebasedatabase.app"
    "/daydine/establishments.json"
)
PARAMS = {"orderBy": '"la"', "equalTo": '"Stratford-on-Avon"'}
OUT_PATH = "stratford_establishments.json"
MIN_EXPECTED_ROWS = 1  # the trial LA has ~210 records; anything under this is a fault

print("Fetching from Firebase RTDB...")
print(f"  URL:    {URL}")
print(f"  params: {PARAMS}")

resp = requests.get(URL, params=PARAMS, timeout=60)
print(f"  HTTP:   {resp.status_code}")
resp.raise_for_status()

data = resp.json()

# Firebase returns `null` when nothing matches — normalise to empty dict
# for the size check below.
if data is None:
    data = {}

if not isinstance(data, dict):
    print(
        f"ERROR: Firebase returned a {type(data).__name__}, not a dict "
        f"(first 200 chars: {str(data)[:200]!r}). Aborting without writing cache.",
        file=sys.stderr,
    )
    sys.exit(2)

row_count = len(data)
print(f"Fetched {row_count} establishments")

if row_count < MIN_EXPECTED_ROWS:
    # Preserve the existing committed cache if present — better to re-run
    # with the previous dataset than to corrupt it with an empty object.
    existing_rows = None
    if os.path.exists(OUT_PATH):
        try:
            with open(OUT_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
            existing_rows = len(existing) if isinstance(existing, dict) else None
        except (OSError, ValueError):
            existing_rows = None

    print(
        "ERROR: Firebase returned 0 establishments. Likely causes:\n"
        "  * The RTDB `la` field has drifted (e.g. 'Stratford-upon-Avon' "
        "instead of 'Stratford-on-Avon').\n"
        "  * The `la` index was removed from firebase-rules.json "
        "(orderBy requires an indexOn rule).\n"
        "  * Upstream ingestion wiped / has not yet populated the node.\n"
        "Not overwriting the existing cache "
        f"({'existed with ' + str(existing_rows) + ' rows' if existing_rows else 'missing / unreadable'}). "
        "Aborting before scoring.",
        file=sys.stderr,
    )
    sys.exit(3)

# Verify postcodes before writing — a sanity check that the blob is shaped
# the way the scoring engine expects.
cv_count = sum(1 for r in data.values() if isinstance(r, dict) and r.get("pc", "").startswith("CV"))
print(f"CV postcodes: {cv_count} of {row_count}")
if cv_count == 0:
    print(
        "WARN: none of the fetched records have a CV postcode. Continuing "
        "but the LA filter may have drifted — inspect the output file before "
        "trusting downstream scores.",
        file=sys.stderr,
    )

with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f"Saved {OUT_PATH} ({row_count} rows)")
