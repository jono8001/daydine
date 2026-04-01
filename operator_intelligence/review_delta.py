"""
operator_intelligence/review_delta.py — Review Narrative Delta Engine

Two modes:
  A. NARRATIVE-RICH: When actual review text exists (g_reviews / ta_reviews),
     perform keyword-based aspect sentiment, extract quotes, detect themes.
  B. STRUCTURED-SIGNAL: When no review text, return explicit "no narrative data"
     flag. Never fabricate themes from star ratings alone.

Persists theme snapshots month-over-month for delta detection.
"""

import json
import os
from collections import Counter

HISTORY_DIR = "history/review_themes"

# ---------------------------------------------------------------------------
# Keyword → theme mapping for real review text analysis
# ---------------------------------------------------------------------------

THEME_MAP = {
    # Praise
    "delicious": ("food_quality", "pos"), "tasty": ("food_quality", "pos"),
    "fresh": ("food_quality", "pos"), "perfectly cooked": ("food_quality", "pos"),
    "amazing food": ("food_quality", "pos"), "excellent food": ("food_quality", "pos"),
    "authentic": ("food_quality", "pos"), "homemade": ("food_quality", "pos"),
    "great food": ("food_quality", "pos"), "gorgeous": ("food_quality", "pos"),
    "bursting with flavor": ("food_quality", "pos"), "well spiced": ("food_quality", "pos"),
    "piping hot": ("food_quality", "pos"), "best indian": ("food_quality", "pos"),
    "friendly": ("service", "pos"), "attentive": ("service", "pos"),
    "professional": ("service", "pos"), "great service": ("service", "pos"),
    "welcoming": ("service", "pos"), "helpful": ("service", "pos"),
    "super friendly": ("service", "pos"), "super attentive": ("service", "pos"),
    "cosy": ("ambience", "pos"), "cozy": ("ambience", "pos"),
    "charming": ("ambience", "pos"), "great atmosphere": ("ambience", "pos"),
    "dog-friendly": ("ambience", "pos"), "pet-friendly": ("ambience", "pos"),
    "good value": ("value", "pos"), "generous portions": ("value", "pos"),
    "affordable": ("value", "pos"), "worth every penny": ("value", "pos"),
    "good selection": ("value", "pos"), "extensive menu": ("value", "pos"),
    "quick": ("speed", "pos"), "prompt": ("speed", "pos"),
    "efficient": ("speed", "pos"), "on time": ("speed", "pos"),
    # Criticism
    "bland": ("food_quality", "neg"), "tasteless": ("food_quality", "neg"),
    "undercooked": ("food_quality", "neg"), "cold food": ("food_quality", "neg"),
    "overcooked": ("food_quality", "neg"), "stale": ("food_quality", "neg"),
    "dry": ("food_quality", "neg"), "greasy": ("food_quality", "neg"),
    "rude": ("service", "neg"), "unfriendly": ("service", "neg"),
    "slow service": ("service", "neg"), "ignored": ("service", "neg"),
    "poor service": ("service", "neg"), "unprofessional": ("service", "neg"),
    "dirty": ("cleanliness", "neg"), "filthy": ("cleanliness", "neg"),
    "noisy": ("ambience", "neg"), "cramped": ("ambience", "neg"),
    "overpriced": ("value", "neg"), "small portions": ("value", "neg"),
    "rip off": ("value", "neg"), "expensive": ("value", "neg"),
    "long wait": ("speed", "neg"), "took ages": ("speed", "neg"),
    "slow": ("speed", "neg"),
    # Risk
    "food poisoning": ("safety", "neg"), "cockroach": ("safety", "neg"),
    "hair in": ("safety", "neg"), "raw chicken": ("safety", "neg"),
    "health hazard": ("safety", "neg"),
}

ASPECT_LABELS = {
    "food_quality": "Food Quality",
    "service": "Service & Hospitality",
    "ambience": "Atmosphere & Setting",
    "value": "Value for Money",
    "speed": "Speed & Efficiency",
    "cleanliness": "Cleanliness",
    "safety": "Food Safety",
}


def _collect_review_texts(record):
    """Gather all actual review texts from a record. Returns list of (text, rating) tuples."""
    reviews = []
    for field in ["g_reviews", "ta_reviews"]:
        raw = record.get(field, [])
        if not isinstance(raw, list):
            continue
        for rev in raw:
            text = (rev.get("text") or "").strip()
            if text:
                rating = rev.get("rating") or rev.get("stars")
                reviews.append((text, int(rating) if rating else None))
    return reviews


