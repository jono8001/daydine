#!/usr/bin/env python3
"""Build per-area rankings JSON files for the DayDine website.

Reads an RCS scoring CSV (e.g. ``stratford_rcs_scores.csv``) and emits:
  - ``assets/rankings/<slug>.json`` — top 10 venues + metadata for the LA
  - updates ``assets/rankings/index.json`` — registry of all available areas

Only the top 10 ranked, food, non-excluded venues are exported. Venues ranked
11+ are NEVER exposed in the output — the Reports funnel depends on this.

Usage
-----
    python scripts/build_rankings.py \\
        --csv stratford_rcs_scores.csv \\
        --la "Stratford-on-Avon" \\
        --display "Stratford-upon-Avon"

The ``--slug`` is auto-derived from ``--la`` if omitted.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
RANKINGS_DIR = REPO_ROOT / "assets" / "rankings"
INDEX_FILE = RANKINGS_DIR / "index.json"
TOP_N = 10

BAND_CLASS = {
    "Excellent": "excellent",
    "Good": "good",
    "Generally Satisfactory": "satisfactory",
    "Improvement Necessary": "improvement",
    "Major Improvement": "major",
    "Urgent Improvement": "urgent",
}


def slugify(value: str) -> str:
    """Lowercase, strip accents, convert non-alphanumerics to single dashes."""
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def parse_convergence(raw: str) -> str:
    """Extract the bare status from 'converged(avg_div=0.080)' etc."""
    if not raw:
        return "unknown"
    match = re.match(r"([a-zA-Z_]+)", raw)
    return match.group(1) if match else "unknown"


def safe_float(value: str) -> float | None:
    if value in (None, "", "None"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def build_venue(row: dict[str, str], prior_ranks: dict[str, int] | None = None) -> dict[str, Any]:
    rcs = safe_float(row.get("rcs_final", ""))
    band = row.get("rcs_band", "").strip() or "Unknown"
    rank = int(row["rank"])
    name = row["business_name"].strip()

    # Compute monthly movement delta from prior snapshot
    movement = "new"
    movement_delta = 0
    if prior_ranks is not None:
        prior_rank = prior_ranks.get(name)
        if prior_rank is not None:
            delta = prior_rank - rank  # positive = improved (moved up)
            movement_delta = delta
            if delta > 0:
                movement = "up"
            elif delta < 0:
                movement = "down"
            else:
                movement = "same"
        else:
            movement = "new"
            movement_delta = 0

    return {
        "rank": rank,
        "name": name,
        "postcode": row.get("postcode", "").strip(),
        "category": row.get("category", "").strip(),
        "rcs_final": rcs,
        "rcs_band": band,
        "band_class": BAND_CLASS.get(band, "good"),
        "convergence": parse_convergence(row.get("convergence", "")),
        "movement": movement,
        "movement_delta": movement_delta,
    }


def load_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def count_ranked(rows: list[dict[str, str]]) -> int:
    """A venue is 'ranked' if it has a numeric rank field."""
    ranked = 0
    for row in rows:
        try:
            int(row.get("rank", ""))
        except (ValueError, TypeError):
            continue
        ranked += 1
    return ranked


def load_prior_ranks(slug: str) -> dict[str, int] | None:
    """Load the previous rankings JSON and return a name→rank map, or None."""
    prior_path = RANKINGS_DIR / f"{slug}.json"
    if not prior_path.exists():
        return None
    try:
        with prior_path.open(encoding="utf-8") as handle:
            prior = json.load(handle)
        # Build lookup from ALL ranked venues, not just the top N that were exported.
        # Since we only export top N, we store them plus a synthetic rank for
        # venues previously in top N but now outside it.
        ranks: dict[str, int] = {}
        for venue in prior.get("venues", []):
            ranks[venue["name"]] = venue["rank"]
        return ranks if ranks else None
    except (json.JSONDecodeError, KeyError):
        return None


def build_area_json(
    rows: list[dict[str, str]],
    la_name: str,
    display_name: str,
    slug: str,
) -> dict[str, Any]:
    ranked_rows = [
        row for row in rows
        if row.get("rank", "").strip().isdigit()
    ]
    ranked_rows.sort(key=lambda row: int(row["rank"]))
    top = ranked_rows[:TOP_N]

    total_venues = len(ranked_rows)
    others_count = max(0, total_venues - len(top))

    # Load prior month's rankings for delta computation
    prior_ranks = load_prior_ranks(slug)

    return {
        "la_name": la_name,
        "display_name": display_name,
        "slug": slug,
        "total_venues": total_venues,
        "top_n": len(top),
        "others_count": others_count,
        "last_updated": date.today().isoformat(),
        "venues": [build_venue(row, prior_ranks) for row in top],
    }


def update_index(area_data: dict[str, Any]) -> dict[str, Any]:
    """Upsert this area in the registry and return the updated index."""
    if INDEX_FILE.exists():
        with INDEX_FILE.open(encoding="utf-8") as handle:
            index = json.load(handle)
    else:
        index = {"last_updated": None, "available": [], "pipeline": []}

    available = [
        entry for entry in index.get("available", [])
        if entry.get("slug") != area_data["slug"]
    ]
    top_score = area_data["venues"][0]["rcs_final"] if area_data["venues"] else None
    available.append({
        "slug": area_data["slug"],
        "la_name": area_data["la_name"],
        "display_name": area_data["display_name"],
        "region": area_data.get("region", ""),
        "status": "live",
        "total_venues": area_data["total_venues"],
        "top_score": top_score,
    })
    available.sort(key=lambda entry: entry["display_name"].lower())

    index["available"] = available
    index["last_updated"] = date.today().isoformat()
    return index


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path,
                        help="Path to the RCS scoring CSV.")
    parser.add_argument("--la", required=True,
                        help="Local Authority name as used by postcodes.io (e.g. 'Stratford-on-Avon').")
    parser.add_argument("--display",
                        help="User-facing display name (defaults to --la).")
    parser.add_argument("--slug",
                        help="URL slug (defaults to slugified --la).")
    args = parser.parse_args()

    csv_path: Path = args.csv
    if not csv_path.is_absolute():
        csv_path = REPO_ROOT / csv_path
    if not csv_path.exists():
        print(f"error: CSV not found at {csv_path}", file=sys.stderr)
        return 1

    display_name = args.display or args.la
    slug = args.slug or slugify(args.la)
    rows = load_rows(csv_path)

    area_data = build_area_json(rows, args.la, display_name, slug)
    area_path = RANKINGS_DIR / f"{slug}.json"
    write_json(area_path, area_data)
    print(f"wrote {area_path.relative_to(REPO_ROOT)} "
          f"({area_data['top_n']} venues, {area_data['others_count']} others)")

    index = update_index(area_data)
    write_json(INDEX_FILE, index)
    print(f"wrote {INDEX_FILE.relative_to(REPO_ROOT)} "
          f"({len(index['available'])} area(s) registered)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
