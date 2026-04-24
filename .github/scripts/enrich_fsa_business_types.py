#!/usr/bin/env python3
"""Enrich Stratford establishments with official FHRS business types.

The Firebase cache used by DayDine is compact and may only carry the numeric
`t` field. For public rankings we need explicit official FHRS business-type
fields so the diner-facing leaderboard can distinguish restaurants/cafes/pubs
from broader FSA-registered retail or institutional food premises.

Reads and updates:
    stratford_establishments.json

Adds/preserves per record when available:
    fhrsid
    fsa_business_name
    fsa_local_authority_business_id
    fsa_business_type
    fsa_business_type_id
    bt      # compact alias for fsa_business_type
    btid    # compact alias for fsa_business_type_id
    fsa_rating_value

Uses the public FHRS API. No auth key is required.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import requests

INPUT_PATH = Path("stratford_establishments.json")
FHRS_ESTABLISHMENT_URL = "https://api.ratings.food.gov.uk/Establishments/{fhrsid}"
HEADERS = {
    "x-api-version": "2",
    "Accept": "application/json",
}
RATE_LIMIT_SECONDS = 0.05


def get_first(source: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            return value
    return None


def fetch_fhrs_establishment(fhrsid: int | str) -> dict[str, Any] | None:
    url = FHRS_ESTABLISHMENT_URL.format(fhrsid=fhrsid)
    response = requests.get(url, headers=HEADERS, timeout=20)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        return None
    return payload


def apply_fsa_fields(record: dict[str, Any], payload: dict[str, Any]) -> bool:
    changed = False

    mappings = {
        "fhrsid": get_first(payload, "FHRSID"),
        "fsa_business_name": get_first(payload, "BusinessName"),
        "fsa_local_authority_business_id": get_first(payload, "LocalAuthorityBusinessID"),
        "fsa_business_type": get_first(payload, "BusinessType"),
        "fsa_business_type_id": get_first(payload, "BusinessTypeID"),
        "bt": get_first(payload, "BusinessType"),
        "btid": get_first(payload, "BusinessTypeID"),
        "fsa_rating_value": get_first(payload, "RatingValue"),
    }

    for key, value in mappings.items():
        if value in (None, ""):
            continue
        if record.get(key) != value:
            record[key] = value
            changed = True

    return changed


def main() -> int:
    if not INPUT_PATH.exists():
        print(f"ERROR: {INPUT_PATH} not found", file=sys.stderr)
        return 1

    data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        print(f"ERROR: {INPUT_PATH} is not a dict", file=sys.stderr)
        return 1

    fetched = changed = skipped = missing = failed = 0
    total = len(data)

    for i, (key, record) in enumerate(data.items(), 1):
        if not isinstance(record, dict):
            skipped += 1
            continue

        # Prefer explicit FHRSID; fall back to compact Firebase id/key.
        fhrsid = get_first(record, "FHRSID", "fhrsid", "id") or key
        if not fhrsid:
            skipped += 1
            continue

        # Skip records that already carry the official business-type fields.
        if record.get("fsa_business_type") and record.get("fsa_business_type_id"):
            skipped += 1
            continue

        try:
            payload = fetch_fhrs_establishment(fhrsid)
            fetched += 1
            time.sleep(RATE_LIMIT_SECONDS)
            if payload is None:
                missing += 1
                print(f"[{i}/{total}] no FHRS API record: {fhrsid}")
                continue
            if apply_fsa_fields(record, payload):
                changed += 1
                print(
                    f"[{i}/{total}] enriched {record.get('n') or record.get('BusinessName') or fhrsid}: "
                    f"{record.get('fsa_business_type')} ({record.get('fsa_business_type_id')})"
                )
        except Exception as exc:
            failed += 1
            print(f"[{i}/{total}] failed FHRS {fhrsid}: {exc}", file=sys.stderr)

    INPUT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        "FSA business-type enrichment complete: "
        f"total={total}, fetched={fetched}, changed={changed}, "
        f"skipped={skipped}, missing={missing}, failed={failed}"
    )
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
