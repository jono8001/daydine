#!/usr/bin/env python3
"""Collect TripAdvisor reviews via Apify scrapapi/tripadvisor-review-scraper actor.

Uses coordinates (lat/lon) from stratford_establishments.json for better
venue matching than the broken name-only approach in collect_tripadvisor_apify.py.

Usage:
    python .github/scripts/collect_tripadvisor_reviews_apify.py [--limit N]

Environment:
    APIFY_TOKEN  — Apify API token (required)
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
# Use scrapapi actor for review scraping (replaces broken automation-lab actor)
SEARCH_ACTOR_ID = "maxcopell/tripadvisor"
REVIEW_ACTOR_ID = "scrapapi/tripadvisor-review-scraper"
APIFY_BASE = "https://api.apify.com/v2"

REPO_ROOT = Path(__file__).resolve().parents[2]
ESTABLISHMENTS_FILE = REPO_ROOT / "stratford_establishments.json"
OUTPUT_DIR = REPO_ROOT / "data" / "raw" / "tripadvisor"

MAX_REVIEWS = 100
POLL_INTERVAL = 10
MAX_WAIT = 600
MAX_RETRIES = 2
MATCH_DISTANCE_M = 500  # Match radius in metres
MATCH_NAME_THRESHOLD = 0.4  # Fuzzy name match threshold


def slugify(name: str) -> str:
    """Convert a restaurant name to a filesystem-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    return slug[:80]


def normalise_name(name: str) -> str:
    """Normalise a venue name for fuzzy comparison."""
    name = name.lower().strip()
    # Remove common suffixes
    for suffix in ["ltd", "limited", "plc", "llp", "restaurant", "cafe", "bar", "pub"]:
        name = re.sub(rf"\b{suffix}\b", "", name)
    name = re.sub(r"[^a-z0-9\s]", "", name)
    return " ".join(name.split())


