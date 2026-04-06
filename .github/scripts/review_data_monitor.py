#!/usr/bin/env python3
"""
review_data_monitor.py — Collection health monitoring.

Scans data/raw/ and data/processed/ directories and reports on
collection quality, coverage, and confidence tiers.
"""

import json
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
PROCESSED = os.path.join(REPO_DIR, "data", "processed")
RAW_GOOGLE = os.path.join(REPO_DIR, "data", "raw", "google")
RAW_TA = os.path.join(REPO_DIR, "data", "raw", "tripadvisor")
HEALTH_PATH = os.path.join(REPO_DIR, "data", "collection_health.json")
LOG_PATH = os.path.join(REPO_DIR, "data", "collection_log.txt")


def confidence_tier(total_reviews):
    if total_reviews >= 100:
        return "Robust"
    elif total_reviews >= 50:
        return "Reliable"
    elif total_reviews >= 25:
        return "Directional"
    else:
        return "Indicative"


def main():
    print("Review Data Monitor")
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M")

    venues = {}
    any_failure = False

    # Scan processed files
    if os.path.exists(PROCESSED):
        for fname in os.listdir(PROCESSED):
            if fname.endswith("_combined.json"):
                path = os.path.join(PROCESSED, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    fhrsid = data.get("fhrsid", fname)
                    summary = data.get("summary", {})
                    venues[fhrsid] = {
                        "name": data.get("name"),
                        "total_reviews": summary.get("total_reviews", 0),
                        "by_source": summary.get("by_source", {}),
                        "reviews_with_text": summary.get("reviews_with_text", 0),
                        "avg_length": summary.get("avg_review_length_words", 0),
                        "date_range": summary.get("date_range"),
                        "confidence": confidence_tier(summary.get("total_reviews", 0)),
                        "below_minimum": summary.get("total_reviews", 0) < 50,
                    }
                except Exception as e:
                    print(f"  Warning: {fname}: {e}")

    # Count raw files by source
    google_count = len([f for f in os.listdir(RAW_GOOGLE)
                        if f.endswith(".json") and f != ".gitkeep"]) if os.path.exists(RAW_GOOGLE) else 0
    ta_count = len([f for f in os.listdir(RAW_TA)
                    if f.endswith(".json") and f != ".gitkeep"]) if os.path.exists(RAW_TA) else 0

    # Summary
    total_venues = len(venues)
    below_min = sum(1 for v in venues.values() if v["below_minimum"])
    total_reviews = sum(v["total_reviews"] for v in venues.values())

    health = {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "raw_files": {"google": google_count, "tripadvisor": ta_count},
        "venues_with_data": total_venues,
        "total_reviews": total_reviews,
        "below_minimum_threshold": below_min,
        "venues": venues,
    }

    # Save health file
    os.makedirs(os.path.dirname(HEALTH_PATH), exist_ok=True)
    with open(HEALTH_PATH, "w", encoding="utf-8") as f:
        json.dump(health, f, indent=2, ensure_ascii=False)

    # Append to log
    log_lines = []
    for fhrsid, v in venues.items():
        sources = ", ".join(f"{s}:{c}" for s, c in v["by_source"].items())
        log_lines.append(f"[{now}] {v['name']}: {v['total_reviews']} reviews ({sources}) "
                         f"— {v['confidence']}")
    log_lines.append(f"[{now}] SUMMARY: {total_venues} restaurants, {total_reviews} total reviews, "
                     f"{below_min} below threshold")

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")

    # Print
    print(f"\n  Raw files: {google_count} Google, {ta_count} TripAdvisor")
    print(f"  Processed venues: {total_venues}")
    print(f"  Total reviews: {total_reviews}")
    print(f"  Below minimum (50): {below_min}")
    for fhrsid, v in venues.items():
        flag = " ⚠️" if v["below_minimum"] else " ✅"
        print(f"    {v['name']}: {v['total_reviews']} reviews [{v['confidence']}]{flag}")

    if google_count == 0 and ta_count == 0:
        print("\n  WARNING: No raw review data found — collection may have failed")
        any_failure = True

    if any_failure:
        sys.exit(1)


if __name__ == "__main__":
    import sys
    main()
