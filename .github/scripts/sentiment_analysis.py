#!/usr/bin/env python3
"""
sentiment_analysis.py — Aspect-based review sentiment analysis.

Processes Google + TripAdvisor review text to produce:
- Overall sentiment score (0-1)
- 5 aspect sub-scores (0-10): Food, Service, Ambience, Value, Wait Time
- Red flag warnings

No external AI API — pure keyword/pattern matching.

Usage:
    python .github/scripts/sentiment_analysis.py

Reads:  stratford_establishments.json
Writes: stratford_sentiment.json
"""

import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# ---------------------------------------------------------------------------
# Overall sentiment keywords (kept from V1)
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
    "overpriced", "rip off", "rip-off", "not worth",
]

POSITIVES = [
    "amazing", "excellent", "outstanding", "exceptional", "superb",
    "best restaurant", "best meal", "best food",
    "highly recommend", "would recommend",
    "fantastic", "fabulous", "phenomenal", "incredible",
    "delicious", "mouth-watering", "perfectly cooked",
    "perfect", "faultless", "wonderful", "lovely",
    "friendly staff", "great service", "attentive service",
    "will definitely return", "will be back",
    "hidden gem", "must visit", "five stars", "5 stars", "10/10",
]

NEGATIVES = [
    "disappointing", "disappointed", "mediocre", "average at best",
    "nothing special", "overrated", "bland", "tasteless",
    "slow service", "poor service", "bad service",
    "small portions", "won't return",
]

# ---------------------------------------------------------------------------
# Aspect keyword dictionaries — positive and negative for each
# ---------------------------------------------------------------------------

ASPECT_KEYWORDS = {
    "food_quality": {
        "pos": [
            "delicious", "tasty", "flavourful", "flavorful", "flavour",
            "fresh", "perfectly cooked", "well cooked", "great food",
            "excellent food", "amazing food", "best food",
            "gorgeous presentation", "beautifully presented",
            "mouth-watering", "mouthwatering", "tender", "succulent",
            "crispy", "juicy", "authentic", "homemade", "home made",
        ],
        "neg": [
            "bland", "tasteless", "stale", "dry", "tough", "chewy",
            "undercooked", "overcooked", "raw", "burnt", "cold food",
            "stone cold", "lukewarm", "frozen", "reheated", "microwaved",
            "greasy", "oily", "salty", "inedible", "disgusting",
            "poor food", "terrible food", "bad food", "awful food",
        ],
    },
    "service_quality": {
        "pos": [
            "friendly", "attentive", "helpful", "professional",
            "welcoming", "polite", "courteous", "warm welcome",
            "great service", "excellent service", "fantastic service",
            "amazing service", "brilliant service", "superb service",
            "knowledgeable", "accommodating", "went above and beyond",
        ],
        "neg": [
            "rude", "rude staff", "rude waiter", "rude waitress",
            "unfriendly", "unhelpful", "disinterested", "ignored",
            "poor service", "bad service", "terrible service",
            "slow service", "inattentive", "couldn't care less",
            "no apology", "unprofessional", "arrogant",
        ],
    },
    "ambience": {
        "pos": [
            "great atmosphere", "lovely atmosphere", "fantastic atmosphere",
            "cosy", "cozy", "charming", "romantic", "intimate",
            "beautiful decor", "lovely decor", "stylish", "elegant",
            "clean", "spotless", "well maintained", "gorgeous setting",
            "lovely setting", "great ambiance", "wonderful ambience",
        ],
        "neg": [
            "noisy", "too loud", "deafening", "cramped", "crowded",
            "dirty", "filthy", "grubby", "smelly", "stuffy",
            "cold", "draughty", "dark", "dingy", "tired decor",
            "run down", "needs a refurb", "dated",
        ],
    },
    "value": {
        "pos": [
            "good value", "great value", "excellent value",
            "worth every penny", "worth it", "reasonable",
            "reasonably priced", "affordable", "bargain",
            "generous portions", "huge portions", "good portions",
            "fair price", "well priced", "cheap and cheerful",
        ],
        "neg": [
            "overpriced", "expensive", "rip off", "rip-off",
            "not worth", "poor value", "bad value", "daylight robbery",
            "small portions", "tiny portions", "stingy",
            "too expensive", "sky high prices", "extortionate",
        ],
    },
    "wait_time": {
        "pos": [
            "quick", "prompt", "fast", "no wait", "didn't wait long",
            "seated immediately", "efficient", "speedy",
            "food came quickly", "food arrived quickly",
        ],
        "neg": [
            "long wait", "waited over an hour", "waited 45 minutes",
            "waited forever", "slow", "took ages", "took so long",
            "still waiting", "had to chase", "forgot our order",
            "wrong order", "waited 30 minutes", "waited an hour",
        ],
    },
}


