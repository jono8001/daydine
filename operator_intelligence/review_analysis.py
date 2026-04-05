"""
operator_intelligence/review_analysis.py — Deep Review Intelligence Engine

Extracts maximum intelligence from available review data (typically 5
Google reviews) plus structured signals (rating, count, recency).

Produces:
  - Per-review breakdown with aspect tagging and sentiment
  - Aggregate theme analysis with praise/criticism separation
  - Rating trajectory analysis (recent vs overall)
  - Volume and momentum signals
  - Risk detection (negative clusters)
  - Historical baseline for future delta comparison

Honest about the 5-review API limit: analyses what exists, flags
what would require more data, never fabricates.
"""

import re
from collections import Counter, defaultdict


# ---------------------------------------------------------------------------
# Aspect keyword maps — expanded for deeper extraction
# ---------------------------------------------------------------------------

ASPECT_KEYWORDS = {
    "food_quality": {
        "pos": ["delicious", "tasty", "flavourful", "fresh", "perfectly cooked",
                "amazing food", "excellent food", "great food", "fantastic food",
                "lovely meal", "lovely food", "gorgeous", "mouth-watering",
                "tender", "succulent", "authentic", "homemade", "well cooked",
                "absolutely fantastic", "absolutely delicious", "generous portions",
                "cooked to perfection", "beautifully presented"],
        "neg": ["bland", "tasteless", "stale", "dry", "tough", "undercooked",
                "overcooked", "raw", "burnt", "cold food", "lukewarm", "reheated",
                "greasy", "inedible", "disgusting", "poor food", "terrible food",
                "small portions", "disappointing food"],
    },
    "service": {
        "pos": ["friendly", "attentive", "helpful", "professional", "welcoming",
                "great service", "excellent service", "fantastic service",
                "polite", "accommodating", "went above and beyond", "looked after",
                "made us feel", "outstanding", "pleasant", "caring", "concerned",
                "lovely staff", "wonderful staff", "brilliant staff"],
        "neg": ["rude", "unfriendly", "unhelpful", "ignored", "poor service",
                "bad service", "terrible service", "slow service", "inattentive",
                "unprofessional", "couldn't care less", "dismissive",
                "appalled", "turned away", "refused", "would not let",
                "could not have a table", "not welcome", "discriminat"],
    },
    "ambience": {
        "pos": ["great atmosphere", "lovely atmosphere", "cosy", "cozy",
                "charming", "romantic", "beautiful", "clean", "spotless",
                "lovely setting", "wonderful ambience", "relaxed", "warm welcome",
                "dog-friendly", "pet-friendly", "nice decor"],
        "neg": ["noisy", "too loud", "cramped", "crowded", "dirty", "filthy",
                "smelly", "stuffy", "dingy", "tired decor", "run down", "cold"],
    },
    "value": {
        "pos": ["good value", "great value", "worth every penny", "reasonable",
                "affordable", "bargain", "generous portions", "fair price",
                "good for the price", "well priced", "worth the money"],
        "neg": ["overpriced", "expensive", "rip off", "rip-off", "not worth",
                "poor value", "small portions", "tiny portions", "extortionate"],
    },
    "speed": {
        "pos": ["quick", "prompt", "fast", "no wait", "seated immediately",
                "efficient", "food came quickly", "quick service", "didn't wait"],
        "neg": ["long wait", "waited over an hour", "waited ages",
                "slow", "took ages", "forgot our order", "waited forever",
                "took a long time", "waited 40 minutes", "waited 30 minutes",
                "waited 20 minutes", "had to wait"],
    },
    "booking": {
        "pos": ["easy to book", "reservation", "booked online", "table ready"],
        "neg": ["couldn't book", "no reservation", "turned away",
                "had to wait for a table", "no booking"],
    },
}

ASPECT_LABELS = {
    "food_quality": "Food Quality",
    "service": "Service & Hospitality",
    "ambience": "Atmosphere & Setting",
    "value": "Value for Money",
    "speed": "Speed & Efficiency",
    "booking": "Booking & Accessibility",
}

RISK_PHRASES = [
    "food poisoning", "sick after", "made me ill", "cockroach", "rat ",
    "hair in", "raw chicken", "undercooked chicken", "health hazard",
    "worst experience", "never again", "avoid", "disgusting",
]


# ---------------------------------------------------------------------------
# Per-review analysis
# ---------------------------------------------------------------------------

