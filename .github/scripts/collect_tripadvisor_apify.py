#!/usr/bin/env python3
"""
collect_tripadvisor_apify.py — Collect TripAdvisor headline metadata via Apify.

For each establishment this script queries an Apify TripAdvisor actor, picks
the best candidate result by combined name similarity + coordinate proximity,
and writes per-venue raw metadata files under `data/raw/tripadvisor/`. A
subsequent `consolidate_tripadvisor.py` run builds `stratford_tripadvisor.json`.

Scoring only needs `ta` (rating) and `trc` (review count). Review text is
collected for report narrative purposes only and is never consumed by the
V4 scoring engine (spec V4 §9).

Env:
    APIFY_TOKEN     (required) — Apify user token
    APIFY_ACTOR     (optional) — Override the default actor. Known good:
                      * automation-lab/tripadvisor-scraper (legacy)
                      * scrapapi/tripadvisor-review-scraper (recommended
                        per docs/review_data_strategy.md §2.2)
    MAX_REVIEWS     (optional) — Max reviews per venue (default 5).
    MATCH_MIN_SCORE (optional) — Min combined match score 0-1 (default 0.55)

Reads:  stratford_establishments.json
Writes: data/raw/tripadvisor/<slug>_<date>.json  (one file per matched venue)
"""

import datetime
import difflib
import json
import math
import os
import re
import sys
import time
from urllib.parse import quote_plus

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
INPUT_PATH = os.path.join(REPO_ROOT, "stratford_establishments.json")
RAW_DIR = os.path.join(REPO_ROOT, "data", "raw", "tripadvisor")

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
APIFY_ACTOR = os.environ.get("APIFY_ACTOR") or "scrapapi/tripadvisor-review-scraper"
LOCATION = "Stratford-upon-Avon"
MAX_REVIEWS = int(os.environ.get("MAX_REVIEWS") or "5")
MATCH_MIN_SCORE = float(os.environ.get("MATCH_MIN_SCORE") or "0.55")
COORD_TOLERANCE_M = 200.0
# Optional dry-run limit wired from the workflow's dispatch input.
# 0 / unset / negative ⇒ no limit; >0 ⇒ process only the first N venues.
DRY_RUN_LIMIT = int(os.environ.get("DRY_RUN_LIMIT") or "0")


def build_apify_input(actor: str, query: str, max_places: int,
                       max_reviews: int) -> dict:
    """Build the Apify actor input payload for `query`, branching by actor.

    TripAdvisor Apify actors do not share a common input schema, so the
    shape has to be chosen per actor. Supporting multiple actors from one
    switch statement means we can swap actors via the APIFY_ACTOR env var
    without editing this script.

    Known actors:

      * `scrapapi/tripadvisor-review-scraper` — strictly requires
        `startUrls`. The "No startUrls provided" error message mentions
        "hotel URL, hotel name, or keyword" — the first is mandatory,
        the other two are aliases the actor understands if present.
        We provide a TripAdvisor Search URL built from the query so the
        actor can resolve restaurants by name even when the exact
        restaurant URL isn't known, plus the keyword/searchString
        aliases as belt-and-braces.

      * `automation-lab/tripadvisor-scraper` — legacy keyword-based
        schema. Takes a list of arbitrary search queries and does
        discovery internally.
    """
    if actor.startswith("scrapapi/tripadvisor-review-scraper"):
        search_url = (
            "https://www.tripadvisor.com/Search?q=" + quote_plus(query)
        )
        return {
            "startUrls": [{"url": search_url}],
            "keywords": [query],
            "searchStrings": [query],
            "locationFullName": query,
            "maxReviewsPerPlace": max_reviews,
            "maxItems": max_places,
            "language": "en",
            "includeReviews": True,
        }

    # Default / legacy: automation-lab/tripadvisor-scraper and compatible.
    return {
        "searchQueries": [query],
        "placeType": "restaurant",
        "maxPlacesPerQuery": max_places,
        "maxReviewsPerPlace": max_reviews,
        "language": "en",
    }


def normalise_name(name):
    name = name.lower().strip()
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def fuzzy_score(a, b):
    return difflib.SequenceMatcher(None, normalise_name(a), normalise_name(b)).ratio()


def slugify(name):
    slug = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
    return slug[:60] or "unknown"


def haversine_m(a_lat, a_lon, b_lat, b_lon):
    if None in (a_lat, a_lon, b_lat, b_lon):
        return float("inf")
    R = 6_371_000.0
    p1 = math.radians(float(a_lat))
    p2 = math.radians(float(b_lat))
    dp = math.radians(float(b_lat) - float(a_lat))
    dl = math.radians(float(b_lon) - float(a_lon))
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def combined_match_score(target_name, target_lat, target_lon, candidate):
    """Combine fuzzy name similarity (70%) and coord proximity (30%).

    Coord proximity contributes only when both the target and the candidate
    have coords. Otherwise fuzzy name similarity is returned unchanged.
    Returns a float 0-1 where >= MATCH_MIN_SCORE is considered a match.
    """
    name = candidate.get("name") or candidate.get("title") or ""
    sim = fuzzy_score(target_name, name)

    c_lat = candidate.get("lat") or candidate.get("latitude")
    c_lon = candidate.get("lng") or candidate.get("lon") or candidate.get("longitude")
    if None in (target_lat, target_lon, c_lat, c_lon):
        return sim
    try:
        d = haversine_m(target_lat, target_lon, float(c_lat), float(c_lon))
    except (TypeError, ValueError):
        return sim
    # Proximity score: 1.0 at 0m, 0 at 1000m, linear in between
    prox = max(0.0, 1.0 - min(d, 1000.0) / 1000.0)
    return 0.7 * sim + 0.3 * prox


