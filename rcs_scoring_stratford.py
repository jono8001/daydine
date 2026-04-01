#!/usr/bin/env python3
"""
rcs_scoring_stratford.py — V3.4 RCS Scoring Engine

Implements the V3.4 methodology: 40 signals across 8 weighted tiers,
6 rating bands, temporal decay, cross-source convergence scoring,
expanded penalty rules, and re-weighting for missing data.

V3.4 changes vs V3.2:
  - Temporal decay: e^(-λt) applied to FSA inspection age and review recency
  - Cross-source convergence: bonus/penalty when Google, TA, and FSA agree/diverge
  - Expanded penalties: 18 rules (was 10)
  - Community tier permanently removed (double-counts Tiers 1-3)
  - Tier weights rebalanced: 6 active tiers + Companies House penalties

Usage:
    python rcs_scoring_stratford.py --from-cache
    python rcs_scoring_stratford.py --la "Stratford-on-Avon"

Requires:
    pip install requests
"""

import argparse
import csv
import json
import math
import os
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
FIREBASE_DB_URL = os.getenv(
    "FIREBASE_DATABASE_URL",
    "https://recursive-research-eu-default-rtdb.europe-west1.firebasedatabase.app",
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_CACHE = os.path.join(SCRIPT_DIR, "stratford_establishments.json")
CSV_OUTPUT = os.path.join(SCRIPT_DIR, "stratford_rcs_scores.csv")
SUMMARY_OUTPUT = os.path.join(SCRIPT_DIR, "stratford_rcs_summary.json")

NOW = datetime.now(timezone.utc)

TOTAL_SIGNALS = 40

# ---------------------------------------------------------------------------
# V3.4: Temporal decay parameters
# ---------------------------------------------------------------------------
# Exponential decay: multiplier = e^(-λ * t_days)
# λ = 0.0023 gives ~300-day half-life (suitable for inspection/review freshness)
TEMPORAL_LAMBDA = 0.0023
TEMPORAL_LAMBDA_FAST = 0.0046  # ~150-day half-life for fast-decaying signals


def temporal_decay(days_elapsed, lam=TEMPORAL_LAMBDA):
    """Compute exponential decay factor for a time-sensitive signal.
    Returns a multiplier in (0, 1] where 1 = perfectly fresh."""
    if days_elapsed is None or days_elapsed <= 0:
        return 1.0
    return math.exp(-lam * days_elapsed)


# ---------------------------------------------------------------------------
# Tier definitions: name, base weight, and signal scorers
# ---------------------------------------------------------------------------

TIER_WEIGHTS = {
    "fsa":        0.23,   # V3.4: +1% from community removal (was 0.22)
    "google":     0.24,
    "online":     0.13,   # V3.4: TripAdvisor-only, +1% from community removal (was 0.12)
    "ops":        0.15,
    "menu":       0.10,
    "reputation": 0.08,
    # V3.4: Community tier REMOVED — double-counts signals from Tiers 1-3,
    # no directly observed data. Its 2% redistributed to FSA and Online.
    # V3.4: convergence applied as post-hoc adjustment, not a tier
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def days_since(date_str):
    """Parse date string, return days elapsed. None if unparseable."""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, (NOW - dt).days)
    except (ValueError, TypeError):
        return None


def clamp(val, lo=0.0, hi=1.0):
    return max(lo, min(hi, val))


def safe_float(val, default=None):
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val, default=None):
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Tier 1: Food Safety Authority (FSA) — Weight 30%
#
# Firebase fields:
#   r  = hygiene_rating (1-5)
#   sh = food_hygiene sub-score (already normalised 0-10, 10=best)
#   ss = structural_compliance sub-score (0-10, 10=best)
#   sm = confidence_in_management sub-score (0-10, 10=best)
#   rd = inspection date
#
# Internal weights: rating 40%, structural 20%, CIM 20%, hygiene 20%
# Inspection recency penalty: >365d = -5%, >730d = -10%
# ---------------------------------------------------------------------------

def score_tier_fsa(record):
    """Score Tier 1: FSA. Returns (score 0-1, signals_used, signals_total)."""
    signals_total = 5  # rating, structural, CIM, food_hygiene, recency
    signals_used = 0
    components = {}

    # hygiene_rating (r): 1-5 → 0-1
    r = safe_float(record.get("r"))
    if r is not None:
        components["hygiene_rating"] = (clamp(r / 5.0), 0.40)
        signals_used += 1

    # structural_compliance (ss): 0-10 normalised → 0-1
    ss = safe_float(record.get("ss"))
    if ss is not None:
        components["structural"] = (clamp(ss / 10.0), 0.20)
        signals_used += 1

    # confidence_in_management (sm): 0-10 normalised → 0-1
    sm = safe_float(record.get("sm"))
    if sm is not None:
        components["cim"] = (clamp(sm / 10.0), 0.20)
        signals_used += 1

    # food_hygiene (sh): 0-10 normalised → 0-1
    sh = safe_float(record.get("sh"))
    if sh is not None:
        components["food_hygiene"] = (clamp(sh / 10.0), 0.20)
        signals_used += 1

    if not components:
        return None, 0, signals_total

    # Weighted average with re-weighting for available signals
    total_w = sum(w for _, w in components.values())
    score = sum(v * (w / total_w) for v, w in components.values())

    # V3.4: Temporal decay for inspection age (replaces step penalties)
    age = days_since(record.get("rd"))
    if age is not None:
        signals_used += 1
        decay = temporal_decay(age)
        # Blend: 80% raw score + 20% decay-adjusted score
        # This means very old inspections lose up to 20% of their tier score
        score = score * (0.80 + 0.20 * decay)

    return clamp(score), signals_used, signals_total


# ---------------------------------------------------------------------------
# Tier 2: Google Signals — Weight 25%
#
# Firebase fields: gr (rating 1-5), grc (review count), gpl (price level 1-4)
# Weights: rating 35%, sentiment 15%, review_count 25%, price 10%, photos 10%, types 5%
# ---------------------------------------------------------------------------

# Import sentiment analysis (works whether run from repo root or .github/scripts)
def _analyze_sentiment(reviews):
    """Keyword-based sentiment analysis of review texts. Returns score 0-1."""
    if not reviews:
        return None, 0, []

    RED_FLAGS = [
        "food poisoning", "sick after", "made me sick", "made us sick",
        "dirty", "filthy", "cockroach", "cockroaches", "rat ", "rats ",
        "hair in", "cold food", "stone cold", "raw chicken", "raw meat",
        "undercooked", "pink chicken", "rude staff", "rude waiter",
        "worst restaurant", "worst meal", "worst experience", "worst food",
        "disgusting", "revolting", "inedible", "never again",
        "avoid at all costs", "avoid this", "do not go",
        "health hazard", "shut down", "closed down",
    ]
    POSITIVES = [
        "amazing", "excellent", "outstanding", "exceptional", "superb",
        "best restaurant", "best meal", "best food",
        "highly recommend", "would recommend",
        "fantastic", "fabulous", "phenomenal", "incredible",
        "delicious", "mouth-watering", "perfectly cooked",
        "perfect", "faultless", "flawless",
        "wonderful", "lovely", "friendly staff", "great service",
        "will definitely return", "will be back", "hidden gem",
        "five stars", "5 stars", "10/10",
    ]
    NEGATIVES = [
        "disappointing", "disappointed", "mediocre", "average at best",
        "nothing special", "overrated", "bland", "tasteless",
        "slow service", "poor service", "bad service",
        "small portions", "won't return",
    ]

    total_pos = 0
    total_neg = 0
    total_red = 0
    red_list = []
    for rev in reviews:
        text = (rev.get("text") or "").lower()
        if not text:
            continue
        for p in RED_FLAGS:
            if p in text:
                total_red += 1
                red_list.append(p)
        for p in POSITIVES:
            if p in text:
                total_pos += 1
        for p in NEGATIVES:
            if p in text:
                total_neg += 1

    score = 0.5 + total_pos * 0.05 - total_neg * 0.08 - total_red * 0.15
    return max(0.0, min(1.0, score)), total_red, list(set(red_list))


