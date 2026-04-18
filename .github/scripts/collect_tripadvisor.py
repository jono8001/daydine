#!/usr/bin/env python3
"""
collect_tripadvisor.py — LEGACY TripAdvisor HTML scraper (NON-VIABLE on
GitHub-hosted runners).

!!! DO NOT USE FOR REAL COLLECTION !!!

The HTML-scrape path against https://www.tripadvisor.co.uk/Search is
blocked by TripAdvisor's bot-protection layer when called from
GitHub-hosted runner IP ranges. Every search returns HTTP 403. The
script now fails fast via `SearchBlocked` + `sys.exit(7)` rather than
silently treating blocks as no-match, but it cannot produce real
TripAdvisor coverage.

Supported path:  `.github/scripts/collect_tripadvisor_apify.py` +
                 `.github/workflows/collect_tripadvisor_apify.yml`
                 (requires the `APIFY_TOKEN` secret).

See:  docs/DayDine-TripAdvisor-Blocker-Diagnosis.md
      docs/DayDine-TripAdvisor-Strategy-Decision.md

This script is retained so engineers can reproduce the 403 behaviour
on demand. The associated workflow (`collect_tripadvisor.yml`) is
gated behind a FORCE_LEGACY_TA_SCRAPER=true dispatch input.

Usage (diagnostic only):
    python .github/scripts/collect_tripadvisor.py

Requires:
    pip install requests beautifulsoup4

Reads:  stratford_establishments.json
Writes: stratford_tripadvisor.json
"""

import difflib
import json
import os
import random
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

INPUT_PATH = os.path.join(REPO_ROOT, "stratford_establishments.json")
OUTPUT_PATH = os.path.join(REPO_ROOT, "stratford_tripadvisor.json")

# TripAdvisor search URL for Stratford-upon-Avon restaurants
TA_SEARCH_URL = "https://www.tripadvisor.co.uk/Search"
TA_BASE = "https://www.tripadvisor.co.uk"

# Stratford-upon-Avon geo ID on TripAdvisor
TA_GEO_ID = "186368"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}

# Throttle: 2-3 seconds between requests
MIN_DELAY = 2.0
MAX_DELAY = 3.5

# Collection is treated as infrastructurally broken if at least this fraction
# of attempted searches return HTTP 403 / 429. The runner IP range is almost
# certainly on TripAdvisor's block list; failing honestly here stops the rest
# of the pipeline from committing a misleading "all no_match" dataset.
BLOCKED_RATIO_THRESHOLD = 0.5
# Minimum attempts before the threshold check kicks in — a single blocked
# lookup is not proof of blocking.
BLOCKED_MIN_ATTEMPTS = 20


class SearchBlocked(Exception):
    """TripAdvisor search endpoint returned an IP-blocking status (403/429)."""

    def __init__(self, message: str, status_code: int = 403) -> None:
        super().__init__(message)
        self.status_code = status_code


def normalise_name(name):
    """Normalise a restaurant name for comparison."""
    name = name.lower().strip()
    # Remove common suffixes
    for suffix in [" ltd", " limited", " plc", " restaurant", " cafe",
                   " bar", " grill", " kitchen", " bistro", " inn",
                   " hotel", " pub"]:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()
    # Remove punctuation
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def fuzzy_match(name1, name2, threshold=0.6):
    """Check if two names match using SequenceMatcher. Returns score 0-1."""
    n1 = normalise_name(name1)
    n2 = normalise_name(name2)
    # Exact normalised match
    if n1 == n2:
        return 1.0
    # One is a substring of the other
    if n1 in n2 or n2 in n1:
        return 0.9
    return difflib.SequenceMatcher(None, n1, n2).ratio()


