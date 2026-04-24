#!/usr/bin/env python3
"""Build public DayDine ranking JSON from V4 scoring output.

The public leaderboard is stricter than the internal V4 scorecard. A venue can
have a useful operator report if it is FSA-registered and Google-enriched, but
it should only appear in the diner-facing leaderboard when it is clearly
food-led. This keeps non-food-led FSA registrations, retail shops with limited
food activity, and ambiguous Google matches out of the public top list.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RANKINGS_DIR = ROOT / "assets" / "rankings"
INDEX_FILE = RANKINGS_DIR / "index.json"

# Google/FSA terms that make a venue food-led enough for the public guide.
FOOD_LED_TERMS = {
    "restaurant", "cafe", "coffee", "tea", "tearoom", "tea_room", "pub",
    "bar", "inn", "bakery", "baker", "takeaway", "meal_takeaway",
    "fast_food", "food", "meal", "diner", "bistro", "pizzeria", "pizza",
    "kitchen", "grill", "brasserie", "tavern", "hotel", "lodging",
    "catering", "caterer", "sandwich", "fish_and_chips", "ice_cream",
}

# Terms that often indicate a retail/non-food-led primary proposition. They do
# not automatically exclude a venue if Google/FSA also clearly marks it as food
# led, but they stop weak/ambiguous matches entering the public leaderboard.
RETAIL_OR_AMBIGUOUS_TERMS = {
    "shop", "store", "retail", "crystal", "crystals", "gift", "gifts",
    "jewellery", "jewelry", "boutique", "gallery", "garden_centre",
    "convenience_store", "supermarket", "market", "farm_shop",
}


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def text_blob(record: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("n", "a", "bt", "business_type", "businessType", "BusinessType"):
        value = record.get(key)
        if value:
            parts.append(str(value))
    parts.extend(str(v) for v in record.get("gty") or [])
    return " ".join(parts).lower()


def has_fsa_backing(record: dict[str, Any]) -> bool:
    """Require a real FSA/FHRS anchor for public-ranking eligibility."""
    return any(record.get(key) not in (None, "", "AwaitingInspection")
               for key in ("r", "rd", "sh", "ss", "sm", "fsa_id", "id"))


def is_food_led_public_venue(record: dict[str, Any]) -> bool:
    """Return True when FSA + type evidence indicate a diner-facing venue."""
    if not has_fsa_backing(record):
        return False

    blob = text_blob(record)
    has_food_signal = any(term in blob for term in FOOD_LED_TERMS)
    has_retail_signal = any(term in blob for term in RETAIL_OR_AMBIGUOUS_TERMS)

    google_types = set(str(t).lower() for t in (record.get("gty") or []))
    strong_google_food = bool(google_types & {
        "restaurant", "cafe", "coffee_shop", "bar", "pub", "bakery",
        "meal_takeaway", "fast_food_restaurant", "pizza_restaurant",
        "sandwich_shop", "ice_cream_shop",
    })

    # Retail-like venues must have a strong food-service type to appear publicly.
    if has_retail_signal and not strong_google_food:
        return False

    return has_food_signal or strong_google_food


def band(score: float) -> tuple[str, str]:
    if score >= 8.0:
        return "Excellent", "excellent"
    if score >= 6.5:
        return "Good", "good"
    if score >= 5.0:
        return "Generally Satisfactory", "satisfactory"
    if score >= 3.5:
        return "Improvement Necessary", "improvement"
    if score >= 2.0:
        return "Major Improvement", "major"
    return "Urgent Improvement", "urgent"


def category(record: dict[str, Any]) -> str:
    joined = text_blob(record)
    if any(x in joined for x in ["cafe", "coffee", "tea_room", "tearoom"]):
        return "Cafe / Coffee Shop"
    if any(x in joined for x in ["pub", "bar", "inn"]):
        return "Pub / Bar"
    if "bakery" in joined:
        return "Bakery"
    if any(x in joined for x in ["hotel", "lodging", "accommodation"]):
        return "Hotel / Accommodation"
    if any(x in joined for x in ["meal_takeaway", "takeaway", "delivery", "fast_food"]):
        return "Takeaway / Delivery"
    return "Restaurant (General)"


def prior_ranks(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    try:
        data = read_json(path)
        return {v["name"]: int(v["rank"]) for v in data.get("venues", []) if v.get("name")}
    except Exception:
        return {}


def movement(name: str, rank: int, old: dict[str, int]) -> tuple[str, int]:
    previous = old.get(name)
    if previous is None:
        return "new", 0
    delta = previous - rank
    if delta > 0:
        return "up", delta
    if delta < 0:
        return "down", delta
    return "same", 0


def build(scores: dict[str, Any], establishments: dict[str, Any], slug: str,
          la: str, display: str, top_n: int) -> dict[str, Any]:
    old = prior_ranks(RANKINGS_DIR / f"{slug}.json")
    eligible = []
    excluded_non_food = 0
    for key, item in scores.items():
        score = item.get("rcs_v4_final")
        if score is None or not item.get("league_table_eligible"):
            continue
        record = establishments.get(str(key), {})
        if not is_food_led_public_venue(record):
            excluded_non_food += 1
            continue
        eligible.append((float(score), str(key), item, record))
    eligible.sort(key=lambda row: row[0], reverse=True)

    venues = []
    for rank, (score, key, item, rec) in enumerate(eligible, 1):
        b, bc = band(score)
        name = item.get("name") or rec.get("n") or key
        mv, mv_delta = movement(name, rank, old)
        platforms = item.get("source_family_summary", {}).get("customer_platforms") or []
        google_only = platforms == ["google"]
        venues.append({
            "rank": rank,
            "name": name,
            "postcode": rec.get("pc", ""),
            "category": category(rec),
            "rcs_final": round(score, 3),
            "rcs_band": b,
            "band_class": bc,
            "convergence": "single-platform" if google_only else "multi-platform",
            "movement": mv,
            "movement_delta": mv_delta,
            "confidence_class": item.get("confidence_class"),
            "coverage_status": item.get("coverage_status"),
            "single_platform_caveat": google_only,
            "public_evidence_label": "Official Google + FSA evidence" if google_only else "Multi-source public evidence",
        })

    visible = venues[:top_n]
    return {
        "la_name": la,
        "display_name": display,
        "slug": slug,
        "methodology_version": "V4 official-source mode",
        "total_venues": len(venues),
        "top_n": len(visible),
        "others_count": max(0, len(venues) - len(visible)),
        "excluded_non_food_or_ambiguous": excluded_non_food,
        "last_updated": date.today().isoformat(),
        "venues": visible,
    }


def update_index(area: dict[str, Any], region: str) -> dict[str, Any]:
    index = read_json(INDEX_FILE) if INDEX_FILE.exists() else {"available": [], "pipeline": []}
    available = [e for e in index.get("available", []) if e.get("slug") != area["slug"]]
    available.append({
        "slug": area["slug"],
        "la_name": area["la_name"],
        "display_name": area["display_name"],
        "region": region,
        "status": "live",
        "methodology_version": area["methodology_version"],
        "total_venues": area["total_venues"],
        "top_score": area["venues"][0]["rcs_final"] if area["venues"] else None,
    })
    index["available"] = sorted(available, key=lambda e: e["display_name"].lower())
    index["last_updated"] = date.today().isoformat()
    return index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores", default="stratford_rcs_v4_scores.json")
    parser.add_argument("--establishments", default="stratford_establishments.json")
    parser.add_argument("--la", default="Stratford-on-Avon")
    parser.add_argument("--display", default="Stratford-upon-Avon")
    parser.add_argument("--region", default="Warwickshire")
    parser.add_argument("--slug")
    parser.add_argument("--top-n", type=int, default=10)
    args = parser.parse_args()

    slug = args.slug or slugify(args.la)
    scores = read_json(ROOT / args.scores)
    establishments = read_json(ROOT / args.establishments)
    area = build(scores, establishments, slug, args.la, args.display, args.top_n)
    write_json(RANKINGS_DIR / f"{slug}.json", area)
    write_json(INDEX_FILE, update_index(area, args.region))
    print(f"Built V4 public rankings for {area['display_name']}: {area['total_venues']} eligible, {area['top_n']} visible")
    print(f"Excluded non-food/ambiguous public entries: {area['excluded_non_food_or_ambiguous']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
