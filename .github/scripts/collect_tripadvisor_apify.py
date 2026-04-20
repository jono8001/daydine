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
from pathlib import Path
from urllib.parse import quote_plus

# Repo root resolved from THIS file's location. .parents[2] because the
# script lives at `<repo>/.github/scripts/collect_tripadvisor_apify.py`.
# Using pathlib here instead of os.path because pathlib's `.parents[N]`
# indexing is less error-prone than stacked `os.path.join(..., "..", "..")`
# calls (which, when the script is loaded from an unrelated directory,
# can resolve to `/` and cause writes to `/data/...` with
# PermissionError — that happened on run #9 of the workflow's preflight
# test step).
REPO_ROOT = Path(__file__).resolve().parents[2]

# All write-paths are env-overridable so tests (and any future alternate
# deployments) can redirect writes to a tmpdir without string-patching
# this file. The defaults are the canonical repo-relative locations.
INPUT_PATH = (
    os.environ.get("STRATFORD_ESTABLISHMENTS_PATH")
    or str(REPO_ROOT / "stratford_establishments.json")
)
RAW_DIR = (
    os.environ.get("TRIPADVISOR_RAW_DIR")
    or str(REPO_ROOT / "data" / "raw" / "tripadvisor")
)
CACHE_DIR = (
    os.environ.get("TRIPADVISOR_CACHE_DIR")
    or str(REPO_ROOT / "data" / "cache")
)
URL_CACHE_PATH = str(Path(CACHE_DIR) / "tripadvisor_url_cache.json")

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
APIFY_ACTOR = os.environ.get("APIFY_ACTOR") or "scrapapi/tripadvisor-review-scraper"
# Pre-stage search actor. scrapapi/tripadvisor-review-scraper only ingests
# already-resolved TripAdvisor /Restaurant_Review-/Hotel_Review- URLs
# (proven empirically on run #8: feeding it a TripAdvisor Search URL
# returned 0 raw items per venue). We resolve each venue name to a
# restaurant URL via a cheap search actor first and cache the mapping.
APIFY_SEARCH_ACTOR = (
    os.environ.get("APIFY_SEARCH_ACTOR")
    or "getdataforme/tripadvisor-places-search-scraper"
)
LOCATION = "Stratford-upon-Avon"
MAX_REVIEWS = int(os.environ.get("MAX_REVIEWS") or "5")
MATCH_MIN_SCORE = float(os.environ.get("MATCH_MIN_SCORE") or "0.55")
COORD_TOLERANCE_M = 200.0
# Optional dry-run limit wired from the workflow's dispatch input.
# 0 / unset / negative ⇒ no limit; >0 ⇒ process only the first N venues.
DRY_RUN_LIMIT = int(os.environ.get("DRY_RUN_LIMIT") or "0")

# Matches a real TripAdvisor review/property URL (vs a Search URL).
# Used to validate search-actor output and to assert the review-scraper
# payload contains resolvable URLs (see tests/).
TA_REVIEW_URL_RE = re.compile(
    r"/(Restaurant_Review|Hotel_Review|Attraction_Review)-", re.IGNORECASE)