def search_apify(query, token, max_places=1, max_reviews=5):
    """
    Run the Apify TripAdvisor scraper for a single query.
    Returns list of place dicts with rating, reviews, etc.
    """
    try:
        from apify_client import ApifyClient
    except ImportError:
        print("ERROR: apify-client not installed. Run: pip install apify-client")
        sys.exit(1)

    client = ApifyClient(token)

    run_input = build_apify_input(APIFY_ACTOR, query, max_places, max_reviews)

    try:
        run = client.actor(APIFY_ACTOR).call(
            run_input=run_input,
            timeout_secs=120,
        )
        results = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            results.append(item)
        return results
    except Exception as e:
        print(f"    Apify error: {e}")
        return []


def extract_ta_data(apify_result, original_name, target_lat=None,
                     target_lon=None):
    """
    Extract structured TripAdvisor data from an Apify result.

    Returns (entry_dict, combined_match_score) or (None, score) if the
    result does not clear `MATCH_MIN_SCORE`.
    """
    entry = {}

    name = apify_result.get("name", "") or apify_result.get("title", "")
    match = combined_match_score(original_name, target_lat, target_lon,
                                  apify_result)
    if match < MATCH_MIN_SCORE:
        return None, match

    entry["ta_name"] = name
    entry["match_score"] = round(match, 2)

    # Rating
    rating = apify_result.get("rating") or apify_result.get("averageRating")
    if rating:
        try:
            entry["ta"] = round(float(rating), 1)
        except (ValueError, TypeError):
            pass

    # Review count
    for field in ["reviewCount", "numberOfReviews", "reviewsCount"]:
        rc = apify_result.get(field)
        if rc is not None:
            try:
                entry["trc"] = int(rc)
                break
            except (ValueError, TypeError):
                pass

    # URL
    url = apify_result.get("url") or apify_result.get("webUrl")
    if url:
        entry["ta_url"] = url

    # Ranking
    ranking = apify_result.get("ranking") or apify_result.get("rankingPosition")
    if ranking:
        entry["ta_ranking"] = str(ranking)

    # Cuisine tags
    cuisines = apify_result.get("cuisines") or apify_result.get("cuisine")
    if cuisines:
        if isinstance(cuisines, list):
            entry["ta_cuisines"] = [c.get("name", c) if isinstance(c, dict) else str(c) for c in cuisines]
        elif isinstance(cuisines, str):
            entry["ta_cuisines"] = [c.strip() for c in cuisines.split(",")]

    # Price range
    price = apify_result.get("priceRange") or apify_result.get("priceLevel")
    if price:
        entry["ta_price"] = str(price)

    # Reviews (up to MAX_REVIEWS)
    reviews = apify_result.get("reviews", [])
    if reviews and isinstance(reviews, list):
        extracted = []
        for rev in reviews[:MAX_REVIEWS]:
            r = {}
            text = rev.get("text") or rev.get("reviewBody")
            if text:
                r["text"] = str(text)[:500]  # Truncate long reviews
            r_rating = rev.get("rating") or rev.get("ratingValue")
            if r_rating:
                try:
                    r["rating"] = int(r_rating)
                except (ValueError, TypeError):
                    pass
            r["date"] = rev.get("publishedDate") or rev.get("createdDate") or ""
            if r.get("text"):
                extracted.append(r)
        if extracted:
            entry["ta_reviews"] = extracted

    return entry, match


def should_search(record):
    """Check if this establishment should be searched on TripAdvisor."""
    gty = record.get("gty", [])
    types_set = set(gty) if isinstance(gty, list) else set()

    # Skip non-food
    non_food = {"sports_club", "church", "place_of_worship", "insurance_agency",
                "miniature_golf_course", "gym", "fitness_center"}
    if non_food & types_set and not (types_set & {"restaurant", "cafe", "food", "bar", "pub"}):
        return False

    # Skip by name
    name = (record.get("n") or "").lower()
    skip_names = ["slimming world", "football club", "golf club", "aston martin",
                  "nfu mutual", "baptist church", "horse sanctuary"]
    if any(sn in name for sn in skip_names):
        return False

    return True


def _raw_path_for(record, key):
    slug = slugify(record.get("n") or f"venue_{key}")
    date = datetime.date.today().strftime("%Y-%m-%d")
    return os.path.join(RAW_DIR, f"{slug}_{key}_{date}.json")


def _already_have_raw(key):
    """Skip if a raw file for this fhrsid already exists (any date)."""
    if not os.path.isdir(RAW_DIR):
        return False
    for f in os.listdir(RAW_DIR):
        if f.endswith(".json") and f"_{key}_" in f:
            return True
    return False