def fuzzy_score(a: str, b: str) -> float:
    """Return similarity ratio between two normalised names."""
    return SequenceMatcher(None, normalise_name(a), normalise_name(b)).ratio()


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate distance in metres between two coordinates."""
    import math
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load_establishments() -> dict:
    with open(ESTABLISHMENTS_FILE) as f:
        return json.load(f)


def should_collect(est: dict) -> bool:
    """Return True if this establishment is worth collecting TA reviews for."""
    name = est.get("n", "")
    if not name:
        return False
    blacklist = [
        "slimming world", "football club", "aston martin",
        "village hall", "scout", "nursery", "school",
    ]
    name_lower = name.lower()
    return not any(term in name_lower for term in blacklist)


def run_apify_actor(actor_id: str, payload: dict, timeout: int = 120, memory: int = 1024) -> str | None:
    """Start an Apify actor run. Returns run ID or None."""
    headers = {"Authorization": f"Bearer {APIFY_TOKEN}"}
    url = f"{APIFY_BASE}/acts/{actor_id}/runs"
    try:
        resp = requests.post(
            url, headers=headers, json=payload,
            params={"timeout": timeout, "memory": memory},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("data", {}).get("id")
    except requests.RequestException as e:
        log.error("Failed to start %s: %s", actor_id, e)
        return None


def wait_for_run(run_id: str) -> dict | None:
    """Poll until actor run finishes."""
    headers = {"Authorization": f"Bearer {APIFY_TOKEN}"}
    url = f"{APIFY_BASE}/actor-runs/{run_id}"
    elapsed = 0
    while elapsed < MAX_WAIT:
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            status = data.get("status")
            if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                return data
        except requests.RequestException as e:
            log.warning("Poll error: %s", e)
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
    return None


def fetch_dataset(dataset_id: str) -> list:
    """Fetch items from an Apify dataset."""
    headers = {"Authorization": f"Bearer {APIFY_TOKEN}"}
    url = f"{APIFY_BASE}/datasets/{dataset_id}/items"
    try:
        resp = requests.get(url, headers=headers, params={"format": "json"}, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        log.error("Failed to fetch dataset: %s", e)
        return []


def search_tripadvisor(name: str, location: str) -> list:
    """Search TripAdvisor for a restaurant via maxcopell/tripadvisor actor."""
    payload = {
        "searchStrings": [f"{name} {location}"],
        "maxItems": 5,
        "includeReviews": False,
    }
    run_id = run_apify_actor(SEARCH_ACTOR_ID, payload)
    if not run_id:
        return []
    run_data = wait_for_run(run_id)
    if not run_data or run_data.get("status") != "SUCCEEDED":
        return []
    dataset_id = run_data.get("defaultDatasetId")
    if not dataset_id:
        return []
    return fetch_dataset(dataset_id)


def find_best_match(est: dict, ta_results: list) -> dict | None:
    """Find the best TripAdvisor match for an establishment using coordinates + name."""
    est_name = est.get("n", "")
    est_lat = est.get("lat")
    est_lon = est.get("lon")

    best = None
    best_score = 0

    for item in ta_results:
        ta_name = item.get("name", "")
        ta_lat = item.get("latitude") or item.get("lat")
        ta_lon = item.get("longitude") or item.get("lon")

        name_score = fuzzy_score(est_name, ta_name)

        # If we have coordinates for both, check distance
        if est_lat and est_lon and ta_lat and ta_lon:
            try:
                dist = haversine_m(float(est_lat), float(est_lon), float(ta_lat), float(ta_lon))
                if dist > MATCH_DISTANCE_M:
                    continue  # Too far away
                # Boost score for close matches
                distance_bonus = max(0, 0.3 * (1 - dist / MATCH_DISTANCE_M))
                combined_score = name_score + distance_bonus
            except (ValueError, TypeError):
                combined_score = name_score
        else:
            combined_score = name_score

        if combined_score > best_score and name_score >= MATCH_NAME_THRESHOLD:
            best_score = combined_score
            best = item

    return best


def collect_reviews_for_location(ta_url: str) -> list:
    """Collect reviews for a TripAdvisor location URL."""
    payload = {
        "startUrls": [{"url": ta_url}],
        "maxItemsPerQuery": MAX_REVIEWS,
        "reviewsLanguages": ["en"],
    }
    run_id = run_apify_actor(REVIEW_ACTOR_ID, payload, timeout=180)
    if not run_id:
        return []
    run_data = wait_for_run(run_id)
    if not run_data or run_data.get("status") != "SUCCEEDED":
        return []
    dataset_id = run_data.get("defaultDatasetId")
    if not dataset_id:
        return []
    return fetch_dataset(dataset_id)


def validate_date(date_str: str, scrape_date: str) -> dict:
    """Validate a review date. Flag future dates."""
    result = {"original": date_str, "valid": True, "flagged": False}
    if not date_str:
        result["valid"] = False
        return result
    try:
        review_dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        scrape_dt = datetime.fromisoformat(scrape_date.replace("Z", "+00:00"))
        if review_dt > scrape_dt:
            result["flagged"] = True
            result["flag_reason"] = "future_date"
    except (ValueError, TypeError):
        pass
    return result


def normalise_review(raw_review: dict, collected_at: str) -> dict:
    """Normalise a TripAdvisor review to standard format."""
    date_str = raw_review.get("publishedDate") or raw_review.get("publishedAt", "")
    date_validation = validate_date(date_str, collected_at)

    return {
        "text": raw_review.get("text", ""),
        "title": raw_review.get("title", ""),
        "rating": raw_review.get("rating"),
        "date": date_str,
        "date_validation": date_validation,
        "reviewer_name": raw_review.get("username") or raw_review.get("user", {}).get("username", ""),
        "reviewer_location": raw_review.get("userLocation", ""),
        "reviewer_contributions": raw_review.get("userContributions"),
        "review_id": raw_review.get("id", ""),
        "review_url": raw_review.get("url", ""),
        "trip_type": raw_review.get("tripType", ""),
        "travel_date": raw_review.get("travelDate", ""),
        "helpful_votes": raw_review.get("helpfulVotes", 0),
        "owner_response": raw_review.get("ownerResponse", ""),
        "owner_response_date": raw_review.get("ownerResponseDate", ""),
        "language": raw_review.get("language", ""),
        "sub_ratings": raw_review.get("subRatings") or {},
        "source": "tripadvisor",
    }


def collect_for_restaurant(fhrsid: str, est: dict) -> dict | None:
    """Collect TripAdvisor reviews for a single restaurant."""
    name = est.get("n", "")
    postcode = est.get("pc", "")
    location = f"Stratford-upon-Avon {postcode}"

    log.info("Searching TripAdvisor for: %s (FHRSID %s)", name, fhrsid)

    for attempt in range(MAX_RETRIES + 1):
        # Step 1: Search for the venue on TripAdvisor
        ta_results = search_tripadvisor(name, location)
        if not ta_results:
            log.warning("  No TripAdvisor search results for %s", name)
            if attempt < MAX_RETRIES:
                time.sleep(5)
                continue
            return None

        # Step 2: Find best coordinate + name match
        match = find_best_match(est, ta_results)
        if not match:
            log.warning("  No match found for %s (best name scores below threshold)", name)
            return None

        ta_url = match.get("url") or match.get("webUrl", "")
        ta_name = match.get("name", "")
        log.info("  Matched: %s -> %s", name, ta_name)

        if not ta_url:
            log.warning("  No URL for matched venue %s", ta_name)
            return None

        # Step 3: Collect reviews for the matched venue
        raw_reviews = collect_reviews_for_location(ta_url)
        if not raw_reviews:
            log.warning("  No reviews returned for %s", ta_name)
            if attempt < MAX_RETRIES:
                time.sleep(5)
                continue
            return None

        collected_at = datetime.now(timezone.utc).isoformat()
        reviews = [normalise_review(r, collected_at) for r in raw_reviews]

        # Count flagged dates
        flagged = sum(1 for r in reviews if r.get("date_validation", {}).get("flagged"))
        if flagged:
            log.warning("  %d reviews with future dates flagged", flagged)

        result = {
            "fhrsid": fhrsid,
            "name": name,
            "ta_name": ta_name,
            "ta_url": ta_url,
            "ta_location_id": match.get("locationId") or match.get("id", ""),
            "ta_rating": match.get("rating") or match.get("averageRating"),
            "ta_review_count": match.get("reviewsCount") or match.get("numberOfReviews"),
            "match_score": fuzzy_score(name, ta_name),
            "reviews": reviews,
            "collected_at": collected_at,
            "flagged_dates": flagged,
        }

        log.info("  -> %d reviews collected (%d flagged dates)", len(reviews), flagged)
        return result

    return None


def save_result(fhrsid: str, est: dict, result: dict, today: str):
    """Save result to data/raw/tripadvisor/{slug}_{date}.json."""
    slug = slugify(est.get("n", fhrsid))
    output_path = OUTPUT_DIR / f"{slug}_{today}.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    log.info("  -> Saved to %s", output_path.name)


def main():
    parser = argparse.ArgumentParser(description="Collect TripAdvisor reviews via Apify")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of restaurants (0=all)")
    args = parser.parse_args()

    if not APIFY_TOKEN:
        log.error("APIFY_TOKEN environment variable is required")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    establishments = load_establishments()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    candidates = {
        fhrsid: est for fhrsid, est in establishments.items()
        if should_collect(est)
    }

    if args.limit > 0:
        candidate_list = list(candidates.items())[:args.limit]
        candidates = dict(candidate_list)

    log.info("Processing %d restaurants", len(candidates))

    stats = {"total": len(candidates), "matched": 0, "no_match": 0, "reviews": 0, "flagged_dates": 0}

    for fhrsid, est in candidates.items():
        result = collect_for_restaurant(fhrsid, est)
        if result and result.get("reviews"):
            save_result(fhrsid, est, result, today)
            stats["matched"] += 1
            stats["reviews"] += len(result["reviews"])
            stats["flagged_dates"] += result.get("flagged_dates", 0)
        else:
            stats["no_match"] += 1
        time.sleep(3)  # Rate limit between restaurants

    log.info("=" * 60)
    log.info("TripAdvisor collection complete:")
    log.info("  Restaurants processed: %d", stats["total"])
    log.info("  Successfully matched: %d", stats["matched"])
    log.info("  No match: %d", stats["no_match"])
    log.info("  Total reviews: %d", stats["reviews"])
    log.info("  Flagged future dates: %d", stats["flagged_dates"])
    log.info("  Match rate: %.1f%%", 100 * stats["matched"] / max(stats["total"], 1))
    log.info("=" * 60)


if __name__ == "__main__":
    main()
