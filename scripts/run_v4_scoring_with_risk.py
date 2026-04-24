#!/usr/bin/env python3
"""Run DayDine V4 scoring with optional Companies House risk input.

This is intentionally a wrapper around rcs_scoring_v4.py, not a replacement for
that engine. The V4 engine already contains the Companies House risk/cap rules;
this runner makes the CLI path pass the enrichment file into score_batch.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from rcs_scoring_v4 import score_batch, score_venue


def read_json(path: str | None, default: Any) -> Any:
    if not path:
        return default
    p = Path(path)
    if not p.exists():
        return default
    with p.open(encoding="utf-8") as handle:
        return json.load(handle)


def score_records(records: dict[str, Any], editorial: dict[str, Any], companies_house: dict[str, Any], menus: dict[str, Any]) -> dict[str, Any]:
    """Call score_batch where supported, with a safe per-record fallback."""
    try:
        return score_batch(
            records,
            editorial=editorial,
            companies_house=companies_house,
            menus=menus,
        )
    except TypeError:
        scored: dict[str, Any] = {}
        for key, record in records.items():
            scored[key] = score_venue(
                record,
                editorial=editorial.get(str(key)) or editorial.get(key),
                companies_house=companies_house.get(str(key)) or companies_house.get(key),
                menu=menus.get(str(key)) or menus.get(key),
            )
        return scored


def serialise_scores(scores: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, score in scores.items():
        output[str(key)] = score.to_dict() if hasattr(score, "to_dict") else score
    return output


def write_json(path: str, data: dict[str, Any]) -> None:
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def write_csv(path: str, data: dict[str, Any]) -> None:
    fields = [
        "id", "fhrsid", "name", "rcs_v4_final", "base_score", "adjusted_score",
        "confidence_class", "coverage_status", "rankable", "league_table_eligible",
        "companies_house", "penalties", "caps",
    ]
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for key, row in data.items():
            source_summary = row.get("source_family_summary") or {}
            writer.writerow({
                "id": key,
                "fhrsid": row.get("fhrsid"),
                "name": row.get("name"),
                "rcs_v4_final": row.get("rcs_v4_final"),
                "base_score": row.get("base_score"),
                "adjusted_score": row.get("adjusted_score"),
                "confidence_class": row.get("confidence_class"),
                "coverage_status": row.get("coverage_status"),
                "rankable": row.get("rankable"),
                "league_table_eligible": row.get("league_table_eligible"),
                "companies_house": source_summary.get("companies_house"),
                "penalties": json.dumps(row.get("penalties_applied") or [], ensure_ascii=False),
                "caps": json.dumps(row.get("caps_applied") or [], ensure_ascii=False),
            })


def summarise_companies_house(data: dict[str, Any]) -> dict[str, int]:
    penalties = caps = matched = 0
    for row in data.values():
        source_summary = row.get("source_family_summary") or {}
        if source_summary.get("companies_house") == "matched":
            matched += 1
        penalties += sum(1 for p in row.get("penalties_applied") or [] if str(p.get("code", "")).startswith("CH-"))
        caps += sum(1 for c in row.get("caps_applied") or [] if str(c.get("code", "")).startswith("CH-"))
    return {"matched": matched, "penalties": penalties, "caps": caps}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--menus", default=None)
    parser.add_argument("--editorial", default=None)
    parser.add_argument("--companies-house", default=None)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-csv", required=True)
    args = parser.parse_args()

    records = read_json(args.input, {})
    menus = read_json(args.menus, {})
    editorial = read_json(args.editorial, {})
    companies_house = read_json(args.companies_house, {})

    raw_scores = score_records(records, editorial, companies_house, menus)
    scores = serialise_scores(raw_scores)
    write_json(args.out_json, scores)
    write_csv(args.out_csv, scores)

    summary = summarise_companies_house(scores)
    print(
        "V4 scoring complete: "
        f"records={len(scores)}, companies_house_matched={summary['matched']}, "
        f"ch_penalties={summary['penalties']}, ch_caps={summary['caps']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