def main():
    if not APIFY_TOKEN:
        print("ERROR: APIFY_TOKEN not set")
        print("Add it as a GitHub secret or set in environment:")
        print("  export APIFY_TOKEN=apify_api_xxxxx")
        sys.exit(1)

    if not os.path.exists(INPUT_PATH):
        print(f"ERROR: {INPUT_PATH} not found")
        sys.exit(1)

    os.makedirs(RAW_DIR, exist_ok=True)

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        establishments = json.load(f)
    print(f"Loaded {len(establishments)} establishments")
    print(f"Using Apify actor: {APIFY_ACTOR}")

    # Dry-run limit. Workflow dispatch input `limit` is threaded through as
    # DRY_RUN_LIMIT. 0 means "no limit" (legacy default). Apply BEFORE the
    # per-venue loop so `total` and the final guard reflect the limited set.
    if DRY_RUN_LIMIT and DRY_RUN_LIMIT > 0:
        limited = dict(list(establishments.items())[:DRY_RUN_LIMIT])
        print(f"DRY_RUN_LIMIT={DRY_RUN_LIMIT} — limiting loop to "
              f"{len(limited)} establishments (of {len(establishments)})")
        establishments = limited

    matched = 0
    no_match = 0
    skipped = 0
    errors = 0
    total = len(establishments)

    for i, (key, record) in enumerate(establishments.items(), 1):
        name = record.get("n", "")

        # Resume: if a raw file already exists for this fhrsid, skip
        if _already_have_raw(key):
            skipped += 1
            continue

        if not name or not should_search(record):
            skipped += 1
            continue

        query = f"{name} {LOCATION}"
        target_lat = record.get("lat")
        target_lon = record.get("lon")
        print(f"  [{i}/{total}] Searching: {query}")

        try:
            results = search_apify(query, APIFY_TOKEN,
                                   max_places=3, max_reviews=MAX_REVIEWS)

            if not results:
                no_match += 1
                print(f"    No results")
                continue

            # Pick best match by combined name+coord score
            best_entry = None
            best_score = 0.0
            for result in results:
                entry, score = extract_ta_data(result, name,
                                                target_lat, target_lon)
                if entry and score > best_score:
                    best_entry = entry
                    best_score = score

            if best_entry:
                # Write a per-venue raw file using the schema used elsewhere
                # in data/raw/tripadvisor/ (see vintner_wine_bar_*.json)
                raw_out = {
                    "fhrsid": str(key),
                    "name": best_entry.get("ta_name"),
                    "tripadvisor_url": best_entry.get("ta_url"),
                    "tripadvisor_rating": best_entry.get("ta"),
                    "tripadvisor_review_count": best_entry.get("trc"),
                    "tripadvisor_ranking": best_entry.get("ta_ranking"),
                    "tripadvisor_cuisines": best_entry.get("ta_cuisines", []),
                    "collected_at": datetime.datetime.utcnow()
                        .strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "collection_method": f"apify/{APIFY_ACTOR}",
                    "match_score": best_entry.get("match_score"),
                    "reviews_collected": len(best_entry.get("ta_reviews", [])),
                    "reviews": best_entry.get("ta_reviews", []),
                }
                out_path = _raw_path_for(record, key)
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(raw_out, f, indent=2, ensure_ascii=False)
                matched += 1
                print(f"    Match! ta={raw_out['tripadvisor_rating']} "
                      f"trc={raw_out['tripadvisor_review_count']} "
                      f"score={best_score:.2f} -> {os.path.basename(out_path)}")
            else:
                no_match += 1
                print(f"    No fuzzy match (best={best_score:.2f})")

        except Exception as e:
            errors += 1
            print(f"    Error: {e}")

        # Small delay between Apify calls
        time.sleep(1)

    print(f"\nDone. Total: {total}")
    print(f"  Matched: {matched}, No match: {no_match}, "
          f"Skipped: {skipped}, Errors: {errors}")
    print(f"  Raw files under: {RAW_DIR}")
    print(f"Next step: run .github/scripts/consolidate_tripadvisor.py "
          f"and .github/scripts/merge_tripadvisor.py")

    # Hard-fail guard. If we attempted any venues and none matched, the
    # actor was almost certainly fed a payload it didn't understand
    # (input-schema mismatch) or the authenticated account is rate-limited
    # / out of credits. Either way, zero matches over N>0 venues is a
    # meaningful pipeline failure that must not be silently counted as
    # "no-match". This covers the case where every per-venue call exits 0
    # with an empty dataset (which would not increment `errors`).
    if total > 0 and matched == 0:
        sys.stderr.write(
            "\n::error::Apify TripAdvisor collection produced ZERO matches "
            f"across {total} attempted venues "
            f"(no_match={no_match}, skipped={skipped}, errors={errors}). "
            "This almost always means the actor's input schema does not "
            "match the payload build in build_apify_input() — inspect the "
            "Apify run logs for the actor's exact error. "
            "See docs/DayDine-TripAdvisor-Strategy-Decision.md.\n"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