def _analyse_single_review(text, rating):
    """Analyse one review. Returns dict with aspects, sentiment, risk flags.

    Per-aspect counts are BINARY per review: 1 if any positive keyword matched,
    1 if any negative keyword matched. This ensures "mentions" = unique reviews,
    not keyword hits.
    """
    text_lower = text.lower()
    aspects_found = defaultdict(lambda: {"pos": 0, "neg": 0, "keywords": []})

    for aspect, keywords in ASPECT_KEYWORDS.items():
        pos_matched = False
        neg_matched = False
        for kw in keywords["pos"]:
            if kw in text_lower:
                aspects_found[aspect]["keywords"].append(f"+{kw}")
                pos_matched = True
        for kw in keywords["neg"]:
            if kw in text_lower:
                aspects_found[aspect]["keywords"].append(f"-{kw}")
                neg_matched = True
        # Count as 1 review mentioning this aspect (positive and/or negative)
        # Rating override: a 1-2 star review should not count as positive —
        # positive keywords in negative reviews often reference other venues
        # ("we went elsewhere and found welcoming service") or are sarcastic.
        if rating is not None and rating <= 2:
            if pos_matched and not neg_matched:
                # Reclassify: this review is negative overall, positive keywords
                # are likely about another venue or contradicted by the rating
                aspects_found[aspect]["neg"] = 1
                aspects_found[aspect]["pos"] = 0
            elif pos_matched and neg_matched:
                # Both matched — keep negative, suppress positive
                aspects_found[aspect]["neg"] = 1
                aspects_found[aspect]["pos"] = 0
            elif neg_matched:
                aspects_found[aspect]["neg"] = 1
        else:
            if pos_matched:
                aspects_found[aspect]["pos"] = 1
            if neg_matched:
                aspects_found[aspect]["neg"] = 1

    # Risk detection
    risks = [phrase for phrase in RISK_PHRASES if phrase in text_lower]

    # Determine overall sentiment from rating + keyword balance
    total_pos = sum(a["pos"] for a in aspects_found.values())
    total_neg = sum(a["neg"] for a in aspects_found.values())

    if rating is not None:
        if rating >= 4:
            sentiment = "positive"
        elif rating <= 2:
            sentiment = "negative"
        else:
            sentiment = "mixed"
    else:
        sentiment = "positive" if total_pos > total_neg else "negative" if total_neg > total_pos else "neutral"

    # Best quote snippet — try to find the most specific sentence
    best_snippet = _extract_best_snippet(text, aspects_found)

    return {
        "rating": rating,
        "sentiment": sentiment,
        "aspects": dict(aspects_found),
        "risks": risks,
        "total_positive_signals": total_pos,
        "total_negative_signals": total_neg,
        "snippet": best_snippet,
    }


def _extract_best_snippet(text, aspects):
    """Extract the most informative sentence from a review (overall best)."""
    sentences = re.split(r'[.!?]+\s+', text)
    if not sentences:
        return text[:150]

    best = None
    best_score = -1
    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 20:
            continue
        sent_lower = sent.lower()
        score = 0
        for aspect, data in aspects.items():
            for kw in data.get("keywords", []):
                clean_kw = kw.lstrip("+-")
                if clean_kw in sent_lower:
                    score += 1
        if score > best_score:
            best_score = score
            best = sent
    return (best or text)[:200]


def _extract_aspect_snippet(text, aspect_key):
    """Extract the best sentence for a SPECIFIC aspect from a review.

    Unlike _extract_best_snippet which picks the overall best sentence,
    this finds the sentence most relevant to one specific aspect.
    Returns None if no aspect-relevant sentence found.
    """
    sentences = re.split(r'[.!?]+\s+|\.{2,}', text)  # split on punctuation+space or ellipsis
    if not sentences:
        return None

    keywords = ASPECT_KEYWORDS.get(aspect_key, {})
    all_kws = keywords.get("pos", []) + keywords.get("neg", [])
    if not all_kws:
        return None

    best = None
    best_score = 0
    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 15:
            continue
        sent_lower = sent.lower()
        score = sum(1 for kw in all_kws if kw in sent_lower)
        if score > best_score:
            best_score = score
            best = sent

    if not best:
        return None
    # If the keyword match is beyond 150 chars, extract around the keyword
    if len(best) > 150:
        keywords = ASPECT_KEYWORDS.get(aspect_key, {})
        all_kws = keywords.get("pos", []) + keywords.get("neg", [])
        for kw in all_kws:
            pos = best.lower().find(kw)
            if pos >= 0:
                start = max(0, pos - 40)
                end = min(len(best), pos + len(kw) + 60)
                return ("..." if start > 0 else "") + best[start:end].strip()
    return best[:150]


