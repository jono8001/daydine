#!/usr/bin/env python3
"""
sentiment_analysis.py — Keyword-based review sentiment analysis.

Processes Google review text to produce a sentiment score (0-1) and
red flag warnings without using any external AI API.

Can be run standalone to analyze stratford_google_enrichment.json,
or imported as a module by the scoring pipeline.

Usage:
    python .github/scripts/sentiment_analysis.py

Reads:  stratford_google_enrichment.json OR stratford_establishments.json
Writes: stratford_sentiment.json
"""

import json
import os
import re
import sys
from collections import Counter

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# ---------------------------------------------------------------------------
# Keyword dictionaries
# ---------------------------------------------------------------------------

RED_FLAGS = [
    "food poisoning", "sick after", "made me sick", "made us sick",
    "dirty", "filthy", "cockroach", "cockroaches", "rat ", "rats ",
    "mouse", "mice", "hair in", "hair found", "cold food", "stone cold",
    "raw chicken", "raw meat", "undercooked", "pink chicken",
    "rude staff", "rude waiter", "rude waitress", "rude manager",
    "worst restaurant", "worst meal", "worst experience", "worst food",
    "disgusting", "revolting", "inedible", "never again", "never go back",
    "avoid at all costs", "avoid this", "do not go", "don't go",
    "health hazard", "health and safety", "shut down", "closed down",
    "food was off", "gone off", "smelled off", "tasted off",
    "long wait", "waited over an hour", "waited 45 minutes",
    "overpriced", "rip off", "rip-off", "not worth",
]

POSITIVE_PHRASES = [
    "amazing", "excellent", "outstanding", "exceptional", "superb",
    "best restaurant", "best meal", "best food", "best we've had",
    "highly recommend", "would recommend", "can't recommend enough",
    "fantastic", "fabulous", "phenomenal", "incredible",
    "delicious", "mouth-watering", "mouthwatering", "perfectly cooked",
    "perfect", "perfection", "faultless", "flawless",
    "wonderful", "lovely", "beautiful", "gorgeous presentation",
    "friendly staff", "great service", "attentive service",
    "will definitely return", "will be back", "coming back",
    "hidden gem", "gem of a place", "must visit",
    "five stars", "5 stars", "10 out of 10", "10/10",
    "michelin quality", "michelin standard",
]

# Moderate negatives (less severe than red flags)
NEGATIVES = [
    "disappointing", "disappointed", "mediocre", "average at best",
    "nothing special", "overrated", "let down", "not great",
    "bland", "tasteless", "dry", "tough", "chewy",
    "slow service", "poor service", "bad service", "terrible service",
    "small portions", "tiny portions",
    "noisy", "too loud", "cramped",
    "won't return", "won't be back",
]


def analyze_review_text(text):
    """
    Analyze a single review text for sentiment signals.
    Returns dict with red_flags, positives, negatives found.
    """
    text_lower = text.lower()
    found_red = []
    found_pos = []
    found_neg = []

    for phrase in RED_FLAGS:
        if phrase in text_lower:
            found_red.append(phrase)

    for phrase in POSITIVE_PHRASES:
        if phrase in text_lower:
            found_pos.append(phrase)

    for phrase in NEGATIVES:
        if phrase in text_lower:
            found_neg.append(phrase)

    return {
        "red_flags": found_red,
        "positives": found_pos,
        "negatives": found_neg,
    }


def compute_sentiment_score(reviews):
    """
    Compute a sentiment score (0.0-1.0) from a list of review dicts.

    Each review should have 'text' and optionally 'rating'.

    Score formula:
        base = 0.5 (neutral)
        + 0.05 per positive phrase found (across all reviews)
        - 0.08 per negative phrase found
        - 0.15 per red flag found
        Clamped to [0.0, 1.0]

    Also returns red_flag_count and warning flag.
    """
    if not reviews:
        return None

    total_pos = 0
    total_neg = 0
    total_red = 0
    all_red_flags = []
    all_positives = []

    for rev in reviews:
        text = rev.get("text", "")
        if not text:
            continue

        result = analyze_review_text(text)
        total_pos += len(result["positives"])
        total_neg += len(result["negatives"])
        total_red += len(result["red_flags"])
        all_red_flags.extend(result["red_flags"])
        all_positives.extend(result["positives"])

    # Compute score
    score = 0.5
    score += total_pos * 0.05
    score -= total_neg * 0.08
    score -= total_red * 0.15
    score = max(0.0, min(1.0, score))

    return {
        "sentiment_score": round(score, 3),
        "positive_count": total_pos,
        "negative_count": total_neg,
        "red_flag_count": total_red,
        "red_flags": list(set(all_red_flags)),
        "positives_sample": list(set(all_positives))[:5],
        "warning": total_red >= 2,
        "reviews_analyzed": len([r for r in reviews if r.get("text")]),
    }


def process_establishments(est_path):
    """
    Process all establishments and compute sentiment scores.
    Returns dict of {key: sentiment_result}.
    """
    with open(est_path, "r", encoding="utf-8") as f:
        establishments = json.load(f)

    results = {}
    warnings = 0

    for key, record in establishments.items():
        reviews = record.get("g_reviews", [])
        if not reviews:
            continue

        sentiment = compute_sentiment_score(reviews)
        if sentiment:
            results[key] = sentiment
            name = record.get("n", "Unknown")
            if sentiment["warning"]:
                warnings += 1
                flags = ", ".join(sentiment["red_flags"][:3])
                print(f"  WARNING: {name} — {sentiment['red_flag_count']} red flags: {flags}")

    return results, warnings


def main():
    # Try establishments first (has merged reviews), fall back to enrichment
    est_path = os.path.join(REPO_ROOT, "stratford_establishments.json")
    output_path = os.path.join(REPO_ROOT, "stratford_sentiment.json")

    if not os.path.exists(est_path):
        print(f"ERROR: {est_path} not found")
        sys.exit(1)

    print("Analyzing review sentiment...")
    results, warning_count = process_establishments(est_path)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    analyzed = len(results)
    avg_score = sum(r["sentiment_score"] for r in results.values()) / analyzed if analyzed else 0
    print(f"\nDone. Analyzed: {analyzed} establishments")
    print(f"  Average sentiment: {avg_score:.3f}")
    print(f"  Warnings (2+ red flags): {warning_count}")
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
