#!/usr/bin/env python3
"""Canonicalise The Vintner Wine Bar into the Stratford public data layer.

This is a deterministic one-off repair for FHRSID 503480. The Vintner already
existed in report/review artifacts, but it was missing from the canonical
Stratford establishments slice and therefore absent from public rankings.

The script does not call external APIs. It writes the committed canonical files:
- stratford_establishments.json
- stratford_rcs_v4_scores.json
- assets/rankings/stratford-upon-avon.json via build_area_rankings_v4.py
- data/public_ranking_overrides.json, removing the temporary include override
- data/known_missing_stratford_venues.json, marking the guardrail resolved
- stratford_entity_resolution_report.json, removing the stale alias-missing flag
"""
from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
FHRSID = "503480"


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return deepcopy(default)
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


VINTNER_ESTABLISHMENT: dict[str, Any] = {
    "a": "The Vintner, 5 Sheep Street, Stratford-upon-Avon",
    "id": 503480,
    "la": "Stratford-on-Avon",
    "lat": 52.191304,
    "lon": -1.705989,
    "n": "The Vintner Wine Bar",
    "pc": "CV37 6EF",
    "r": 5,
    "rd": "2024-05-09T00:00:00",
    "s": 10.0,
    "sh": 7.5,
    "sm": 7.5,
    "ss": 7.5,
    "t": 1,
    "fhrsid": 503480,
    "fsa_business_name": "Vintner Wine Bar",
    "fsa_local_authority_business_id": "3152",
    "fsa_business_type": "Restaurant/Cafe/Canteen",
    "fsa_business_type_id": 1,
    "bt": "Restaurant/Cafe/Canteen",
    "btid": 1,
    "fsa_rating_value": "5",
    "gr": 4.6,
    "grc": 887,
    "ta": 4.4,
    "trc": 20,
    "ta_url": "https://www.tripadvisor.co.uk/Restaurant_Review-g186460-d730193-Reviews-The_Vintner_Wine_Bar-Stratford_upon_Avon_Warwickshire_England.html",
    "ta_cuisines": ["British", "Wine Bar"],
    "ta_ranking": "12",
    "gty": [
        "restaurant",
        "wine_bar",
        "bar",
        "food",
        "point_of_interest",
        "establishment",
    ],
    "gpid": "ChIJM4d8OjLOcEgRtipI76ULZ6E",
    "goh": [
        "Monday: 12:00–9:00 PM",
        "Tuesday: 12:00–9:00 PM",
        "Wednesday: 12:00–9:00 PM",
        "Thursday: 12:00–9:00 PM",
        "Friday: 12:00–9:30 PM",
        "Saturday: 12:00–9:30 PM",
        "Sunday: 12:00–8:30 PM",
    ],
    "web": True,
    "web_url": "https://www.the-vintner.co.uk/",
    "phone": "01789 297259",
    "reservable": True,
    "business_status": "OPERATIONAL",
    "public_name": "The Vintner Wine Bar",
    "trading_names": ["The Vintner", "Vintner", "Vintner Wine Bar"],
    "alias_source": "Manual canonical repair for FHRSID 503480; official FHRS venue missing from prior Stratford trial slice",
    "alias_confidence": "high",
    "entity_match": "confirmed",
}

# Preserved from the existing V4 sample artifact for this venue. The next full
# market pipeline run can recompute this record from source signals; this repair
# makes the current public ranking internally consistent immediately.
VINTNER_SCORE: dict[str, Any] = {
    "fhrsid": "503480",
    "name": "The Vintner Wine Bar",
    "components": {
        "trust_compliance": {"score": 8.523, "available": True, "signals_used": 5},
        "customer_validation": {
            "score": 8.803,
            "available": True,
            "platforms": {
                "google": {"raw": 4.6, "count": 887, "shrunk": 4.5673, "weight": 1.0},
                "tripadvisor": {"raw": 4.4, "count": 20, "shrunk": 3.9556, "weight": 0.1333},
            },
        },
        "commercial_readiness": {"score": 7.5, "available": True, "signals_used": 3},
    },
    "modifiers": {"distinction": {"value": 0.0, "sources": []}},
    "penalties_applied": [],
    "caps_applied": [],
    "base_score": 8.496,
    "adjusted_score": 8.496,
    "rcs_v4_final": 8.496,
    "confidence_class": "Rankable-A",
    "coverage_status": "coverage-ready",
    "rankable": True,
    "league_table_eligible": True,
    "source_family_summary": {
        "fsa": "present",
        "customer_platforms": ["google", "tripadvisor"],
        "commercial": "full",
        "companies_house": "unmatched",
    },
    "entity_match_status": "confirmed",
    "audit": {
        "engine_version": "v4.0.0",
        "computed_at": "2026-04-18T14:47:05Z",
        "decision_trace": [
            "Canonical repair from committed V4 sample artifact for FHRSID 503480",
            "TrustCompliance=8.523; CustomerValidation=8.803; CommercialReadiness=7.500",
            "base=8.496; distinction+0.000; adjusted=8.496; final=8.496",
            "class=Rankable-A; rankable=True; league=True",
        ],
    },
}


