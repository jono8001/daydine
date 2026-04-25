#!/usr/bin/env python3
"""Generate an example operator report tracking snapshot.

This is a standalone example generator for the new operator-report tracking
product layer. It does not replace the main V4 report generator; it produces a
clear sample markdown section so the product shape can be reviewed immediately.

Usage:
    python scripts/generate_operator_tracking_example.py \
      --market stratford \
      --venue "Lambs" \
      --out outputs/examples/Lambs_tracking_snapshot_example.md
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

MARKETS = {
    "stratford": {
        "label": "Stratford-upon-Avon",
        "scores": "stratford_rcs_v4_scores.json",
        "establishments": "stratford_establishments.json",
    },
    "leamington": {
        "label": "Leamington Spa",
        "scores": "leamington_rcs_v4_scores.json",
        "establishments": "leamington_establishments.json",
    },
}


def norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def read_json(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def score(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def category(record: dict[str, Any]) -> str:
    name = norm(record.get("n"))
    bt = norm(record.get("fsa_business_type") or record.get("bt"))
    gty = {norm(t).replace(" ", "_") for t in (record.get("gty") or [])}
    if {"pub", "bar", "wine_bar", "cocktail_bar", "night_club"} & gty or any(x in name for x in [" pub", " bar", " inn"]):
        return "Pub / Bar"
    if {"hotel", "lodging", "bed_and_breakfast", "guest_house"} & gty or "hotel" in bt:
        return "Hotel / Accommodation"
    if "bakery" in gty or any(x in name for x in ["bakery", "baker", "patisserie", "gail"]):
        return "Bakery"
    if {"cafe", "coffee_shop", "tea_house"} & gty or any(x in name for x in ["cafe", "coffee", "tearoom"]):
        return "Cafe / Coffee Shop"
    if {"meal_takeaway", "fast_food_restaurant", "sandwich_shop"} & gty or "takeaway" in bt:
        return "Takeaway / Delivery"
    return "Restaurant (General)"


def build_rows(scores: dict[str, Any], establishments: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key, block in scores.items():
        final = score(block.get("rcs_v4_final"))
        if final is None or not block.get("league_table_eligible"):
            continue
        record = establishments.get(str(key)) or establishments.get(str(block.get("fhrsid"))) or {}
        rows.append({
            "key": str(key),
            "fhrsid": str(block.get("fhrsid") or record.get("fhrsid") or record.get("id") or key),
            "name": block.get("name") or record.get("public_name") or record.get("n") or str(key),
            "postcode": record.get("pc") or "",
            "score": final,
            "category": category(record),
            "confidence_class": block.get("confidence_class") or "",
        })
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows


def find_venue(rows: list[dict[str, Any]], query: str) -> dict[str, Any]:
    q = norm(query)
    exact = [r for r in rows if norm(r["name"]) == q]
    if exact:
        return exact[0]
    contains = [r for r in rows if q in norm(r["name"]) or norm(r["name"]) in q]
    if contains:
        return contains[0]
    raise SystemExit(f"No venue matching {query!r}. Try one of: " + ", ".join(r["name"] for r in rows[:10]))


def gap_text(rank: int, current_score: float, rows: list[dict[str, Any]], threshold_index: int, label: str) -> str:
    if len(rows) < threshold_index:
        return f"No {label} threshold yet."
    threshold = rows[threshold_index - 1]["score"]
    if rank <= threshold_index:
        return f"Already inside {label}."
    return f"+{max(0.0, threshold - current_score):.3f} RCS points to reach the current {label} threshold ({threshold:.3f})."


def visibility(rank: int, category_rank: int) -> str:
    if rank <= 10:
        return "Public top 10 overall"
    if category_rank <= 3:
        return "Public category top 3"
    return "Tracked, but not currently public-shortlisted"


def render_snapshot(market: dict[str, str], rows: list[dict[str, Any]], venue: dict[str, Any]) -> str:
    rank = rows.index(venue) + 1
    category_rows = [r for r in rows if r["category"] == venue["category"]]
    category_rank = category_rows.index(venue) + 1
    current_score = venue["score"]

    lower = max(0, rank - 3)
    upper = min(len(rows), rank + 2)
    neighbours = rows[lower:upper]

    lines: list[str] = []
    out = lines.append
    out(f"# {venue['name']} — Operator Tracking Snapshot Example")
    out("")
    out("This example shows the new section that should appear inside paid operator reports. It turns the report from a static score explanation into a monthly tracking product.")
    out("")
    out("## Monthly Tracking Snapshot")
    out("")
    out("| Tracking metric | Current position | Commercial meaning |")
    out("|---|---:|---|")
    out(f"| Local market | {market['label']} | Fully scored DayDine market |")
    out(f"| Overall DayDine position | #{rank} of {len(rows)} | {visibility(rank, category_rank)} |")
    out(f"| Category position | #{category_rank} of {len(category_rows)} {venue['category'].replace(' (General)', '').lower()} venues | Public category visibility starts at top 3 |")
    out(f"| DayDine RCS | {fmt(current_score)} | Current baseline for future movement tracking |")
    out(f"| Gap to public top 10 | {gap_text(rank, current_score, rows, 10, 'public top 10')} | Shows whether the venue is close to public overall visibility |")
    out(f"| Gap to category top 3 | {gap_text(category_rank, current_score, category_rows, 3, venue['category'].replace(' (General)', '') + ' top 3')} | Shows whether the venue is close to category visibility |")
    out("| Monthly movement | Baseline month | Next report can show up/down movement when prior snapshot is supplied |")
    out("")
    out("**Nearest overall competitors**")
    out("")
    out("| Rank | Venue | Category | RCS | Gap vs you |")
    out("|---:|---|---|---:|---:|")
    for idx, row in enumerate(neighbours, lower + 1):
        gap = row["score"] - current_score
        marker = "you" if row is venue else f"{gap:+.3f}"
        out(f"| #{idx} | {row['name']} | {row['category'].replace(' (General)', '')} | {fmt(row['score'])} | {marker} |")
    out("")
    out("**Operator focus for next month**")
    out("")
    if rank <= 10 or category_rank <= 3:
        out("- Protect current public visibility: keep listings complete, maintain review momentum, and avoid hygiene/compliance issues that could cap the score.")
    else:
        out("- Treat the top-10/category-top-3 gap as the monthly target: focus first on missing commercial-readiness signals, then review volume/validation, then trust/compliance caps.")
    out("- Use this section month by month: the paid report should show whether position, category rank and RCS are moving, not just explain the current score.")
    out("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", choices=sorted(MARKETS), default="stratford")
    parser.add_argument("--venue", default="Lambs")
    parser.add_argument("--out", default="outputs/examples/operator_tracking_snapshot_example.md")
    args = parser.parse_args()

    market = MARKETS[args.market]
    rows = build_rows(read_json(market["scores"]), read_json(market["establishments"]))
    venue = find_venue(rows, args.venue)
    text = render_snapshot(market, rows, venue)
    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
