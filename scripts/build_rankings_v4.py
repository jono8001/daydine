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

Public category labels are deliberately different from eligibility:
- FSA type decides whether the venue can appear;
- Google Places types and venue-name terms decide whether the label shown to
  diners is Restaurant, Cafe, Pub, Hotel, Takeaway, etc.

Manual public overrides are supported via data/public_ranking_overrides.json.
They affect only assets/rankings/*.json, not V4 scores or operator reports.
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
OVERRIDES_FILE = ROOT / "data" / "public_ranking_overrides.json"

PUBLIC_FSA_BUSINESS_TYPES = {
    "restaurant/cafe/canteen",
    "pub/bar/nightclub",
    "takeaway/sandwich shop",
    "hotel/bed & breakfast/guest house",
    "mobile caterer",
}

FOOD_LED_TERMS = {
    "restaurant", "cafe", "coffee", "tea", "tearoom", "tea_room", "pub",
    "bar", "inn", "bakery", "baker", "takeaway", "meal_takeaway",
    "fast_food", "food", "meal", "diner", "bistro", "pizzeria", "pizza",
    "kitchen", "grill", "brasserie", "tavern", "hotel", "lodging",
    "catering", "caterer", "sandwich", "fish_and_chips", "ice_cream",
}

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

PUB_TYPES = {"pub", "bar", "wine_bar", "cocktail_bar", "beer_hall", "night_club"}
HOTEL_TYPES = {"hotel", "lodging", "bed_and_breakfast", "guest_house"}
CAFE_TYPES = {"cafe", "coffee_shop", "tea_house"}
TAKEAWAY_TYPES = {"meal_takeaway", "fast_food_restaurant", "sandwich_shop"}
BAKERY_TYPES = {"bakery"}
RESTAURANT_TYPES = {
    "restaurant", "british_restaurant", "italian_restaurant",
    "thai_restaurant", "chinese_restaurant", "indian_restaurant",
    "pizza_restaurant", "seafood_restaurant", "steak_house", "fine_dining_restaurant",
    "vegan_restaurant", "vegetarian_restaurant", "mediterranean_restaurant",
    "japanese_restaurant", "french_restaurant", "mexican_restaurant",
    "turkish_restaurant", "greek_restaurant", "spanish_restaurant",
    "brunch_restaurant", "breakfast_restaurant",
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


def canonical_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", norm(value)).strip()


def load_overrides() -> dict[str, list[dict[str, Any]]]:
    if not OVERRIDES_FILE.exists():
        return {"exclude_public": [], "include_public": [], "rename_public": []}
    data = read_json(OVERRIDES_FILE)
    return {
        "exclude_public": [x for x in data.get("exclude_public", []) if isinstance(x, dict)],
        "include_public": [x for x in data.get("include_public", []) if isinstance(x, dict)],
        "rename_public": [x for x in data.get("rename_public", []) if isinstance(x, dict)],
    }


def record_identifiers(name: str, key: str, item: dict[str, Any], record: dict[str, Any]) -> dict[str, str]:
    return {
        "key": norm(key),
        "name": canonical_name(name),
        "fhrsid": norm(item.get("fhrsid") or record.get("fhrsid") or record.get("id")),
        "gpid": norm(record.get("gpid")),
        "postcode": norm(record.get("pc")),
    }


def override_matches(override: dict[str, Any], identifiers: dict[str, str]) -> bool:
    """Match an override by fhrsid, gpid, key, or name+optional postcode."""
    for field in ("fhrsid", "gpid", "key"):
        value = norm(override.get(field))
        if value and value == identifiers.get(field):
            return True

    name = canonical_name(override.get("name"))
    if not name or name != identifiers.get("name"):
        return False

    postcode = norm(override.get("postcode"))
    if postcode and postcode != identifiers.get("postcode"):
        return False
    return True


def matching_override(overrides: list[dict[str, Any]], identifiers: dict[str, str]) -> dict[str, Any] | None:
    for override in overrides:
        if override_matches(override, identifiers):
            return override
    return None


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
    return any(record.get(key) not in (None, "", "AwaitingInspection")
               for key in ("r", "rd", "sh", "ss", "sm", "fsa_id", "fhrsid", "id"))


def official_fsa_public_type(record: dict[str, Any]) -> bool | None:
    business_type = fsa_business_type(record)
    if not business_type:
        return None
    return business_type in PUBLIC_FSA_BUSINESS_TYPES


def is_food_led_public_venue(record: dict[str, Any]) -> bool:
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

    if official_type_ok is False:
        return False
    if name_has_retail_signal and not name_has_food_signal:
        return False
    if official_type_ok is True:
        return True
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
    """Return the diner-facing category label.

    Eligibility is FSA-first, but category labelling should be more specific
    and public-friendly. It therefore prefers Google Places types and explicit
    venue-name terms before falling back to the broader official FSA type.
    """
    business_type = fsa_business_type(record)
    name = norm(record.get("n"))
    name_tokens = tokenise(name)
    joined = text_blob(record)
    google_types = set(str(t).lower() for t in (record.get("gty") or []))

    if google_types & PUB_TYPES or any(x in name_tokens for x in ["pub", "bar", "inn"]):
        return "Pub / Bar"
    if google_types & HOTEL_TYPES or any(x in joined for x in ["hotel", "lodging", "accommodation", "guest house"]):
        return "Hotel / Accommodation"
    if google_types & TAKEAWAY_TYPES or any(x in joined for x in ["meal_takeaway", "takeaway", "delivery", "fast_food"]):
        return "Takeaway / Delivery"
    if google_types & BAKERY_TYPES or "bakery" in name_tokens:
        return "Bakery"
    if google_types & CAFE_TYPES or any(x in name_tokens for x in ["cafe", "coffee", "tearoom", "tea_room"]):
        return "Cafe / Coffee Shop"
    if google_types & RESTAURANT_TYPES:
        return "Restaurant (General)"

    # Fallback only after specific public signals have been tried.
    if business_type == "pub/bar/nightclub":
        return "Pub / Bar"
    if business_type == "takeaway/sandwich shop":
        return "Takeaway / Delivery"
    if business_type == "hotel/bed & breakfast/guest house":
        return "Hotel / Accommodation"
    if business_type == "mobile caterer":
        return "Catering / Mobile Food"
    return "Restaurant (General)"


def build_category_rankings(venues: list[dict[str, Any]], per_category: int = 5) -> list[dict[str, Any]]:
    """Return compact top lists for each diner-facing category."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for venue in venues:
        grouped.setdefault(venue.get("category") or "Other", []).append(venue)

    category_rankings: list[dict[str, Any]] = []
    for cat, items in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        top_items = []
        for category_rank, venue in enumerate(items[:per_category], 1):
            public_venue = dict(venue)
            public_venue["category_rank"] = category_rank
            top_items.append(public_venue)
        category_rankings.append({
            "category": cat,
            "slug": slugify(cat),
            "total_venues": len(items),
            "top_n": len(top_items),
            "venues": top_items,
        })
    return category_rankings


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
    overrides = load_overrides()
    eligible = []
    excluded_non_food = 0
    excluded_by_override = 0
    included_by_override = 0

    for key, item in scores.items():
        score = item.get("rcs_v4_final")
        if score is None or not item.get("league_table_eligible"):
            continue
        record = establishments.get(str(key), {})
        name = item.get("name") or record.get("n") or str(key)
        ids = record_identifiers(name, str(key), item, record)

        exclude = matching_override(overrides["exclude_public"], ids)
        if exclude:
            excluded_by_override += 1
            continue

        include = matching_override(overrides["include_public"], ids)
        if include:
            included_by_override += 1
        elif not is_food_led_public_venue(record):
            excluded_non_food += 1
            continue

        rename = matching_override(overrides["rename_public"], ids)
        public_name = rename.get("public_name") if rename else None
        if public_name:
            item = dict(item)
            item["name"] = public_name

        eligible.append((float(score), str(key), item, record, include, rename))

    eligible.sort(key=lambda row: row[0], reverse=True)

    venues = []
    for rank, (score, key, item, rec, include_override, rename_override) in enumerate(eligible, 1):
        b, bc = band(score)
        name = item.get("name") or rec.get("n") or key
        mv, mv_delta = movement(name, rank, old)
        platforms = item.get("source_family_summary", {}).get("customer_platforms") or []
        google_only = platforms == ["google"]
        override_notes = []
        if include_override:
            override_notes.append("include_public")
        if rename_override:
            override_notes.append("rename_public")
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
            "public_override": override_notes or None,
        })

    visible = venues[:top_n]
    category_rankings = build_category_rankings(venues, per_category=5)
    return {
        "la_name": la,
        "display_name": display,
        "slug": slug,
        "methodology_version": "V4 official-source mode",
        "total_venues": len(venues),
        "top_n": len(visible),
        "others_count": max(0, len(venues) - len(visible)),
        "excluded_non_food_or_ambiguous": excluded_non_food,
        "excluded_by_public_override": excluded_by_override,
        "included_by_public_override": included_by_override,
        "category_rankings": category_rankings,
        "category_count": len(category_rankings),
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
    print(f"Excluded by public override: {area['excluded_by_public_override']}")
    print(f"Included by public override: {area['included_by_public_override']}")
    print(f"Category-specific lists: {area['category_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
