#!/usr/bin/env python3
"""
merge_tripadvisor.py — Merge TripAdvisor data into establishments JSON.

Reads stratford_tripadvisor.json and merges ta (rating), trc (review count),
ta_url, ta_present, ta_cuisines, ta_reviews, ta_ranking fields.
Also computes ta_recency_score (0-1) from review dates.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

NOW = datetime.now(timezone.utc)


def compute_review_recency(reviews):
    """
    Compute what fraction of reviews are recent (last 6 months).
    Returns score 0-1 where 1 = all reviews are recent.

    Parses relative time strings like "a month ago", "2 weeks ago",
    "3 months ago", "a year ago", or ISO date strings.
    """
    if not reviews:
        return None

    recent = 0
    total = 0

    for rev in reviews:
        total += 1
        # Try date field first
        date_str = rev.get("date", "") or rev.get("time", "")
        if not date_str:
            continue

        is_recent = False
        d = date_str.lower().strip()

        # Parse relative time descriptions
        if "ago" in d:
            if any(w in d for w in ["a week", "1 week", "2 weeks", "3 weeks",
                                     "a day", "1 day", "2 day", "3 day",
                                     "yesterday", "today"]):
                is_recent = True
            elif "a month" in d or "1 month" in d or "2 month" in d:
                is_recent = True
            elif "3 month" in d or "4 month" in d or "5 month" in d or "6 month" in d:
                is_recent = True
            # "a year ago", "2 years ago" etc. = not recent
        else:
            # Try parsing ISO date
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                days = (NOW - dt).days
                is_recent = days <= 180
            except (ValueError, TypeError):
                pass

        if is_recent:
            recent += 1

    if total == 0:
        return None
    return round(recent / total, 2)


def main():
    est_path = "stratford_establishments.json"
    ta_path = "stratford_tripadvisor.json"

    if not os.path.exists(est_path):
        print(f"ERROR: {est_path} not found")
        sys.exit(1)

    with open(est_path, "r", encoding="utf-8") as f:
        establishments = json.load(f)

    if not os.path.exists(ta_path):
        print(f"No TripAdvisor data found ({ta_path}), skipping merge")
        return

    with open(ta_path, "r", encoding="utf-8") as f:
        ta_data = json.load(f)

    merged = 0
    recency_count = 0
    for key, ta_record in ta_data.items():
        if key not in establishments:
            continue
        if ta_record.get("_skipped") or ta_record.get("_no_match") or ta_record.get("_error"):
            continue

        est = establishments[key]

        if ta_record.get("ta") is not None:
            est["ta"] = ta_record["ta"]
            est["ta_present"] = True
            merged += 1
        if ta_record.get("trc") is not None:
            est["trc"] = ta_record["trc"]
        if ta_record.get("ta_url"):
            est["ta_url"] = ta_record["ta_url"]
        if ta_record.get("ta_cuisines"):
            est["ta_cuisines"] = ta_record["ta_cuisines"]
        if ta_record.get("ta_price"):
            est["ta_price"] = ta_record["ta_price"]
        if ta_record.get("ta_reviews"):
            est["ta_reviews"] = ta_record["ta_reviews"]
            # Compute review recency
            recency = compute_review_recency(ta_record["ta_reviews"])
            if recency is not None:
                est["ta_recency"] = recency
                recency_count += 1
        if ta_record.get("ta_ranking"):
            est["ta_ranking"] = ta_record["ta_ranking"]

    with open(est_path, "w", encoding="utf-8") as f:
        json.dump(establishments, f, indent=2, ensure_ascii=False)

    with_ta = sum(1 for v in establishments.values() if v.get("ta") is not None)
    print(f"Merged TripAdvisor data for {merged} establishments")
    print(f"  With TA rating: {with_ta}/{len(establishments)}")
    print(f"  With recency score: {recency_count}")


if __name__ == "__main__":
    main()
