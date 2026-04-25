#!/usr/bin/env python3
"""Build public DayDine ranking JSON from V4 scoring output.

The public leaderboard is stricter than the internal V4 scorecard. A venue can
have a useful operator report if it is registered and enriched, but it should
only appear in the diner-facing leaderboard when it is clearly food-led.

Public output principles:
- public pages show top 10 overall and top 3 by category;
- public copy leads with DayDine Restaurant Confidence Score labels;
- shared public destinations can be clustered without merging underlying
  operator records or V4 scores.

Manual public overrides are supported via data/public_ranking_overrides.json.
Manual public clusters are supported via data/public_venue_clusters.json.
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
CLUSTERS_FILE = ROOT / "data" / "public_venue_clusters.json"

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
BAKERY_NAME_TERMS = {"bakery", "baker", "patisserie", "patisseries", "gail", "gails"}
CAFE_NAME_TERMS = {"cafe", "coffee", "tearoom", "tea_room", "starbucks", "costa", "coffee1"}
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


def load_clusters() -> list[dict[str, Any]]:
    if not CLUSTERS_FILE.exists():
        return []
    data = read_json(CLUSTERS_FILE)
    return [x for x in data.get("clusters", []) if isinstance(x, dict)]


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


def cluster_member_matches(member: dict[str, Any], venue: dict[str, Any]) -> bool:
    name = canonical_name(member.get("name"))
    postcode = norm(member.get("postcode"))
    if not name or name != canonical_name(venue.get("name")):
        return False
    if postcode and postcode != norm(venue.get("postcode")):
        return False
    return True


def find_cluster_for_venue(clusters: list[dict[str, Any]], venue: dict[str, Any]) -> dict[str, Any] | None:
    for cluster in clusters:
        for member in cluster.get("members", []):
            if isinstance(member, dict) and cluster_member_matches(member, venue):
                return cluster
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

    Eligibility is official-register-first, but category labelling should be
    specific and public-friendly. Bakery and cafe signals deliberately beat
    generic takeaway signals because Google often attaches meal_takeaway to
    bakeries, coffee shops and chains.
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
    if google_types & BAKERY_TYPES or name_tokens & BAKERY_NAME_TERMS:
        return "Bakery"
    if google_types & CAFE_TYPES or name_tokens & CAFE_NAME_TERMS:
        return "Cafe / Coffee Shop"
    if google_types & TAKEAWAY_TYPES or any(x in joined for x in ["meal_takeaway", "takeaway", "delivery", "fast_food"]):
        return "Takeaway / Delivery"
    if google_types & RESTAURANT_TYPES:
        return "Restaurant (General)"

    if business_type == "pub/bar/nightclub":
        return "Pub / Bar"
    if business_type == "takeaway/sandwich shop":
        return "Takeaway / Delivery"
    if business_type == "hotel/bed & breakfast/guest house":
        return "Hotel / Accommodation"
    if business_type == "mobile caterer":
        return "Catering / Mobile Food"
    return "Restaurant (General)"


def build_category_rankings(venues: list[dict[str, Any]], per_category: int = 3) -> list[dict[str, Any]]:
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


def apply_public_clusters(venues: list[dict[str, Any]], clusters: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Merge same-premises public destinations while preserving source members.

    This is public-output-only. The highest scoring member anchors the public
    score; source members remain listed in the metadata for auditability.
    """
    if not clusters:
        return venues, 0

    clustered: dict[int, list[dict[str, Any]]] = {}
    unclustered: list[dict[str, Any]] = []

    for venue in venues:
        cluster = find_cluster_for_venue(clusters, venue)
        if cluster:
            clustered.setdefault(id(cluster), []).append({"venue": venue, "cluster": cluster})
        else:
            unclustered.append(venue)

    merged_count = 0
    merged_venues: list[dict[str, Any]] = list(unclustered)
    for entries in clustered.values():
        if not entries:
            continue
        cluster = entries[0]["cluster"]
        members = [entry["venue"] for entry in entries]
        primary = max(members, key=lambda v: float(v.get("rcs_final") or 0))
        merged = dict(primary)
        merged["name"] = cluster.get("canonical_public_name") or primary.get("name")
        merged["category"] = cluster.get("canonical_category") or primary.get("category")
        if cluster.get("public_display_category"):
            merged["public_display_category"] = cluster.get("public_display_category")
        merged["public_cluster"] = True
        merged["public_cluster_reason"] = cluster.get("reason")
        merged["operator_reports"] = cluster.get("operator_reports", "keep_separate")
        merged["cluster_members"] = [
            {
                "name": v.get("name"),
                "postcode": v.get("postcode"),
                "category": v.get("category"),
                "rcs_final": v.get("rcs_final"),
            }
            for v in sorted(members, key=lambda v: float(v.get("rcs_final") or 0), reverse=True)
        ]
        merged_venues.append(merged)
        merged_count += max(0, len(members) - 1)

    merged_venues.sort(key=lambda v: float(v.get("rcs_final") or 0), reverse=True)
    return merged_venues, merged_count


def build(scores: dict[str, Any], establishments: dict[str, Any], slug: str,
          la: str, display: str, top_n: int) -> dict[str, Any]:
    old = prior_ranks(RANKINGS_DIR / f"{slug}.json")
    overrides = load_overrides()
    clusters = load_clusters()
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

    raw_venues = []
    for score, key, item, rec, include_override, rename_override in eligible:
        b, bc = band(score)
        name = item.get("name") or rec.get("n") or key
        override_notes = []
        if include_override:
            override_notes.append("include_public")
        if rename_override:
            override_notes.append("rename_public")
        raw_venues.append({
            "name": name,
            "postcode": rec.get("pc", ""),
            "category": category(rec),
            "rcs_final": round(score, 3),
            "rcs_band": b,
            "band_class": bc,
            "movement": "new",
            "movement_delta": 0,
            "daydine_scoring_status": "fully_scored",
            "daydine_scoring_label": "DayDine Restaurant Confidence Score",
            "public_visibility_label": "Tracked in live market",
            "methodology_label": "See RCS methodology",
            "public_override": override_notes or None,
        })

    venues, clustered_duplicates_removed = apply_public_clusters(raw_venues, clusters)

    ranked_venues = []
    for rank, venue in enumerate(venues, 1):
        v = dict(venue)
        v["rank"] = rank
        v["public_visibility_label"] = "Public top 10" if rank <= top_n else "Tracked in live market"
        mv, mv_delta = movement(v.get("name", ""), rank, old)
        v["movement"] = mv
        v["movement_delta"] = mv_delta
        ranked_venues.append(v)

    visible = ranked_venues[:top_n]
    category_rankings = build_category_rankings(ranked_venues, per_category=3)
    return {
        "la_name": la,
        "display_name": display,
        "slug": slug,
        "methodology_version": "V4 DayDine RCS official-source mode",
        "total_venues": len(ranked_venues),
        "top_n": len(visible),
        "others_count": max(0, len(ranked_venues) - len(visible)),
        "excluded_non_food_or_ambiguous": excluded_non_food,
        "excluded_by_public_override": excluded_by_override,
        "included_by_public_override": included_by_override,
        "public_clusters_applied": clustered_duplicates_removed,
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
    print(f"Public duplicate clusters removed: {area['public_clusters_applied']}")
    print(f"Category-specific lists: {area['category_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