def search_tripadvisor(name, location="Stratford-upon-Avon"):
    """
    Search TripAdvisor for a restaurant by name + location.
    Returns list of search result dicts or empty list.
    """
    params = {
        "q": f"{name} {location}",
        "searchSessionId": "",
        "sid": "",
    }

    try:
        resp = requests.get(TA_SEARCH_URL, params=params, headers=HEADERS,
                            timeout=15, allow_redirects=True)
    except requests.RequestException as e:
        # Transport-level error (DNS, TLS, connection). Not the same class
        # of failure as IP blocking; treat as a soft "no result".
        print(f"    Network error: {e}")
        return []

    # Treat IP-blocking status codes as a distinct failure mode. Swallowing
    # them as "no match" (the pre-fix behaviour) hides the real cause and
    # makes every run look like TripAdvisor has zero data for Stratford.
    if resp.status_code in (403, 429):
        raise SearchBlocked(
            f"TripAdvisor returned HTTP {resp.status_code} for "
            f"search query {name!r}. Runner IP is likely blocked.",
            status_code=resp.status_code,
        )

    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        print(f"    Search HTTP error: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    # TripAdvisor search results use various selectors depending on version
    # Try multiple patterns
    for result_div in soup.select("[data-test-target='search-result']"):
        result = parse_search_result(result_div)
        if result:
            results.append(result)

    # Fallback: look for restaurant links with ratings
    if not results:
        for link in soup.find_all("a", href=re.compile(r"/Restaurant_Review")):
            title = link.get_text(strip=True)
            href = link.get("href", "")
            if title and href:
                results.append({
                    "name": title,
                    "url": TA_BASE + href if href.startswith("/") else href,
                    "rating": None,
                    "review_count": None,
                })

    return results[:5]  # Top 5 results


def parse_search_result(div):
    """Parse a TripAdvisor search result div."""
    result = {}

    # Name
    title_el = div.select_one("a[href*='Restaurant_Review']")
    if not title_el:
        return None
    result["name"] = title_el.get_text(strip=True)
    href = title_el.get("href", "")
    result["url"] = TA_BASE + href if href.startswith("/") else href

    # Rating — look for bubble rating
    bubble = div.select_one("[class*='bubble_rating'], [class*='UctUV']")
    if bubble:
        # Extract from class like "bubble_45" = 4.5
        cls = " ".join(bubble.get("class", []))
        m = re.search(r"bubble_(\d)(\d)", cls)
        if m:
            result["rating"] = float(f"{m.group(1)}.{m.group(2)}")

    # Review count
    review_el = div.select_one("[class*='review_count'], [class*='IcelI']")
    if review_el:
        text = review_el.get_text(strip=True)
        m = re.search(r"[\d,]+", text)
        if m:
            result["review_count"] = int(m.group().replace(",", ""))

    return result


def get_restaurant_details(url):
    """
    Fetch a TripAdvisor restaurant page and extract detailed info.
    Returns dict with rating, review_count, cuisine, price_range.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"    Detail page error: {e}")
        return {}

    soup = BeautifulSoup(resp.text, "html.parser")
    details = {}

    # Rating — from JSON-LD or meta tags
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            ld = json.loads(script.string)
            if isinstance(ld, dict):
                ar = ld.get("aggregateRating") or {}
                if ar.get("ratingValue"):
                    details["rating"] = float(ar["ratingValue"])
                if ar.get("reviewCount"):
                    details["review_count"] = int(ar["reviewCount"])
                # Cuisine from @type or servesCuisine
                if ld.get("servesCuisine"):
                    cuisines = ld["servesCuisine"]
                    if isinstance(cuisines, list):
                        details["cuisines"] = cuisines
                    else:
                        details["cuisines"] = [cuisines]
            elif isinstance(ld, list):
                for item in ld:
                    ar = item.get("aggregateRating") or {}
                    if ar.get("ratingValue"):
                        details["rating"] = float(ar["ratingValue"])
                    if ar.get("reviewCount"):
                        details["review_count"] = int(ar["reviewCount"])
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    # Price range — look for price tag elements
    for el in soup.select("[class*='price'], [class*='Price']"):
        text = el.get_text(strip=True)
        if "£" in text or "$" in text:
            details["price_range"] = text
            break

    # Cuisine tags — from detail section
    if "cuisines" not in details:
        for el in soup.select("[class*='cuisine'], [class*='tag']"):
            text = el.get_text(strip=True)
            if text and len(text) < 50:
                details.setdefault("cuisines", []).append(text)

    return details


def find_best_match(name, results, threshold=0.6):
    """Find the best fuzzy match from search results."""
    if not results:
        return None, 0

    best_match = None
    best_score = 0

    for result in results:
        score = fuzzy_match(name, result.get("name", ""))
        if score > best_score:
            best_score = score
            best_match = result

    if best_score >= threshold:
        return best_match, best_score
    return None, best_score


def main():
    if not os.path.exists(INPUT_PATH):
        print(f"ERROR: {INPUT_PATH} not found")
        sys.exit(1)

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        establishments = json.load(f)
    print(f"Loaded {len(establishments)} establishments")

    # Load existing results for resume support
    ta_data = {}
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            ta_data = json.load(f)
        print(f"Loaded {len(ta_data)} existing TripAdvisor records (resuming)")

    matched = 0
    no_match = 0
    skipped = 0
    errors = 0
    blocked = 0
    attempts = 0
    total = len(establishments)

    for i, (key, record) in enumerate(establishments.items(), 1):
        name = record.get("n", "")
        postcode = record.get("pc", "")

        # Skip if already processed. Also skip reserved top-level metadata
        # keys (`_meta`, `_unmatched`, …) that may have been written into
        # the side file by consolidate_tripadvisor.py — those are not
        # establishment fhrsids and must not be iterated as such.
        if key.startswith("_") or key in ta_data:
            skipped += 1
            continue

        if not name:
            ta_data[key] = {"_skipped": True, "_reason": "no_name"}
            skipped += 1
            continue

        # Skip non-restaurant types (sports clubs, churches, etc.)
        gty = record.get("gty", [])
        if isinstance(gty, list):
            non_food = {"sports_club", "church", "place_of_worship",
                        "insurance_agency", "real_estate_agency"}
            if non_food & set(gty) and "restaurant" not in gty and "food" not in gty:
                ta_data[key] = {"_skipped": True, "_reason": "non_food"}
                skipped += 1
                continue

        try:
            # Step 1: Search TripAdvisor
            attempts += 1
            results = search_tripadvisor(name)
            time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

            if not results:
                ta_data[key] = {"_no_match": True}
                no_match += 1
                print(f"  [{i}/{total}] no results: {name}")
                continue

            # Step 2: Fuzzy match
            best, score = find_best_match(name, results)
            if not best:
                ta_data[key] = {"_no_match": True, "_best_score": round(score, 2)}
                no_match += 1
                print(f"  [{i}/{total}] no fuzzy match (best={score:.2f}): {name}")
                continue

            # Step 3: Get details from restaurant page
            entry = {
                "ta": best.get("rating"),
                "trc": best.get("review_count"),
                "ta_url": best.get("url", ""),
                "ta_name": best.get("name", ""),
                "match_score": round(score, 2),
            }

            if best.get("url"):
                details = get_restaurant_details(best["url"])
                time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

                # Prefer detail page data over search data
                if details.get("rating"):
                    entry["ta"] = details["rating"]
                if details.get("review_count"):
                    entry["trc"] = details["review_count"]
                if details.get("cuisines"):
                    entry["ta_cuisines"] = details["cuisines"]
                if details.get("price_range"):
                    entry["ta_price"] = details["price_range"]

            ta_data[key] = entry
            matched += 1
            print(f"  [{i}/{total}] {name} -> ta={entry.get('ta')} "
                  f"reviews={entry.get('trc')} match={score:.2f}")

        except SearchBlocked as e:
            # Record and keep probing for a while so we can prove we're
            # blocked at the network layer rather than misdiagnosing a
            # single transient 403. The threshold check below decides
            # whether to fail the whole run.
            blocked += 1
            ta_data[key] = {"_blocked": True, "_status": e.status_code}
            print(f"  [{i}/{total}] BLOCKED (HTTP {e.status_code}): {name}")
            time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

            # Early abort once the pattern is clear: once we've attempted
            # enough and most are blocked, stop wasting requests.
            if (attempts >= BLOCKED_MIN_ATTEMPTS
                    and blocked / attempts >= BLOCKED_RATIO_THRESHOLD):
                print(f"  ... early abort: {blocked}/{attempts} blocked "
                      f"({100 * blocked / attempts:.0f}%). "
                      f"Stopping before further requests.")
                break

        except Exception as e:
            errors += 1
            ta_data[key] = {"_error": str(e)}
            print(f"  [{i}/{total}] error for {name}: {e}")

        # Save progress every 20 records
        if i % 20 == 0:
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(ta_data, f, indent=2, ensure_ascii=False)
            print(f"  ... saved progress ({len(ta_data)} records)")

    # Final save
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(ta_data, f, indent=2, ensure_ascii=False)

    # Type-safe valid count. The resume file may carry top-level metadata
    # keys (`_meta`, `_unmatched`) whose values are dicts or LISTS written
    # by consolidate_tripadvisor.py. Iterating `ta_data.values()` and
    # calling `.get()` on a list was the source of the AttributeError
    # previously seen on CI.
    valid = sum(
        1 for k, v in ta_data.items()
        if not k.startswith("_")
        and isinstance(v, dict)
        and v.get("ta") is not None
        and not v.get("_skipped")
        and not v.get("_no_match")
        and not v.get("_error")
        and not v.get("_blocked")
    )

    print(
        f"\nDone. Total: {total}, Attempted: {attempts}, "
        f"Matched: {matched}, No match: {no_match}, "
        f"Skipped (pre-existing or non-food): {skipped}, "
        f"Errors: {errors}, Blocked (HTTP 403/429): {blocked}"
    )
    print(f"Records with TripAdvisor rating: {valid}")
    print(f"Saved to {OUTPUT_PATH}")

    # Fail honestly when the runner's IP range is blocked by TripAdvisor.
    # Without this guard every 403 is silently counted as 'no match' and
    # downstream scoring commits a dataset that looks like TripAdvisor has
    # zero coverage for Stratford, which is not the truth.
    if attempts >= BLOCKED_MIN_ATTEMPTS and blocked / max(attempts, 1) >= BLOCKED_RATIO_THRESHOLD:
        ratio_pct = 100 * blocked / attempts
        sys.stderr.write(
            "\n::error::TripAdvisor blocked "
            f"{blocked}/{attempts} search attempts ({ratio_pct:.0f}%). "
            "The current HTML-scrape approach is not viable from GitHub-hosted "
            "runners. See docs/DayDine-TripAdvisor-Blocker-Diagnosis.md for the "
            "recommended next strategy (TripAdvisor Content API or a "
            "self-hosted / residential-IP collector).\n"
        )
        sys.exit(7)


if __name__ == "__main__":
    main()
