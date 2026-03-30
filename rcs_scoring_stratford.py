#!/usr/bin/env python3
"""
rcs_scoring_stratford.py — V2 RCS Scoring Engine

Implements the V2 methodology: 35 signals across 7 weighted tiers,
6 rating bands, penalty rules, and re-weighting for missing data.

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

TOTAL_SIGNALS = 35


# ---------------------------------------------------------------------------
# Tier definitions: name, base weight, and signal scorers
# ---------------------------------------------------------------------------

TIER_WEIGHTS = {
    "fsa":        0.30,
    "google":     0.20,
    "online":     0.15,
    "ops":        0.15,
    "menu":       0.10,
    "reputation": 0.05,
    "community":  0.05,
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

    # Inspection recency penalty
    age = days_since(record.get("rd"))
    if age is not None:
        signals_used += 1
        if age > 730:
            score *= 0.90  # -10%
        elif age > 365:
            score *= 0.95  # -5%

    return clamp(score), signals_used, signals_total


# ---------------------------------------------------------------------------
# Tier 2: Google Signals — Weight 20%
#
# Firebase fields: gr (rating 1-5), grc (review count), gpl (price level 1-4)
# Weights: rating 50%, review_count 30%, price_level 10%, photos 10%
# ---------------------------------------------------------------------------

def score_tier_google(record):
    """Score Tier 2: Google. Returns (score 0-1, signals_used, signals_total)."""
    signals_total = 5  # rating, review_count, price_level, photos, place_types
    signals_used = 0
    components = {}

    # google_rating: 1-5 → 0-1
    gr = safe_float(record.get("gr"))
    if gr is not None:
        components["google_rating"] = (clamp(gr / 5.0), 0.50)
        signals_used += 1

    # google_review_count: log10 scale, cap 1000
    grc = safe_int(record.get("grc"))
    if grc is not None:
        vol = clamp(math.log10(max(1, grc)) / math.log10(1000))
        components["google_reviews"] = (vol, 0.30)
        signals_used += 1

    # google_price_level: 1-4 → 0-1 (presence is signal, not quality)
    gpl = safe_int(record.get("gpl"))
    if gpl is not None:
        components["google_price"] = (clamp(gpl / 4.0), 0.10)
        signals_used += 1

    # google_photos_count: gpc from enrichment, cap at 10 = 1.0
    gpc = safe_int(record.get("gpc"))
    if gpc is not None:
        components["google_photos"] = (clamp(gpc / 10.0), 0.10)
        signals_used += 1

    # google_place_types: gty from enrichment, presence = 1.0
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
    """Score Tier 3: Online Presence. Returns (score 0-1, used, total)."""
    signals_total = 6
    signals_used = 0
    components = {}

    for field, key, weight in [
        ("has_website", "web", 0.20),
        ("has_facebook", "fb", 0.15),
        ("has_instagram", "ig", 0.15),
    ]:
        val = record.get(key)
        if val is not None:
            components[field] = (1.0 if val else 0.0, weight)
            signals_used += 1

    # TripAdvisor presence — derive from ta field if ta_present not set
    ta_present = record.get("ta_present")
    if ta_present is None and record.get("ta") is not None:
        ta_present = True
    if ta_present is not None:
        components["has_tripadvisor"] = (1.0 if ta_present else 0.0, 0.15)
        signals_used += 1

    # tripadvisor_rating
    ta = safe_float(record.get("ta"))
    if ta is not None:
        components["ta_rating"] = (clamp(ta / 5.0), 0.20)
        signals_used += 1

    # tripadvisor_review_count
    trc = safe_int(record.get("trc"))
    if trc is not None:
        vol = clamp(math.log10(max(1, trc)) / math.log10(1000))
        components["ta_reviews"] = (vol, 0.15)
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

    # opening_hours_completeness
    ohc = safe_float(record.get("opening_hours_completeness"))
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
    """Score Tier 5: Menu & Offering. Returns (score 0-1, used, total)."""
    signals_total = 3
    signals_used = 0
    components = {}

    val = record.get("has_menu_online")
    if val is not None:
        components["menu"] = (1.0 if val else 0.0, 0.40)
        signals_used += 1

    diets = safe_int(record.get("dietary_options_count"))
    if diets is not None:
        components["dietary"] = (clamp(diets / 5.0), 0.30)
        signals_used += 1

    cuisines = safe_int(record.get("cuisine_tags_count"))
    if cuisines is not None:
        components["cuisine"] = (clamp(cuisines / 3.0), 0.30)
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

    for field, key in [
        ("aa_rating", "has_aa_rating"),
        ("michelin", "has_michelin_mention"),
    ]:
        val = record.get(key)
        if val is not None:
            components[field] = (1.0 if val else 0.0, 1.0 / 3.0)
            signals_used += 1

    awards = safe_int(record.get("local_awards_count"))
    if awards is not None:
        components["awards"] = (clamp(awards / 3.0), 1.0 / 3.0)
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
    """Score Tier 7: Community. Returns (score 0-1, used, total)."""
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

    if not components:
        return None, 0, signals_total

    total_w = sum(w for _, w in components.values())
    score = sum(v * (w / total_w) for v, w in components.values())
    return clamp(score), signals_used, signals_total


# ---------------------------------------------------------------------------
# Penalty rules
# ---------------------------------------------------------------------------

def apply_penalties(raw_score, record):
    """
    Apply penalty rules. Returns (final_score, list of applied penalties).
    raw_score is 0-100.
    """
    score = raw_score
    applied = []

    r = safe_int(record.get("r"))
    gr = safe_float(record.get("gr"))
    grc = safe_int(record.get("grc"))
    age = days_since(record.get("rd"))

    # FSA rating caps (0-10 scale)
    if r is not None and r <= 1:
        if score > 2.0:
            applied.append(("fsa_rating_0_1_cap_2", score, 2.0))
            score = 2.0
    if r is not None and r == 2:
        if score > 4.0:
            applied.append(("fsa_rating_2_cap_4", score, 4.0))
            score = 4.0

    # No inspection in 3+ years
    if age is not None and age > 1095:
        penalty = score * 0.15
        applied.append(("no_inspection_3yr", score, score - penalty))
        score -= penalty

    # Google rating < 2.0
    if gr is not None and gr < 2.0:
        penalty = score * 0.10
        applied.append(("google_rating_below_2", score, score - penalty))
        score -= penalty

    # Zero Google reviews
    if grc is not None and grc == 0:
        penalty = score * 0.05
        applied.append(("zero_google_reviews", score, score - penalty))
        score -= penalty

    # No online presence at all (no Google, no TA, no website)
    has_any_online = (
        record.get("gr") is not None
        or record.get("ta") is not None
        or record.get("web") is not None
    )
    if not has_any_online:
        penalty = score * 0.10
        applied.append(("no_online_presence", score, score - penalty))
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
# Full V2 RCS pipeline
# ---------------------------------------------------------------------------

TIER_SCORERS = {
    "fsa":        score_tier_fsa,
    "google":     score_tier_google,
    "online":     score_tier_online,
    "ops":        score_tier_ops,
    "menu":       score_tier_menu,
    "reputation": score_tier_reputation,
    "community":  score_tier_community,
}

def compute_rcs_v2(record):
    """
    Run V2 RCS pipeline on a single establishment.

    Returns dict with per-tier scores, final score, band, and metadata.
    """
    tier_scores = {}
    signals_available = 0
    tier_details = {}

    for tier_name, scorer in TIER_SCORERS.items():
        result = scorer(record)
        score, used, total = result
        tier_details[tier_name] = {
            "score": score,
            "signals_used": used,
            "signals_total": total,
        }
        if score is not None:
            tier_scores[tier_name] = score
        signals_available += used

    # Re-weight available tiers
    if not tier_scores:
        return {
            "fsa_tier": None, "google_tier": None, "online_tier": None,
            "ops_tier": None, "menu_tier": None, "reputation_tier": None,
            "community_tier": None,
            "rcs_final": 0.0, "rcs_band": "Urgent Improvement",
            "signals_available": 0, "signals_total": TOTAL_SIGNALS,
            "penalties": [],
        }

    available_weight_sum = sum(
        TIER_WEIGHTS[t] for t in tier_scores
    )
    weighted_sum = sum(
        tier_scores[t] * (TIER_WEIGHTS[t] / available_weight_sum)
        for t in tier_scores
    )

    # Scale to 0-10
    raw_score = weighted_sum * 10

    # Apply penalties
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
        "community_tier": round(tier_scores.get("community", 0) * 10, 3) if "community" in tier_scores else None,
        "rcs_final": final_score,
        "rcs_band": band,
        "signals_available": signals_available,
        "signals_total": TOTAL_SIGNALS,
        "penalties": penalties,
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
# Pipeline: score all, save CSV + JSON summary
# ---------------------------------------------------------------------------

CSV_FIELDS = [
    "rank", "fhrsid", "business_name", "postcode", "category", "category_source",
    "fsa_tier_score", "google_tier_score", "online_tier_score",
    "ops_tier_score", "menu_tier_score", "reputation_tier_score",
    "community_tier_score",
    "rcs_final", "rcs_band", "signals_available", "signals_total",
]

def run_pipeline(data):
    scored = []
    for key, record in data.items():
        result = compute_rcs_v2(record)
        cat, cat_source = classify_category(record)
        scored.append({
            "fhrsid": record.get("id") or key,
            "business_name": record.get("n", "Unknown"),
            "postcode": record.get("pc", ""),
            "category": cat,
            "category_source": cat_source,
            "fsa_tier_score": result["fsa_tier"],
            "google_tier_score": result["google_tier"],
            "online_tier_score": result["online_tier"],
            "ops_tier_score": result["ops_tier"],
            "menu_tier_score": result["menu_tier"],
            "reputation_tier_score": result["reputation_tier"],
            "community_tier_score": result["community_tier"],
            "rcs_final": result["rcs_final"],
            "rcs_band": result["rcs_band"],
            "signals_available": result["signals_available"],
            "signals_total": result["signals_total"],
            # Tiebreaker fields (not written to CSV)
            "_fsa_rating": safe_int(record.get("r")) or 0,
            "_rd_days": days_since(record.get("rd")) or 999999,
            "_ss": safe_float(record.get("ss")) or 0.0,
            "_sm": safe_float(record.get("sm")) or 0.0,
        })
    return scored


def apply_tiebreakers(scored):
    """
    Sort by rcs_final desc, then break ties so every restaurant has a
    unique rank and a numerically distinct final score.

    Tiebreaker order (all among records sharing the same rcs_final):
      1. Higher FSA hygiene_rating
      2. More recent inspection (fewer days since)
      3. Higher structural compliance (ss)
      4. Higher confidence in management (sm)
      5. Alphabetical by business name (A before Z)

    After sorting, tied scores get a tiny descending offset (0.001 per
    position within a tie group) so each rcs_final is unique.
    """
    scored.sort(key=lambda r: (
        -r["rcs_final"],
        -r["_fsa_rating"],
        r["_rd_days"],          # lower = more recent = better
        -r["_ss"],
        -r["_sm"],
        r["business_name"].lower(),
    ))

    # Ensure every score is strictly less than the one above it.
    # Walk top-down: if a score is not strictly less than the previous,
    # nudge it down by 0.001. This guarantees global uniqueness
    # regardless of how many ties exist or how close groups are.
    for i in range(1, len(scored)):
        if scored[i]["rcs_final"] >= scored[i - 1]["rcs_final"]:
            scored[i]["rcs_final"] = round(scored[i - 1]["rcs_final"] - 0.001, 3)

    # If the walk-down pushed scores below zero, re-space the tail
    # so the worst record gets 0.000 and others above it are spaced
    # 0.001 apart ascending.
    if scored[-1]["rcs_final"] < 0:
        # Find where scores went negative
        first_neg = next(i for i, r in enumerate(scored) if r["rcs_final"] < 0)
        # Also include any zeros that precede the negatives (they'd be ties)
        while first_neg > 0 and scored[first_neg - 1]["rcs_final"] <= 0:
            first_neg -= 1
        tail_count = len(scored) - first_neg
        for k in range(tail_count):
            scored[first_neg + k]["rcs_final"] = round(
                (tail_count - 1 - k) * 0.001, 3
            )

    # Assign sequential ranks
    for rank, row in enumerate(scored, 1):
        row["rank"] = rank

    # Clean up internal tiebreaker fields
    for row in scored:
        for field in ("_fsa_rating", "_rd_days", "_ss", "_sm"):
            del row[field]

    return scored


def save_scores_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} scored records to {path}")


def build_summary(scored):
    scores = [r["rcs_final"] for r in scored]
    band_counts = Counter(r["rcs_band"] for r in scored)
    band_order = [b for _, b in BANDS]

    # Build rankings by category (top 5 per category)
    categories = {}
    for r in scored:
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
        "generated_at": NOW.isoformat(),
    }


def save_summary_json(summary, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"Wrote summary to {path}")


def print_results(scored):
    # scored is already sorted by rank from apply_tiebreakers
    print()
    print("=" * 92)
    print("  TOP 10 RESTAURANTS BY RCS SCORE (0-10)")
    print("=" * 92)
    print(f"  {'Rank':<6} {'Name':<35} {'PC':<10} {'FSA':>6} {'RCS':>7}  {'Band'}")
    print("  " + "-" * 88)
    for row in scored[:10]:
        fsa = f"{row['fsa_tier_score']:.3f}" if row["fsa_tier_score"] is not None else "  —"
        print(f"  {row['rank']:<6} {row['business_name'][:34]:<35} {row['postcode']:<10} "
              f"{fsa:>6} {row['rcs_final']:>7.3f}  {row['rcs_band']}")

    print()
    print("=" * 92)
    print("  BOTTOM 10 RESTAURANTS BY RCS SCORE (0-10)")
    print("=" * 92)
    print(f"  {'Rank':<6} {'Name':<35} {'PC':<10} {'FSA':>6} {'RCS':>7}  {'Band'}")
    print("  " + "-" * 88)
    for row in scored[-10:]:
        fsa = f"{row['fsa_tier_score']:.3f}" if row["fsa_tier_score"] is not None else "  —"
        print(f"  {row['rank']:<6} {row['business_name'][:34]:<35} {row['postcode']:<10} "
              f"{fsa:>6} {row['rcs_final']:>7.3f}  {row['rcs_band']}")

    # Band summary
    band_counts = Counter(r["rcs_band"] for r in scored)
    band_order = [b for _, b in BANDS]
    total = len(scored)

    print()
    print("=" * 50)
    print("  BAND DISTRIBUTION")
    print("=" * 50)
    print(f"  {'Band':<26} {'Count':>7} {'%':>7}")
    print("  " + "-" * 46)
    for band in band_order:
        count = band_counts.get(band, 0)
        pct = (count / total * 100) if total else 0
        print(f"  {band:<26} {count:>7} {pct:>6.1f}%")
    print("  " + "-" * 46)
    print(f"  {'TOTAL':<26} {total:>7}")

    # Signal coverage
    avg_signals = statistics.mean(r["signals_available"] for r in scored) if scored else 0
    print()
    print(f"  Signals: {avg_signals:.1f} / {TOTAL_SIGNALS} avg per record")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="V2 RCS Scoring Engine — 35 signals, 7 tiers, 6 rating bands"
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

    print(f"\nRunning V2 RCS pipeline on {len(data)} establishments...")
    print(f"  7 tiers | 35 signals | 6 rating bands\n")

    # Score
    scored = run_pipeline(data)

    # Apply tiebreakers for unique rankings
    scored = apply_tiebreakers(scored)

    # Save CSV
    save_scores_csv(scored, CSV_OUTPUT)

    # Build and save summary
    summary = build_summary(scored)
    save_summary_json(summary, SUMMARY_OUTPUT)

    # Print
    print_results(scored)


if __name__ == "__main__":
    main()
