#!/usr/bin/env python3
"""
collect_google_reviews_playwright.py — Google Maps Review Collector

Uses Playwright (headless Chromium) to collect reviews from Google Maps.
No API key needed — scrapes the public web interface.

Usage:
    python collect_google_reviews_playwright.py                    # all restaurants
    python collect_google_reviews_playwright.py --limit 5          # first 5 only
    python collect_google_reviews_playwright.py --fhrsid 503480    # specific restaurant
    python collect_google_reviews_playwright.py --max-reviews 100  # override max per venue
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
OUTPUT_DIR = os.path.join(REPO_DIR, "data", "raw", "google")


def slugify(name):
    """Convert venue name to filesystem-safe slug."""
    slug = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')
    return slug[:60]


def parse_relative_date(date_text):
    """Convert Google's relative date to approximate ISO date."""
    now = datetime.utcnow()
    text = date_text.lower().strip()

    patterns = [
        (r'(\d+)\s*minute', lambda m: now - timedelta(minutes=int(m.group(1)))),
        (r'(\d+)\s*hour', lambda m: now - timedelta(hours=int(m.group(1)))),
        (r'a\s*day\s*ago', lambda m: now - timedelta(days=1)),
        (r'(\d+)\s*day', lambda m: now - timedelta(days=int(m.group(1)))),
        (r'a\s*week\s*ago', lambda m: now - timedelta(weeks=1)),
        (r'(\d+)\s*week', lambda m: now - timedelta(weeks=int(m.group(1)))),
        (r'a\s*month\s*ago', lambda m: now - timedelta(days=30)),
        (r'(\d+)\s*month', lambda m: now - timedelta(days=int(m.group(1)) * 30)),
        (r'a\s*year\s*ago', lambda m: now - timedelta(days=365)),
        (r'(\d+)\s*year', lambda m: now - timedelta(days=int(m.group(1)) * 365)),
    ]

    for pattern, calc in patterns:
        match = re.search(pattern, text)
        if match:
            return calc(match).strftime("%Y-%m-%d")

    return None