def _score_aspects(record):
    """
    Compute 5 aspect sub-scores from review text (Google + TripAdvisor).
    Returns dict of {aspect: score_0_to_1} for aspects with data.
    """
    from collections import defaultdict

    ASPECT_KW = {
        "food_quality": {
            "pos": ["delicious", "tasty", "flavourful", "fresh", "perfectly cooked",
                    "great food", "excellent food", "amazing food", "gorgeous presentation",
                    "mouth-watering", "tender", "succulent", "authentic", "homemade"],
            "neg": ["bland", "tasteless", "stale", "dry", "tough", "undercooked",
                    "overcooked", "raw", "burnt", "cold food", "lukewarm", "reheated",
                    "greasy", "inedible", "disgusting", "poor food", "terrible food"],
        },
        "service_quality": {
            "pos": ["friendly", "attentive", "helpful", "professional", "welcoming",
                    "great service", "excellent service", "fantastic service",
                    "knowledgeable", "accommodating", "went above and beyond"],
            "neg": ["rude", "rude staff", "unfriendly", "unhelpful", "ignored",
                    "poor service", "bad service", "terrible service", "slow service",
                    "inattentive", "unprofessional"],
        },
        "ambience": {
            "pos": ["great atmosphere", "lovely atmosphere", "cosy", "cozy",
                    "charming", "romantic", "beautiful decor", "clean", "spotless",
                    "lovely setting", "wonderful ambience"],
            "neg": ["noisy", "too loud", "cramped", "crowded", "dirty", "filthy",
                    "smelly", "stuffy", "dingy", "tired decor", "run down"],
        },
        "value": {
            "pos": ["good value", "great value", "worth every penny", "reasonable",
                    "affordable", "bargain", "generous portions", "fair price"],
            "neg": ["overpriced", "expensive", "rip off", "rip-off", "not worth",
                    "poor value", "small portions", "tiny portions", "extortionate"],
        },
        "wait_time": {
            "pos": ["quick", "prompt", "fast", "no wait", "seated immediately",
                    "efficient", "food came quickly"],
            "neg": ["long wait", "waited over an hour", "waited 45 minutes",
                    "slow", "took ages", "forgot our order", "waited forever"],
        },
    }

    texts = []
    for rev in record.get("g_reviews", []):
        t = rev.get("text", "")
        if t:
            texts.append(t.lower())
    for rev in record.get("ta_reviews", []):
        t = rev.get("text", "")
        if t:
            texts.append(t.lower())

    if not texts:
        return {}

    # Aspect weights: food and service matter more than ambience/value/wait
    ASPECT_WEIGHTS = {
        "food_quality": 0.30,
        "service_quality": 0.25,
        "ambience": 0.15,
        "value": 0.15,
        "wait_time": 0.15,
    }

    scores = {}
    for aspect, kw in ASPECT_KW.items():
        pos = sum(1 for t in texts for p in kw["pos"] if p in t)
        neg = sum(1 for t in texts for n in kw["neg"] if n in t)
        total = pos + neg
        if total > 0:
            raw = pos / total  # 0-1
            # Apply aspect weight so food/service dominate the combined score
            scores[aspect] = raw

    # If we have multiple aspects, compute a weighted composite
    # stored as _aspect_composite for potential use
    if scores:
        weighted = sum(scores.get(a, 0.5) * w
                       for a, w in ASPECT_WEIGHTS.items()
                       if a in scores)
        total_w = sum(w for a, w in ASPECT_WEIGHTS.items() if a in scores)
        if total_w > 0:
            scores["_composite"] = weighted / total_w

    return scores


def score_tier_google(record):
    """Score Tier 2: Google + aspect sentiment. Returns (score 0-1, used, total)."""
    signals_total = 11  # rating, 5 aspects, sentiment, review_count, price, photos, types
    signals_used = 0
    components = {}

    # google_rating: 1-5 → 0-1  (weight 0.20)
    gr = safe_float(record.get("gr"))
    if gr is not None:
        components["google_rating"] = (clamp(gr / 5.0), 0.20)
        signals_used += 1

    # Aspect-based sentiment (5 sub-scores, SCP 0.55-0.62)
    # Total weight for aspects: 0.25 (0.05 each)
    aspects = _score_aspects(record)
    for aspect_name, aspect_score in aspects.items():
        components[f"aspect_{aspect_name}"] = (clamp(aspect_score), 0.05)
        signals_used += 1
    # Store aspects for reporting
    if aspects:
        record["_aspects"] = {k: round(v * 10, 1) for k, v in aspects.items()}

    # Overall review sentiment (red flags etc) — weight 0.10
    all_reviews = []
    g_reviews = record.get("g_reviews")
    if g_reviews and isinstance(g_reviews, list):
        all_reviews.extend(g_reviews)
    ta_reviews = record.get("ta_reviews")
    if ta_reviews and isinstance(ta_reviews, list):
        all_reviews.extend(ta_reviews)
    if all_reviews:
        sentiment, red_count, red_flags = _analyze_sentiment(all_reviews)
        if sentiment is not None:
            components["review_sentiment"] = (sentiment, 0.10)
            signals_used += 1
            record["_sentiment_score"] = round(sentiment, 3)
            record["_red_flag_count"] = red_count
            record["_red_flags"] = red_flags

    # google_review_count: log10 scale, cap 1000  (weight 0.20)
    # V3.4: Apply temporal decay to review volume if we know review age
    grc = safe_int(record.get("grc"))
    if grc is not None:
        vol = clamp(math.log10(max(1, grc)) / math.log10(1000))
        # If we have a latest review date, decay the volume signal
        review_age = days_since(record.get("g_latest_review_date"))
        if review_age is not None:
            vol *= temporal_decay(review_age, TEMPORAL_LAMBDA_FAST)
        components["google_reviews"] = (vol, 0.20)
        signals_used += 1

    # google_price_level: 1-4  (weight 0.05)
    gpl = safe_int(record.get("gpl"))
    if gpl is not None:
        components["google_price"] = (clamp(gpl / 4.0), 0.05)
        signals_used += 1

    # google_photos_count: cap 10  (weight 0.05)
    gpc = safe_int(record.get("gpc"))
    if gpc is not None:
        components["google_photos"] = (clamp(gpc / 10.0), 0.05)
        signals_used += 1

    # google_place_types: presence  (weight 0.05)
    gty = record.get("gty")
    if gty is not None and isinstance(gty, list) and len(gty) > 0:
        components["google_types"] = (1.0, 0.05)
        signals_used += 1

    if not components:
        return None, 0, signals_total

    total_w = sum(w for _, w in components.values())
    score = sum(v * (w / total_w) for v, w in components.values())
    return clamp(score), signals_used, signals_total


# ---------------------------------------------------------------------------
# Tier 3: Online Presence — Weight 15%
# ---------------------------------------------------------------------------

def score_tier_online(record):
    """Score Tier 3: TripAdvisor-only (V3.2). Returns (score 0-1, used, total).
    Web/FB/IG moved to profile-completeness confidence layer."""
    signals_total = 4  # ta_present, ta_rating, ta_reviews, ta_recency
    signals_used = 0
    components = {}

    # TripAdvisor presence
    ta_present = record.get("ta_present")
    if ta_present is None and record.get("ta") is not None:
        ta_present = True
    if ta_present is not None:
        components["has_tripadvisor"] = (1.0 if ta_present else 0.0, 0.20)
        signals_used += 1

    # TripAdvisor rating
    ta = safe_float(record.get("ta"))
    if ta is not None:
        components["ta_rating"] = (clamp(ta / 5.0), 0.35)
        signals_used += 1

    # TripAdvisor review count
    trc = safe_int(record.get("trc"))
    if trc is not None:
        vol = clamp(math.log10(max(1, trc)) / math.log10(1000))
        components["ta_reviews"] = (vol, 0.25)
        signals_used += 1

    # TripAdvisor review recency (0-1, 1 = all recent)
    ta_recency = safe_float(record.get("ta_recency"))
    if ta_recency is not None:
        components["ta_recency"] = (clamp(ta_recency), 0.15)
        signals_used += 1

    if not components:
        return None, 0, signals_total

    total_w = sum(w for _, w in components.values())
    score = sum(v * (w / total_w) for v, w in components.values())
    return clamp(score), signals_used, signals_total


# ---------------------------------------------------------------------------
# Tier 4: Operational Signals — Weight 15%
# ---------------------------------------------------------------------------

def score_tier_ops(record):
    """Score Tier 4: Operational. Returns (score 0-1, used, total)."""
    signals_total = 6
    signals_used = 0
    components = {}

    for field, key in [
        ("reservations", "accepts_reservations"),
        ("delivery", "offers_delivery"),
        ("takeaway", "offers_takeaway"),
        ("wheelchair", "wheelchair_accessible"),
        ("parking", "has_parking"),
    ]:
        val = record.get(key)
        if val is not None:
            components[field] = (1.0 if val else 0.0, 1.0 / 6.0)
            signals_used += 1

    # Infer delivery/takeaway from Google types if not explicitly set
    gty = record.get("gty", [])
    if isinstance(gty, list):
        if "delivery" not in components and "meal_takeaway" in gty:
            components["takeaway"] = (1.0, 1.0 / 6.0)
            signals_used += 1
        if "delivery" not in components and "food_delivery" in gty:
            components["delivery"] = (1.0, 1.0 / 6.0)
            signals_used += 1

    # opening_hours_completeness — derive from goh if available
    ohc = safe_float(record.get("opening_hours_completeness"))
    if ohc is None:
        goh = record.get("goh")
        if isinstance(goh, list) and len(goh) > 0:
            # 7 days = complete, fewer = partial
            ohc = min(1.0, len(goh) / 7.0)
    if ohc is not None:
        components["hours"] = (clamp(ohc), 1.0 / 6.0)
        signals_used += 1

    if not components:
        return None, 0, signals_total

    total_w = sum(w for _, w in components.values())
    score = sum(v * (w / total_w) for v, w in components.values())
    return clamp(score), signals_used, signals_total


# ---------------------------------------------------------------------------
# Tier 5: Menu & Offering — Weight 10%
# ---------------------------------------------------------------------------

