#!/usr/bin/env python3
"""
merge_multi_source_reviews.py — Merge and deduplicate reviews from all sources.

Reads data/raw/google/ and data/raw/tripadvisor/, groups by FHRSID,
deduplicates, quality-tags, and saves combined files to data/processed/.
"""

import difflib
import json
import os
import re
from collections import Counter
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
RAW_GOOGLE = os.path.join(REPO_DIR, "data", "raw", "google")
RAW_TA = os.path.join(REPO_DIR, "data", "raw", "tripadvisor")
PROCESSED = os.path.join(REPO_DIR, "data", "processed")

# Quality tagging keywords
ASPECT_KEYWORDS = {
    "food", "service", "atmosphere", "ambience", "value", "staff", "menu",
    "wine", "beer", "cocktail", "dessert", "starter", "main course",
    "booking", "reservation", "wait", "price", "portion", "fresh",
    "delicious", "friendly", "attentive", "clean", "cosy", "view",
}


def _is_owner_response(text):
    """Check if text looks like an owner response, not a customer review."""
    lower = text.lower().strip()
    patterns = [
        "thanks for your", "thank you for your review",
        "thank you for your 5", "thank you for your 4",
        "thank you for visiting", "thank you for dining",
        "we appreciate your", "glad you enjoyed",
        "thanks for the review", "thank you for the review",
    ]
    return any(lower.startswith(p) for p in patterns)


def quality_tag(review):
    """Tag a review with quality: HIGH, MEDIUM, LOW, or EXCLUDE."""
    text = (review.get("text") or "").strip()
    words = text.split()
    word_count = len(words)

    if word_count < 5:
        return "EXCLUDE"

    # Owner responses are not customer reviews
    if _is_owner_response(text):
        return "EXCLUDE"

    # Spam detection
    if text.isupper() and word_count > 3:
        return "EXCLUDE"
    if re.search(r'(.)\1{5,}', text):  # repeated characters
        return "EXCLUDE"
    if re.search(r'https?://', text):
        return "EXCLUDE"

    text_lower = text.lower()
    has_aspect = any(kw in text_lower for kw in ASPECT_KEYWORDS)

    if word_count >= 50 and has_aspect:
        return "HIGH"
    elif word_count >= 20 or has_aspect:
        return "MEDIUM"
    else:
        return "LOW"


def is_duplicate(rev_a, rev_b, similarity_threshold=0.8):
    """Check if two reviews are likely duplicates."""
    text_a = (rev_a.get("text") or "").strip()
    text_b = (rev_b.get("text") or "").strip()

    if not text_a or not text_b:
        return False

    # Quick check: same rating required
    if rev_a.get("rating") != rev_b.get("rating"):
        return False

    # Text similarity
    ratio = difflib.SequenceMatcher(None, text_a.lower(), text_b.lower()).ratio()
    return ratio >= similarity_threshold


def load_raw_files(directory, source_name):
    """Load all JSON files from a raw directory."""
    files = {}
    if not os.path.exists(directory):
        return files
    for fname in os.listdir(directory):
        if not fname.endswith(".json") or fname == ".gitkeep":
            continue
        path = os.path.join(directory, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            fhrsid = data.get("fhrsid", "")
            if fhrsid:
                if fhrsid not in files:
                    files[fhrsid] = []
                for rev in data.get("reviews", []):
                    rev["source"] = source_name
                    rev["_source_file"] = fname
                files[fhrsid].extend(data.get("reviews", []))
                # Store metadata
                if "_meta" not in files:
                    files["_meta"] = {}
                files.setdefault("_meta", {})[fhrsid] = {
                    "name": data.get("name"),
                    "collected_at": data.get("collected_at"),
                    "total_found": data.get("total_reviews_found") or data.get("tripadvisor_review_count"),
                }
        except (json.JSONDecodeError, IOError) as e:
            print(f"  Warning: could not read {path}: {e}")
    return files


def main():
    print("Multi-Source Review Merger")
    os.makedirs(PROCESSED, exist_ok=True)

    # Load all raw data
    google_data = load_raw_files(RAW_GOOGLE, "google")
    ta_data = load_raw_files(RAW_TA, "tripadvisor")

    # Collect all FHRSIDs
    all_fhrsids = set()
    for d in [google_data, ta_data]:
        all_fhrsids.update(k for k in d.keys() if k != "_meta")

    if not all_fhrsids:
        print("No raw review data found.")
        return

    period = datetime.utcnow().strftime("%Y-%m")
    total_merged = 0

    for fhrsid in sorted(all_fhrsids):
        google_reviews = google_data.get(fhrsid, [])
        ta_reviews = ta_data.get(fhrsid, [])
        all_reviews = google_reviews + ta_reviews

        if not all_reviews:
            continue

        # Get venue name from metadata
        name = "Unknown"
        for meta_source in [google_data.get("_meta", {}), ta_data.get("_meta", {})]:
            if fhrsid in meta_source and meta_source[fhrsid].get("name"):
                name = meta_source[fhrsid]["name"]
                break

        # Deduplicate
        kept = []
        excluded_dupes = []
        for rev in all_reviews:
            is_dupe = False
            for existing in kept:
                if is_duplicate(rev, existing):
                    is_dupe = True
                    excluded_dupes.append(rev)
                    break
            if not is_dupe:
                kept.append(rev)

        # Quality tag
        tagged = []
        excluded = []
        by_quality = Counter()
        for rev in kept:
            tag = quality_tag(rev)
            rev["quality"] = tag
            if tag == "EXCLUDE":
                excluded.append(rev)
            else:
                tagged.append(rev)
            by_quality[tag] += 1

        # Source counts
        by_source = Counter(r.get("source", "unknown") for r in tagged)
        reviews_with_text = sum(1 for r in tagged if (r.get("text") or "").strip())

        # Word count stats
        word_counts = [len((r.get("text") or "").split()) for r in tagged if r.get("text")]
        avg_words = round(sum(word_counts) / len(word_counts)) if word_counts else 0

        # Date range
        dates = [r.get("date") or r.get("published_date") or "" for r in tagged]
        dates = sorted([d for d in dates if d and d > "2000"])
        date_range = {"earliest": dates[0], "latest": dates[-1]} if dates else None

        slug = slugify(name)

        # Save combined
        combined = {
            "fhrsid": fhrsid,
            "name": name,
            "period": period,
            "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "summary": {
                "total_reviews": len(tagged),
                "by_source": dict(by_source),
                "by_quality": dict(by_quality),
                "reviews_with_text": reviews_with_text,
                "avg_review_length_words": avg_words,
                "date_range": date_range,
                "duplicates_removed": len(excluded_dupes),
            },
            "reviews": tagged,
        }

        combined_path = os.path.join(PROCESSED, f"{slug}_{period}_combined.json")
        with open(combined_path, "w", encoding="utf-8") as f:
            json.dump(combined, f, indent=2, ensure_ascii=False)

        # Save excluded
        if excluded or excluded_dupes:
            excluded_path = os.path.join(PROCESSED, f"{slug}_{period}_excluded.json")
            with open(excluded_path, "w", encoding="utf-8") as f:
                json.dump({"excluded": excluded, "duplicates": excluded_dupes}, f, indent=2)

        total_merged += 1
        sources = "+".join(f"{s}:{c}" for s, c in by_source.items())
        print(f"  {name}: {len(tagged)} reviews ({sources}), "
              f"{len(excluded_dupes)} dupes removed, quality: {dict(by_quality)}")

    print(f"\nMerged {total_merged} restaurants to {PROCESSED}/")


def slugify(name):
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')[:60]


if __name__ == "__main__":
    main()
