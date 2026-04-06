#!/usr/bin/env python3
"""Collect Google reviews via Apify compass/crawler-google-places actor.

Reads restaurants from stratford_establishments.json, runs the Apify actor
to collect reviews for each, and saves raw output per restaurant to
data/raw/google/{slug}_{YYYY-MM-DD}.json.

Usage:
    python .github/scripts/collect_google_reviews_apify.py [--limit N]

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
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
ACTOR_ID = "compass/crawler-google-places"
APIFY_RUN_URL = f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs"
APIFY_DATASET_URL = "https://api.apify.com/v2/datasets"

REPO_ROOT = Path(__file__).resolve().parents[2]
ESTABLISHMENTS_FILE = REPO_ROOT / "stratford_establishments.json"
OUTPUT_DIR = REPO_ROOT / "data" / "raw" / "google"

MAX_REVIEWS = 100
POLL_INTERVAL = 10  # seconds
MAX_WAIT = 600  # 10 minutes per actor run
MAX_RETRIES = 2


def slugify(name: str) -> str:
    """Convert a restaurant name to a filesystem-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    return slug[:80]


def load_establishments() -> dict:
    """Load and return establishments keyed by FHRSID."""
    with open(ESTABLISHMENTS_FILE) as f:
        return json.load(f)


def should_collect(est: dict) -> bool:
    """Return True if this establishment is a food venue worth collecting."""
    name = est.get("n", "")
    # Skip non-food blacklist
    blacklist = [
        "slimming world", "football club", "aston martin",
        "village hall", "scout", "nursery", "school",
    ]
    name_lower = name.lower()
    for term in blacklist:
        if term in name_lower:
            return False
    # Must have a Google Place ID or at least a name and postcode
    if not name:
        return False
    return True