def patch_establishments() -> None:
    path = ROOT / "stratford_establishments.json"
    data = read_json(path, {})
    data[FHRSID] = VINTNER_ESTABLISHMENT
    write_json(path, dict(sorted(data.items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else str(kv[0]))))


def patch_scores() -> None:
    path = ROOT / "stratford_rcs_v4_scores.json"
    data = read_json(path, {})
    data[FHRSID] = VINTNER_SCORE
    write_json(path, dict(sorted(data.items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else str(kv[0]))))


def patch_known_missing() -> None:
    path = ROOT / "data" / "known_missing_stratford_venues.json"
    data = read_json(path, {"_note": "", "venues": []})
    changed = False
    for venue in data.get("venues", []):
        if str(venue.get("fhrsid")) == FHRSID:
            venue["status"] = "resolved"
            venue["resolved_by"] = "scripts/canonicalise_vintner.py"
            venue["resolved_note"] = "Canonical Stratford establishment, V4 score and public ranking output now include FHRSID 503480."
            changed = True
    if changed:
        write_json(path, data)


def patch_public_overrides() -> None:
    path = ROOT / "data" / "public_ranking_overrides.json"
    data = read_json(path, {"exclude_public": [], "include_public": [], "rename_public": []})
    data["include_public"] = [
        override for override in data.get("include_public", [])
        if str(override.get("fhrsid")) != FHRSID
    ]
    write_json(path, data)


def patch_entity_resolution_report() -> None:
    path = ROOT / "stratford_entity_resolution_report.json"
    data = read_json(path, None)
    if not isinstance(data, dict):
        return
    data["manual_aliases_missing_fhrsids"] = [
        x for x in data.get("manual_aliases_missing_fhrsids", []) if str(x) != FHRSID
    ]
    data["total_establishments"] = max(int(data.get("total_establishments") or 0), 209)
    named = data.setdefault("named_venue_resolution", {})
    named["Vintner"] = {
        "resolved_fhrsids": [FHRSID],
        "resolved": True,
        "public_names": ["The Vintner Wine Bar"],
    }
    write_json(path, data)


def patch_search_guardrail_filter() -> None:
    path = ROOT / "search-v2.html"
    if not path.exists():
        return
    html = path.read_text(encoding="utf-8")
    old = "return (data.venues||[]).map(v=>({"
    new = "return (data.venues||[]).filter(v=>v.status!=='resolved').map(v=>({"
    if old in html:
        html = html.replace(old, new)
        path.write_text(html, encoding="utf-8")


def rebuild_rankings() -> None:
    subprocess.run([
        sys.executable,
        "scripts/build_area_rankings_v4.py",
        "--scores", "stratford_rcs_v4_scores.json",
        "--establishments", "stratford_establishments.json",
        "--areas", "data/ranking_areas.json",
    ], cwd=ROOT, check=True)


def assert_canonicalised() -> None:
    establishments = read_json(ROOT / "stratford_establishments.json", {})
    scores = read_json(ROOT / "stratford_rcs_v4_scores.json", {})
    ranking = read_json(ROOT / "assets" / "rankings" / "stratford-upon-avon.json", {})
    all_ranked = list(ranking.get("venues", []))
    for category in ranking.get("category_rankings", []) or []:
        all_ranked.extend(category.get("venues", []) or [])

    assert FHRSID in establishments, "Vintner missing from stratford_establishments.json"
    assert FHRSID in scores, "Vintner missing from stratford_rcs_v4_scores.json"
    assert any("vintner" in str(v.get("name", "")).lower() for v in all_ranked), "Vintner missing from public ranking/category output"


def main() -> int:
    patch_establishments()
    patch_scores()
    patch_known_missing()
    patch_public_overrides()
    patch_entity_resolution_report()
    patch_search_guardrail_filter()
    rebuild_rankings()
    assert_canonicalised()
    print("Canonicalised FHRSID 503480 — The Vintner Wine Bar — into Stratford establishments, scores and rankings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
