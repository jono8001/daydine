#!/usr/bin/env python3
"""
merge_enrichment.py — Merge Google enrichment data into establishments JSON.

Also merges processed review data from data/processed/ into establishments
when --include-reviews flag is passed, feeding into the existing
review_delta.py / review_analysis.py pipeline via g_reviews/ta_reviews arrays.
"""

import json
import os
import sys


def merge_google_enrichment(establishments):
    """Merge Google Places API enrichment data."""
    enrich_path = "stratford_google_enrichment.json"
    if not os.path.exists(enrich_path):
        print(f"No enrichment file found ({enrich_path}), skipping Google merge")
        return 0

    with open(enrich_path, "r", encoding="utf-8") as f:
        enrichment = json.load(f)

    merged = 0
    for key, google_data in enrichment.items():
        if key not in establishments:
            continue
        if google_data.get("_no_match"):
            continue
        for field in ["gr", "grc", "gpl", "gty", "gpc", "gpid", "goh", "g_reviews"]:
            if field in google_data:
                establishments[key][field] = google_data[field]
        merged += 1

    print(f"Merged Google API data for {merged}/{len(establishments)} establishments")
    return merged


def merge_processed_reviews(establishments):
    """Merge processed review files into establishments for the existing pipeline."""
    processed_dir = "data/processed"
    if not os.path.exists(processed_dir):
        print("No processed review data found, skipping review merge")
        return 0

    merged = 0
    for fname in os.listdir(processed_dir):
        if not fname.endswith("_combined.json"):
            continue
        path = os.path.join(processed_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue

        fhrsid = data.get("fhrsid", "")
        if fhrsid not in establishments:
            continue

        reviews = data.get("reviews", [])
        if not reviews:
            continue

        rec = establishments[fhrsid]

        # Split reviews by source for backwards compatibility
        g_reviews = []
        ta_reviews = []
        for rev in reviews:
            source = rev.get("source", "")
            review_rec = {
                "text": rev.get("text", ""),
                "rating": rev.get("rating"),
            }
            if source == "google":
                review_rec["time"] = rev.get("date_raw", "")
                g_reviews.append(review_rec)
            elif source == "tripadvisor":
                review_rec["date"] = rev.get("published_date", "")
                review_rec["title"] = rev.get("title", "")
                review_rec["username"] = rev.get("reviewer_name", "")
                review_rec["source"] = "tripadvisor"
                ta_reviews.append(review_rec)

        # Only update if we have more reviews than currently stored
        existing_g = len(rec.get("g_reviews", []))
        existing_ta = len(rec.get("ta_reviews", []))

        if len(g_reviews) > existing_g:
            rec["g_reviews"] = g_reviews

        if len(ta_reviews) > existing_ta:
            rec["ta_reviews"] = ta_reviews
            # Also update TA metadata
            rec["ta_present"] = True
            rec["trc"] = len(ta_reviews)
            # Calculate average TA rating
            ta_ratings = [r["rating"] for r in ta_reviews if r.get("rating")]
            if ta_ratings:
                rec["ta"] = round(sum(ta_ratings) / len(ta_ratings), 1)

        merged += 1

    print(f"Merged processed reviews for {merged} establishments")
    return merged


def main():
    est_path = "stratford_establishments.json"

    if not os.path.exists(est_path):
        print(f"ERROR: {est_path} not found")
        sys.exit(1)

    with open(est_path, "r", encoding="utf-8") as f:
        establishments = json.load(f)

    # Always merge Google enrichment
    merge_google_enrichment(establishments)

    # Merge processed reviews if flag is passed
    if "--include-reviews" in sys.argv:
        merge_processed_reviews(establishments)

    # Save
    with open(est_path, "w", encoding="utf-8") as f:
        json.dump(establishments, f, indent=2, ensure_ascii=False)

    # Stats
    with_rating = sum(1 for v in establishments.values() if v.get("gr") is not None)
    with_g_reviews = sum(1 for v in establishments.values() if v.get("g_reviews"))
    with_ta = sum(1 for v in establishments.values() if v.get("ta_present"))
    print(f"  With Google rating: {with_rating}")
    print(f"  With Google review text: {with_g_reviews}")
    print(f"  With TripAdvisor data: {with_ta}")


if __name__ == "__main__":
    main()
