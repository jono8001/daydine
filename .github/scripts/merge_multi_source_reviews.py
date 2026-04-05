#!/usr/bin/env python3
"""Merge reviews from multiple raw source directories into combined files.

Reads data/raw/google/, data/raw/tripadvisor/, data/raw/opentable/,
deduplicates across sources, applies quality filters, and writes
combined per-restaurant files to data/processed/.

Usage:
    python .github/scripts/merge_multi_source_reviews.py
"""

import json
import logging
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"

SOURCES = ["google", "tripadvisor", "opentable"]

# Quality classification thresholds
HIGH_MIN_WORDS = 50
MEDIUM_MIN_WORDS = 20
LOW_MIN_WORDS = 5

# Deduplication thresholds
DEDUP_TEXT_SIMILARITY = 0.80
DEDUP_DATE_WINDOW_DAYS = 1

# Keywords for HIGH quality classification
ASPECT_KEYWORDS = {
    "food", "menu", "dish", "meal", "steak", "fish", "chicken", "pasta",
    "wine", "beer", "cocktail", "drink", "dessert", "starter", "main",
    "service", "staff", "waiter", "waitress", "server", "manager",
    "atmosphere", "ambience", "decor", "music", "noise", "lighting",
    "cozy", "romantic", "lively",
    "value", "price", "expensive", "cheap", "reasonable", "worth",
    "portion", "quality",
}


def load_raw_reviews(source: str) -> dict:
    """Load all raw review files for a source. Returns {slug: [reviews]}."""
    source_dir = RAW_DIR / source
    restaurants = defaultdict(list)

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

        # Extract slug from filename
        match = re.match(r"^(.+?)_(\d{4}-\d{2}-\d{2})\.json$", f.name)
        slug = match.group(1) if match else f.stem

        # Handle both array and dict formats
        reviews = []
        fhrsid = None
        if isinstance(data, list):
            reviews = data
        elif isinstance(data, dict):
            reviews = data.get("reviews", [])
            fhrsid = data.get("fhrsid")

        # Ensure source tag on each review
        for rev in reviews:
            if "source" not in rev:
                rev["source"] = source
            if fhrsid and "fhrsid" not in rev:
                rev["fhrsid"] = fhrsid

        restaurants[slug].extend(reviews)

    return restaurants


def classify_quality(review: dict) -> str:
    """Classify a review into HIGH, MEDIUM, LOW, or EXCLUDE quality tier."""
    text = (review.get("text") or "").strip()
    words = text.split()
    word_count = len(words)

    # EXCLUDE: no text and no rating
    if not text and review.get("rating") is None:
        return "EXCLUDE"

    # EXCLUDE: very short non-rating text (likely spam or meaningless)
    if text and word_count < LOW_MIN_WORDS:
        return "EXCLUDE"

    # LOW: rating-only (no text) or very short text
    if not text:
        return "LOW"
    if word_count < MEDIUM_MIN_WORDS:
        return "LOW"

    # Check for aspect keywords
    text_lower = text.lower()
    has_aspects = any(kw in text_lower for kw in ASPECT_KEYWORDS)

    # HIGH: 50+ words with aspect mentions
    if word_count >= HIGH_MIN_WORDS and has_aspects:
        return "HIGH"

    # MEDIUM: 20-50 words or 50+ without aspects
    if word_count >= MEDIUM_MIN_WORDS:
        return "MEDIUM"

    return "LOW"


def detect_spam(review: dict) -> bool:
    """Detect likely spam reviews."""
    text = (review.get("text") or "").strip().lower()
    if not text:
        return False

    # Keyword stuffing: excessive repetition
    words = text.split()
    if len(words) > 10:
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio < 0.3:
            return True

    # Competitor mentions (obvious spam pattern)
    spam_patterns = [
        r"visit us at",
        r"www\.\S+\.com",
        r"call \d{5,}",
        r"discount code",
        r"promo code",
    ]
    for pattern in spam_patterns:
        if re.search(pattern, text):
            return True

    return False


def is_duplicate(rev1: dict, rev2: dict) -> bool:
    """Check if two reviews are duplicates using text similarity + date proximity."""
    # Same source + same review ID = exact duplicate
    if (rev1.get("review_id") and rev2.get("review_id") and
            rev1.get("source") == rev2.get("source") and
            rev1["review_id"] == rev2["review_id"]):
        return True

    # Cross-source: fuzzy text match + same-day date
    text1 = (rev1.get("text") or "").strip()
    text2 = (rev2.get("text") or "").strip()

    if not text1 or not text2:
        return False

    # Quick length check first
    if abs(len(text1) - len(text2)) > max(len(text1), len(text2)) * 0.3:
        return False

    similarity = SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    if similarity < DEDUP_TEXT_SIMILARITY:
        return False

    # Check date proximity
    date1 = (rev1.get("date") or rev1.get("publishedDate", ""))[:10]
    date2 = (rev2.get("date") or rev2.get("publishedDate", ""))[:10]

    if date1 and date2:
        try:
            d1 = datetime.strptime(date1, "%Y-%m-%d")
            d2 = datetime.strptime(date2, "%Y-%m-%d")
            if abs((d1 - d2).days) > DEDUP_DATE_WINDOW_DAYS:
                return False
        except ValueError:
            pass

    return True


