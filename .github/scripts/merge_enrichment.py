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
    web_from_api = 0
    phone_from_api = 0
    reservable_from_api = 0
    for key, google_data in enrichment.items():
        if key not in establishments:
            continue
        if google_data.get("_no_match"):
            continue
        # Core fields
        for field in ["gr", "grc", "gpl", "gty", "gpc", "gpid", "goh",
                      "g_reviews"]:
            if field in google_data:
                establishments[key][field] = google_data[field]

        # Commercial Readiness customer-path fields (V4 spec §5)
        est = establishments[key]
        website_uri = google_data.get("websiteUri") or google_data.get("web_url")
        if website_uri:
            est["web"] = True
            est["web_url"] = website_uri
            web_from_api += 1
        # phone (prefer national, fall back to international)
        phone = (google_data.get("phone")
                 or google_data.get("nationalPhoneNumber")
                 or google_data.get("internationalPhoneNumber"))
        if phone:
            est["phone"] = phone
            phone_from_api += 1
        # reservable (boolean from Google)
        if "reservable" in google_data:
            est["reservable"] = bool(google_data["reservable"])
            if est["reservable"]:
                reservable_from_api += 1
        # business_status (for V4 §7.4 closure handling)
        if google_data.get("business_status"):
            est["business_status"] = google_data["business_status"]

        merged += 1

    print(f"Merged Google API data for {merged}/{len(establishments)} "
          f"establishments")
    if web_from_api or phone_from_api or reservable_from_api:
        print(f"  Observed customer-path signals: "
              f"web={web_from_api}, phone={phone_from_api}, "
              f"reservable={reservable_from_api}")
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
            text = rev.get("text", "").strip()

            # Skip owner responses — these are not customer reviews
            text_lower = text.lower()
            if any(text_lower.startswith(p) for p in [
                "thanks for your", "thank you for your review",
                "thank you for your 5", "thank you for your 4",
                "thank you for your 3", "thank you for visiting",
                "thank you for dining", "we appreciate your",
                "glad you enjoyed", "thanks for the review",
                "thank you for the review",
            ]):
                continue

            source = rev.get("source", "")
            review_rec = {
                "text": text,
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

        # Always update with cleaned reviews (owner responses filtered above)
        if g_reviews:
            rec["g_reviews"] = g_reviews

        if ta_reviews:
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
