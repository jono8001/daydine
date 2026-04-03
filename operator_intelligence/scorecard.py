"""
operator_intelligence/scorecard.py — Dimension Scorecard

Computes 5 operator-facing dimensions from raw establishment data:
  - Experience: food quality, service, ambience (FSA + Google + sentiment)
  - Visibility: online presence, review volume, photos, GBP completeness
  - Trust: FSA rating, inspection recency, convergence across sources
  - Conversion: operational readiness — hours, delivery, reservations, menu
  - Prestige: awards, editorial recognition, price positioning

Each dimension is 0-10. An overall Operator Score is a weighted roll-up.
"""

import json
import math
import os
import sys

# Add parent dir so we can import the scoring engine
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rcs_scoring_stratford import (
    safe_float, safe_int, clamp, days_since, temporal_decay,
    classify_category, is_food_establishment, TEMPORAL_LAMBDA,
)

# ---------------------------------------------------------------------------
# Dimension weights for overall Operator Score
# ---------------------------------------------------------------------------
DIMENSION_WEIGHTS = {
    "experience":  0.30,
    "visibility":  0.20,
    "trust":       0.25,
    "conversion":  0.15,
    "prestige":    0.10,
}

# ---------------------------------------------------------------------------
# Dimension scorers — each returns 0-10 float
# ---------------------------------------------------------------------------

def score_experience(rec):
    """Food quality, service, ambience signals. 0-10."""
    parts = []
    weights = []

    # FSA sub-scores (food hygiene quality)
    sh = safe_float(rec.get("sh"))
    if sh is not None:
        parts.append(sh)  # already 0-10
        weights.append(0.25)

    # Google rating as experience proxy
    gr = safe_float(rec.get("gr"))
    if gr is not None:
        parts.append(gr * 2.0)  # 1-5 → 2-10
        weights.append(0.35)

    # TripAdvisor rating
    ta = safe_float(rec.get("ta"))
    if ta is not None:
        parts.append(ta * 2.0)
        weights.append(0.25)

    # Sentiment score (0-1 → 0-10)
    sent = safe_float(rec.get("_sentiment_score"))
    if sent is not None:
        parts.append(sent * 10.0)
        weights.append(0.15)

    if not parts:
        return None

    total_w = sum(weights)
    return round(clamp(sum(p * w for p, w in zip(parts, weights)) / total_w, 0, 10), 2)


def score_visibility(rec):
    """Online presence, review volume, photos, GBP completeness. 0-10."""
    signals = 0
    total = 0
    max_score = 0.0

    # Google review count (log scale, cap 2000)
    grc = safe_int(rec.get("grc"))
    if grc is not None:
        vol = clamp(math.log10(max(1, grc)) / math.log10(2000))
        max_score += vol * 2.5
        signals += 1
    total += 1

    # Google photos
    gpc = safe_int(rec.get("gpc"))
    if gpc is not None:
        max_score += clamp(gpc / 10.0) * 1.5
        signals += 1
    total += 1

    # GBP completeness (0-10 → 0-2)
    gbp = safe_float(rec.get("gbp_completeness"))
    if gbp is not None:
        max_score += clamp(gbp / 10.0) * 2.0
        signals += 1
    total += 1

    # Web / Facebook / Instagram presence
    for field, weight in [("web", 1.0), ("fb", 0.8), ("ig", 0.7)]:
        val = rec.get(field)
        if val is True:
            max_score += weight
            signals += 1
        total += 1

    # TripAdvisor presence
    if rec.get("ta") is not None or rec.get("ta_present"):
        max_score += 1.5
        signals += 1
    total += 1

    if signals == 0:
        return None

    return round(clamp(max_score, 0, 10), 2)


def score_trust(rec):
    """FSA rating, inspection recency, source convergence. 0-10."""
    parts = []
    weights = []

    # FSA rating (1-5 → 2-10)
    r = safe_float(rec.get("r"))
    if r is not None:
        parts.append(r * 2.0)
        weights.append(0.40)

    # Inspection recency (decay-based)
    age = days_since(rec.get("rd"))
    if age is not None:
        decay = temporal_decay(age)
        parts.append(decay * 10.0)
        weights.append(0.25)

    # Structural compliance
    ss = safe_float(rec.get("ss"))
    if ss is not None:
        parts.append(ss)  # already 0-10
        weights.append(0.15)

    # Confidence in management
    sm = safe_float(rec.get("sm"))
    if sm is not None:
        parts.append(sm)
        weights.append(0.20)

    if not parts:
        return None

    total_w = sum(weights)
    return round(clamp(sum(p * w for p, w in zip(parts, weights)) / total_w, 0, 10), 2)