def score_aspect(texts, aspect_name):
    """
    Score a single aspect from 0-10 based on keyword matches.
    Returns (score, pos_count, neg_count) or (None, 0, 0) if no mentions.
    """
    keywords = ASPECT_KEYWORDS.get(aspect_name)
    if not keywords:
        return None, 0, 0

    pos_count = 0
    neg_count = 0

    for text in texts:
        t = text.lower()
        for kw in keywords["pos"]:
            if kw in t:
                pos_count += 1
        for kw in keywords["neg"]:
            if kw in t:
                neg_count += 1

    total = pos_count + neg_count
    if total == 0:
        return None, 0, 0

    # Score: ratio of positive to total, scaled to 0-10
    raw = pos_count / total  # 0-1
    score = round(raw * 10, 1)
    return score, pos_count, neg_count


def compute_overall_sentiment(texts):
    """Compute overall sentiment 0-1 from review texts."""
    total_pos = 0
    total_neg = 0
    total_red = 0
    red_list = []

    for text in texts:
        t = text.lower()
        for p in RED_FLAGS:
            if p in t:
                total_red += 1
                red_list.append(p)
        for p in POSITIVES:
            if p in t:
                total_pos += 1
        for p in NEGATIVES:
            if p in t:
                total_neg += 1

    score = 0.5 + total_pos * 0.05 - total_neg * 0.08 - total_red * 0.15
    score = max(0.0, min(1.0, score))

    return {
        "sentiment_score": round(score, 3),
        "positive_count": total_pos,
        "negative_count": total_neg,
        "red_flag_count": total_red,
        "red_flags": list(set(red_list)),
        "warning": total_red >= 2,
    }


def analyze_establishment(record):
    """
    Full analysis: overall sentiment + 5 aspect scores.
    Combines Google reviews (g_reviews) and TripAdvisor reviews (ta_reviews).
    """
    texts = []
    for rev in record.get("g_reviews", []):
        t = rev.get("text", "")
        if t:
            texts.append(t)
    for rev in record.get("ta_reviews", []):
        t = rev.get("text", "")
        if t:
            texts.append(t)

    if not texts:
        return None

    result = compute_overall_sentiment(texts)
    result["reviews_analyzed"] = len(texts)

    # Aspect scores
    aspects = {}
    for aspect in ["food_quality", "service_quality", "ambience", "value", "wait_time"]:
        score, pos, neg = score_aspect(texts, aspect)
        if score is not None:
            aspects[aspect] = {
                "score": score,
                "positive_mentions": pos,
                "negative_mentions": neg,
            }

    result["aspects"] = aspects
    return result


def main():
    est_path = os.path.join(REPO_ROOT, "stratford_establishments.json")
    output_path = os.path.join(REPO_ROOT, "stratford_sentiment.json")

    if not os.path.exists(est_path):
        print(f"ERROR: {est_path} not found")
        sys.exit(1)

    with open(est_path, "r", encoding="utf-8") as f:
        establishments = json.load(f)

    print("Analyzing review sentiment (aspect-based)...")
    results = {}
    warnings = 0

    for key, record in establishments.items():
        analysis = analyze_establishment(record)
        if analysis:
            results[key] = analysis
            name = record.get("n", "Unknown")
            if analysis["warning"]:
                warnings += 1
                flags = ", ".join(analysis["red_flags"][:3])
                print(f"  WARNING: {name} — {analysis['red_flag_count']} red flags: {flags}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    analyzed = len(results)
    avg = sum(r["sentiment_score"] for r in results.values()) / analyzed if analyzed else 0

    # Aspect coverage
    aspect_counts = {}
    for r in results.values():
        for a in r.get("aspects", {}):
            aspect_counts[a] = aspect_counts.get(a, 0) + 1

    print(f"\nDone. Analyzed: {analyzed} establishments")
    print(f"  Overall sentiment avg: {avg:.3f}")
    print(f"  Warnings: {warnings}")
    print(f"  Aspect coverage:")
    for a, c in sorted(aspect_counts.items()):
        print(f"    {a}: {c}/{analyzed}")
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