async def setup_stealth(page):
    """Apply stealth measures to avoid bot detection."""
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-GB', 'en']});
        window.chrome = {runtime: {}};
    """)


async def accept_cookies(page):
    """Accept Google consent dialog if it appears."""
    try:
        # Google consent button variants
        for selector in [
            'button:has-text("Accept all")',
            'button:has-text("Accept")',
            '[aria-label="Accept all"]',
            'form[action*="consent"] button',
        ]:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=3000):
                await btn.click()
                await page.wait_for_timeout(1000)
                return True
    except Exception:
        pass
    return False


async def collect_reviews_for_venue(page, venue, max_reviews):
    """Collect reviews for a single venue from Google Maps."""
    name = venue.get("n", "")
    postcode = venue.get("pc", "")
    fhrsid = str(venue.get("id", ""))
    lat = venue.get("lat")
    lon = venue.get("lon")
    gpid = venue.get("gpid")

    search_query = f"{name} {postcode}"
    print(f"  Searching: {search_query}...", end=" ", flush=True)

    # Navigate to Google Maps search
    await page.goto(f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}")
    await page.wait_for_timeout(random.randint(2000, 4000))

    # Accept cookies on first load
    await accept_cookies(page)
    await page.wait_for_timeout(1000)

    # Wait for results or place page to load
    try:
        await page.wait_for_selector('[data-value="Sort"], [role="main"] h1, .fontHeadlineLarge',
                                      timeout=10000)
    except Exception:
        print("place not found")
        return None

    # Check if we landed directly on a place page or need to click a result
    title_el = page.locator('.fontHeadlineLarge, [role="main"] h1').first
    try:
        if not await title_el.is_visible(timeout=3000):
            # Click first result
            first_result = page.locator('[role="feed"] a[href*="/maps/place/"]').first
            if await first_result.is_visible(timeout=5000):
                await first_result.click()
                await page.wait_for_timeout(random.randint(2000, 4000))
    except Exception:
        pass

    # Get total review count from the place page
    total_reviews = 0
    try:
        review_count_el = page.locator('[aria-label*="review"]').first
        if await review_count_el.is_visible(timeout=3000):
            text = await review_count_el.text_content()
            match = re.search(r'([\d,]+)\s*review', text)
            if match:
                total_reviews = int(match.group(1).replace(',', ''))
    except Exception:
        pass

    # Click on Reviews tab
    try:
        reviews_tab = page.locator('button[role="tab"]:has-text("Reviews")').first
        if await reviews_tab.is_visible(timeout=5000):
            await reviews_tab.click()
            await page.wait_for_timeout(random.randint(2000, 3000))
        else:
            print("no reviews tab")
            return None
    except Exception:
        print("no reviews tab")
        return None

    # Sort by Newest
    try:
        sort_btn = page.locator('button[aria-label*="Sort"], button:has-text("Sort")').first
        if await sort_btn.is_visible(timeout=3000):
            await sort_btn.click()
            await page.wait_for_timeout(1000)
            newest = page.locator('[data-index="1"], [role="menuitemradio"]:has-text("Newest")').first
            if await newest.is_visible(timeout=3000):
                await newest.click()
                await page.wait_for_timeout(random.randint(2000, 3000))
    except Exception:
        pass  # Continue with default sort

    # Scroll and collect reviews
    reviews = []
    scroll_container = page.locator('[role="main"]').first
    last_count = 0
    stall_count = 0

    while len(reviews) < max_reviews:
        # Find all review elements currently loaded
        review_elements = page.locator('[data-review-id], [jscontroller] [class*="review"]')
        count = await review_elements.count()

        if count == last_count:
            stall_count += 1
            if stall_count >= 3:
                break  # No more reviews loading
        else:
            stall_count = 0
        last_count = count

        # Extract reviews we haven't processed yet
        for i in range(len(reviews), min(count, max_reviews)):
            try:
                el = review_elements.nth(i)

                # Click "More" to expand truncated text
                more_btn = el.locator('button:has-text("More")').first
                try:
                    if await more_btn.is_visible(timeout=500):
                        await more_btn.click()
                        await page.wait_for_timeout(300)
                except Exception:
                    pass

                # Extract review data
                text = ""
                try:
                    text_el = el.locator('[class*="review-full-text"], .wiI7pd, [class*="MyEned"]').first
                    if await text_el.is_visible(timeout=500):
                        text = (await text_el.text_content() or "").strip()
                except Exception:
                    pass

                rating = None
                try:
                    stars_el = el.locator('[role="img"][aria-label*="star"]').first
                    if await stars_el.is_visible(timeout=500):
                        label = await stars_el.get_attribute("aria-label") or ""
                        match = re.search(r'(\d)', label)
                        if match:
                            rating = int(match.group(1))
                except Exception:
                    pass

                date_raw = ""
                date_iso = None
                try:
                    date_el = el.locator('[class*="rsqaWe"], [class*="DU9Pgb"]').first
                    if await date_el.is_visible(timeout=500):
                        date_raw = (await date_el.text_content() or "").strip()
                        date_iso = parse_relative_date(date_raw)
                except Exception:
                    pass

                reviewer_name = ""
                try:
                    name_el = el.locator('[class*="d4r55"], [class*="WNxzHc"] a, button[class*="WEBjve"]').first
                    if await name_el.is_visible(timeout=500):
                        reviewer_name = (await name_el.text_content() or "").strip()
                except Exception:
                    pass

                owner_response = None
                try:
                    response_el = el.locator('[class*="CDe7pd"], [class*="owner-response"]').first
                    if await response_el.is_visible(timeout=500):
                        owner_response = (await response_el.text_content() or "").strip()
                except Exception:
                    pass

                if text or rating:
                    reviews.append({
                        "text": text,
                        "rating": rating,
                        "date": date_iso,
                        "date_raw": date_raw,
                        "reviewer_name": reviewer_name,
                        "reviewer_reviews": None,
                        "is_local_guide": False,
                        "owner_response": owner_response,
                        "owner_response_date": None,
                        "helpful_count": 0,
                        "source": "google",
                    })
            except Exception:
                continue

        if len(reviews) >= max_reviews:
            break

        # Scroll to load more
        try:
            await scroll_container.evaluate(
                "el => el.scrollTop = el.scrollHeight"
            )
        except Exception:
            try:
                await page.keyboard.press("End")
            except Exception:
                pass
        await page.wait_for_timeout(random.randint(1500, 3000))

    print(f"{len(reviews)} reviews collected ({total_reviews} total on Google)")

    return {
        "fhrsid": fhrsid,
        "name": name,
        "google_place_id": gpid,
        "collected_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "collection_method": "playwright",
        "total_reviews_found": total_reviews,
        "reviews_collected": len(reviews),
        "reviews": reviews,
    }


async def main():
    parser = argparse.ArgumentParser(description="Collect Google Maps reviews via Playwright")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of restaurants")
    parser.add_argument("--fhrsid", type=str, help="Collect for specific FHRSID only")
    parser.add_argument("--max-reviews", type=int, default=50, help="Max reviews per venue")
    args = parser.parse_args()

    # Load establishments
    with open(ESTABLISHMENTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Filter venues
    venues = []
    for fid, rec in data.items():
        if args.fhrsid and str(rec.get("id", fid)) != args.fhrsid and fid != args.fhrsid:
            continue
        if rec.get("n"):
            venues.append(rec)

    if args.limit > 0:
        venues = venues[:args.limit]

    print(f"Google Review Collector: {len(venues)} venues, max {args.max_reviews} reviews each")
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

        # Randomised viewport
        width = random.randint(1280, 1920)
        height = random.randint(800, 1080)
        context = await browser.new_context(
            viewport={"width": width, "height": height},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-GB",
        )

        # Block images to speed things up
        await context.route("**/*.{png,jpg,jpeg,gif,svg,ico,webp}", lambda route: route.abort())

        page = await context.new_page()
        await setup_stealth(page)

        collected = 0
        blocked = 0
        today = datetime.utcnow().strftime("%Y-%m-%d")

        for i, venue in enumerate(venues):
            name = venue.get("n", "Unknown")

            try:
                result = await collect_reviews_for_venue(page, venue, args.max_reviews)

                if result and result["reviews_collected"] > 0:
                    slug = slugify(name)
                    path = os.path.join(OUTPUT_DIR, f"{slug}_{today}.json")
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(result, f, indent=2, ensure_ascii=False)
                    collected += 1
                elif result is None:
                    print(f"  Skipped: {name}")

            except Exception as e:
                error_msg = str(e).lower()
                if "captcha" in error_msg or "unusual traffic" in error_msg:
                    blocked += 1
                    print(f"  BLOCKED: {name} — {e}")
                    if blocked >= 3:
                        print("STOPPING: 3 consecutive blocks detected")
                        break
                else:
                    print(f"  ERROR: {name} — {e}")
                    blocked = 0  # Reset block counter on non-block errors

            # Delay between restaurants
            if i < len(venues) - 1:
                delay = random.randint(8, 15)
                await page.wait_for_timeout(delay * 1000)

        await browser.close()

    print(f"\nSummary: {collected} venues collected, {len(venues) - collected} skipped/failed")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
