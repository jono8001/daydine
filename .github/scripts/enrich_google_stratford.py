#!/usr/bin/env python3
"""Official Google Places enrichment for the Stratford DayDine dataset.

This script reads ``stratford_establishments.json``, calls the Google Places API
(New) Text Search endpoint for each establishment, and writes
``stratford_google_enrichment.json``.

V4 public-ranking policy:
- use official Google Places API metadata only;
- do not scrape Google;
- do not request or store Google review text;
- do not request or store Google AI summaries;
- do not request or store Google photos/photo counts for headline scoring;
- keep field masks deliberately small and auditable.

Requires:
    GOOGLE_PLACES_API_KEY environment variable
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

GOOGLE_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")
PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Rate limit: ~10 req/sec max; 0.15s is deliberately conservative.
RATE_LIMIT_DELAY = 0.15

# Schema v3 = official-source V4 metadata mode. This deliberately excludes
# places.reviews, places.photos, generative summaries, and other non-essential
# fields. Keep this constant near the top so policy review is easy.
GOOGLE_PLACES_FIELD_MASK_V4 = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.types",
    "places.businessStatus",
    "places.nationalPhoneNumber",
    "places.internationalPhoneNumber",
    "places.websiteUri",
    "places.rating",
    "places.userRatingCount",
    "places.regularOpeningHours.weekdayDescriptions",
    "places.currentOpeningHours.weekdayDescriptions",
    "places.reservable",
])

FORBIDDEN_FIELD_MASK_TOKENS = (
    "places.reviews",
    "places.photos",
    "places.generativeSummary",
    "places.reviewSummary",
    "places.editorialSummary",
)

SCHEMA_VERSION = 3
MIN_OFFICIAL_SCHEMA = 3


def assert_official_field_mask() -> None:
    """Fail fast if a future edit adds non-approved high-risk fields."""
    offenders = [token for token in FORBIDDEN_FIELD_MASK_TOKENS
                 if token in GOOGLE_PLACES_FIELD_MASK_V4]
    if offenders:
        raise RuntimeError(
            "Google Places V4 field mask includes forbidden fields: "
            + ", ".join(offenders)
        )


def build_query(name: str, address: str, postcode: str) -> str:
    if address:
        return f"{name}, {address}, {postcode}, UK"
    return f"{name}, {postcode}, UK"


def extract_place(place: dict[str, Any], generated_at: str) -> dict[str, Any]:
    """Map one Places API response object into DayDine's compact aliases."""
    result: dict[str, Any] = {
        "gpid": place.get("id", ""),
        "_schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "data_provenance": ["google_places_api_new_official"],
        "google_official_fields_used": GOOGLE_PLACES_FIELD_MASK_V4.split(","),
    }

    display_name = place.get("displayName") or {}
    if isinstance(display_name, dict) and display_name.get("text"):
        result["google_display_name"] = display_name["text"]

    if place.get("formattedAddress"):
        result["google_formatted_address"] = place["formattedAddress"]
    if place.get("location"):
        result["google_location"] = place["location"]
    if "rating" in place:
        result["gr"] = place["rating"]
    if "userRatingCount" in place:
        result["grc"] = place["userRatingCount"]
    if place.get("types"):
        result["gty"] = place["types"]

    website_uri = place.get("websiteUri")
    if website_uri:
        result["websiteUri"] = website_uri
        result["web_url"] = website_uri

    national_phone = place.get("nationalPhoneNumber")
    international_phone = place.get("internationalPhoneNumber")
    if national_phone:
        result["nationalPhoneNumber"] = national_phone
    if international_phone:
        result["internationalPhoneNumber"] = international_phone
    phone = national_phone or international_phone
    if phone:
        result["phone"] = phone

    if "reservable" in place:
        result["reservable"] = bool(place["reservable"])

    if place.get("businessStatus"):
        result["business_status"] = place["businessStatus"]

    hours = place.get("regularOpeningHours") or place.get("currentOpeningHours")
    if hours and hours.get("weekdayDescriptions"):
        result["goh"] = hours["weekdayDescriptions"]

    return result