def score_tier_menu(record):
    """Score Tier 5: Menu & Offering + GBP completeness. Returns (score 0-1, used, total)."""
    signals_total = 4  # menu, dietary, cuisine, gbp_completeness
    signals_used = 0
    components = {}

    val = record.get("has_menu_online")
    if val is not None:
        components["menu"] = (1.0 if val else 0.0, 0.30)
        signals_used += 1

    diets = safe_int(record.get("dietary_options_count"))
    if diets is not None:
        components["dietary"] = (clamp(diets / 5.0), 0.20)
        signals_used += 1

    cuisines = safe_int(record.get("cuisine_tags_count"))
    if cuisines is None:
        gty = record.get("gty", [])
        if isinstance(gty, list):
            cuisine_types = [t for t in gty if t.endswith("_restaurant")
                             and t != "fast_food_restaurant"]
            if cuisine_types:
                cuisines = len(cuisine_types)
    if cuisines is not None:
        components["cuisine"] = (clamp(cuisines / 3.0), 0.20)
        signals_used += 1

    # GBP completeness (SCP 0.62) — how populated is their Google profile
    gbp = safe_float(record.get("gbp_completeness"))
    if gbp is not None:
        components["gbp_completeness"] = (clamp(gbp / 10.0), 0.30)
        signals_used += 1

    if not components:
        return None, 0, signals_total

    total_w = sum(w for _, w in components.values())
    score = sum(v * (w / total_w) for v, w in components.values())
    return clamp(score), signals_used, signals_total


# ---------------------------------------------------------------------------
# Tier 6: Reputation & Awards — Weight 5%
# ---------------------------------------------------------------------------

def score_tier_reputation(record):
    """Score Tier 6: Reputation. Returns (score 0-1, used, total)."""
    signals_total = 3
    signals_used = 0
    components = {}

    # V3.2: Michelin and AA outweigh local awards
    val = record.get("has_michelin_mention")
    if val is not None:
        components["michelin"] = (1.0 if val else 0.0, 0.40)
        signals_used += 1

    val = record.get("has_aa_rating")
    if val is not None:
        components["aa_rating"] = (1.0 if val else 0.0, 0.35)
        signals_used += 1

    awards = safe_int(record.get("local_awards_count"))
    if awards is not None:
        components["awards"] = (clamp(awards / 3.0), 0.25)
        signals_used += 1

    if not components:
        return None, 0, signals_total

    total_w = sum(w for _, w in components.values())
    score = sum(v * (w / total_w) for v, w in components.values())
    return clamp(score), signals_used, signals_total


# ---------------------------------------------------------------------------
# Tier 7: Community & Engagement — Weight 5%
# ---------------------------------------------------------------------------

def score_tier_community(record):
    """Score Tier 7: Community & Recency. Returns (score 0-1, used, total)."""
    signals_total = 4
    signals_used = 0
    components = {}

    val = record.get("responds_to_reviews")
    if val is not None:
        components["responds"] = (1.0 if val else 0.0, 0.25)
        signals_used += 1

    resp_time = safe_float(record.get("avg_response_time_days"))
    if resp_time is not None:
        if resp_time < 1:
            s = 1.0
        elif resp_time < 3:
            s = 0.7
        elif resp_time < 7:
            s = 0.4
        else:
            s = 0.1
        components["resp_time"] = (s, 0.25)
        signals_used += 1

    for field, key in [
        ("events", "community_events"),
        ("loyalty", "loyalty_program"),
    ]:
        val = record.get(key)
        if val is not None:
            components[field] = (1.0 if val else 0.0, 0.25)
            signals_used += 1

    # Compute recency/trend signals from existing data if no explicit fields
    if not components:
        # Inspection recency as engagement proxy
        age = days_since(record.get("rd"))
        if age is not None:
            if age < 180:
                s = 1.0
            elif age < 365:
                s = 0.8
            elif age < 730:
                s = 0.5
            else:
                s = 0.2
            components["recency"] = (s, 0.30)
            signals_used += 1

        # Review volume trend — high review counts suggest active community
        grc = safe_int(record.get("grc"))
        trc = safe_int(record.get("trc"))
        total_reviews = (grc or 0) + (trc or 0)
        if total_reviews > 0:
            vol = clamp(math.log10(max(1, total_reviews)) / math.log10(2000))
            components["review_activity"] = (vol, 0.30)
            signals_used += 1

        # Online presence breadth as community signal
        presence = sum(1 for f in ["gr", "ta", "web", "fb", "ig"]
                       if record.get(f) is not None)
        if presence > 0:
            components["presence_breadth"] = (clamp(presence / 4.0), 0.40)
            signals_used += 1

    if not components:
        return None, 0, signals_total

    total_w = sum(w for _, w in components.values())
    score = sum(v * (w / total_w) for v, w in components.values())
    return clamp(score), signals_used, signals_total


# ---------------------------------------------------------------------------
# V3.4: Cross-source convergence scoring
# ---------------------------------------------------------------------------

def compute_convergence(record):
    """
    Measure agreement between independent rating sources.
    Returns (adjustment_factor, details_str).

    Convergence means multiple sources agree → higher confidence → score bonus.
    Divergence means sources disagree → lower confidence → score penalty.

    All ratings normalised to 0-1 scale before comparison.
    """
    sources = {}

    # FSA rating (1-5 → 0-1)
    r = safe_float(record.get("r"))
    if r is not None:
        sources["fsa"] = clamp(r / 5.0)

    # Google rating (1-5 → 0-1)
    gr = safe_float(record.get("gr"))
    if gr is not None:
        sources["google"] = clamp(gr / 5.0)

    # TripAdvisor rating (1-5 → 0-1)
    ta = safe_float(record.get("ta"))
    if ta is not None:
        sources["ta"] = clamp(ta / 5.0)

    if len(sources) < 2:
        return 1.0, "insufficient_sources"

    # Compute pairwise divergence
    keys = list(sources.keys())
    divergences = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            diff = abs(sources[keys[i]] - sources[keys[j]])
            divergences.append((f"{keys[i]}_vs_{keys[j]}", diff))

    avg_divergence = sum(d for _, d in divergences) / len(divergences)

    # Convergence thresholds (on 0-1 normalised scale)
    # 0.10 on 0-1 = 0.5 on 1-5 star scale
    if avg_divergence <= 0.10:
        # Strong convergence: sources agree within ~0.5 stars
        return 1.03, f"converged(avg_div={avg_divergence:.3f})"
    elif avg_divergence <= 0.20:
        # Moderate agreement: no adjustment
        return 1.0, f"neutral(avg_div={avg_divergence:.3f})"
    elif avg_divergence <= 0.30:
        # Mild divergence: small penalty
        return 0.97, f"mild_divergence(avg_div={avg_divergence:.3f})"
    else:
        # Strong divergence: notable penalty
        return 0.95, f"diverged(avg_div={avg_divergence:.3f})"


# ---------------------------------------------------------------------------
# Penalty rules
# ---------------------------------------------------------------------------