def extract_review_intelligence(record, sentiment_data=None):
    """Extract review intelligence. Returns a structured dict.

    If review text exists → narrative-rich analysis.
    If not → returns has_narrative=False with no fabricated themes.
    """
    reviews = _collect_review_texts(record)

    if not reviews:
        return {
            "has_narrative": False,
            "review_count_google": record.get("grc"),
            "review_count_ta": record.get("trc"),
            "aspects": _load_external_sentiment(record, sentiment_data),
        }

    # Narrative-rich mode — real review text available
    aspect_scores = {}  # aspect → {"pos": count, "neg": count, "quotes_pos": [], "quotes_neg": []}
    all_quotes_pos = []
    all_quotes_neg = []

    for text, rating in reviews:
        text_lower = text.lower()

        # Keyword theme extraction
        for keyword, (aspect, polarity) in THEME_MAP.items():
            if keyword in text_lower:
                if aspect not in aspect_scores:
                    aspect_scores[aspect] = {"pos": 0, "neg": 0, "quotes_pos": [], "quotes_neg": []}
                aspect_scores[aspect][polarity] += 1

        # Quote extraction — take first ~150 chars as snippet
        snippet = text[:150].strip()
        if len(text) > 150:
            # Try to cut at sentence boundary
            for end in [". ", "! ", "? "]:
                idx = snippet.rfind(end)
                if idx > 60:
                    snippet = snippet[:idx + 1]
                    break

        # Attribute quote to the aspect with the MOST keyword matches in this review
        if rating is not None and rating >= 4:
            all_quotes_pos.append(snippet)
            aspect_hits = {}
            for kw, (asp, pol) in THEME_MAP.items():
                if kw in text_lower and pol == "pos":
                    aspect_hits[asp] = aspect_hits.get(asp, 0) + 1
            if aspect_hits:
                best_asp = max(aspect_hits, key=aspect_hits.get)
                if best_asp in aspect_scores and len(aspect_scores[best_asp]["quotes_pos"]) < 2:
                    aspect_scores[best_asp]["quotes_pos"].append(snippet)
        elif rating is not None and rating <= 2:
            all_quotes_neg.append(snippet)
            aspect_hits = {}
            for kw, (asp, pol) in THEME_MAP.items():
                if kw in text_lower and pol == "neg":
                    aspect_hits[asp] = aspect_hits.get(asp, 0) + 1
            if aspect_hits:
                best_asp = max(aspect_hits, key=aspect_hits.get)
                if best_asp in aspect_scores and len(aspect_scores[best_asp]["quotes_neg"]) < 2:
                    aspect_scores[best_asp]["quotes_neg"].append(snippet)

    # Build praise/criticism theme lists
    praise = []
    criticism = []
    for aspect, counts in sorted(aspect_scores.items(), key=lambda x: -(x[1]["pos"] + x[1]["neg"])):
        label = ASPECT_LABELS.get(aspect, aspect)
        if counts["pos"] > 0:
            praise.append({"aspect": aspect, "label": label, "mentions": counts["pos"],
                           "quotes": counts["quotes_pos"]})
        if counts["neg"] > 0:
            criticism.append({"aspect": aspect, "label": label, "mentions": counts["neg"],
                              "quotes": counts["quotes_neg"]})

    return {
        "has_narrative": True,
        "reviews_analyzed": len(reviews),
        "praise_themes": praise,
        "criticism_themes": criticism,
        "strongest_positive_quotes": all_quotes_pos[:3],
        "strongest_constructive_quotes": all_quotes_neg[:3],
        "aspect_scores": {
            asp: {"positive": c["pos"], "negative": c["neg"],
                  "sentiment": round(c["pos"] / max(1, c["pos"] + c["neg"]) * 10, 1)}
            for asp, c in aspect_scores.items()
        },
    }


def _load_external_sentiment(record, sentiment_data):
    """Load pre-computed sentiment from stratford_sentiment.json if available."""
    if not sentiment_data:
        return None
    venue_id = str(record.get("id", ""))
    return sentiment_data.get(venue_id)


# ---------------------------------------------------------------------------
# Delta computation (only meaningful with narrative data)
# ---------------------------------------------------------------------------

def compute_review_delta(current, previous):
    """Compare two review intelligence snapshots."""
    if not previous or not current.get("has_narrative"):
        return {"is_first_month": True, "has_delta": False}

    if not previous.get("has_narrative"):
        return {"is_first_month": False, "has_delta": False}

    cur_aspects = set(current.get("aspect_scores", {}).keys())
    prev_aspects = set(previous.get("aspect_scores", {}).keys())

    return {
        "is_first_month": False,
        "has_delta": True,
        "new_aspects": list(cur_aspects - prev_aspects),
        "fading_aspects": list(prev_aspects - cur_aspects),
        "aspect_shifts": {
            asp: {
                "prev": previous["aspect_scores"][asp]["sentiment"],
                "current": current["aspect_scores"][asp]["sentiment"],
                "change": round(current["aspect_scores"][asp]["sentiment"] -
                                previous["aspect_scores"][asp]["sentiment"], 1),
            }
            for asp in cur_aspects & prev_aspects
            if asp in current.get("aspect_scores", {}) and asp in previous.get("aspect_scores", {})
        },
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_review_snapshot(venue_id, review_intel, month_str):
    os.makedirs(HISTORY_DIR, exist_ok=True)
    path = os.path.join(HISTORY_DIR, f"{venue_id}_{month_str}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(review_intel, f, indent=2, ensure_ascii=False)
    return path


def load_review_snapshot(venue_id, month_str):
    path = os.path.join(HISTORY_DIR, f"{venue_id}_{month_str}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
