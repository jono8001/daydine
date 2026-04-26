#!/usr/bin/env python3
"""Generate a static DayDine market-readiness QA summary.

This script is intentionally offline/deterministic. It does not call Google,
Firebase, FSA, TripAdvisor, Companies House or any other external service.
It answers a simple release question: does the committed market data look safe
enough to publish or refresh?

Example:
    python scripts/check_market_readiness.py --market stratford-upon-avon
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
AREAS_FILE = ROOT / "data" / "ranking_areas.json"
ALIASES_FILE = ROOT / "data" / "entity_aliases.json"
RANKINGS_DIR = ROOT / "assets" / "rankings"


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def resolve_area(market: str) -> dict[str, Any]:
    config = read_json(AREAS_FILE, {"areas": []})
    wanted = slugify(market)
    for area in config.get("areas", []):
        aliases = [
            area.get("slug"),
            area.get("display_name"),
            area.get("la_name"),
            *(area.get("legacy_slugs") or []),
        ]
        if wanted in {slugify(str(a)) for a in aliases if a}:
            return area
    raise SystemExit(f"Unknown market '{market}'. Add it to {AREAS_FILE.relative_to(ROOT)} first.")


def data_prefix_for_area(area: dict[str, Any]) -> str:
    """Infer the committed source-data prefix for the configured area.

    The current repo has one canonical source dataset for the Stratford-on-Avon
    local-authority pull, from which both Stratford town and Stratford district
    outputs are built. This helper keeps the convention explicit until a richer
    markets config adds data_source_prefix directly.
    """
    if area.get("data_source_prefix"):
        return str(area["data_source_prefix"])
    la = norm(area.get("la_name"))
    slug = norm(area.get("slug"))
    if "stratford" in la or "stratford" in slug:
        return "stratford"
    if "leamington" in la or "leamington" in slug:
        return "leamington"
    return slugify(area.get("slug") or area.get("display_name") or "market")


def load_known_missing() -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for file_name in sorted(glob.glob(str(ROOT / "data" / "known_missing_*_venues.json"))):
        path = Path(file_name)
        data = read_json(path, {"venues": []})
        for venue in data.get("venues", []):
            fhrsid = str(venue.get("fhrsid") or "").strip()
            if not fhrsid:
                continue
            enriched = dict(venue)
            enriched["guardrail_file"] = str(path.relative_to(ROOT))
            records[fhrsid] = enriched
    return records


def collect_alias_warnings(establishments: dict[str, Any], known_missing: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    aliases = read_json(ALIASES_FILE, {"aliases": []}).get("aliases", [])
    missing = []
    unresolved = []
    for alias in aliases:
        fhrsid = str(alias.get("fhrsid") or "").strip()
        if not fhrsid:
            continue
        if fhrsid in establishments:
            continue
        entry = {
            "fhrsid": fhrsid,
            "public_name": alias.get("public_name"),
            "postcode": alias.get("postcode"),
        }
        missing.append(entry)
        if fhrsid not in known_missing:
            unresolved.append(entry)
    return missing, unresolved


def collect_duplicate_gpids(prefix: str) -> list[dict[str, Any]]:
    report = read_json(ROOT / f"{prefix}_entity_resolution_report.json", {}) or {}
    groups = []
    for group in report.get("duplicate_gpid_groups", []) or []:
        groups.append({
            "gpid": group.get("gpid"),
            "fhrsids": group.get("fhrsids", []),
            "names": group.get("names", []),
            "reason": group.get("reason_for_operator") or group.get("note"),
        })
    for group in report.get("manual_ambiguous_groups", []) or []:
        groups.append({
            "gpid_conflict": group.get("gpid_conflict"),
            "disambiguation_type": group.get("disambiguation_type"),
            "fhrsids": group.get("fhrsids", []),
            "names": group.get("names", []),
            "reason": group.get("reason_for_operator") or group.get("note"),
        })
    return groups


def build_summary(market: str) -> dict[str, Any]:
    area = resolve_area(market)
    prefix = data_prefix_for_area(area)
    establishments_path = ROOT / f"{prefix}_establishments.json"
    scores_path = ROOT / f"{prefix}_rcs_v4_scores.json"
    ranking_path = RANKINGS_DIR / f"{area['slug']}.json"

    establishments = read_json(establishments_path, {}) or {}
    scores = read_json(scores_path, {}) or {}
    ranking = read_json(ranking_path, {}) or {}
    known_missing = load_known_missing()
    alias_missing, alias_unresolved = collect_alias_warnings(establishments, known_missing)
    duplicate_gpids = collect_duplicate_gpids(prefix)

    scored = [s for s in scores.values() if s.get("rcs_v4_final") is not None]
    rankable = [s for s in scores.values() if s.get("league_table_eligible")]
    public_venues = ranking.get("venues", []) or []
    category_venues = sum(len(c.get("venues", []) or []) for c in ranking.get("category_rankings", []) or [])

    warnings: list[str] = []
    if not establishments:
        warnings.append(f"No establishments loaded from {establishments_path.relative_to(ROOT)}")
    if not scores:
        warnings.append(f"No V4 scores loaded from {scores_path.relative_to(ROOT)}")
    if not public_venues:
        warnings.append(f"No public ranking venues loaded from {ranking_path.relative_to(ROOT)}")
    if alias_unresolved:
        warnings.append(f"{len(alias_unresolved)} alias FHRSID(s) are missing from establishments and are not covered by known-missing guardrails")
    if alias_missing:
        warnings.append(f"{len(alias_missing)} alias FHRSID(s) are missing from establishments; see alias_missing_from_establishments")
    if known_missing:
        warnings.append(f"{len(known_missing)} known-missing venue guardrail(s) active; canonical data rebuild still required")
    if duplicate_gpids:
        warnings.append(f"{len(duplicate_gpids)} duplicate/ambiguous Google Place group(s) recorded")
    if ranking.get("total_venues") and len(public_venues) < min(30, ranking.get("total_venues", 0)):
        warnings.append("Public venues list is shorter than expected top-N visibility")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market": area.get("slug"),
        "display_name": area.get("display_name"),
        "area_type": area.get("area_type"),
        "public": bool(area.get("public")),
        "operator": bool(area.get("operator")),
        "data_source_prefix": prefix,
        "files": {
            "area_config": str(AREAS_FILE.relative_to(ROOT)),
            "establishments": str(establishments_path.relative_to(ROOT)),
            "scores": str(scores_path.relative_to(ROOT)),
            "ranking": str(ranking_path.relative_to(ROOT)),
        },
        "counts": {
            "total_establishments": len(establishments),
            "total_scored": len(scored),
            "total_rankable": len(rankable),
            "total_public_ranking_venues": len(public_venues),
            "total_category_ranking_entries": category_venues,
            "aliases_missing_from_establishments": len(alias_missing),
            "aliases_unresolved_without_guardrail": len(alias_unresolved),
            "known_missing_venues": len(known_missing),
            "duplicate_or_ambiguous_gpid_groups": len(duplicate_gpids),
        },
        "alias_missing_from_establishments": alias_missing,
        "alias_unresolved_without_guardrail": alias_unresolved,
        "known_missing_venues": list(known_missing.values()),
        "duplicate_or_ambiguous_gpid_groups": duplicate_gpids[:20],
        "top_warnings": warnings[:20],
        "status": "blocked" if alias_unresolved else ("warning" if warnings else "ready"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", default="stratford-upon-avon")
    parser.add_argument("--out", help="Optional path to write the readiness JSON")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on blocked status")
    args = parser.parse_args()

    summary = build_summary(args.market)
    if args.out:
        write_json(ROOT / args.out, summary)
    json.dump(summary, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    if args.strict and summary["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