def score_conversion(rec):
    """Operational readiness — hours, delivery, menu, reservations. 0-10."""
    score = 0.0
    signals = 0

    # Opening hours completeness
    goh = rec.get("goh")
    if isinstance(goh, list) and len(goh) > 0:
        score += min(1.0, len(goh) / 7.0) * 2.5
        signals += 1

    # Delivery / takeaway
    gty = rec.get("gty", [])
    if isinstance(gty, list):
        if "meal_takeaway" in gty or rec.get("offers_takeaway"):
            score += 1.5
            signals += 1
        if "food_delivery" in gty or rec.get("offers_delivery"):
            score += 1.5
            signals += 1

    # Menu online
    if rec.get("has_menu_online"):
        score += 2.0
        signals += 1

    # Reservations
    if rec.get("accepts_reservations"):
        score += 1.5
        signals += 1

    # Price level set (signals operator intent)
    if rec.get("gpl") is not None:
        score += 1.0
        signals += 1

    if signals == 0:
        return None

    return round(clamp(score, 0, 10), 2)


def score_prestige(rec):
    """Awards, editorial recognition, price positioning. 0-10."""
    score = 0.0
    signals = 0

    if rec.get("has_michelin_mention"):
        score += 4.0
        signals += 1

    if rec.get("has_aa_rating"):
        score += 3.0
        signals += 1

    awards = safe_int(rec.get("local_awards_count"))
    if awards is not None and awards > 0:
        score += min(awards, 3) * 1.0
        signals += 1

    # Price level as prestige indicator (higher = more premium positioning)
    gpl = safe_int(rec.get("gpl"))
    if gpl is not None and gpl >= 3:
        score += 1.5
        signals += 1

    # High Google rating (4.5+) as earned prestige
    gr = safe_float(rec.get("gr"))
    if gr is not None and gr >= 4.5:
        score += 1.5
        signals += 1

    if signals == 0:
        return 0.0  # No prestige is valid — score zero, not None

    return round(clamp(score, 0, 10), 2)


# ---------------------------------------------------------------------------
# Full scorecard for one venue
# ---------------------------------------------------------------------------

SCORERS = {
    "experience":  score_experience,
    "visibility":  score_visibility,
    "trust":       score_trust,
    "conversion":  score_conversion,
    "prestige":    score_prestige,
}


def compute_scorecard(rec):
    """Compute all 5 dimensions + overall score for one establishment.
    Returns dict with dimension scores (0-10) and overall (0-10)."""
    dims = {}
    for name, scorer in SCORERS.items():
        dims[name] = scorer(rec)

    # Overall = weighted average of available dimensions
    num = 0.0
    den = 0.0
    for name, weight in DIMENSION_WEIGHTS.items():
        val = dims.get(name)
        if val is not None:
            num += val * weight
            den += weight

    dims["overall"] = round(num / den, 2) if den > 0 else None
    return dims


def compute_all_scorecards(data):
    """Score all establishments. Returns dict keyed by FHRSID."""
    results = {}
    for key, rec in data.items():
        food_ok, _ = is_food_establishment(rec)
        if not food_ok:
            continue
        cat, cat_source = classify_category(rec)
        card = compute_scorecard(rec)
        card["fhrsid"] = rec.get("id") or key
        card["name"] = rec.get("n", "Unknown")
        card["postcode"] = rec.get("pc", "")
        card["category"] = cat
        card["category_source"] = cat_source
        card["lat"] = rec.get("lat")
        card["lon"] = rec.get("lon")
        card["google_rating"] = safe_float(rec.get("gr"))
        card["google_reviews"] = safe_int(rec.get("grc"))
        card["fsa_rating"] = safe_int(rec.get("r"))
        card["price_level"] = safe_int(rec.get("gpl"))
        results[str(card["fhrsid"])] = card
    return results


# ---------------------------------------------------------------------------
# Snapshot persistence
# ---------------------------------------------------------------------------

def save_snapshot(scorecards, month_str, output_dir="history/monthly_snapshots"):
    """Persist a month's scorecards to JSON for delta comparison."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"snapshot_{month_str}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(scorecards, f, indent=2, ensure_ascii=False)
    return path


def load_snapshot(month_str, output_dir="history/monthly_snapshots"):
    """Load a previous month's snapshot. Returns None if not found."""
    path = os.path.join(output_dir, f"snapshot_{month_str}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_score_deltas(current, previous):
    """Compare two scorecards for the same venue.
    Returns dict of {dimension: delta} where delta = current - previous."""
    if not previous:
        return None
    deltas = {}
    for dim in list(DIMENSION_WEIGHTS.keys()) + ["overall"]:
        cur = current.get(dim)
        prev = previous.get(dim)
        if cur is not None and prev is not None:
            deltas[dim] = round(cur - prev, 2)
        else:
            deltas[dim] = None
    return deltas