def apply_penalties(raw_score, record):
    """
    Apply penalty rules. Returns (final_score, list of applied penalties).
    raw_score is on 0-10 scale.

    V3.4: 18 rules (was 10 in V3.2). New rules marked with V3.4.
    """
    score = raw_score
    applied = []

    r = safe_int(record.get("r"))
    gr = safe_float(record.get("gr"))
    grc = safe_int(record.get("grc"))
    ta = safe_float(record.get("ta"))
    trc = safe_int(record.get("trc"))
    age = days_since(record.get("rd"))

    # --- FSA-based caps ---

    # P1: FSA rating 0-1 → hard cap at 2.0
    if r is not None and r <= 1:
        if score > 2.0:
            applied.append(("fsa_rating_0_1_cap_2", score, 2.0))
            score = 2.0

    # P2: FSA rating 2 → hard cap at 4.0
    if r is not None and r == 2:
        if score > 4.0:
            applied.append(("fsa_rating_2_cap_4", score, 4.0))
            score = 4.0

    # P3 (V3.4): FSA rating 3 with stale inspection (>2yr) → cap at 7.0
    if r is not None and r == 3 and age is not None and age > 730:
        if score > 7.0:
            applied.append(("fsa_3_stale_cap_7", score, 7.0))
            score = 7.0

    # P4: No inspection in 3+ years
    if age is not None and age > 1095:
        penalty = score * 0.15
        applied.append(("no_inspection_3yr", score, score - penalty))
        score -= penalty

    # --- Google-based penalties ---

    # P5: Google rating < 2.0 → -10%
    if gr is not None and gr < 2.0:
        penalty = score * 0.10
        applied.append(("google_rating_below_2", score, score - penalty))
        score -= penalty

    # P6 (V3.4): Google rating < 3.0 (but >= 2.0) → -5%
    elif gr is not None and gr < 3.0:
        penalty = score * 0.05
        applied.append(("google_rating_below_3", score, score - penalty))
        score -= penalty

    # P7: Zero Google reviews → -5%
    if grc is not None and grc == 0:
        penalty = score * 0.05
        applied.append(("zero_google_reviews", score, score - penalty))
        score -= penalty

    # P8 (V3.4): Very few reviews (<5 combined Google+TA) → -3%
    elif grc is not None:
        combined_reviews = grc + (trc or 0)
        if 0 < combined_reviews < 5:
            penalty = score * 0.03
            applied.append(("sparse_reviews", score, score - penalty))
            score -= penalty

    # P9 (V3.4): No photos at all → -3%
    gpc = safe_int(record.get("gpc"))
    if gpc is not None and gpc == 0:
        penalty = score * 0.03
        applied.append(("no_photos", score, score - penalty))
        score -= penalty

    # --- Online presence penalties ---

    # P10: No online presence at all (no Google, no TA, no website)
    has_any_online = (
        record.get("gr") is not None
        or record.get("ta") is not None
        or record.get("web") is not None
    )
    if not has_any_online:
        penalty = score * 0.10
        applied.append(("no_online_presence", score, score - penalty))
        score -= penalty

    # P11 (V3.4): TripAdvisor rating < 2.5 → -5%
    if ta is not None and ta < 2.5:
        penalty = score * 0.05
        applied.append(("ta_rating_below_2_5", score, score - penalty))
        score -= penalty

    # P12 (V3.4): No opening hours listed → -3%
    goh = record.get("goh")
    ohc = safe_float(record.get("opening_hours_completeness"))
    has_hours = (isinstance(goh, list) and len(goh) > 0) or (ohc is not None and ohc > 0)
    if record.get("gr") is not None and not has_hours:
        # Only penalise if we have Google data (so we'd expect hours)
        penalty = score * 0.03
        applied.append(("no_opening_hours", score, score - penalty))
        score -= penalty

    # --- Sentiment penalties ---

    # P13 (V3.4): Multiple red flags (3+) → -15%
    red_count = record.get("_red_flag_count", 0)
    if red_count >= 3:
        penalty = score * 0.15
        applied.append(("multiple_red_flags", score, score - penalty))
        score -= penalty

    # --- Rating inconsistency ---

    # P14 (V3.4): Google and TA diverge by >2 stars → -5%
    if gr is not None and ta is not None:
        if abs(gr - ta) > 2.0:
            penalty = score * 0.05
            applied.append(("google_ta_inconsistent", score, score - penalty))
            score -= penalty

    # --- Companies House penalties (business viability) ---

    ch_status = record.get("company_status")

    # P15: CH dissolved → cap at 3.0
    if ch_status == "dissolved":
        if score > 3.0:
            applied.append(("ch_dissolved_cap_3", score, 3.0))
            score = 3.0

    # P16: CH liquidation → cap at 5.0
    elif ch_status == "liquidation":
        if score > 5.0:
            applied.append(("ch_liquidation_cap_5", score, 5.0))
            score = 5.0

    # P17: CH accounts overdue → -0.5 absolute
    if record.get("accounts_overdue"):
        applied.append(("ch_accounts_overdue", score, score - 0.5))
        score -= 0.5

    # P18: CH director churn (3+ changes in 12mo) → -12%
    dir_changes = safe_int(record.get("director_changes_12m"))
    if dir_changes is not None and dir_changes >= 3:
        penalty = score * 0.12
        applied.append(("ch_director_churn", score, score - penalty))
        score -= penalty

    return clamp(score, 0, 10), applied


# ---------------------------------------------------------------------------
# Rating bands (0-10 scale)
# ---------------------------------------------------------------------------

BANDS = [
    (8.0, "Excellent"),
    (6.5, "Good"),
    (5.0, "Generally Satisfactory"),
    (3.5, "Improvement Necessary"),
    (2.0, "Major Improvement"),
    (0.0, "Urgent Improvement"),
]

def assign_band(score):
    for threshold, band in BANDS:
        if score >= threshold:
            return band
    return "Urgent Improvement"


# ---------------------------------------------------------------------------
# Full V3.4 RCS pipeline
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# V3.4 Weight caps and tier configuration
# ---------------------------------------------------------------------------

# Tiers that derive signals from Google data (for cross-tier cap)
GOOGLE_DERIVED_TIERS = {"google", "ops", "menu"}
GOOGLE_CROSS_TIER_CAP = 0.45
GOOGLE_SINGLE_CAP = 0.30

# V3.4: Community tier REMOVED — double-counts Tiers 1-3, no directly observed data
# V3.4: Convergence scoring applied as post-hoc multiplier
# V3.4: Temporal decay replaces step-function recency penalties

TIER_SCORERS = {
    "fsa":        score_tier_fsa,
    "google":     score_tier_google,
    "online":     score_tier_online,
    "ops":        score_tier_ops,
    "menu":       score_tier_menu,
    "reputation": score_tier_reputation,
    # community removed in V3.4 — function retained for legacy reporting only
}

def _apply_weight_caps(eff_weights):
    """
    Apply Google caps. Returns modified weights and audit trail.
    Redistribution is explicit and auditable.
    """
    audit = {"google_single_before": eff_weights.get("google", 0),
             "google_derived_before": sum(eff_weights.get(t, 0) for t in GOOGLE_DERIVED_TIERS),
             "adjustments": []}

    # Cap 1: Google Tier 2 alone at 30%
    if "google" in eff_weights and eff_weights["google"] > GOOGLE_SINGLE_CAP:
        excess = round(eff_weights["google"] - GOOGLE_SINGLE_CAP, 4)
        eff_weights["google"] = GOOGLE_SINGLE_CAP
        others = {t: w for t, w in eff_weights.items() if t != "google"}
        ot = sum(others.values())
        if ot > 0:
            for t in others:
                eff_weights[t] += excess * (others[t] / ot)
        audit["adjustments"].append(f"google_single_cap: excess {excess:.4f} redistributed")

    # Cap 2: All Google-derived tiers combined at 45%
    gd_total = sum(eff_weights.get(t, 0) for t in GOOGLE_DERIVED_TIERS)
    if gd_total > GOOGLE_CROSS_TIER_CAP:
        scale = GOOGLE_CROSS_TIER_CAP / gd_total
        excess = 0
        for t in GOOGLE_DERIVED_TIERS:
            if t in eff_weights:
                old = eff_weights[t]
                eff_weights[t] = round(old * scale, 4)
                excess += old - eff_weights[t]
        non_gd = {t: w for t, w in eff_weights.items() if t not in GOOGLE_DERIVED_TIERS}
        nt = sum(non_gd.values())
        if nt > 0:
            for t in non_gd:
                eff_weights[t] += excess * (non_gd[t] / nt)
        audit["adjustments"].append(f"google_cross_cap: {gd_total:.4f}->{GOOGLE_CROSS_TIER_CAP}, excess {excess:.4f}")

    audit["google_single_after"] = eff_weights.get("google", 0)
    audit["google_derived_after"] = sum(eff_weights.get(t, 0) for t in GOOGLE_DERIVED_TIERS)
    return eff_weights, audit


def compute_rcs_v2(record):
    """
    Run V3.4 RCS pipeline on a single establishment.

    V3.4 changes vs V3.2:
    - Community tier removed (double-counts Tiers 1-3, no observed data)
    - Temporal decay on FSA inspection age and review recency
    - Cross-source convergence bonus/penalty
    - Expanded penalty rules (18 total)
    - 45% Google-derived cap with audit trail (unchanged)
    """
    tier_scores = {}
    signals_available = 0

    for tier_name, scorer in TIER_SCORERS.items():
        score, used, total = scorer(record)
        if score is not None:
            tier_scores[tier_name] = score
        signals_available += used

    if not tier_scores:
        return {
            "fsa_tier": None, "google_tier": None, "online_tier": None,
            "ops_tier": None, "menu_tier": None, "reputation_tier": None,
            "rcs_final": 0.0, "rcs_band": "Urgent Improvement",
            "signals_available": 0, "signals_total": TOTAL_SIGNALS,
            "penalties": [], "convergence": "no_data",
        }

    # V3.4: Direct tier weights, normalised for active tiers
    raw_weights = {t: TIER_WEIGHTS[t] for t in tier_scores}
    total_raw = sum(raw_weights.values())
    eff_weights = {t: w / total_raw for t, w in raw_weights.items()}

    # Apply Google caps with audit trail
    eff_weights, cap_audit = _apply_weight_caps(eff_weights)

    weighted_sum = sum(
        tier_scores[t] * eff_weights[t]
        for t in tier_scores
    )

    # Scale to 0-10
    raw_score = weighted_sum * 10

    # Downward penalty for missing core tiers
    has_fsa = "fsa" in tier_scores
    has_google = "google" in tier_scores
    if not has_fsa and not has_google:
        raw_score *= 0.85  # Missing both core tiers
    elif not has_fsa:
        raw_score *= 0.92  # Missing FSA
    elif not has_google:
        raw_score *= 0.95  # Missing Google

    # V3.4: Cross-source convergence adjustment
    conv_factor, conv_detail = compute_convergence(record)
    raw_score *= conv_factor

    # Apply penalties (expanded in V3.4)
    final_score, penalties = apply_penalties(raw_score, record)
    final_score = round(clamp(final_score, 0, 10), 3)

    band = assign_band(final_score)

    return {
        "fsa_tier": round(tier_scores.get("fsa", 0) * 10, 3) if "fsa" in tier_scores else None,
        "google_tier": round(tier_scores.get("google", 0) * 10, 3) if "google" in tier_scores else None,
        "online_tier": round(tier_scores.get("online", 0) * 10, 3) if "online" in tier_scores else None,
        "ops_tier": round(tier_scores.get("ops", 0) * 10, 3) if "ops" in tier_scores else None,
        "menu_tier": round(tier_scores.get("menu", 0) * 10, 3) if "menu" in tier_scores else None,
        "reputation_tier": round(tier_scores.get("reputation", 0) * 10, 3) if "reputation" in tier_scores else None,
        "rcs_final": final_score,
        "rcs_band": band,
        "signals_available": signals_available,
        "signals_total": TOTAL_SIGNALS,
        "penalties": penalties,
        "convergence": conv_detail,
    }