# ---------------------------------------------------------------------------
# Aggregate analysis across all reviews
# ---------------------------------------------------------------------------

def analyse_reviews(reviews):
    """Full review intelligence from a list of review items.

    Each item can be:
      - (text, rating) tuple — backward compatible, no date
      - (text, rating, date_str) tuple — with optional ISO date
      - (text, rating, date_str, source) tuple — with date and source

    Returns a rich analysis dict or None if no reviews.
    """
    if not reviews:
        return None

    per_review = []
    for item in reviews:
        if isinstance(item, dict):
            text, rating = item.get("text", ""), item.get("rating")
            date_str, source = item.get("date"), item.get("source")
        elif len(item) >= 4:
            text, rating, date_str, source = item[0], item[1], item[2], item[3]
        elif len(item) >= 3:
            text, rating, date_str = item[0], item[1], item[2]
            source = None
        else:
            text, rating = item[0], item[1]
            date_str, source = None, None
        analysis = _analyse_single_review(text, rating)
        analysis["date"] = date_str
        analysis["source"] = source
        analysis["full_text"] = text
        per_review.append(analysis)

    # Aggregate aspects
    aspect_totals = defaultdict(lambda: {"pos": 0, "neg": 0, "keywords": []})
    for rev in per_review:
        for aspect, data in rev["aspects"].items():
            aspect_totals[aspect]["pos"] += data["pos"]
            aspect_totals[aspect]["neg"] += data["neg"]
            aspect_totals[aspect]["keywords"].extend(data["keywords"])

    # Build aspect scores (0-10 scale)
    aspect_scores = {}
    for aspect, data in aspect_totals.items():
        total = data["pos"] + data["neg"]
        if total > 0:
            aspect_scores[aspect] = {
                "score": round(data["pos"] / total * 10, 1),
                "positive": data["pos"],
                "negative": data["neg"],
                "mentions": total,
            }

    # Praise and criticism themes with ASPECT-SPECIFIC quotes
    # Each quote must be about the specific aspect, not a general snippet
    praise = []
    criticism = []
    used_quotes = set()  # prevent same quote appearing under multiple themes

    for aspect, scores in sorted(aspect_scores.items(), key=lambda x: -x[1]["mentions"]):
        label = ASPECT_LABELS.get(aspect, aspect.replace("_", " ").title())

        # Find aspect-specific quotes (not the general review snippet)
        pos_quotes = []
        for rev in per_review:
            if aspect in rev["aspects"] and rev["aspects"][aspect]["pos"] > 0:
                asp_quote = _extract_aspect_snippet(rev.get("full_text", rev["snippet"]), aspect)
                if asp_quote and asp_quote not in used_quotes:
                    pos_quotes.append(asp_quote)
                    used_quotes.add(asp_quote)

        neg_quotes = []
        for rev in per_review:
            if aspect in rev["aspects"] and rev["aspects"][aspect]["neg"] > 0:
                asp_quote = _extract_aspect_snippet(rev.get("full_text", rev["snippet"]), aspect)
                if asp_quote and asp_quote not in used_quotes:
                    neg_quotes.append(asp_quote)
                    used_quotes.add(asp_quote)

        if scores["positive"] > 0:
            praise.append({
                "aspect": aspect, "label": label,
                "mentions": scores["positive"],
                "quotes": pos_quotes[:2],
            })
        if scores["negative"] > 0:
            criticism.append({
                "aspect": aspect, "label": label,
                "mentions": scores["negative"],
                "quotes": neg_quotes[:2],
            })

    # Rating distribution
    ratings = [r["rating"] for r in per_review if r["rating"] is not None]
    rating_dist = Counter(ratings)
    avg_rating = sum(ratings) / len(ratings) if ratings else None

    # Sentiment distribution
    sentiments = Counter(r["sentiment"] for r in per_review)

    # Risk detection
    all_risks = []
    for rev in per_review:
        all_risks.extend(rev["risks"])
    risk_flags = list(set(all_risks))

    # Rating trajectory — prefer date-sorted if dates available,
    # fall back to positional split with honest labelling
    trajectory = None
    trajectory_method = None
    dated_reviews = [(r, r.get("date")) for r in per_review if r.get("date")]
    if len(dated_reviews) >= 4:
        # Date-sorted trajectory: compare older half vs newer half by date
        dated_sorted = sorted(dated_reviews, key=lambda x: x[1])
        mid = len(dated_sorted) // 2
        older_ratings = [r["rating"] for r, _ in dated_sorted[:mid] if r["rating"] is not None]
        newer_ratings = [r["rating"] for r, _ in dated_sorted[mid:] if r["rating"] is not None]
        if older_ratings and newer_ratings:
            diff = (sum(newer_ratings) / len(newer_ratings)) - (sum(older_ratings) / len(older_ratings))
            trajectory = "improving" if diff > 0.3 else "declining" if diff < -0.3 else "stable"
            trajectory_method = "date_sorted"
    if trajectory is None and len(ratings) >= 4:
        # Positional fallback — not temporal evidence
        first_half = ratings[:len(ratings)//2]
        second_half = ratings[len(ratings)//2:]
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)
        diff = second_avg - first_avg
        if diff > 0.3:
            trajectory = "improving"
        elif diff < -0.3:
            trajectory = "declining"
        else:
            trajectory = "stable"
        trajectory_method = "positional"

    return {
        "reviews_analyzed": len(per_review),
        "aspect_scores": aspect_scores,
        "praise_themes": praise,
        "criticism_themes": criticism,
        "rating_distribution": dict(rating_dist),
        "average_sample_rating": round(avg_rating, 2) if avg_rating else None,
        "sentiment_distribution": dict(sentiments),
        "risk_flags": risk_flags,
        "trajectory": trajectory,
        "trajectory_method": trajectory_method,
        "per_review": [
            {"rating": r["rating"], "sentiment": r["sentiment"],
             "snippet": r["snippet"],
             "full_text": r.get("full_text", r["snippet"]),
             "aspects": list(r["aspects"].keys()),
             "risk_count": len(r["risks"]),
             "date": r.get("date"),
             "source": r.get("source")}
            for r in per_review
        ],
    }


# ---------------------------------------------------------------------------
# Volume and momentum signals (from structured data, not review text)
# ---------------------------------------------------------------------------

def analyse_volume_signals(record, google_rating, google_review_count):
    """Analyse review volume and rating signals for momentum/risk."""
    signals = {}

    grc = google_review_count or 0
    gr = google_rating

    # Volume tier
    if grc >= 1000:
        signals["volume_tier"] = "dominant"
        signals["volume_note"] = (f"{grc:,} reviews — statistically robust rating. "
                                  "Individual reviews have negligible impact.")
    elif grc >= 500:
        signals["volume_tier"] = "strong"
        signals["volume_note"] = (f"{grc} reviews — strong base. Rating is stable "
                                  "but a sustained negative pattern could shift it.")
    elif grc >= 100:
        signals["volume_tier"] = "adequate"
        signals["volume_note"] = (f"{grc} reviews — adequate but not dominant. "
                                  "5 consecutive low ratings could drop average by ~0.1.")
    elif grc >= 20:
        signals["volume_tier"] = "thin"
        signals["volume_note"] = (f"Only {grc} reviews — rating is volatile. "
                                  "A single 1-star review moves the average measurably.")
    else:
        signals["volume_tier"] = "critical"
        signals["volume_note"] = (f"Only {grc} reviews — insufficient for reliable "
                                  "assessment. Priority: build review count.")

    # Rating position assessment
    if gr is not None:
        if gr >= 4.5:
            signals["rating_position"] = "premium"
            signals["rating_note"] = (f"{gr}/5 places you in the top tier of Google "
                                      "search results. This drives discovery.")
        elif gr >= 4.0:
            signals["rating_position"] = "competitive"
            signals["rating_note"] = (f"{gr}/5 is competitive but not dominant. "
                                      "The gap to 4.5 is meaningful for Google ranking.")
        elif gr >= 3.5:
            signals["rating_position"] = "vulnerable"
            signals["rating_note"] = (f"{gr}/5 is below the threshold where most "
                                      "customers filter. You're losing discovery.")
        else:
            signals["rating_position"] = "critical"
            signals["rating_note"] = (f"{gr}/5 actively suppresses discovery. "
                                      "Google deprioritises sub-3.5 venues.")

    # Momentum — compare sample rating to aggregate
    # (sample = the 5 most relevant/recent, aggregate = overall Google rating)
    signals["aggregate_rating"] = gr
    signals["review_count"] = grc

    return signals