def start_actor_run(search_query: str, max_reviews: int = MAX_REVIEWS) -> str | None:
    """Start an Apify actor run and return the run ID."""
    headers = {"Authorization": f"Bearer {APIFY_TOKEN}"}
    payload = {
        "searchStringsArray": [search_query],
        "maxCrawledPlacesPerSearch": 1,
        "maxReviews": max_reviews,
        "language": "en",
        "reviewsSort": "newest",
        "scrapeReviewerName": True,
        "scrapeReviewerId": True,
        "scrapeReviewerUrl": True,
        "scrapeReviewId": True,
        "scrapeReviewUrl": True,
        "scrapeResponseFromOwnerText": True,
    }
    try:
        resp = requests.post(
            APIFY_RUN_URL,
            headers=headers,
            json=payload,
            params={"timeout": 120, "memory": 1024},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("id")
    except requests.RequestException as e:
        log.error("Failed to start actor run for %r: %s", search_query, e)
        return None


def wait_for_run(run_id: str) -> dict | None:
    """Poll until the actor run finishes. Return run data or None."""
    headers = {"Authorization": f"Bearer {APIFY_TOKEN}"}
    url = f"https://api.apify.com/v2/actor-runs/{run_id}"
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
            log.warning("Poll error for run %s: %s", run_id, e)
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
    log.error("Run %s timed out after %ds", run_id, MAX_WAIT)
    return None


def fetch_dataset(dataset_id: str) -> list:
    """Fetch all items from an Apify dataset."""
    headers = {"Authorization": f"Bearer {APIFY_TOKEN}"}
    url = f"{APIFY_DATASET_URL}/{dataset_id}/items"
    try:
        resp = requests.get(url, headers=headers, params={"format": "json"}, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        log.error("Failed to fetch dataset %s: %s", dataset_id, e)
        return []


def extract_reviews(place_data: dict) -> list[dict]:
    """Extract normalised review records from Apify place result."""
    reviews = []
    for rev in place_data.get("reviews", []):
        review = {
            "text": rev.get("text") or rev.get("textTranslated", ""),
            "rating": rev.get("stars"),
            "date": rev.get("publishedAtDate") or rev.get("publishAt", ""),
            "reviewer_name": rev.get("name", ""),
            "reviewer_id": rev.get("reviewerId", ""),
            "review_id": rev.get("reviewId", ""),
            "review_url": rev.get("reviewUrl", ""),
            "is_local_guide": rev.get("isLocalGuide", False),
            "owner_response": rev.get("responseFromOwnerText", ""),
            "owner_response_date": rev.get("responseFromOwnerDate", ""),
            "review_photos": [p.get("photoUrl", "") for p in (rev.get("reviewImageUrls") or [])],
            "detailed_ratings": rev.get("reviewDetailedRating") or {},
            "source": "google",
        }
        reviews.append(review)
    return reviews


def collect_for_restaurant(fhrsid: str, est: dict) -> dict | None:
    """Collect Google reviews for a single restaurant. Returns result dict or None."""
    name = est.get("n", "")
    postcode = est.get("pc", "")
    search_query = f"{name} {postcode}"

    log.info("Collecting: %s (FHRSID %s)", name, fhrsid)

    for attempt in range(MAX_RETRIES + 1):
        run_id = start_actor_run(search_query)
        if not run_id:
            if attempt < MAX_RETRIES:
                log.warning("Retry %d/%d for %s", attempt + 1, MAX_RETRIES, name)
                time.sleep(5)
                continue
            return None

        run_data = wait_for_run(run_id)
        if not run_data:
            if attempt < MAX_RETRIES:
                log.warning("Retry %d/%d (timeout) for %s", attempt + 1, MAX_RETRIES, name)
                continue
            return None

        if run_data.get("status") != "SUCCEEDED":
            log.warning("Run %s status: %s for %s", run_id, run_data.get("status"), name)
            if attempt < MAX_RETRIES:
                time.sleep(5)
                continue
            return None

        dataset_id = run_data.get("defaultDatasetId")
        if not dataset_id:
            log.warning("No dataset for run %s", run_id)
            return None

        items = fetch_dataset(dataset_id)
        if not items:
            log.warning("No results for %s", name)
            return None

        # Take the first (best match) place result
        place = items[0]
        reviews = extract_reviews(place)

        result = {
            "fhrsid": fhrsid,
            "name": name,
            "google_place_id": place.get("placeId", ""),
            "google_rating": place.get("totalScore"),
            "google_review_count": place.get("reviewsCount"),
            "google_url": place.get("url", ""),
            "reviews": reviews,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "actor_run_id": run_id,
        }

        log.info("  -> %d reviews collected for %s", len(reviews), name)
        return result

    return None


def save_result(fhrsid: str, est: dict, result: dict, today: str):
    """Save collection result to data/raw/google/{slug}_{date}.json."""
    slug = slugify(est.get("n", fhrsid))
    output_path = OUTPUT_DIR / f"{slug}_{today}.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    log.info("  -> Saved to %s", output_path.name)


def main():
    parser = argparse.ArgumentParser(description="Collect Google reviews via Apify")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of restaurants to process (0=all)")
    args = parser.parse_args()

    if not APIFY_TOKEN:
        log.error("APIFY_TOKEN environment variable is required")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    establishments = load_establishments()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Filter to collectible establishments
    candidates = {
        fhrsid: est for fhrsid, est in establishments.items()
        if should_collect(est)
    }

    if args.limit > 0:
        candidate_list = list(candidates.items())[:args.limit]
        candidates = dict(candidate_list)

    log.info("Processing %d restaurants (of %d total)", len(candidates), len(establishments))

    stats = {"total": len(candidates), "collected": 0, "failed": 0, "reviews": 0}

    for fhrsid, est in candidates.items():
        result = collect_for_restaurant(fhrsid, est)
        if result and result.get("reviews"):
            save_result(fhrsid, est, result, today)
            stats["collected"] += 1
            stats["reviews"] += len(result["reviews"])
        else:
            stats["failed"] += 1
        # Rate limit: pause between restaurants
        time.sleep(2)

    log.info("=" * 60)
    log.info("Collection complete:")
    log.info("  Restaurants processed: %d", stats["total"])
    log.info("  Successfully collected: %d", stats["collected"])
    log.info("  Failed: %d", stats["failed"])
    log.info("  Total reviews: %d", stats["reviews"])
    log.info("=" * 60)


if __name__ == "__main__":
    main()
