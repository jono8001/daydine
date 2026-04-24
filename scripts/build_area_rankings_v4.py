#!/usr/bin/env python3
"""Build V4 ranking JSON for configured DayDine ranking areas.

This wrapper separates the data-collection unit from the public geography:
- the refreshed source dataset can remain local-authority/district based;
- public diner guides can be town/city/neighbourhood based;
- operator outputs can keep wider district/catchment views.

It delegates scoring/eligibility/overrides to build_rankings_v4.py and only
filters records by configured area before building each output file.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from build_rankings_v4 import build, read_json, write_json

ROOT = Path(__file__).resolve().parent.parent
RANKINGS_DIR = ROOT / "assets" / "rankings"
INDEX_FILE = RANKINGS_DIR / "index.json"
DEFAULT_AREAS_FILE = ROOT / "data" / "ranking_areas.json"


def safe_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in kilometres."""
    radius = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def record_in_area(record: dict[str, Any], area: dict[str, Any]) -> tuple[bool, float | None]:
    """Return (in_area, distance_km_or_none)."""
    if area.get("area_type") == "district":
        return True, None

    centre = area.get("centre") or {}
    radius_km = safe_float(area.get("radius_km"))
    centre_lat = safe_float(centre.get("lat"))
    centre_lon = safe_float(centre.get("lon"))
    rec_lat = safe_float(record.get("lat"))
    rec_lon = safe_float(record.get("lon"))

    if None in (radius_km, centre_lat, centre_lon, rec_lat, rec_lon):
        return False, None

    km = distance_km(float(centre_lat), float(centre_lon), float(rec_lat), float(rec_lon))
    return km <= float(radius_km), round(km, 3)


def filter_for_area(scores: dict[str, Any], establishments: dict[str, Any], area: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, float]]:
    filtered_scores: dict[str, Any] = {}
    filtered_establishments: dict[str, Any] = {}
    distances: dict[str, float] = {}

    for key, record in establishments.items():
        in_area, km = record_in_area(record, area)
        if not in_area:
            continue
        if key not in scores:
            continue
        filtered_scores[key] = scores[key]
        filtered_establishments[key] = record
        if km is not None:
            distances[key] = km

    return filtered_scores, filtered_establishments, distances


def add_area_metadata(area_json: dict[str, Any], area: dict[str, Any], distances: dict[str, float]) -> dict[str, Any]:
    area_json["area_type"] = area.get("area_type")
    area_json["public"] = bool(area.get("public"))
    area_json["operator"] = bool(area.get("operator"))
    area_json["description"] = area.get("description", "")
    if area.get("centre"):
        area_json["centre"] = area.get("centre")
    if area.get("radius_km") is not None:
        area_json["radius_km"] = area.get("radius_km")

    area_json["distance_filter_applied"] = bool(distances)
    return area_json


def build_index(area_outputs: list[dict[str, Any]], pipeline_from_existing: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    available = []
    operator_areas = []
    for area in area_outputs:
        entry = {
            "slug": area["slug"],
            "la_name": area["la_name"],
            "display_name": area["display_name"],
            "region": area.get("region", "Warwickshire"),
            "area_type": area.get("area_type"),
            "status": "live",
            "methodology_version": area.get("methodology_version"),
            "total_venues": area.get("total_venues"),
            "top_score": area["venues"][0]["rcs_final"] if area.get("venues") else None,
        }
        if area.get("public"):
            available.append(entry)
        if area.get("operator") and not area.get("public"):
            operator_areas.append(entry)

    return {
        "last_updated": area_outputs[0].get("last_updated") if area_outputs else None,
        "available": sorted(available, key=lambda x: x["display_name"].lower()),
        "operator_areas": sorted(operator_areas, key=lambda x: x["display_name"].lower()),
        "pipeline": pipeline_from_existing or [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores", default="stratford_rcs_v4_scores.json")
    parser.add_argument("--establishments", default="stratford_establishments.json")
    parser.add_argument("--areas", default=str(DEFAULT_AREAS_FILE))
    args = parser.parse_args()

    scores = read_json(ROOT / args.scores)
    establishments = read_json(ROOT / args.establishments)
    areas_config = read_json(ROOT / args.areas)
    areas = areas_config.get("areas", [])
    if not areas:
        raise SystemExit("No areas configured")

    existing_pipeline = []
    if INDEX_FILE.exists():
        try:
            existing_pipeline = read_json(INDEX_FILE).get("pipeline", [])
        except Exception:
            existing_pipeline = []

    outputs = []
    for area in areas:
        slug = area["slug"]
        filtered_scores, filtered_establishments, distances = filter_for_area(scores, establishments, area)
        output = build(
            scores=filtered_scores,
            establishments=filtered_establishments,
            slug=slug,
            la=area.get("la_name", ""),
            display=area.get("display_name", slug),
            top_n=int(area.get("top_n", 10)),
        )
        output["region"] = area.get("region")
        add_area_metadata(output, area, distances)
        write_json(RANKINGS_DIR / f"{slug}.json", output)

        # Backwards-compatible aliases let older pages and links continue to
        # consume the canonical town data while the new canonical slug rolls out.
        for legacy_slug in area.get("legacy_slugs", []):
            alias_output = dict(output)
            alias_output["canonical_slug"] = slug
            alias_output["slug"] = legacy_slug
            alias_output["legacy_alias"] = True
            write_json(RANKINGS_DIR / f"{legacy_slug}.json", alias_output)
            print(f"Wrote legacy alias {legacy_slug}.json -> {slug}.json")

        outputs.append(output)
        print(
            f"Built {slug}: {output['total_venues']} eligible, "
            f"{output['top_n']} visible, area_type={output.get('area_type')}"
        )

    write_json(INDEX_FILE, build_index(outputs, existing_pipeline))
    print(f"Updated {INDEX_FILE.relative_to(ROOT)} with {len(outputs)} configured area(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