def search_place(name: str, address: str, postcode: str,
                 generated_at: str) -> dict[str, Any] | None:
    """Search for a place and return compact official metadata or None."""
    assert_official_field_mask()
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": GOOGLE_PLACES_FIELD_MASK_V4,
    }
    body = {
        "textQuery": build_query(name, address, postcode),
        "languageCode": "en",
        "regionCode": "GB",
    }

    resp = requests.post(PLACES_SEARCH_URL, headers=headers, json=body, timeout=20)
    resp.raise_for_status()
    places = resp.json().get("places", [])
    if not places:
        return None
    return extract_place(places[0], generated_at)


def _has_official_schema(entry: dict[str, Any]) -> bool:
    """Return True if a cached enrichment entry uses the official-source schema."""
    if entry.get("_no_match"):
        return int(entry.get("_schema_version", 1) or 1) >= MIN_OFFICIAL_SCHEMA
    return int(entry.get("_schema_version", 1) or 1) >= MIN_OFFICIAL_SCHEMA


def main() -> int:
    if not GOOGLE_API_KEY:
        print("ERROR: GOOGLE_PLACES_API_KEY not set", file=sys.stderr)
        return 1

    assert_official_field_mask()

    input_path = Path("stratford_establishments.json")
    output_path = Path("stratford_google_enrichment.json")

    if not input_path.exists():
        print(f"ERROR: {input_path} not found", file=sys.stderr)
        return 1

    data = json.loads(input_path.read_text(encoding="utf-8"))
    print(f"Loaded {len(data)} establishments")
    print("Google field mask:", GOOGLE_PLACES_FIELD_MASK_V4)

    enrichment: dict[str, Any] = {}
    if output_path.exists():
        enrichment = json.loads(output_path.read_text(encoding="utf-8"))
        pre_official = sum(1 for entry in enrichment.values()
                           if not _has_official_schema(entry))
        print(f"Loaded {len(enrichment)} existing enrichment records; "
              f"{pre_official} will be re-enriched for schema v{SCHEMA_VERSION}.")

    generated_at = datetime.now(timezone.utc).isoformat()
    enriched = skipped = no_match = failed = 0
    total = len(data)

    for i, (key, record) in enumerate(data.items(), 1):
        name = record.get("n", "")
        address = record.get("a", "")
        postcode = record.get("pc", "")

        if key in enrichment and _has_official_schema(enrichment[key]):
            skipped += 1
            continue
        if not name:
            skipped += 1
            continue

        try:
            result = search_place(name, address, postcode, generated_at)
            time.sleep(RATE_LIMIT_DELAY)

            if result is None:
                no_match += 1
                print(f"  [{i}/{total}] no match: {name}")
                enrichment[key] = {
                    "_no_match": True,
                    "_schema_version": SCHEMA_VERSION,
                    "generated_at": generated_at,
                    "data_provenance": ["google_places_api_new_official"],
                    "google_official_fields_used": GOOGLE_PLACES_FIELD_MASK_V4.split(","),
                }
            else:
                enrichment[key] = result
                enriched += 1
                print(
                    f"  [{i}/{total}] {name} -> "
                    f"gr={result.get('gr', '-')} "
                    f"grc={result.get('grc', 0)} "
                    f"web={'yes' if result.get('web_url') else 'no'} "
                    f"phone={'yes' if result.get('phone') else 'no'}"
                )

        except requests.exceptions.HTTPError as exc:
            failed += 1
            status = exc.response.status_code if exc.response is not None else "?"
            print(f"  [{i}/{total}] API error ({status}) for {name}: {exc}")
            if status == 429:
                print("  Rate limited — sleeping 10s")
                time.sleep(10)
            elif status == 403:
                print("  API key invalid, API disabled, or quota exceeded — stopping")
                break
        except Exception as exc:
            failed += 1
            print(f"  [{i}/{total}] error for {name}: {exc}")

        if i % 25 == 0:
            output_path.write_text(
                json.dumps(enrichment, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(f"  ... saved progress ({len(enrichment)} records)")

    output_path.write_text(
        json.dumps(enrichment, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    matched = sum(1 for v in enrichment.values() if not v.get("_no_match"))
    print(f"\nDone. Total: {total}, Enriched: {enriched}, Skipped: {skipped}, "
          f"No match: {no_match}, Failed: {failed}")
    print(f"Enrichment file: {len(enrichment)} records ({matched} with Google data)")
    print(f"Saved to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
