#!/usr/bin/env python3
"""Review data collection health monitor.

Scans data/raw/ directories, counts reviews per source per restaurant,
compares against minimum viable thresholds, and generates health reports.

Usage:
    python .github/scripts/review_data_monitor.py

Outputs:
    data/collection_health.json  — per-restaurant health stats
    data/collection_log.txt      — timestamped log entries (appended)

Exit codes:
    0 — All sources operational
    1 — One or more sources failed completely (no data collected)
"""

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"
HEALTH_FILE = REPO_ROOT / "data" / "collection_health.json"
LOG_FILE = REPO_ROOT / "data" / "collection_log.txt"

# Minimum viable thresholds
MIN_TOTAL_REVIEWS = 50
MIN_REVIEWS_WITH_TEXT = 30
MIN_SOURCES = 2


def confidence_tier(total_reviews: int, num_sources: int) -> str:
    """Determine data confidence tier."""
    if total_reviews >= 100 and num_sources >= 2:
        return "Robust"
    if total_reviews >= 50:
        return "Reliable"
    if total_reviews >= 25:
        return "Directional"
    return "Indicative"


def scan_source_dir(source_dir: Path) -> dict:
    """Scan a source directory and return per-restaurant review data."""
    restaurants = {}

    if not source_dir.exists():
        return restaurants

    for f in sorted(source_dir.glob("*.json")):
        if f.name == ".gitkeep":
            continue
        try:
            with open(f) as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Skipping %s: %s", f.name, e)
            continue

        # Extract slug from filename: {slug}_{YYYY-MM-DD}.json
        match = re.match(r"^(.+?)_(\d{4}-\d{2}-\d{2})\.json$", f.name)
        if not match:
            # Try without date pattern (legacy files)
            slug = f.stem
            collection_date = None
        else:
            slug = match.group(1)
            collection_date = match.group(2)

        # Handle both array and dict formats
        reviews = []
        if isinstance(data, list):
            reviews = data
        elif isinstance(data, dict):
            reviews = data.get("reviews", [])

        if slug not in restaurants:
            restaurants[slug] = {
                "files": [],
                "reviews": [],
                "collection_dates": [],
            }

        restaurants[slug]["files"].append(f.name)
        restaurants[slug]["reviews"].extend(reviews)
        if collection_date:
            restaurants[slug]["collection_dates"].append(collection_date)

    return restaurants


def analyse_reviews(reviews: list) -> dict:
    """Analyse a list of reviews for quality metrics."""
    total = len(reviews)
    with_text = 0
    word_counts = []
    dates = []

    for rev in reviews:
        text = rev.get("text", "") or ""
        if text.strip():
            with_text += 1
            word_counts.append(len(text.split()))

        date = rev.get("date") or rev.get("publishedDate", "")
        if date:
            dates.append(date)

    avg_length = sum(word_counts) / len(word_counts) if word_counts else 0

    # Sort dates to find range
    sorted_dates = sorted(d for d in dates if d)
    earliest = sorted_dates[0] if sorted_dates else None
    latest = sorted_dates[-1] if sorted_dates else None

    return {
        "total_reviews": total,
        "reviews_with_text": with_text,
        "avg_review_length_words": round(avg_length, 1),
        "date_range": {
            "earliest": earliest,
            "latest": latest,
        },
    }


def main():
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat()

    # Scan all source directories
    sources = ["google", "tripadvisor", "opentable"]
    all_data = {}  # source -> {slug -> data}
    source_has_data = {}

    for source in sources:
        source_dir = RAW_DIR / source
        data = scan_source_dir(source_dir)
        all_data[source] = data
        source_has_data[source] = len(data) > 0

    # Merge per-restaurant across sources
    restaurant_slugs = set()
    for source_data in all_data.values():
        restaurant_slugs.update(source_data.keys())

    restaurant_health = {}
    total_reviews_all = 0
    below_threshold_count = 0

    for slug in sorted(restaurant_slugs):
        by_source = {}
        all_reviews = []

        for source in sources:
            source_data = all_data[source].get(slug)
            if source_data:
                reviews = source_data["reviews"]
                by_source[source] = len(reviews)
                all_reviews.extend(reviews)

        analysis = analyse_reviews(all_reviews)
        num_sources = sum(1 for v in by_source.values() if v > 0)
        conf = confidence_tier(analysis["total_reviews"], num_sources)
        below = analysis["total_reviews"] < MIN_TOTAL_REVIEWS

        if below:
            below_threshold_count += 1
        total_reviews_all += analysis["total_reviews"]

        restaurant_health[slug] = {
            "total_reviews": analysis["total_reviews"],
            "by_source": by_source,
            "reviews_with_text": analysis["reviews_with_text"],
            "avg_review_length_words": analysis["avg_review_length_words"],
            "date_range": analysis["date_range"],
            "below_threshold": below,
            "confidence_level": conf,
            "sources_count": num_sources,
        }

    # Sources that are active (have any data)
    active_sources = [s for s in sources if source_has_data.get(s)]
    # Sources that were expected but have zero data
    failed_sources = [s for s in sources if not source_has_data.get(s) and (RAW_DIR / s).exists()]

    health_report = {
        "generated_at": timestamp,
        "restaurants": restaurant_health,
        "summary": {
            "total_restaurants": len(restaurant_slugs),
            "below_threshold": below_threshold_count,
            "total_reviews": total_reviews_all,
            "sources_active": active_sources,
            "sources_failed": failed_sources,
        },
    }

    # Write health file
    HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HEALTH_FILE, "w") as f:
        json.dump(health_report, f, indent=2, ensure_ascii=False)
    log.info("Health report written to %s", HEALTH_FILE)

    # Append to collection log
    log_entry = (
        f"[{timestamp}] "
        f"restaurants={len(restaurant_slugs)} "
        f"reviews={total_reviews_all} "
        f"below_threshold={below_threshold_count} "
        f"sources_active={','.join(active_sources) or 'none'} "
        f"sources_failed={','.join(failed_sources) or 'none'}\n"
    )
    with open(LOG_FILE, "a") as f:
        f.write(log_entry)
    log.info("Log entry appended to %s", LOG_FILE)

    # Print summary
    log.info("=" * 60)
    log.info("Collection Health Summary:")
    log.info("  Restaurants tracked: %d", len(restaurant_slugs))
    log.info("  Total reviews: %d", total_reviews_all)
    log.info("  Below threshold (%d): %d", MIN_TOTAL_REVIEWS, below_threshold_count)
    log.info("  Active sources: %s", ", ".join(active_sources) or "none")
    log.info("  Failed sources: %s", ", ".join(failed_sources) or "none")
    log.info("=" * 60)

    # Per-restaurant detail
    for slug, health in sorted(restaurant_health.items()):
        status = "BELOW" if health["below_threshold"] else "OK"
        log.info(
            "  %-40s %3d reviews  %s  [%s]",
            slug[:40],
            health["total_reviews"],
            health["confidence_level"],
            status,
        )

    # Exit code 1 if any expected source completely failed
    if failed_sources:
        log.warning("Sources with zero data: %s", ", ".join(failed_sources))
        sys.exit(1)


if __name__ == "__main__":
    main()
