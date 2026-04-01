"""
operator_intelligence/review_delta.py — Review Narrative Delta Engine

Compares current-month review themes against previous month to surface:
  - Praise themes (what customers love)
  - Criticism themes (what needs work)
  - New themes (appeared this month)
  - Fading themes (disappeared this month)
  - Strongest positive/constructive quotes
  - Commercial interpretation

Since we don't yet have per-month review text snapshots from the API,
this module works with the keyword-theme analysis from the scoring engine
and persists theme snapshots month-over-month for delta detection.
"""

import json
import os
from collections import Counter

HISTORY_DIR = "history/review_themes"

# ---------------------------------------------------------------------------
# Theme extraction from available data
# ---------------------------------------------------------------------------

# Keyword → theme mapping (groups related keywords into business-meaningful themes)
THEME_MAP = {
    # Praise themes
    "delicious": "food_quality", "tasty": "food_quality",
    "fresh": "food_quality", "perfectly cooked": "food_quality",
    "amazing food": "food_quality", "excellent food": "food_quality",
    "authentic": "food_quality", "homemade": "food_quality",
    "friendly": "service", "attentive": "service",
    "professional": "service", "great service": "service",
    "welcoming": "service", "helpful": "service",
    "cosy": "ambience", "charming": "ambience",
    "clean": "ambience", "great atmosphere": "ambience",
    "good value": "value", "generous portions": "value",
    "affordable": "value", "worth every penny": "value",
    "quick": "speed", "prompt": "speed", "efficient": "speed",
    # Criticism themes
    "bland": "food_quality_neg", "tasteless": "food_quality_neg",
    "undercooked": "food_quality_neg", "cold food": "food_quality_neg",
    "overcooked": "food_quality_neg", "stale": "food_quality_neg",
    "rude": "service_neg", "unfriendly": "service_neg",
    "slow service": "service_neg", "ignored": "service_neg",
    "poor service": "service_neg", "unprofessional": "service_neg",
    "dirty": "cleanliness_neg", "filthy": "cleanliness_neg",
    "noisy": "ambience_neg", "cramped": "ambience_neg",
    "overpriced": "value_neg", "small portions": "value_neg",
    "rip off": "value_neg", "expensive": "value_neg",
    "long wait": "speed_neg", "took ages": "speed_neg",
    "slow": "speed_neg",
    # Risk themes
    "food poisoning": "safety_risk", "cockroach": "safety_risk",
    "hair in": "safety_risk", "raw chicken": "safety_risk",
}

THEME_LABELS = {
    "food_quality": "Food Quality",
    "service": "Service & Hospitality",
    "ambience": "Atmosphere & Setting",
    "value": "Value for Money",
    "speed": "Speed & Efficiency",
    "food_quality_neg": "Food Quality Concerns",
    "service_neg": "Service Issues",
    "cleanliness_neg": "Cleanliness Concerns",
    "ambience_neg": "Ambience Issues",
    "value_neg": "Value Perception",
    "speed_neg": "Wait Time / Speed Issues",
    "safety_risk": "Food Safety Risk Flags",
}


def extract_themes(record):
    """Extract review themes from a venue's data.
    Works with available review text or infers from scores/flags."""
    themes = Counter()
    quotes_pos = []
    quotes_neg = []

    # Try to extract from actual review text (if we have it)
    for review_field in ["g_reviews", "ta_reviews"]:
        reviews = record.get(review_field, [])
        if not isinstance(reviews, list):
            continue
        for rev in reviews:
            text = (rev.get("text") or "").lower()
            if not text:
                continue
            for keyword, theme in THEME_MAP.items():
                if keyword in text:
                    themes[theme] += 1

            # Extract quote snippets (first sentence, capped)
            rating = rev.get("rating") or rev.get("stars")
            snippet = (rev.get("text") or "")[:120].strip()
            if snippet:
                if rating and int(rating) >= 4:
                    quotes_pos.append(snippet)
                elif rating and int(rating) <= 2:
                    quotes_neg.append(snippet)

    # If no review text, infer themes from available signals
    if not themes:
        themes = _infer_themes_from_signals(record)

    return {
        "themes": dict(themes),
        "quotes_positive": quotes_pos[:3],
        "quotes_constructive": quotes_neg[:3],
    }