def deduplicate(reviews: list) -> tuple[list, list]:
    """Remove duplicate reviews. Returns (unique, duplicates)."""
    unique = []
    duplicates = []

    for rev in reviews:
        is_dup = False
        for existing in unique:
            if is_duplicate(rev, existing):
                is_dup = True
                # Keep the version with richer metadata (more fields)
                rev_fields = sum(1 for v in rev.values() if v)
                existing_fields = sum(1 for v in existing.values() if v)
                if rev_fields > existing_fields:
                    unique.remove(existing)
                    unique.append(rev)
                    duplicates.append(existing)
                else:
                    duplicates.append(rev)
                break
        if not is_dup:
            unique.append(rev)

    return unique, duplicates


def process_restaurant(slug: str, reviews: list) -> tuple[list, list]:
    """Process reviews for a restaurant: deduplicate, classify, filter.

    Returns (included, excluded) review lists.
    """
    # Deduplicate
    unique, dupes = deduplicate(reviews)

    included = []
    excluded = []

    # Add duplicates to excluded
    for rev in dupes:
        rev["_quality"] = "EXCLUDE"
        rev["_exclude_reason"] = "duplicate"
        excluded.append(rev)

    # Classify and filter unique reviews
    for rev in unique:
        if detect_spam(rev):
            rev["_quality"] = "EXCLUDE"
            rev["_exclude_reason"] = "spam"
            excluded.append(rev)
            continue

        quality = classify_quality(rev)
        rev["_quality"] = quality

        if quality == "EXCLUDE":
            rev["_exclude_reason"] = "below_minimum"
            excluded.append(rev)
        else:
            included.append(rev)

    # Sort included by date (newest first)
    def sort_key(r):
        d = r.get("date") or r.get("publishedDate", "")
        return d if d else "0000-00-00"

    included.sort(key=sort_key, reverse=True)
    excluded.sort(key=sort_key, reverse=True)

    return included, excluded


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Load all raw reviews by source
    all_reviews = defaultdict(list)  # slug -> [reviews from all sources]

    for source in SOURCES:
        source_data = load_raw_reviews(source)
        for slug, reviews in source_data.items():
            all_reviews[slug].extend(reviews)

    if not all_reviews:
        log.info("No raw review data found in %s", RAW_DIR)
        return

    now = datetime.now(timezone.utc)
    month_str = now.strftime("%Y-%m")

    stats = {
        "restaurants": 0,
        "total_input": 0,
        "total_included": 0,
        "total_excluded": 0,
        "by_quality": {"HIGH": 0, "MEDIUM": 0, "LOW": 0},
        "by_source": defaultdict(int),
    }

    for slug in sorted(all_reviews.keys()):
        reviews = all_reviews[slug]
        stats["restaurants"] += 1
        stats["total_input"] += len(reviews)

        included, excluded = process_restaurant(slug, reviews)

        # Count stats
        stats["total_included"] += len(included)
        stats["total_excluded"] += len(excluded)
        for rev in included:
            q = rev.get("_quality", "LOW")
            stats["by_quality"][q] = stats["by_quality"].get(q, 0) + 1
            src = rev.get("source", "unknown")
            stats["by_source"][src] += 1

        # Save combined file
        if included:
            combined_path = PROCESSED_DIR / f"{slug}_{month_str}_combined.json"
            with open(combined_path, "w") as f:
                json.dump({
                    "slug": slug,
                    "month": month_str,
                    "generated_at": now.isoformat(),
                    "total_reviews": len(included),
                    "quality_breakdown": {
                        "HIGH": sum(1 for r in included if r.get("_quality") == "HIGH"),
                        "MEDIUM": sum(1 for r in included if r.get("_quality") == "MEDIUM"),
                        "LOW": sum(1 for r in included if r.get("_quality") == "LOW"),
                    },
                    "source_breakdown": {
                        src: sum(1 for r in included if r.get("source") == src)
                        for src in set(r.get("source", "unknown") for r in included)
                    },
                    "reviews": included,
                }, f, indent=2, ensure_ascii=False)

        # Save excluded file
        if excluded:
            excluded_path = PROCESSED_DIR / f"{slug}_{month_str}_excluded.json"
            with open(excluded_path, "w") as f:
                json.dump({
                    "slug": slug,
                    "month": month_str,
                    "generated_at": now.isoformat(),
                    "total_excluded": len(excluded),
                    "reviews": excluded,
                }, f, indent=2, ensure_ascii=False)

    # Print summary
    log.info("=" * 60)
    log.info("Multi-source merge complete:")
    log.info("  Restaurants: %d", stats["restaurants"])
    log.info("  Input reviews: %d", stats["total_input"])
    log.info("  Included: %d", stats["total_included"])
    log.info("  Excluded: %d", stats["total_excluded"])
    log.info("  Quality breakdown:")
    for q in ["HIGH", "MEDIUM", "LOW"]:
        log.info("    %s: %d", q, stats["by_quality"].get(q, 0))
    log.info("  Source breakdown:")
    for src, count in sorted(stats["by_source"].items()):
        log.info("    %s: %d", src, count)
    log.info("=" * 60)


if __name__ == "__main__":
    main()
