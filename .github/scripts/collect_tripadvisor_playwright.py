#!/usr/bin/env python3
"""
collect_tripadvisor_playwright.py — TripAdvisor Review Collector

Uses Playwright (headless Chromium) to collect reviews from TripAdvisor.
Replaces the broken Apify approach. No API key needed.

Usage:
    python collect_tripadvisor_playwright.py                    # all restaurants
    python collect_tripadvisor_playwright.py --limit 5          # first 5 only
    python collect_tripadvisor_playwright.py --fhrsid 503480    # specific restaurant
    python collect_tripadvisor_playwright.py --max-reviews 50   # override max per venue
"""

import argparse
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
ESTABLISHMENTS_PATH = os.path.join(REPO_DIR, "stratford_establishments.json")
OUTPUT_DIR = os.path.join(REPO_DIR, "data", "raw", "tripadvisor")


def slugify(name):
    slug = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')
    return slug[:60]


async def setup_stealth(page):
    """Apply stealth measures — TripAdvisor has stronger anti-bot than Google."""
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-GB', 'en']});
        window.chrome = {runtime: {}};
        // Override permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
                ? Promise.resolve({state: Notification.permission})
                : originalQuery(parameters);
    """)


async def handle_cloudflare(page):
    """Wait for Cloudflare challenge if detected."""
    try:
        cf = page.locator('#cf-wrapper, #challenge-running, .cf-browser-verification')
        if await cf.is_visible(timeout=2000):
            print("  Cloudflare challenge detected, waiting...", end=" ", flush=True)
            await page.wait_for_timeout(12000)
            # Check if we got through
            if await cf.is_visible(timeout=2000):
                print("still blocked")
                return False
            print("passed")
            return True
    except Exception:
        pass
    return True


async def accept_ta_cookies(page):
    """Accept TripAdvisor consent dialog."""
    try:
        for selector in [
            '#onetrust-accept-btn-handler',
            'button:has-text("Accept All")',
            'button:has-text("Accept")',
            '[id*="accept"]',
        ]:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                await page.wait_for_timeout(1000)
                return True
    except Exception:
        pass
    return False


async def find_restaurant_on_ta(page, name, postcode):
    """Search TripAdvisor and find the correct restaurant page."""
    search_url = f"https://www.tripadvisor.co.uk/Search?q={name.replace(' ', '+')}+{postcode.replace(' ', '+')}"
    await page.goto(search_url)
    await page.wait_for_timeout(random.randint(3000, 5000))

    if not await handle_cloudflare(page):
        return None

    await accept_ta_cookies(page)

    # Wait for search results
    try:
        await page.wait_for_selector('[data-test-target="search-result"], .result-title, .search-result',
                                      timeout=10000)
    except Exception:
        # Try alternative: direct URL construction
        return None

    # Click first restaurant result that mentions Stratford
    results = page.locator('[data-test-target="search-result"] a, .result-title a, a[href*="Restaurant_Review"]')
    count = await results.count()

    for i in range(min(count, 5)):
        try:
            link = results.nth(i)
            href = await link.get_attribute("href") or ""
            text = (await link.text_content() or "").lower()

            if "restaurant_review" in href.lower() or "restaurant" in href.lower():
                # Check name similarity
                name_lower = name.lower()
                if any(word in text for word in name_lower.split()[:2]):
                    await link.click()
                    await page.wait_for_timeout(random.randint(3000, 5000))
                    return page.url
        except Exception:
            continue

    return None


async def extract_ta_metadata(page):
    """Extract restaurant metadata from TripAdvisor page."""
    metadata = {
        "tripadvisor_rating": None,
        "tripadvisor_review_count": None,
        "tripadvisor_ranking": None,
        "tripadvisor_cuisines": [],
    }

    try:
        # Rating
        rating_el = page.locator('[data-test-target="restaurant-detail-info"] svg[aria-label*="of 5"], .ZDEqb').first
        if await rating_el.is_visible(timeout=3000):
            label = await rating_el.get_attribute("aria-label") or ""
            match = re.search(r'([\d.]+)\s*of\s*5', label)
            if match:
                metadata["tripadvisor_rating"] = float(match.group(1))

        # Review count
        count_el = page.locator('[data-test-target="restaurant-detail-info"] a[href*="Reviews"], .reviews_header_count').first
        if await count_el.is_visible(timeout=2000):
            text = await count_el.text_content() or ""
            match = re.search(r'([\d,]+)', text)
            if match:
                metadata["tripadvisor_review_count"] = int(match.group(1).replace(',', ''))

        # Ranking
        ranking_el = page.locator('.cNFlb, [data-test-target*="ranking"]').first
        if await ranking_el.is_visible(timeout=2000):
            metadata["tripadvisor_ranking"] = (await ranking_el.text_content() or "").strip()

        # Cuisines
        cuisine_els = page.locator('.SrqKb a, [data-test-target="restaurant-detail-info"] .BMlpu a')
        count = await cuisine_els.count()
        for i in range(min(count, 10)):
            try:
                text = (await cuisine_els.nth(i).text_content() or "").strip()
                if text and len(text) < 30:
                    metadata["tripadvisor_cuisines"].append(text)
            except Exception:
                pass
    except Exception:
        pass

    return metadata


async def collect_ta_reviews(page, max_reviews):
    """Collect reviews from the current TripAdvisor restaurant page."""
    reviews = []

    # Sort by most recent if possible
    try:
        sort_dropdown = page.locator('#LanguageFilter_0, select[id*="trating"]').first
        if await sort_dropdown.is_visible(timeout=3000):
            await sort_dropdown.select_option("mr")  # Most recent
            await page.wait_for_timeout(random.randint(2000, 4000))
    except Exception:
        pass

    page_num = 0
    while len(reviews) < max_reviews:
        page_num += 1

        # Expand truncated reviews
        more_buttons = page.locator('[data-test-target="expand-review"], .pZUbB, span:has-text("Read more")')
        more_count = await more_buttons.count()
        for i in range(more_count):
            try:
                btn = more_buttons.nth(i)
                if await btn.is_visible(timeout=500):
                    await btn.click()
                    await page.wait_for_timeout(300)
            except Exception:
                pass

        # Extract reviews on current page
        review_cards = page.locator('[data-test-target="HR_CC_CARD"], .reviewSelector, [data-automation="reviewCard"]')
        count = await review_cards.count()

        if count == 0:
            break

        for i in range(count):
            if len(reviews) >= max_reviews:
                break
            try:
                card = review_cards.nth(i)

                # Title
                title = ""
                try:
                    title_el = card.locator('[data-test-target="review-title"] a, .noQuotes, a.Qwuub').first
                    if await title_el.is_visible(timeout=500):
                        title = (await title_el.text_content() or "").strip()
                except Exception:
                    pass

                # Text
                text = ""
                try:
                    text_el = card.locator('[data-test-target="review-body"], .entry .partial_entry, .pIRBV q').first
                    if await text_el.is_visible(timeout=500):
                        text = (await text_el.text_content() or "").strip()
                except Exception:
                    pass

                # Rating (bubble count)
                rating = None
                try:
                    bubble_el = card.locator('svg[aria-label*="of 5"], .ui_bubble_rating').first
                    if await bubble_el.is_visible(timeout=500):
                        label = await bubble_el.get_attribute("aria-label") or ""
                        cls = await bubble_el.get_attribute("class") or ""
                        match = re.search(r'(\d)', label)
                        if match:
                            rating = int(match.group(1))
                        elif "bubble_" in cls:
                            match = re.search(r'bubble_(\d)', cls)
                            if match:
                                rating = int(match.group(1))
                except Exception:
                    pass

                # Published date
                published_date = None
                try:
                    date_el = card.locator('.ratingDate, [data-test-target="review-date"], .cRVSd').first
                    if await date_el.is_visible(timeout=500):
                        date_text = (await date_el.text_content() or "").strip()
                        # Try to parse "Month YYYY" or "DD Month YYYY"
                        for fmt in ["%B %Y", "%d %B %Y", "%b %Y"]:
                            try:
                                dt = datetime.strptime(date_text.replace("Date of visit: ", "").strip(), fmt)
                                published_date = dt.strftime("%Y-%m-%d")
                                break
                            except ValueError:
                                continue
                        if not published_date:
                            # Store raw if can't parse
                            published_date = date_text
                except Exception:
                    pass

                # Visit date
                visit_date = None
                try:
                    visit_el = card.locator('.prw_reviews_stay_date_hsx, [data-test-target="review-date"]').first
                    if await visit_el.is_visible(timeout=500):
                        visit_text = (await visit_el.text_content() or "").strip()
                        if "visit" in visit_text.lower():
                            visit_date = visit_text.replace("Date of visit: ", "").strip()
                except Exception:
                    pass

                # Trip type
                trip_type = None
                try:
                    trip_el = card.locator('.recommend-titleInline, [data-test-target="review-tag"]').first
                    if await trip_el.is_visible(timeout=500):
                        trip_type = (await trip_el.text_content() or "").strip()
                except Exception:
                    pass

                # Reviewer info
                reviewer_name = ""
                reviewer_location = ""
                reviewer_contributions = 0
                try:
                    name_el = card.locator('.info_text a, [data-test-target="reviewer-name"], .ui_header_link').first
                    if await name_el.is_visible(timeout=500):
                        reviewer_name = (await name_el.text_content() or "").strip()
                except Exception:
                    pass

                # Owner response
                owner_response = None
                try:
                    resp_el = card.locator('.mgrRspnInline, [data-test-target="management-response"]').first
                    if await resp_el.is_visible(timeout=500):
                        owner_response = (await resp_el.text_content() or "").strip()
                except Exception:
                    pass

                if text or rating:
                    reviews.append({
                        "title": title,
                        "text": text,
                        "rating": rating,
                        "published_date": published_date,
                        "visit_date": visit_date,
                        "trip_type": trip_type,
                        "reviewer_name": reviewer_name,
                        "reviewer_location": reviewer_location,
                        "reviewer_contributions": reviewer_contributions,
                        "helpful_votes": 0,
                        "owner_response": owner_response,
                        "sub_ratings": {},
                        "source": "tripadvisor",
                    })
            except Exception:
                continue

        # Paginate — click next page
        try:
            next_btn = page.locator('a.next, [data-test-target="pagination-next"], a:has-text("Next")').first
            if await next_btn.is_visible(timeout=3000):
                await next_btn.click()
                await page.wait_for_timeout(random.randint(3000, 6000))
            else:
                break  # No more pages
        except Exception:
            break

    return reviews


async def collect_for_venue(page, venue, max_reviews):
    """Full collection for one venue."""
    name = venue.get("n", "")
    postcode = venue.get("pc", "")
    fhrsid = str(venue.get("id", ""))

    print(f"  Searching TripAdvisor: {name} {postcode}...", end=" ", flush=True)

    ta_url = await find_restaurant_on_ta(page, name, postcode)
    if not ta_url:
        print("not found")
        return None

    metadata = await extract_ta_metadata(page)
    reviews = await collect_ta_reviews(page, max_reviews)

    print(f"{len(reviews)} reviews collected" +
          (f" (rating: {metadata['tripadvisor_rating']})" if metadata['tripadvisor_rating'] else ""))

    return {
        "fhrsid": fhrsid,
        "name": name,
        "tripadvisor_url": ta_url,
        "tripadvisor_rating": metadata["tripadvisor_rating"],
        "tripadvisor_review_count": metadata["tripadvisor_review_count"],
        "tripadvisor_ranking": metadata["tripadvisor_ranking"],
        "tripadvisor_cuisines": metadata["tripadvisor_cuisines"],
        "collected_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "collection_method": "playwright",
        "reviews_collected": len(reviews),
        "reviews": reviews,
    }


async def main():
    parser = argparse.ArgumentParser(description="Collect TripAdvisor reviews via Playwright")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of restaurants")
    parser.add_argument("--fhrsid", type=str, help="Collect for specific FHRSID only")
    parser.add_argument("--max-reviews", type=int, default=50, help="Max reviews per venue")
    args = parser.parse_args()

    with open(ESTABLISHMENTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    venues = []
    for fid, rec in data.items():
        if args.fhrsid and str(rec.get("id", fid)) != args.fhrsid and fid != args.fhrsid:
            continue
        if rec.get("n"):
            venues.append(rec)

    if args.limit > 0:
        venues = venues[:args.limit]

    print(f"TripAdvisor Review Collector: {len(venues)} venues, max {args.max_reviews} reviews each")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ]
        )

        width = random.randint(1280, 1920)
        height = random.randint(800, 1080)
        context = await browser.new_context(
            viewport={"width": width, "height": height},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-GB",
        )

        await context.route("**/*.{png,jpg,jpeg,gif,svg,ico,webp}", lambda route: route.abort())

        page = await context.new_page()
        await setup_stealth(page)

        collected = 0
        consecutive_blocks = 0
        today = datetime.utcnow().strftime("%Y-%m-%d")

        for i, venue in enumerate(venues):
            name = venue.get("n", "Unknown")

            try:
                result = await collect_for_venue(page, venue, args.max_reviews)

                if result and result["reviews_collected"] > 0:
                    slug = slugify(name)
                    path = os.path.join(OUTPUT_DIR, f"{slug}_{today}.json")
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(result, f, indent=2, ensure_ascii=False)
                    collected += 1
                    consecutive_blocks = 0
                elif result is None:
                    consecutive_blocks += 1
                    if consecutive_blocks >= 3:
                        print("STOPPING: 3 consecutive failures — likely blocked")
                        break

            except Exception as e:
                print(f"  ERROR: {name} — {e}")
                consecutive_blocks += 1
                if consecutive_blocks >= 3:
                    print("STOPPING: 3 consecutive errors")
                    break

            # Longer delays for TripAdvisor (stronger anti-bot)
            if i < len(venues) - 1:
                delay = random.randint(15, 25)
                await page.wait_for_timeout(delay * 1000)

        await browser.close()

    print(f"\nSummary: {collected} venues collected, {len(venues) - collected} skipped/failed")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