# ---------------------------------------------------------------------------
# Firebase fetch
# ---------------------------------------------------------------------------

def fetch_establishments(la_name):
    print(f"Fetching establishments for LA: {la_name}")
    url = f"{FIREBASE_DB_URL}/daydine/establishments.json"
    params = {"orderBy": '"la"', "equalTo": f'"{la_name}"'}
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        print(f"No establishments found for LA '{la_name}'")
        return {}
    print(f"Found {len(data)} establishments")
    return data


# ---------------------------------------------------------------------------
# 3-Tier Category Classifier
# ---------------------------------------------------------------------------

# --- Tier 1: Google Place Type rules (most reliable) ---
_GTYPE_RULES = [
    ({"indian_restaurant", "bangladeshi_restaurant"}, "Indian Restaurant"),
    ({"italian_restaurant", "pizza_restaurant"}, "Italian Restaurant"),
    ({"chinese_restaurant"}, "Chinese Restaurant"),
    ({"thai_restaurant"}, "Thai Restaurant"),
    ({"japanese_restaurant"}, "Japanese Restaurant"),
    ({"french_restaurant", "bistro"}, "French Restaurant"),
    ({"turkish_restaurant", "greek_restaurant"}, "Mediterranean Restaurant"),
    ({"asian_restaurant", "vietnamese_restaurant", "noodle_shop"}, "Asian Restaurant"),
    ({"brazilian_restaurant", "american_restaurant", "hamburger_restaurant",
      "chicken_restaurant", "chicken_wings_restaurant", "steak_house"}, "American / Grill"),
    ({"british_restaurant", "fish_and_chips_restaurant", "seafood_restaurant"}, "British Restaurant"),
    ({"vegan_restaurant", "vegetarian_restaurant"}, "Vegan / Vegetarian"),
    ({"fine_dining_restaurant"}, "Fine Dining"),
    ({"fast_food_restaurant", "sandwich_shop", "snack_bar"}, "Fast Food / Quick Service"),
    ({"meal_takeaway", "food_delivery"}, "Takeaway"),
    ({"pub", "gastropub", "brewpub", "beer_garden"}, "Pub / Bar"),
    ({"bar", "wine_bar", "cocktail_bar", "lounge_bar", "bar_and_grill"}, "Pub / Bar"),
    ({"coffee_shop", "coffee_stand", "coffee_roastery", "tea_house"}, "Cafe / Coffee Shop"),
    ({"cafe", "breakfast_restaurant", "brunch_restaurant", "diner"}, "Cafe / Coffee Shop"),
    ({"bakery", "pastry_shop", "cake_shop", "confectionery",
      "dessert_shop", "ice_cream_shop"}, "Bakery / Desserts"),
    ({"hotel", "lodging", "bed_and_breakfast", "inn"}, "Hotel / Accommodation"),
    ({"catering_service"}, "Catering"),
]

# --- Tier 2: Name-based keyword matching ---
# Each rule: (set of keywords, category). Match if ANY keyword appears in
# the lowercased business name. Rules checked in order, first match wins.
import re

_NAME_RULES = [
    # Indian / South Asian
    ({"curry", "tandoori", "spice", "masala", "balti", "bengali", "biryani",
      "naan", "chapati", "bhaji", "tikka", "vindaloo", "korma", "mughal",
      "raj ", "maharaja", "bombay", "delhi", "punjab", "bengal", "nepal",
      "everest", "gurkha", "namaste", "nepalese", "mouchak", "chutni",
      "bengali"}, "Indian Restaurant"),
    # Chinese
    ({"chinese", "wok", "dragon", "oriental", "canton", "peking", "szechuan",
      "dim sum", "chow", "china garden", "summer palace"}, "Chinese Restaurant"),
    # Italian
    ({"pizza", "pizzeria", "pasta", "trattoria", "ristorante", "italiano",
      "napoli", "roma", "vesuvio", "carluccio", "bella italia", "sorrento",
      "zizzi", "prezzo"}, "Italian Restaurant"),
    # Thai
    ({"thai", "siam", "bangkok", "pad thai", "tom yum"}, "Thai Restaurant"),
    # Japanese
    ({"sushi", "ramen", "tempura", "miso", "sake", "japanese",
      "wagamama"}, "Japanese Restaurant"),
    # Turkish / Mediterranean
    ({"turkish", "kebab", "mediterranean", "greek", "tzatziki", "meze",
      "falafel", "shawarma", "stone baker"}, "Mediterranean Restaurant"),
    # Mexican
    ({"mexican", "burrito", "taco", "cantina", "enchilada",
      "tortilla"}, "Mexican Restaurant"),
    # Fish & Chips
    ({"fish & chips", "fish and chips", "fish bar", "chippy",
      "fryer"}, "Fish & Chips"),
    # Fast Food (check before pub since some share keywords)
    ({"burger king", "mcdonald", "kfc", "greggs", "domino", "papa john",
      "subway", "fried chicken", "chicken wings", "chicken express",
      "burger"}, "Fast Food / Quick Service"),
    # Cafe / Coffee (before pub to catch "tea" names)
    ({"cafe", "caff", "coffee", "tea room", "tea shed", "patisserie",
      "bean", "roast", "costa", "starbucks", "espresso",
      "canteen"}, "Cafe / Coffee Shop"),
    # Bakery
    ({"bakery", "bakehouse", "cake", "patisserie"}, "Bakery / Desserts"),
    # Hotel / Accommodation
    ({"hotel", "manor", "hall", "castle", "spa", "resort", "hilton",
      "marriott", "plaza"}, "Hotel / Accommodation"),
    # Pub / Bar — pub-specific name patterns
    ({"arms", "tavern", "ale ", "alehouse", "taphouse"}, "Pub / Bar"),
    # Catering
    ({"catering", "lunch club"}, "Catering"),
]

# Pub names: "The <Animal/Object>" pattern — common pub naming convention
_PUB_ANIMAL_WORDS = {
    "inn", "bull", "bell", "swan", "lion", "horse", "crown", "plough",
    "anchor", "fox", "stag", "hare", "pheasant", "eagle", "bear",
    "roebuck", "red lion", "bluebell", "black horse", "white hart",
}


def _tier1_google_types(record):
    """Tier 1: classify from Google place types. Returns (category, True) or (None, False)."""
    gty = record.get("gty")
    if not gty or not isinstance(gty, list):
        return None, False

    types_set = set(gty)
    for match_types, category in _GTYPE_RULES:
        if types_set & match_types:
            return category, True

    if "restaurant" in types_set or "family_restaurant" in types_set:
        return "Restaurant (General)", True
    if "food" in types_set:
        return "Food & Drink", True
    return None, False


def _tier2_name_match(record):
    """Tier 2: classify from business name keywords. Returns (category, True) or (None, False)."""
    name = (record.get("n") or "").lower().strip()
    if not name:
        return None, False

    # Check keyword rules
    for keywords, category in _NAME_RULES:
        for kw in keywords:
            if kw in name:
                return category, True

    # Pub pattern: "The <Word>" where word is a common pub name element
    # but NOT "The <X> Hotel/Cafe/Restaurant/Sanctuary/Church"
    if name.startswith("the "):
        rest = name[4:]
        non_pub = {"hotel", "cafe", "restaurant", "sanctuary", "church",
                   "golf", "college", "school", "club", "centre", "center"}
        if not any(np in rest for np in non_pub):
            for pub_word in _PUB_ANIMAL_WORDS:
                # Use word-boundary matching to avoid substring false
                # positives (e.g. "lion" inside "pavillion")
                if re.search(r'\b' + re.escape(pub_word) + r'\b', rest):
                    return "Pub / Bar", True

    return None, False


def classify_category(record):
    """
    3-tier category classifier.
    Tier 1: Google place types (most reliable)
    Tier 2: Name-based keyword matching (fallback)
    Tier 3: Web lookup (external script, not run here)
    Returns (category, source) tuple.
    """
    # Tier 1
    cat, matched = _tier1_google_types(record)
    if matched:
        return cat, "google_types"

    # Tier 2
    cat, matched = _tier2_name_match(record)
    if matched:
        return cat, "name_match"

    # Unclassified — Tier 3 would run externally
    return "Other", "unclassified"


# ---------------------------------------------------------------------------
# Food-service verification — checks if an establishment actually serves food
# ---------------------------------------------------------------------------