def _infer_themes_from_signals(record):
    """When no review text, infer likely themes from structured data."""
    themes = Counter()

    gr = record.get("gr")
    if gr is not None:
        gr = float(gr)
        if gr >= 4.5:
            themes["food_quality"] += 2
            themes["service"] += 1
        elif gr >= 4.0:
            themes["food_quality"] += 1
        elif gr < 3.0:
            themes["food_quality_neg"] += 1
            themes["service_neg"] += 1

    r = record.get("r")
    if r is not None:
        r = int(r)
        if r >= 5:
            themes["food_quality"] += 1
        elif r <= 2:
            themes["cleanliness_neg"] += 1

    # Red flags from scoring
    red_flags = record.get("_red_flags", [])
    if red_flags:
        themes["safety_risk"] += len(red_flags)

    return themes


# ---------------------------------------------------------------------------
# Delta computation
# ---------------------------------------------------------------------------

def compute_review_delta(current_themes, previous_themes):
    """Compare two theme snapshots. Returns delta analysis dict."""
    if not previous_themes:
        return {
            "new_themes": list(current_themes.get("themes", {}).keys()),
            "fading_themes": [],
            "growing_themes": [],
            "declining_themes": [],
            "is_first_month": True,
        }

    cur = current_themes.get("themes", {})
    prev = previous_themes.get("themes", {})
    all_themes = set(cur.keys()) | set(prev.keys())

    new_themes = [t for t in cur if t not in prev]
    fading = [t for t in prev if t not in cur]
    growing = [t for t in all_themes if cur.get(t, 0) > prev.get(t, 0) and t in prev]
    declining = [t for t in all_themes if cur.get(t, 0) < prev.get(t, 0) and t in cur]

    return {
        "new_themes": new_themes,
        "fading_themes": fading,
        "growing_themes": growing,
        "declining_themes": declining,
        "is_first_month": False,
    }


def interpret_commercially(themes, delta):
    """Generate a commercial interpretation paragraph from themes and delta."""
    lines = []

    praise = [t for t in themes.get("themes", {}) if not t.endswith("_neg") and t != "safety_risk"]
    criticism = [t for t in themes.get("themes", {}) if t.endswith("_neg")]
    risks = [t for t in themes.get("themes", {}) if t == "safety_risk"]

    if praise:
        labels = [THEME_LABELS.get(t, t) for t in praise[:3]]
        lines.append(f"Customers respond well to your {', '.join(labels).lower()}.")

    if criticism:
        labels = [THEME_LABELS.get(t, t) for t in criticism[:2]]
        lines.append(f"Recurring criticism around {', '.join(labels).lower()} "
                      "may be suppressing repeat visits and review scores.")

    if risks:
        lines.append("Safety-related language in reviews is a reputational risk "
                      "that needs immediate operational attention.")

    if delta and not delta.get("is_first_month"):
        if delta["new_themes"]:
            new_labels = [THEME_LABELS.get(t, t) for t in delta["new_themes"][:2]]
            lines.append(f"New this month: {', '.join(new_labels).lower()} "
                          "appearing in customer feedback.")
        if delta["fading_themes"]:
            fade_labels = [THEME_LABELS.get(t, t) for t in delta["fading_themes"][:2]]
            lines.append(f"No longer mentioned: {', '.join(fade_labels).lower()} "
                          "— this may reflect resolved issues or shifting priorities.")

    if not lines:
        lines.append("Limited review data available this month. "
                      "Focus on building review volume to enable richer analysis.")

    return " ".join(lines)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_theme_snapshot(venue_id, themes, month_str):
    os.makedirs(HISTORY_DIR, exist_ok=True)
    path = os.path.join(HISTORY_DIR, f"{venue_id}_{month_str}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(themes, f, indent=2, ensure_ascii=False)
    return path


def load_theme_snapshot(venue_id, month_str):
    path = os.path.join(HISTORY_DIR, f"{venue_id}_{month_str}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
