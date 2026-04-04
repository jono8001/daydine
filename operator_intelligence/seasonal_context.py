"""
operator_intelligence/seasonal_context.py — Seasonal Pattern Recognition

For Stratford-upon-Avon and eventually any location, classifies metric
changes as structural, seasonal, anomalous, or insufficient_data.

V1: Hardcoded Stratford-upon-Avon seasonality patterns.
"""


# ---------------------------------------------------------------------------
# Stratford-upon-Avon seasonality (V1 — hardcoded)
# ---------------------------------------------------------------------------
# RSC theatre season: approx Mar–Oct (main season), Nov–Feb (quieter)
# Peak tourism: Jun–Sep
# Quiet: Nov–Feb
# Pre-theatre dining peaks: Mar–Oct when RSC is running

_STRATFORD_MONTHS = {
    1:  {"season": "quiet",  "tourism": "low",    "rsc": False, "note": "Post-holiday quiet period"},
    2:  {"season": "quiet",  "tourism": "low",    "rsc": False, "note": "Pre-season quiet period"},
    3:  {"season": "shoulder", "tourism": "moderate", "rsc": True, "note": "RSC season opens — early tourism uptick"},
    4:  {"season": "shoulder", "tourism": "moderate", "rsc": True, "note": "Easter tourism + RSC spring programme"},
    5:  {"season": "rising",  "tourism": "moderate", "rsc": True, "note": "Tourism building toward summer peak"},
    6:  {"season": "peak",    "tourism": "high",     "rsc": True, "note": "Peak summer tourism begins"},
    7:  {"season": "peak",    "tourism": "high",     "rsc": True, "note": "Peak summer season"},
    8:  {"season": "peak",    "tourism": "high",     "rsc": True, "note": "Peak summer — highest review volume expected"},
    9:  {"season": "peak",    "tourism": "high",     "rsc": True, "note": "Late summer — still peak tourism"},
    10: {"season": "declining", "tourism": "moderate", "rsc": True, "note": "Autumn — tourism declining, RSC still running"},
    11: {"season": "quiet",  "tourism": "low",    "rsc": False, "note": "Post-season quiet begins"},
    12: {"season": "quiet",  "tourism": "moderate", "rsc": False, "note": "Christmas tourism — brief seasonal uptick"},
}

# Expected review velocity patterns (relative to annual average)
_REVIEW_VELOCITY_FACTORS = {
    1: 0.6, 2: 0.6, 3: 0.8, 4: 0.9, 5: 1.0, 6: 1.3,
    7: 1.5, 8: 1.5, 9: 1.3, 10: 1.0, 11: 0.7, 12: 0.8,
}

# FSA inspection timing patterns
_INSPECTION_NOTES = {
    "imminent": "Last inspection was {months} months ago. The typical re-inspection cycle for a {rating}-rated premises is 18–24 months — a new inspection may be imminent.",
    "overdue": "Last inspection was {months} months ago — beyond the typical 24-month cycle. An unannounced inspection is increasingly likely.",
    "normal": "Last inspection was {months} months ago — within normal re-inspection cycle.",
}


def get_seasonal_context(month_str, location="stratford-upon-avon"):
    """Get seasonal context for a given month and location.

    Returns dict with: season, tourism, rsc, note, review_velocity_factor.
    """
    try:
        month_num = int(month_str.split("-")[1])
    except (ValueError, IndexError):
        return None

    if location.lower() in ("stratford-upon-avon", "stratford"):
        ctx = _STRATFORD_MONTHS.get(month_num, {}).copy()
        ctx["review_velocity_factor"] = _REVIEW_VELOCITY_FACTORS.get(month_num, 1.0)
        ctx["location"] = "Stratford-upon-Avon"
        return ctx

    # Default: no seasonal data
    return {"season": "unknown", "tourism": "unknown", "rsc": False,
            "note": "No seasonal pattern data available for this location",
            "review_velocity_factor": 1.0, "location": location}


def classify_metric_change(delta, metric_name, months_of_data, month_str,
                           location="stratford-upon-avon"):
    """Classify a metric change as structural/seasonal/anomaly/insufficient.

    Returns dict with: classification, explanation.
    """
    if months_of_data < 3:
        return {
            "classification": "insufficient_data",
            "explanation": "Fewer than 3 months of data — too early to classify this change.",
        }

    ctx = get_seasonal_context(month_str, location)
    if not ctx:
        return {
            "classification": "insufficient_data",
            "explanation": "No seasonal context available for this location.",
        }

    # Check if the change aligns with seasonal patterns
    if metric_name in ("google_review_count", "review_velocity"):
        factor = ctx.get("review_velocity_factor", 1.0)
        if delta and delta > 0 and factor > 1.1:
            return {
                "classification": "seasonal",
                "explanation": (f"Review volume increase is consistent with the "
                                f"{ctx['season']} season in {ctx['location']} "
                                f"({ctx['note']}). Treat as seasonal until confirmed "
                                f"over 3+ months."),
            }
        if delta and delta < 0 and factor < 0.8:
            return {
                "classification": "seasonal",
                "explanation": (f"Review volume decline is consistent with the "
                                f"{ctx['season']} period in {ctx['location']} "
                                f"({ctx['note']}). Expected to recover in "
                                f"{'spring' if ctx['season'] == 'quiet' else 'next season'}."),
            }

    # Default: if we have 3+ months and the change persists, it's structural
    if months_of_data >= 3:
        if abs(delta or 0) >= 0.3:
            return {
                "classification": "structural",
                "explanation": "This change has persisted across 3+ months — treat as structural, not seasonal.",
            }

    return {
        "classification": "anomaly",
        "explanation": "Single-month deviation — too early to act on. Monitor for confirmation next month.",
    }


def get_inspection_timing_note(fsa_rating, inspection_date_str):
    """Get a note about inspection timing and likelihood of re-inspection."""
    if not inspection_date_str:
        return None
    try:
        from datetime import datetime
        insp = datetime.strptime(inspection_date_str[:10], "%Y-%m-%d")
        now = datetime.utcnow()
        months = round((now - insp).days / 30)
    except (ValueError, TypeError):
        return None

    if months >= 24:
        return _INSPECTION_NOTES["overdue"].format(months=months, rating=fsa_rating or "?")
    elif months >= 18:
        return _INSPECTION_NOTES["imminent"].format(months=months, rating=fsa_rating or "?")
    else:
        return _INSPECTION_NOTES["normal"].format(months=months, rating=fsa_rating or "?")