def build_apify_input(actor: str, query: str, max_places: int,
                       max_reviews: int,
                       resolved_urls: list | None = None) -> dict:
    """Build the Apify actor input payload for `query`, branching by actor.

    TripAdvisor Apify actors do not share a common input schema, so the
    shape has to be chosen per actor. Supporting multiple actors from one
    switch statement means we can swap actors via the APIFY_ACTOR env var
    without editing this script.

    Known actors:

      * `scrapapi/tripadvisor-review-scraper` — this is a REVIEW scraper.
        It ingests already-resolved TripAdvisor `/Restaurant_Review-` /
        `/Hotel_Review-` URLs and emits reviews. It does NOT resolve
        venue names itself: feeding it a TripAdvisor Search URL returns
        0 raw items (proven empirically on run #8 — the actor visits
        the Search page, finds nothing review-shaped, and exits clean).
        The surrounding pipeline resolves names to URLs via a search
        actor first (see resolve_tripadvisor_url / APIFY_SEARCH_ACTOR),
        and passes the resolved URLs in via `resolved_urls`.

        `startUrls` shape: `array<string>` per the actor's schema (NOT
        `array<{url: string}>` like apify/web-scraper). Sending dicts
        yields "Field input.startUrls.0 must be string" on every call.

        `searchString` / `keywords` / `locationFullName` aliases are
        included as belt-and-braces — they're ignored by this actor
        today, but cost nothing and cover the case where a future
        schema change adds a built-in search mode.

      * `automation-lab/tripadvisor-scraper` — legacy keyword-based
        schema. Takes a list of arbitrary search queries and does
        discovery internally.
    """
    if actor.startswith("scrapapi/tripadvisor-review-scraper"):
        if resolved_urls:
            urls = [u for u in resolved_urls if isinstance(u, str) and u]
        else:
            # No resolved URL — this call is expected to return 0 items
            # against this specific actor, but we still send a valid
            # payload rather than skipping: the guard layer is what
            # catches the "zero raw items" case, and callers that know
            # they have no URL should not reach here.
            urls = [
                "https://www.tripadvisor.com/Search?q=" + quote_plus(query)
            ]
        return {
            "startUrls": urls,
            # searchString (singular) is the field name in some TripAdvisor
            # scrapers that DO support internal search. searchStrings
            # (plural) is the alias used by others. Including both plus
            # keywords / locationFullName is cheap belt-and-braces.
            "searchString": query,
            "searchStrings": [query],
            "keywords": [query],
            "locationFullName": query,
            "maxReviewsPerUrl": max_reviews,
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


def build_search_actor_input(actor: str, query: str,
                              max_items: int = 5) -> dict:
    """Build input payload for the URL-resolution search actor.

    Keeps the same branch-by-actor pattern as `build_apify_input`.

    `getdataforme/tripadvisor-places-search-scraper` — per run #10's
    validation error ("Field input.query is required") the actor's
    declared input field is `query` (singular), NOT `search`. We send
    `search` / `searchString` as belt-and-braces aliases in case a
    future minor schema change adds them, but `query` is the one the
    actor actually validates against.
    """
    if actor.startswith("getdataforme/tripadvisor-places-search-scraper"):
        return {
            "query": query,
            "search": query,
            "searchString": query,
            "maxItems": max_items,
            "locationFullName": query,
        }
    # Generic fallback covers search actors that follow the more common
    # apify convention.
    return {
        "query": query,
        "searchQueries": [query],
        "search": query,
        "searchString": query,
        "maxItems": max_items,
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

    Accepts both normalised candidates (from normalise_apify_items: `name`,
    `latitude`, `longitude`) and raw Apify items (`title`, `lat`, `lng`);
    the normalised keys take precedence.
    """
    name = candidate.get("name") or candidate.get("title") or ""
    sim = fuzzy_score(target_name, name)

    c_lat = (candidate.get("latitude")
             or candidate.get("lat"))
    c_lon = (candidate.get("longitude")
             or candidate.get("lng")
             or candidate.get("lon"))
    if None in (target_lat, target_lon, c_lat, c_lon):
        return sim
    try:
        d = haversine_m(target_lat, target_lon, float(c_lat), float(c_lon))
    except (TypeError, ValueError):
        return sim
    # Proximity score: 1.0 at 0m, 0 at 1000m, linear in between
    prox = max(0.0, 1.0 - min(d, 1000.0) / 1000.0)
    return 0.7 * sim + 0.3 * prox


def _first(d, *keys, default=None):
    """Return the first present, non-empty value from `d` for the given keys."""
    if not isinstance(d, dict):
        return default
    for k in keys:
        v = d.get(k)
        if v is not None and v != "":
            return v
    return default


def _place_container(item):
    """Return the dict that actually carries the restaurant metadata.

    scrapapi/tripadvisor-review-scraper emits one Apify item per REVIEW,
    with restaurant-level metadata nested under `placeInfo` (sometimes
    `place`, `location`, or `restaurant` depending on actor version).
    Legacy place-scraper actors emit each place at the top level. We
    unwrap the nested container when present so downstream code can
    treat every candidate uniformly.
    """
    if not isinstance(item, dict):
        return {}
    for key in ("placeInfo", "place", "location", "restaurant"):
        sub = item.get(key)
        if isinstance(sub, dict) and sub:
            return sub
    return item


def _looks_like_review(item):
    """Heuristic: top-level review-text fields plus a place sub-container."""
    if not isinstance(item, dict):
        return False
    has_review_text = any(
        k in item for k in ("text", "reviewBody", "title", "publishedDate")
    )
    has_place_sub = any(
        isinstance(item.get(k), dict) for k in
        ("placeInfo", "place", "location", "restaurant")
    )
    return has_review_text and has_place_sub


def normalise_apify_items(raw_items):
    """Fold Apify actor output into a list of per-place normalised dicts.

    Two input shapes are handled:

      1. Review-shaped items (scrapapi/tripadvisor-review-scraper):
         one item per review with a nested `placeInfo` subdict.
         We group by (url | locationId | name) so many reviews of the
         same place fold into one candidate, and we collect the review
         texts into that candidate's `reviews` list.

      2. Place-shaped items (legacy / automation-lab):
         one item per place with metadata at the top level. Passes
         through with the same normalised key-set.

    Normalised keys (consistent for downstream matching / extraction):
        name, url, rating, review_count, latitude, longitude,
        cuisines, price_range, ranking, reviews (list of
        {text, rating, date}).
    """
    grouped = {}
    for item in raw_items:
        place = _place_container(item)
        if not place:
            continue
        url = _first(place, "url", "webUrl", "tripadvisor_url")
        loc_id = _first(place, "locationId", "location_id", "id")
        name = _first(place, "name", "title")
        key = url or (str(loc_id) if loc_id else None) or name
        if not key:
            continue
        if key not in grouped:
            grouped[key] = {
                "name": name,
                "url": url,
                "rating": _first(place, "rating", "averageRating"),
                "review_count": _first(
                    place, "numberOfReviews", "reviewCount", "reviewsCount"),
                "latitude": _first(place, "latitude", "lat"),
                "longitude": _first(place, "longitude", "lng", "lon"),
                "cuisines": _first(place, "cuisines", "cuisine") or [],
                "price_range": _first(place, "priceRange", "priceLevel"),
                "ranking": _first(place, "ranking", "rankingPosition"),
                "reviews": [],
            }
        # Review-shaped item: append text to this place's reviews list.
        if _looks_like_review(item):
            rev_text = _first(item, "text", "reviewBody")
            if rev_text:
                grouped[key]["reviews"].append({
                    "text": str(rev_text)[:500],
                    "rating": _first(item, "rating", "ratingValue"),
                    "date": _first(
                        item, "publishedDate", "createdDate", "date",
                        default=""),
                })
        # Place-shaped item that carries a `reviews` array inline:
        # merge those reviews too.
        inline_reviews = item.get("reviews")
        if isinstance(inline_reviews, list) and not _looks_like_review(item):
            for rev in inline_reviews:
                if not isinstance(rev, dict):
                    continue
                rev_text = _first(rev, "text", "reviewBody")
                if not rev_text:
                    continue
                grouped[key]["reviews"].append({
                    "text": str(rev_text)[:500],
                    "rating": _first(rev, "rating", "ratingValue"),
                    "date": _first(
                        rev, "publishedDate", "createdDate", "date",
                        default=""),
                })
    return list(grouped.values())


def search_apify(query, token, max_places=1, max_reviews=5,
                  resolved_urls=None):
    """
    Run the Apify TripAdvisor REVIEW scraper for a single query.

    `resolved_urls` (list[str] | None) is the output of the pre-stage
    URL-resolution search actor. When provided, those URLs are passed
    verbatim to the review actor — which is the only shape the
    `scrapapi/tripadvisor-review-scraper` actor will actually act on
    (see build_apify_input docstring).

    Returns list of normalised per-place dicts (see normalise_apify_items).
    """
    try:
        from apify_client import ApifyClient
    except ImportError:
        print("ERROR: apify-client not installed. Run: pip install apify-client")
        sys.exit(1)

    client = ApifyClient(token)

    run_input = build_apify_input(
        APIFY_ACTOR, query, max_places, max_reviews,
        resolved_urls=resolved_urls)

    try:
        run = client.actor(APIFY_ACTOR).call(
            run_input=run_input,
            timeout_secs=120,
        )
        raw_items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        if not raw_items:
            print(f"    Apify actor returned 0 raw items")
            return []
        places = normalise_apify_items(raw_items)
        print(
            f"    Apify actor returned {len(raw_items)} raw items "
            f"-> {len(places)} normalised place(s)"
        )
        return places
    except Exception as e:
        print(f"    Apify error: {e}")
        return []


def extract_ta_data(place, original_name, target_lat=None,
                     target_lon=None):
    """
    Extract structured TripAdvisor data from a NORMALISED place dict
    (as emitted by normalise_apify_items).

    Returns (entry_dict, combined_match_score) or (None, score) if the
    candidate does not clear `MATCH_MIN_SCORE`.
    """
    entry = {}

    name = place.get("name") or ""
    match = combined_match_score(original_name, target_lat, target_lon, place)
    if match < MATCH_MIN_SCORE:
        return None, match

    entry["ta_name"] = name
    entry["match_score"] = round(match, 2)

    # Rating
    rating = place.get("rating")
    if rating is not None and rating != "":
        try:
            entry["ta"] = round(float(rating), 1)
        except (ValueError, TypeError):
            pass

    # Review count
    rc = place.get("review_count")
    if rc is not None and rc != "":
        try:
            entry["trc"] = int(rc)
        except (ValueError, TypeError):
            pass

    # URL
    url = place.get("url")
    if url:
        entry["ta_url"] = url

    # Ranking
    ranking = place.get("ranking")
    if ranking:
        entry["ta_ranking"] = str(ranking)

    # Cuisine tags
    cuisines = place.get("cuisines")
    if cuisines:
        if isinstance(cuisines, list):
            entry["ta_cuisines"] = [
                c.get("name", c) if isinstance(c, dict) else str(c)
                for c in cuisines
            ]
        elif isinstance(cuisines, str):
            entry["ta_cuisines"] = [c.strip() for c in cuisines.split(",")]

    # Price range
    price = place.get("price_range")
    if price:
        entry["ta_price"] = str(price)

    # Reviews (up to MAX_REVIEWS) — already normalised by
    # normalise_apify_items into {text, rating, date} dicts.
    reviews = place.get("reviews") or []
    extracted = []
    for rev in reviews[:MAX_REVIEWS]:
        if not isinstance(rev, dict):
            continue
        text = rev.get("text")
        if not text:
            continue
        r = {"text": str(text)[:500], "date": rev.get("date") or ""}
        r_rating = rev.get("rating")
        if r_rating is not None:
            try:
                r["rating"] = int(r_rating)
            except (ValueError, TypeError):
                pass
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


def _count_raw_files():
    """Count .json files currently on disk under RAW_DIR."""
    if not os.path.isdir(RAW_DIR):
        return 0
    return sum(1 for f in os.listdir(RAW_DIR) if f.endswith(".json"))


def _load_url_cache():
    """Read data/cache/tripadvisor_url_cache.json if present."""
    if not os.path.exists(URL_CACHE_PATH):
        return {}
    try:
        with open(URL_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_url_cache(cache):
    """Persist the URL cache. Safe to call after every venue so a
    partially-run job doesn't waste credits on a re-run."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(URL_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False, sort_keys=True)


def _extract_ta_url_candidates(item):
    """Pull every plausible TA URL out of a search-actor item."""
    urls = []
    if not isinstance(item, dict):
        return urls
    for key in ("url", "webUrl", "tripadvisor_url", "link", "href"):
        v = item.get(key)
        if isinstance(v, str) and v:
            urls.append(v)
    place = _place_container(item)
    if place is not item and isinstance(place, dict):
        for key in ("url", "webUrl", "tripadvisor_url", "link", "href"):
            v = place.get(key)
            if isinstance(v, str) and v:
                urls.append(v)
    return urls


def resolve_tripadvisor_url(query: str, token: str, cache: dict):
    """Resolve a venue name+location to a TripAdvisor place URL.

    Two-stage pipeline stage 1: query a lightweight TripAdvisor places
    search actor and take the first result whose URL matches a real
    review page (TA_REVIEW_URL_RE). Results are cached in
    `tripadvisor_url_cache.json` keyed by the lowercased query, so
    re-runs only burn search-actor credits on new venues.

    Returns (url, resolved_name). Both None if nothing matched. Cache
    entries with `url: null` are stored too so repeat failures don't
    re-query the search actor.
    """
    cache_key = query.lower().strip()
    if cache_key in cache:
        hit = cache[cache_key]
        if isinstance(hit, dict):
            return hit.get("url"), hit.get("name")

    try:
        from apify_client import ApifyClient
    except ImportError:
        print("ERROR: apify-client not installed")
        return None, None

    client = ApifyClient(token)
    run_input = build_search_actor_input(APIFY_SEARCH_ACTOR, query)

    try:
        run = client.actor(APIFY_SEARCH_ACTOR).call(
            run_input=run_input, timeout_secs=120)
        items = list(
            client.dataset(run["defaultDatasetId"]).iterate_items())
    except Exception as e:
        print(f"    Search actor error: {e}")
        # Do NOT cache transient errors — next run should retry.
        return None, None

    print(f"    Search actor returned {len(items)} item(s)")

    url = None
    name = None
    for item in items:
        for candidate in _extract_ta_url_candidates(item):
            if TA_REVIEW_URL_RE.search(candidate):
                url = candidate
                place = _place_container(item)
                name = (
                    (place.get("name") if isinstance(place, dict) else None)
                    or (item.get("name") if isinstance(item, dict) else None)
                    or (item.get("title") if isinstance(item, dict) else None)
                )
                break
        if url:
            break

    cache[cache_key] = {
        "url": url,
        "name": name,
        "resolved_at": datetime.datetime.utcnow().strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
    }
    return url, name


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
    # Track how many raw files existed before this run so the hard-fail
    # guard can use "new raw files written" as an independent signal. The
    # `matched` counter alone was insufficient on b705c2d (the guard
    # appeared to be bypassed for reasons we cannot fully reconstruct);
    # this second signal plus the try/finally below makes the failure
    # mode impossible to miss.
    pre_raw_count = _count_raw_files()
    # Track if all candidates fell BELOW MATCH_MIN_SCORE so we can
    # log a more informative diagnostic at the end of the run.
    under_threshold = 0
    # Count how many venues were dropped at stage 1 (URL resolution)
    # vs stage 2 (review scrape / matcher). Makes post-mortems easier.
    unresolved_url = 0
    # Load the persistent name-to-URL cache. Search-actor calls are the
    # expensive bit; caching means a rerun only pays for new venues.
    url_cache = _load_url_cache()
    print(f"URL cache: {len(url_cache)} entries loaded from "
          f"{os.path.relpath(URL_CACHE_PATH, REPO_ROOT)}")
    print(f"Using search actor: {APIFY_SEARCH_ACTOR}")

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
        print(f"  [{i}/{total}] Resolving: {query}")

        try:
            # Stage 1 — name -> TripAdvisor URL via the search actor.
            # The result is cached; repeat calls hit the cache, not
            # the actor, so re-dispatches are cheap.
            resolved_url, resolved_name = resolve_tripadvisor_url(
                query, APIFY_TOKEN, url_cache)
            # Persist cache after every venue so a mid-run failure
            # doesn't waste the stage-1 credits already spent.
            _save_url_cache(url_cache)

            if not resolved_url:
                no_match += 1
                unresolved_url += 1
                print(f"    No review URL resolved for {name!r}")
                continue

            print(f"    Resolved -> {resolved_url}")

            # Stage 2 — review scrape against the resolved URL.
            results = search_apify(
                query, APIFY_TOKEN, max_places=3, max_reviews=MAX_REVIEWS,
                resolved_urls=[resolved_url])

            if not results:
                no_match += 1
                print(f"    Review actor returned no usable items for "
                      f"{resolved_url}")
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
                under_threshold += 1
                print(
                    f"    No fuzzy match (best={best_score:.2f}, "
                    f"threshold={MATCH_MIN_SCORE})"
                )

        except Exception as e:
            errors += 1
            print(f"    Error: {e}")

        # Small delay between Apify calls
        time.sleep(1)

    # Summary counters. Attempted = venues that actually reached the actor
    # (i.e. weren't resume-skipped and weren't filtered by should_search).
    attempted = total - skipped
    post_raw_count = _count_raw_files()
    new_raw_files = max(0, post_raw_count - pre_raw_count)

    # Final cache save catches any last-venue updates.
    _save_url_cache(url_cache)

    print(f"\nDone. Total: {total}")
    print(
        f"  Matched: {matched}, No match: {no_match} "
        f"(of which {unresolved_url} had no URL resolved, "
        f"{under_threshold} below MATCH_MIN_SCORE), "
        f"Skipped: {skipped}, Errors: {errors}"
    )
    print(
        f"  Attempted: {attempted}, "
        f"new raw files written this run: {new_raw_files} "
        f"(pre={pre_raw_count}, post={post_raw_count})"
    )
    print(f"  URL cache now has {len(url_cache)} entries")
    print(f"  Raw files under: {RAW_DIR}")
    print(f"Next step: run .github/scripts/consolidate_tripadvisor.py "
          f"and .github/scripts/merge_tripadvisor.py")

    # Hard-fail guard, strengthened after b705c2d. Two independent signals,
    # both must clear for the run to count as a success:
    #
    #   (a) `matched == 0` when we actually attempted any venue. The actor
    #       was fed a payload it didn't understand, the authenticated
    #       account is rate-limited / out of credits, or the matcher is
    #       looking in the wrong nested keys. Either way, zero matches
    #       over N>0 attempted venues is a pipeline failure — never a
    #       silent success.
    #
    #   (b) `new_raw_files == 0` when we attempted any venue. Even if
    #       something bumped `matched` (stale counter, partial write,
    #       etc.), the on-disk artefact is the ground truth: if nothing
    #       new landed in data/raw/tripadvisor/, the collector produced
    #       nothing.
    #
    # Previously this check was a single-signal post-hoc `if total > 0
    # and matched == 0:` — on b705c2d the run committed an empty result
    # without the guard firing. The two-signal check below is designed
    # so at least one signal must catch the failure even if the other
    # is spoofed.
    failure_reasons = []
    if attempted > 0 and matched == 0:
        failure_reasons.append(
            f"matched == 0 over {attempted} attempted venues "
            f"(no_match={no_match}, errors={errors})"
        )
    if attempted > 0 and new_raw_files == 0:
        failure_reasons.append(
            f"no new raw files written this run "
            f"(pre={pre_raw_count}, post={post_raw_count})"
        )

    if failure_reasons:
        sys.stderr.write(
            "\n::error::Apify TripAdvisor collection failed. "
            + "; ".join(failure_reasons)
            + ". Likely causes: (1) the search actor resolved no URLs "
              "for these venues — check APIFY_SEARCH_ACTOR and the "
              f"cache at {os.path.relpath(URL_CACHE_PATH, REPO_ROOT)}; "
              "(2) the review actor's response shape changed and "
              "normalise_apify_items now sees nothing; "
              "(3) the authenticated Apify account is rate-limited. "
              "See docs/DayDine-TripAdvisor-Strategy-Decision.md.\n"
        )
        # raise SystemExit is slightly more robust than sys.exit: it is an
        # exception and therefore propagates through a try/except Exception
        # sibling (there isn't one here, but future edits may add one).
        raise SystemExit(1)


if __name__ == "__main__":
    main()
