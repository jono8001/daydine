#!/usr/bin/env python3
"""
collect_tripadvisor_apify.py — Collect TripAdvisor data via Apify scraper.

Uses the Apify TripAdvisor scraper (automation-lab/tripadvisor-scraper)
to search for each restaurant and extract rating, review count, ranking,
cuisine tags, price range, and up to 5 review texts.

Cost: ~$0.003/review, ~$0.50 for 200 restaurants with 5 reviews each.

Requires:
    pip install apify-client
    APIFY_TOKEN environment variable

Reads:  stratford_establishments.json
Writes: stratford_tripadvisor.json
"""

import difflib
import json
import os
import re
import sys
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
INPUT_PATH = os.path.join(REPO_ROOT, "stratford_establishments.json")
OUTPUT_PATH = os.path.join(REPO_ROOT, "stratford_tripadvisor.json")

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
LOCATION = "Stratford-upon-Avon"
MAX_REVIEWS = 5


def normalise_name(name):
    name = name.lower().strip()
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def fuzzy_score(a, b):
    return difflib.SequenceMatcher(None, normalise_name(a), normalise_name(b)).ratio()


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

    run_input = {
        "searchQueries": [query],
        "placeType": "restaurant",
        "maxPlacesPerQuery": max_places,
        "maxReviewsPerPlace": max_reviews,
        "language": "en",
    }

    try:
        run = client.actor("automation-lab/tripadvisor-scraper").call(
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


def extract_ta_data(apify_result, original_name):
    """
    Extract structured TripAdvisor data from an Apify result.
    Returns dict with ta, trc, ta_url, ta_cuisines, ta_price, ta_reviews, etc.
    """
    entry = {}

    name = apify_result.get("name", "")
    match = fuzzy_score(original_name, name)
    if match < 0.5:
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


def main():
    if not APIFY_TOKEN:
        print("ERROR: APIFY_TOKEN not set")
        print("Add it as a GitHub secret or set in environment:")
        print("  export APIFY_TOKEN=apify_api_xxxxx")
        sys.exit(1)

    if not os.path.exists(INPUT_PATH):
        print(f"ERROR: {INPUT_PATH} not found")
        sys.exit(1)

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        establishments = json.load(f)
    print(f"Loaded {len(establishments)} establishments")

    # Resume support — only keep records that have actual TA data
    ta_data = {}
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)
        # Only keep successful results (have a ta rating), discard
        # _skipped/_no_match/_error from previous failed runs
        for k, v in existing.items():
            if v.get("ta") is not None:
                ta_data[k] = v
        print(f"Loaded {len(ta_data)} existing records with TA data (resuming)")

    matched = 0
    no_match = 0
    skipped = 0
    errors = 0
    total = len(establishments)

    for i, (key, record) in enumerate(establishments.items(), 1):
        name = record.get("n", "")

        # Skip if already processed
        if key in ta_data:
            skipped += 1
            continue

        if not name or not should_search(record):
            ta_data[key] = {"_skipped": True}
            skipped += 1
            continue

        query = f"{name} {LOCATION}"
        print(f"  [{i}/{total}] Searching: {query}")

        try:
            results = search_apify(query, APIFY_TOKEN,
                                   max_places=1, max_reviews=MAX_REVIEWS)

            if not results:
                ta_data[key] = {"_no_match": True}
                no_match += 1
                print(f"    No results")
                continue

            # Take best match
            best_entry = None
            best_score = 0
            for result in results:
                entry, score = extract_ta_data(result, name)
                if entry and score > best_score:
                    best_entry = entry
                    best_score = score

            if best_entry:
                ta_data[key] = best_entry
                matched += 1
                ta_r = best_entry.get("ta", "-")
                trc = best_entry.get("trc", 0)
                revs = len(best_entry.get("ta_reviews", []))
                print(f"    Match! rating={ta_r} reviews={trc} texts={revs} score={best_score:.2f}")
            else:
                ta_data[key] = {"_no_match": True, "_best_score": round(best_score, 2)}
                no_match += 1
                print(f"    No fuzzy match (best={best_score:.2f})")

        except Exception as e:
            errors += 1
            ta_data[key] = {"_error": str(e)[:200]}
            print(f"    Error: {e}")

        # Save progress every 20 records
        if i % 20 == 0:
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(ta_data, f, indent=2, ensure_ascii=False)
            print(f"    ... saved progress ({len(ta_data)} records)")

        # Small delay between Apify calls
        time.sleep(1)

    # Final save
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(ta_data, f, indent=2, ensure_ascii=False)

    valid = sum(1 for v in ta_data.values() if v.get("ta") is not None)
    with_reviews = sum(1 for v in ta_data.values() if v.get("ta_reviews"))
    print(f"\nDone. Total: {total}")
    print(f"  Matched: {matched}, No match: {no_match}, Skipped: {skipped}, Errors: {errors}")
    print(f"  With TA rating: {valid}")
    print(f"  With review text: {with_reviews}")
    print(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