# Google types that confirm food service
_FOOD_TYPES = {
    "restaurant", "cafe", "coffee_shop", "bakery", "bar", "pub",
    "meal_takeaway", "food", "food_delivery", "diner", "bistro",
    "gastropub", "brewpub", "tea_house", "dessert_shop", "ice_cream_shop",
    "pastry_shop", "cake_shop", "confectionery", "deli", "snack_bar",
    "fast_food_restaurant", "sandwich_shop", "pizza_restaurant",
    "indian_restaurant", "chinese_restaurant", "italian_restaurant",
    "thai_restaurant", "japanese_restaurant", "french_restaurant",
    "turkish_restaurant", "greek_restaurant", "asian_restaurant",
    "vietnamese_restaurant", "mexican_restaurant", "brazilian_restaurant",
    "american_restaurant", "british_restaurant", "seafood_restaurant",
    "steak_house", "hamburger_restaurant", "chicken_restaurant",
    "noodle_shop", "fine_dining_restaurant", "family_restaurant",
    "breakfast_restaurant", "brunch_restaurant", "vegan_restaurant",
    "vegetarian_restaurant", "fish_and_chips_restaurant",
    "bangladeshi_restaurant", "wine_bar", "cocktail_bar", "beer_garden",
    "bar_and_grill", "dog_cafe", "cat_cafe",
}

# Google types that confirm NOT a food business
_NON_FOOD_TYPES = {
    "insurance_agency", "real_estate_agency", "church", "place_of_worship",
    "miniature_golf_course", "gym", "fitness_center", "swimming_pool",
    "medical_clinic", "library", "clothing_store", "jewelry_store",
}

# Names that confirm NOT a food business
_NON_FOOD_NAMES = {
    "slimming world", "nfu mutual", "aston martin", "football club",
    "golf club", "baptist church", "juniors fc", "town fc",
    "barrow ltd", "equipment ltd", "horse sanctuary",
}


def is_food_establishment(record):
    """
    Verify whether an establishment actually serves food.
    Returns (is_food: bool, reason: str).

    Priority: name blacklist → Google food types → FSA rating as
    strong override → Google non-food types → name food keywords.
    """
    name = (record.get("n") or "").lower()
    gty = record.get("gty", [])
    types_set = set(gty) if isinstance(gty, list) else set()
    fsa_rating = record.get("r")

    # Step 1: Hard-exclude by name (known non-food businesses)
    for nf in _NON_FOOD_NAMES:
        if nf in name:
            return False, f"non_food_name:{nf}"

    # Step 2: If ANY Google food type is present → definitely food
    if types_set & _FOOD_TYPES:
        return True, "google_food_type"

    # Step 3: FSA rating 3+ is strong evidence of real food service,
    # even if Google types are wrong (misclassified gym, estate agent, etc.)
    if fsa_rating is not None:
        try:
            if int(fsa_rating) >= 3:
                return True, "fsa_high_rating"
        except (ValueError, TypeError):
            pass

    # Step 4: Hotels/lodging without food types — keep (likely have restaurant)
    if "hotel" in types_set or "lodging" in types_set:
        return True, "hotel_assumed_food"

    # Step 5: Check name for food keywords (catches cafes in gyms, etc.)
    food_names = {"cafe", "caff", "catering", "kitchen", "restaurant",
                  "canteen", "lunch", "coffee", "tea", "food", "diner",
                  "bistro", "grill", "bakery", "pizza"}
    if any(fn in name for fn in food_names):
        return True, "food_name_keyword"

    # Step 6: Google non-food types with no food evidence
    if types_set & _NON_FOOD_TYPES:
        return False, "google_non_food_type"

    # Step 7: Sports clubs / venues with low or no FSA rating
    if types_set & {"sports_club", "event_venue", "community_center"}:
        if fsa_rating is not None:
            return True, "venue_with_fsa"
        return False, "venue_no_food_evidence"

    # Step 8: Has an FSA registration at all → include
    if fsa_rating is not None:
        return True, "fsa_registered"

    return True, "default_include"


# ---------------------------------------------------------------------------
# Confidence calculation
# ---------------------------------------------------------------------------

MIN_SIGNALS_FOR_RANKING = 8


def compute_confidence(signals_available, n_tiers_active, provenance_ratio=1.0):
    """
    Compute confidence level and band width.
    Factors in provenance ratio: 60% signal count + 40% provenance.
    Returns (level: str, margin: float).
    """
    # Composite confidence score: signal count normalized + provenance
    count_score = min(1.0, signals_available / 25)  # 25 signals = 1.0
    composite = 0.60 * count_score + 0.40 * provenance_ratio

    if composite >= 0.70 and signals_available >= 20 and n_tiers_active >= 5:
        return "High", 0.3
    elif composite >= 0.50 and signals_available >= 14 and n_tiers_active >= 4:
        return "Medium", 0.5
    elif signals_available >= MIN_SIGNALS_FOR_RANKING:
        return "Low", 0.8
    else:
        return "Insufficient", 1.5


# ---------------------------------------------------------------------------
# Pipeline: score all, save CSV + JSON summary
# ---------------------------------------------------------------------------

CSV_FIELDS = [
    "rank", "fhrsid", "business_name", "postcode", "category", "category_source",
    "is_food", "confidence", "confidence_margin",
    "fsa_tier_score", "google_tier_score", "online_tier_score",
    "ops_tier_score", "menu_tier_score", "reputation_tier_score",
    "rcs_final", "rcs_band", "convergence",
    "quality_score", "digital_presence_score",
    "signals_available", "signals_total",
    "observed_signals", "inferred_signals", "provenance_ratio",
    "sentiment_score", "red_flag_count", "red_flags",
    "companies_house_status",
]

def _count_observed_signals(record):
    """Count directly observed vs inferred signals."""
    observed = 0
    # FSA fields: directly from API
    for f in ["r", "sh", "ss", "sm", "rd"]:
        if record.get(f) is not None:
            observed += 1
    # Google fields: directly from API
    for f in ["gr", "grc", "gpl", "gpc", "gty"]:
        if record.get(f) is not None:
            observed += 1
    # TripAdvisor: directly from Apify
    for f in ["ta", "trc", "ta_recency"]:
        if record.get(f) is not None:
            observed += 1
    # Review text (observed if present)
    if record.get("g_reviews") or record.get("ta_reviews"):
        observed += 1  # sentiment signal
    return observed


def _compute_quality_score(result, record):
    """Quality sub-score: FSA + sentiment + menu + reputation + aspects."""
    components = []
    if result.get("fsa_tier") is not None:
        components.append(result["fsa_tier"])
    sent = record.get("_sentiment_score")
    if sent is not None:
        components.append(sent * 10)  # 0-1 → 0-10
    if result.get("menu_tier") is not None:
        components.append(result["menu_tier"])
    if result.get("reputation_tier") is not None:
        components.append(result["reputation_tier"])
    aspects = record.get("_aspects", {})
    if aspects:
        aspect_vals = [v for v in aspects.values() if v is not None]
        if aspect_vals:
            components.append(sum(aspect_vals) / len(aspect_vals))
    if not components:
        return None
    return round(sum(components) / len(components), 3)


def _compute_digital_score(result, record):
    """Digital presence sub-score: website, social, Google, photos."""
    checks = 0
    total = 6
    if record.get("web") is True:
        checks += 1
    if record.get("fb") is True:
        checks += 1
    if record.get("ig") is True:
        checks += 1
    if record.get("gr") is not None:
        checks += 1
    gpc = record.get("gpc")
    if gpc is not None and int(gpc) > 0:
        checks += 1
    if record.get("ta") is not None:
        checks += 1
    return round(checks / total * 10, 3)


def run_pipeline(data):
    scored = []
    for key, record in data.items():
        result = compute_rcs_v2(record)
        cat, cat_source = classify_category(record)
        food_ok, food_reason = is_food_establishment(record)

        n_tiers = sum(1 for t in ["fsa_tier", "google_tier", "online_tier",
                                   "ops_tier", "menu_tier", "reputation_tier"]
                      if result.get(t) is not None)

        # Signal provenance
        observed = _count_observed_signals(record)
        total_sig = result["signals_available"]
        inferred = max(0, total_sig - observed)
        prov_ratio = round(observed / total_sig, 2) if total_sig > 0 else 0

        # Confidence with provenance weighting (60% count + 40% provenance)
        conf_level, conf_margin = compute_confidence(
            result["signals_available"], n_tiers, prov_ratio)

        # Quality vs Digital sub-scores
        quality = _compute_quality_score(result, record)
        digital = _compute_digital_score(result, record)

        # Companies House status
        ch_status = record.get("company_status", "not_checked")

        scored.append({
            "fhrsid": record.get("id") or key,
            "business_name": record.get("n", "Unknown"),
            "postcode": record.get("pc", ""),
            "category": cat,
            "category_source": cat_source,
            "is_food": food_ok,
            "_food_reason": food_reason,
            "confidence": conf_level,
            "confidence_margin": conf_margin,
            "fsa_tier_score": result["fsa_tier"],
            "google_tier_score": result["google_tier"],
            "online_tier_score": result["online_tier"],
            "ops_tier_score": result["ops_tier"],
            "menu_tier_score": result["menu_tier"],
            "reputation_tier_score": result["reputation_tier"],
            "rcs_final": result["rcs_final"],
            "rcs_band": result["rcs_band"],
            "convergence": result.get("convergence", ""),
            "quality_score": quality,
            "digital_presence_score": digital,
            "signals_available": total_sig,
            "signals_total": result["signals_total"],
            "observed_signals": observed,
            "inferred_signals": inferred,
            "provenance_ratio": prov_ratio,
            "sentiment_score": record.get("_sentiment_score", ""),
            "red_flag_count": record.get("_red_flag_count", 0),
            "red_flags": "; ".join(record.get("_red_flags", [])),
            "companies_house_status": ch_status,
            # Tiebreaker fields (not written to CSV)
            "_fsa_rating": safe_int(record.get("r")) or 0,
            "_rd_days": days_since(record.get("rd")) or 999999,
            "_ss": safe_float(record.get("ss")) or 0.0,
            "_sm": safe_float(record.get("sm")) or 0.0,
        })
    return scored


