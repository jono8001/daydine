#!/usr/bin/env python3
"""Build public DayDine ranking JSON from V4 scoring output.

The public leaderboard is stricter than the internal V4 scorecard. A venue can
have a useful operator report if it is FSA-registered and Google-enriched, but
it should only appear in the diner-facing leaderboard when it is clearly
food-led. This keeps non-food-led FSA registrations, retail shops with limited
food activity, and ambiguous Google matches out of the public top list.

Public eligibility is now FSA-first:
- official FHRS/FSA business type is the primary gate when available;
- Google Places type is enrichment and sanity-check evidence, not the sole
  authority for public restaurant eligibility;
- retail-led public names are excluded unless the name itself is food-led.
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

# Official FHRS business types considered diner-facing enough for the public
# guide. Broader FSA registrations such as Retailers - other, Manufacturers,
# Distributors/Transporters, School/College, Caring Premises, etc. can still
# exist in the internal/operator layer but should not lead the public list.
PUBLIC_FSA_BUSINESS_TYPES = {
    "restaurant/cafe/canteen",
    "pub/bar/nightclub",
    "takeaway/sandwich shop",
    "hotel/bed & breakfast/guest house",
    "mobile caterer",
}

# Google/name terms that make a venue food-led enough for the public guide.
FOOD_LED_TERMS = {
    "restaurant", "cafe", "coffee", "tea", "tearoom", "tea_room", "pub",
    "bar", "inn", "bakery", "baker", "takeaway", "meal_takeaway",
    "fast_food", "food", "meal", "diner", "bistro", "pizzeria", "pizza",
    "kitchen", "grill", "brasserie", "tavern", "hotel", "lodging",
    "catering", "caterer", "sandwich", "fish_and_chips", "ice_cream",
}

# Terms that often indicate a retail/non-food-led primary proposition.
RETAIL_OR_AMBIGUOUS_TERMS = {
    "shop", "store", "retail", "crystal", "crystals", "gift", "gifts",
    "jewellery", "jewelry", "boutique", "gallery", "garden_centre",
    "convenience_store", "supermarket", "market", "farm_shop",
}

STRONG_GOOGLE_FOOD_TYPES = {
    "restaurant", "cafe", "coffee_shop", "bar", "pub", "bakery",
    "meal_takeaway", "fast_food_restaurant", "pizza_restaurant",
    "sandwich_shop", "ice_cream_shop",
}


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def tokenise(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", value.lower()))


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def norm(value: Any) -> str:
    return str(value or "").strip().lower()


def text_blob(record: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "n", "a", "bt", "business_type", "businessType", "BusinessType",
        "fsa_business_type", "fsa_business_name",
    ):
        value = record.get(key)
        if value:
            parts.append(str(value))
    parts.extend(str(v) for v in record.get("gty") or [])
    return " ".join(parts).lower()


def fsa_business_type(record: dict[str, Any]) -> str:
    return norm(
        record.get("fsa_business_type")
        or record.get("BusinessType")
        or record.get("businessType")
        or record.get("business_type")
        or record.get("bt")
    )


def has_fsa_backing(record: dict[str, Any]) -> bool:
    """Require a real FSA/FHRS anchor for public-ranking eligibility."""
    return any(record.get(key) not in (None, "", "AwaitingInspection")
               for key in ("r", "rd", "sh", "ss", "sm", "fsa_id", "fhrsid", "id"))


def official_fsa_public_type(record: dict[str, Any]) -> bool | None:
    """Return True/False when official FSA business type is known, else None."""
    business_type = fsa_business_type(record)
    if not business_type:
        return None
    return business_type in PUBLIC_FSA_BUSINESS_TYPES


def is_food_led_public_venue(record: dict[str, Any]) -> bool:
    """Return True when FSA + type evidence indicate a diner-facing venue."""
    if not has_fsa_backing(record):
        return False

    name = str(record.get("n") or "").lower()
    name_tokens = tokenise(name)
    blob = text_blob(record)
    blob_tokens = tokenise(blob)
    google_types = set(str(t).lower() for t in (record.get("gty") or []))

    has_food_signal = bool(blob_tokens & FOOD_LED_TERMS)
    has_retail_signal = bool(blob_tokens & RETAIL_OR_AMBIGUOUS_TERMS)
    name_has_food_signal = bool(name_tokens & FOOD_LED_TERMS)
    name_has_retail_signal = bool(name_tokens & RETAIL_OR_AMBIGUOUS_TERMS)
    strong_google_food = bool(google_types & STRONG_GOOGLE_FOOD_TYPES)
    official_type_ok = official_fsa_public_type(record)

    # Primary rule: if official FSA business type is available, use it as the
    # public leaderboard gate. Google can enrich/categorise the record but
    # should not override a non-public FSA type into the diner list.
    if official_type_ok is False:
        return False

    # Retail-led public trading names remain excluded unless the name itself
    # also carries a food-led term, e.g. "Farm Shop Cafe".
    if name_has_retail_signal and not name_has_food_signal:
        return False

    # If the official type is known and public-facing, it is enough, provided
    # the retail-name safeguard above has not fired.
    if official_type_ok is True:
        return True

    # Fallback only for older compact data before FHRS business-type enrichment:
    # require food-led Google/name evidence, with an ambiguity guard.
    if has_retail_signal and not (name_has_food_signal or strong_google_food):
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
    business_type = fsa_business_type(record)
    joined = text_blob(record)
    if business_type == "pub/bar/nightclub" or any(x in joined for x in ["pub", "bar", "inn"]):
        return "Pub / Bar"
    if business_type == "takeaway/sandwich shop" or any(x in joined for x in ["meal_takeaway", "takeaway", "delivery", "fast_food", "sandwich"]):
        return "Takeaway / Delivery"
    if business_type == "hotel/bed & breakfast/guest house" or any(x in joined for x in ["hotel", "lodging", "accommodation", "guest house"]):
        return "Hotel / Accommodation"
    if any(x in joined for x in ["cafe", "coffee", "tea_room", "tearoom"]):
        return "Cafe / Coffee Shop"
    if "bakery" in joined:
        return "Bakery"
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
            "fsa_business_type": fsa_business_type(rec) or None,
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