def _sort_key(r):
    return (
        -r["rcs_final"],
        -r["signals_available"],   # more signals = higher rank among ties
        -r["_fsa_rating"],
        r["_rd_days"],
        -r["_ss"],
        -r["_sm"],
        r["business_name"].lower(),
    )


def apply_tiebreakers(scored):
    """
    Rank establishments in three groups. Scores are kept as-is (ties
    allowed in rcs_final). Ties are broken only in the rank column
    using secondary sort by signal count then alphabetical.
    """
    ranked = []
    insufficient = []
    non_food = []

    for row in scored:
        if not row["is_food"]:
            non_food.append(row)
        elif row["confidence"] == "Insufficient":
            insufficient.append(row)
        else:
            ranked.append(row)

    # Sort ranked group — ties in rcs_final are broken by signal count,
    # FSA rating, recency, sub-scores, then alphabetical
    ranked.sort(key=_sort_key)

    # Assign sequential ranks (no score manipulation)
    for rank, row in enumerate(ranked, 1):
        row["rank"] = rank

    # Insufficient data: score but don't rank
    insufficient.sort(key=_sort_key)
    for row in insufficient:
        row["rank"] = ""
        row["rcs_band"] = "Insufficient Data"

    # Non-food: don't rank
    non_food.sort(key=_sort_key)
    for row in non_food:
        row["rank"] = ""
        row["rcs_band"] = "Not Ranked"

    # Combine
    all_rows = ranked + insufficient + non_food

    # Clean up internal fields
    for row in all_rows:
        for field in ("_fsa_rating", "_rd_days", "_ss", "_sm", "_food_reason"):
            row.pop(field, None)

    return all_rows


def save_scores_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} scored records to {path}")


def build_summary(scored):
    ranked = [r for r in scored if r["rank"] != ""]
    not_ranked = [r for r in scored if r["rcs_band"] == "Not Ranked"]
    insufficient = [r for r in scored if r["rcs_band"] == "Insufficient Data"]

    scores = [r["rcs_final"] for r in ranked]
    band_counts = Counter(r["rcs_band"] for r in ranked)
    band_order = [b for _, b in BANDS]

    # Build rankings by category (top 5 per category, ranked food only)
    categories = {}
    for r in ranked:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)

    rankings_by_category = {}
    for cat in sorted(categories):
        entries = sorted(categories[cat], key=lambda x: x["rank"])
        rankings_by_category[cat] = {
            "count": len(entries),
            "top_5": [
                {"rank": e["rank"], "name": e["business_name"],
                 "rcs": e["rcs_final"], "band": e["rcs_band"]}
                for e in entries[:5]
            ],
        }

    return {
        "count": len(scored),
        "ranked": len(ranked),
        "not_ranked": len(not_ranked),
        "insufficient_data": len(insufficient),
        "mean": round(statistics.mean(scores), 2) if scores else 0,
        "median": round(statistics.median(scores), 2) if scores else 0,
        "min": round(min(scores), 2) if scores else 0,
        "max": round(max(scores), 2) if scores else 0,
        "stdev": round(statistics.stdev(scores), 2) if len(scores) > 1 else 0,
        "band_distribution": {
            band: {"count": band_counts.get(band, 0),
                   "pct": round(band_counts.get(band, 0) / len(scored) * 100, 1) if scored else 0}
            for band in band_order
        },
        "rankings_by_category": rankings_by_category,
        "signals_coverage": {
            "available_per_record_avg": round(
                statistics.mean(r["signals_available"] for r in scored), 1
            ) if scored else 0,
            "total_possible": TOTAL_SIGNALS,
        },
        "sentiment_warnings": [
            {"rank": r.get("rank", ""), "name": r["business_name"],
             "postcode": r["postcode"], "rcs": r["rcs_final"],
             "sentiment": r["sentiment_score"],
             "red_flag_count": r["red_flag_count"],
             "red_flags": r["red_flags"]}
            for r in scored if r.get("red_flag_count", 0) >= 2
        ],
        "convergence": {
            "converged": sum(1 for r in ranked if "converged" in str(r.get("convergence", ""))),
            "neutral": sum(1 for r in ranked if "neutral" in str(r.get("convergence", ""))),
            "mild_divergence": sum(1 for r in ranked if "mild_divergence" in str(r.get("convergence", ""))),
            "diverged": sum(1 for r in ranked if "diverged" in str(r.get("convergence", ""))),
            "insufficient_sources": sum(1 for r in ranked if "insufficient" in str(r.get("convergence", ""))),
        },
        "methodology": "RCS V3.4",
        "generated_at": NOW.isoformat(),
    }


def save_summary_json(summary, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"Wrote summary to {path}")


def print_results(scored):
    ranked = [r for r in scored if r["rank"] != ""]
    not_ranked = [r for r in scored if r["rcs_band"] == "Not Ranked"]
    insufficient = [r for r in scored if r["rcs_band"] == "Insufficient Data"]

    print()
    print("=" * 98)
    print("  TOP 10 RESTAURANTS BY RCS SCORE (0-10)")
    print("=" * 98)
    print(f"  {'Rank':<6} {'Name':<32} {'PC':<10} {'FSA':>6} {'RCS':>7}  {'Conf':<6} {'Band'}")
    print("  " + "-" * 94)
    for row in ranked[:10]:
        fsa = f"{row['fsa_tier_score']:.3f}" if row["fsa_tier_score"] is not None else "  —"
        margin = f"\u00b1{row['confidence_margin']}"
        print(f"  {row['rank']:<6} {row['business_name'][:31]:<32} {row['postcode']:<10} "
              f"{fsa:>6} {row['rcs_final']:>7.3f}  {margin:<6} {row['rcs_band']}")

    print()
    print("=" * 98)
    print("  BOTTOM 10 RANKED RESTAURANTS")
    print("=" * 98)
    print(f"  {'Rank':<6} {'Name':<32} {'PC':<10} {'FSA':>6} {'RCS':>7}  {'Conf':<6} {'Band'}")
    print("  " + "-" * 94)
    for row in ranked[-10:]:
        fsa = f"{row['fsa_tier_score']:.3f}" if row["fsa_tier_score"] is not None else "  —"
        margin = f"\u00b1{row['confidence_margin']}"
        print(f"  {row['rank']:<6} {row['business_name'][:31]:<32} {row['postcode']:<10} "
              f"{fsa:>6} {row['rcs_final']:>7.3f}  {margin:<6} {row['rcs_band']}")

    # Band summary (ranked only)
    band_counts = Counter(r["rcs_band"] for r in ranked)
    band_order = [b for _, b in BANDS]
    total_ranked = len(ranked)

    print()
    print("=" * 55)
    print("  BAND DISTRIBUTION (ranked food establishments)")
    print("=" * 55)
    print(f"  {'Band':<26} {'Count':>7} {'%':>7}")
    print("  " + "-" * 51)
    for band in band_order:
        count = band_counts.get(band, 0)
        pct = (count / total_ranked * 100) if total_ranked else 0
        print(f"  {band:<26} {count:>7} {pct:>6.1f}%")
    print("  " + "-" * 51)
    print(f"  {'Ranked':<26} {total_ranked:>7}")
    if insufficient:
        print(f"  {'Insufficient Data':<26} {len(insufficient):>7}")
    if not_ranked:
        print(f"  {'Not Ranked (non-food)':<26} {len(not_ranked):>7}")
    print(f"  {'Total records':<26} {len(scored):>7}")

    # Signal coverage
    avg_signals = statistics.mean(r["signals_available"] for r in scored) if scored else 0
    print()
    print(f"  Signals: {avg_signals:.1f} / {TOTAL_SIGNALS} avg per record")

    if not_ranked:
        print(f"\n  Non-food excluded ({len(not_ranked)}):")
        for row in not_ranked[:10]:
            print(f"    {row['business_name']}: {row['category']}")
        if len(not_ranked) > 10:
            print(f"    ... and {len(not_ranked) - 10} more")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="V3.4 RCS Scoring Engine — 40 signals, 7 tiers, 6 rating bands"
    )
    parser.add_argument("--la", default="Stratford-on-Avon",
                        help="Local authority name")
    parser.add_argument("--from-cache", action="store_true",
                        help="Load from stratford_establishments.json")
    args = parser.parse_args()

    # Load data
    if args.from_cache:
        if not os.path.exists(JSON_CACHE):
            print(f"ERROR: {JSON_CACHE} not found. Run without --from-cache first.")
            sys.exit(1)
        print(f"Loading from cache: {JSON_CACHE}")
        with open(JSON_CACHE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = fetch_establishments(args.la)
        if not data:
            sys.exit(1)
        with open(JSON_CACHE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nRunning V3.4 RCS pipeline on {len(data)} establishments...")
    print(f"  7 tiers | 40 signals | 6 rating bands | temporal decay | convergence\n")

    # Score
    scored = run_pipeline(data)

    # Apply tiebreakers for unique rankings
    scored = apply_tiebreakers(scored)

    # Band calibration curve not applied — scores reflect raw methodology output

    # Save CSV
    save_scores_csv(scored, CSV_OUTPUT)

    # Build and save summary
    summary = build_summary(scored)
    save_summary_json(summary, SUMMARY_OUTPUT)

    # Generate report
    generate_report(scored, summary)

    # Print
    print_results(scored)


# ---------------------------------------------------------------------------
# Report generator — produces stratford_rcs_report.md
# ---------------------------------------------------------------------------

REPORT_PATH = os.path.join(SCRIPT_DIR, "stratford_rcs_report.md")

def generate_report(scored, summary):
    """Generate stratford_rcs_report.md from scored data."""
    ranked = [r for r in scored if r["rank"] != ""]
    not_ranked = [r for r in scored if r["rcs_band"] == "Not Ranked"]
    insufficient = [r for r in scored if r["rcs_band"] == "Insufficient Data"]
    bands = Counter(r["rcs_band"] for r in ranked)
    band_order = ["Excellent", "Good", "Generally Satisfactory",
                  "Improvement Necessary", "Major Improvement", "Urgent Improvement"]
    ranges_map = {"Excellent": "8.000-10.000", "Good": "6.500-7.999",
                  "Generally Satisfactory": "5.000-6.499",
                  "Improvement Necessary": "3.500-4.999",
                  "Major Improvement": "2.000-3.499",
                  "Urgent Improvement": "0.000-1.999"}

    cats = {}
    for r in ranked:
        cats.setdefault(r["category"], []).append(r)

    ranked_scores = [r["rcs_final"] for r in ranked]
    avg_sig = sum(r["signals_available"] for r in scored) / len(scored) if scored else 0

    tier_info = [
        ("fsa", "FSA (Tier 1)", "23%"), ("google", "Google (Tier 2)", "24%"),
        ("online", "Online (Tier 3)", "13%"), ("ops", "Operational (Tier 4)", "15%"),
        ("menu", "Menu (Tier 5)", "10%"), ("reputation", "Reputation (Tier 6)", "8%"),
    ]
    tier_pop = {}
    for t, *_ in tier_info:
        col = f"{t}_tier_score"
        tier_pop[t] = sum(1 for r in scored if r.get(col) and r[col] not in ("", None))

    # Load sanity report if available
    sanity_path = os.path.join(SCRIPT_DIR, "stratford_sanity_report.json")
    sanity = {}
    if os.path.exists(sanity_path):
        with open(sanity_path, "r", encoding="utf-8") as f:
            sanity = json.load(f)
    missing = sanity.get("missing_from_our_data", [])
    nf_suspects = sanity.get("non_food_suspects", [])

    with_sent = [r for r in ranked if r.get("sentiment_score") and r["sentiment_score"] != ""]
    red_flagged = [r for r in ranked if int(r.get("red_flag_count", 0)) >= 2]

    L = []
    w = L.append
    w("# DayDine RCS Report - Stratford-upon-Avon")
    w(f"\n*Generated: {NOW.strftime('%d %B %Y')} | Methodology: RCS V3.4 | Scale: 0.000-10.000*")
    w("\n---\n")
    w("## 1. Executive Summary\n")
    w("| Metric | Value |\n|---|---|")
    w(f"| Total establishments | **{len(scored)}** |")
    w(f"| Ranked (food service) | **{len(ranked)}** |")
    w(f"| Excluded (non-food) | {len(not_ranked)} |")
    w(f"| Insufficient data | {len(insufficient)} |")
    w(f"| Methodology | RCS V3.4 — 40 signals, 7 tiers, temporal decay, convergence |")
    w(f"| Mean RCS | {statistics.mean(ranked_scores):.2f} |")
    w(f"| Median RCS | {statistics.median(ranked_scores):.2f} |")
    w(f"| Signals avg | {avg_sig:.1f} / {TOTAL_SIGNALS} ({avg_sig/TOTAL_SIGNALS*100:.0f}%) |")
    w(f"| Review sentiment | {len(with_sent)} analyzed, {len(red_flagged)} red flags |")
    w("")
    w("## 2. Top 10\n")
    w("| Rank | Name | Postcode | Category | RCS | Conf | Band |\n|---:|---|---|---|---:|---|---|")
    for r in ranked[:10]:
        w(f"| {r['rank']} | {r['business_name']} | {r['postcode']} | {r['category']} | {r['rcs_final']} | {r['confidence']} (+-{r['confidence_margin']}) | {r['rcs_band']} |")
    w("")
    w("## 3. Bottom 10\n")
    w("| Rank | Name | Postcode | Category | RCS | Conf | Band |\n|---:|---|---|---|---:|---|---|")
    for r in ranked[-10:]:
        w(f"| {r['rank']} | {r['business_name']} | {r['postcode']} | {r['category']} | {r['rcs_final']} | {r['confidence']} (+-{r['confidence_margin']}) | {r['rcs_band']} |")
    w("")
    w("## 4. Band Distribution\n")
    w("| Band | Range | Count | % |\n|---|---|---:|---:|")
    for band in band_order:
        c = bands.get(band, 0)
        pct = c / len(ranked) * 100 if ranked else 0
        w(f"| {band} | {ranges_map[band]} | {c} | {pct:.1f}% |")
    w(f"| **Ranked** | | **{len(ranked)}** | |")
    if not_ranked:
        w(f"| *Not Ranked* | | *{len(not_ranked)}* | |")
    w("")
    w("## 5. Signal Coverage\n")
    w("| Tier | Weight | Coverage |\n|---|---:|---:|")
    for t, name, weight in tier_info:
        pop = tier_pop[t]
        pct = pop / len(scored) * 100 if scored else 0
        w(f"| {name} | {weight} | {pop}/{len(scored)} ({pct:.0f}%) |")
    w("")
    w("## 6. Rankings by Category\n")
    for cat_name in sorted(cats):
        cat_rows = sorted(cats[cat_name], key=lambda x: x["rank"])
        w(f"### {cat_name} ({len(cat_rows)})\n")
        w("| # | Rank | Name | PC | RCS | Band |\n|---:|---:|---|---|---:|---|")
        for j, r in enumerate(cat_rows, 1):
            w(f"| {j} | {r['rank']} | {r['business_name']} | {r['postcode']} | {r['rcs_final']} | {r['rcs_band']} |")
        w("")
    w(f"## 7. Complete Rankings (1-{len(ranked)})\n")
    w("| Rank | Name | PC | Category | RCS | Quality | Digital | Conf | Band | Obs/Inf | Prov |\n|---:|---|---|---|---:|---:|---:|---|---|---|---:|")
    for r in ranked:
        qual = r["quality_score"] if r["quality_score"] is not None else "-"
        digi = r["digital_presence_score"] if r["digital_presence_score"] is not None else "-"
        obs_inf = f"{r['observed_signals']}/{r['inferred_signals']}"
        w(f"| {r['rank']} | {r['business_name']} | {r['postcode']} | {r['category']} | {r['rcs_final']} | {qual} | {digi} | {r['confidence']} | {r['rcs_band']} | {obs_inf} | {r['provenance_ratio']} |")
    w("")
    w("## 8. Excluded\n")
    if not_ranked:
        w("| Name | Postcode | Category |\n|---|---|---|")
        for r in not_ranked:
            w(f"| {r['business_name']} | {r['postcode']} | {r['category']} |")
    w("")
    # V3.4: Convergence summary
    conv_counts = Counter(r.get("convergence", "") for r in ranked)
    conv_converged = sum(1 for r in ranked if "converged" in str(r.get("convergence", "")))
    conv_diverged = sum(1 for r in ranked if "diverged" in str(r.get("convergence", "")))
    conv_mild = sum(1 for r in ranked if "mild_divergence" in str(r.get("convergence", "")))
    conv_neutral = sum(1 for r in ranked if "neutral" in str(r.get("convergence", "")))
    conv_insuf = sum(1 for r in ranked if "insufficient" in str(r.get("convergence", "")))
    w("## 9. Cross-Source Convergence (V3.4)\n")
    w("| Status | Count | % |\n|---|---:|---:|")
    for label, cnt in [("Converged (+3%)", conv_converged), ("Neutral (0%)", conv_neutral),
                        ("Mild divergence (-3%)", conv_mild), ("Diverged (-5%)", conv_diverged),
                        ("Insufficient sources", conv_insuf)]:
        pct = cnt / len(ranked) * 100 if ranked else 0
        w(f"| {label} | {cnt} | {pct:.1f}% |")
    w("")

    if missing:
        w(f"## 10. Sanity Check ({len(missing)} missing)\n")
        w("| Name | Rating | Reviews |\n|---|---:|---:|")
        for m in missing:
            w(f"| {m['name']} | {m.get('rating', '-')} | {m.get('reviews', '-')} |")
    w("\n---\n")
    w(f"*Generated by rcs_scoring_stratford.py V3.4 ({len(scored)} records, {len(ranked)} ranked)*")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"Generated report: {REPORT_PATH} ({len(L)} lines)")


if __name__ == "__main__":
    main()
