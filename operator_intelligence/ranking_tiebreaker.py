"""Deterministic DayDine ranking tie-break helpers.

Ranking order is intentionally reproducible when venues share the same rounded
DayDine RCS value. The hierarchy is:

1. Higher review volume.
2. Higher recent-90-day weighted sentiment, where present.
3. Higher category-normalised score, where present.
4. Earliest first-indexed date, where present.
5. Alphabetical venue name as final fallback.

Some data sources do not yet provide recent sentiment, category-normalised
score, or first-indexed date. In those cases the helper records that the value
was unavailable and continues down the hierarchy. This keeps ordering stable
without pretending the missing fields were used.
"""
from __future__ import annotations

from datetime import date
from typing import Any

MISSING_LOW = -1_000_000_000.0
MISSING_LATE_DATE = "9999-12-31"


def safe_float(value: Any, default: float = MISSING_LOW) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def canonical_date(value: Any) -> str:
    if not value:
        return MISSING_LATE_DATE
    text = str(value)[:10]
    try:
        date.fromisoformat(text)
        return text
    except ValueError:
        return MISSING_LATE_DATE


def review_volume(score_block: dict[str, Any], record: dict[str, Any] | None = None) -> int:
    """Return total observed customer review volume across known platforms."""
    record = record or {}
    total = 0
    platforms = (((score_block.get("components") or {})
                  .get("customer_validation") or {})
                 .get("platforms") or {})
    for platform in platforms.values():
        if isinstance(platform, dict):
            total += safe_int(platform.get("count"), 0)

    # Fallbacks for enriched records.
    for key in ("grc", "google_review_count", "review_count", "reviews_count", "user_ratings_total"):
        total = max(total, safe_int(record.get(key), 0))
    return total


def recent_90_sentiment(score_block: dict[str, Any], record: dict[str, Any] | None = None) -> float:
    record = record or {}
    for source in (score_block, record):
        for key in (
            "recent_90_weighted_sentiment",
            "recent_90_day_weighted_sentiment",
            "sentiment_90_weighted",
            "recent_sentiment_weighted",
        ):
            if key in source:
                return safe_float(source.get(key))
    return MISSING_LOW


def category_normalised_score(score_block: dict[str, Any], record: dict[str, Any] | None = None) -> float:
    record = record or {}
    for source in (score_block, record):
        for key in (
            "category_normalised_score",
            "category_normalized_score",
            "category_norm_score",
            "category_z_score",
        ):
            if key in source:
                return safe_float(source.get(key))
    return MISSING_LOW


def first_indexed_date(score_block: dict[str, Any], record: dict[str, Any] | None = None) -> str:
    record = record or {}
    for source in (record, score_block):
        for key in (
            "first_indexed_date",
            "first_indexed",
            "indexed_at",
            "created_at",
            "first_seen",
            "first_seen_at",
        ):
            if source.get(key):
                return canonical_date(source.get(key))
    return MISSING_LATE_DATE


def tiebreak_values(score_block: dict[str, Any], record: dict[str, Any] | None, name: str) -> dict[str, Any]:
    return {
        "review_volume": review_volume(score_block, record),
        "recent_90_weighted_sentiment": recent_90_sentiment(score_block, record),
        "category_normalised_score": category_normalised_score(score_block, record),
        "first_indexed_date": first_indexed_date(score_block, record),
        "venue_name": str(name or "").strip().lower(),
    }


def sort_key(score: float, score_block: dict[str, Any], record: dict[str, Any] | None, name: str) -> tuple[Any, ...]:
    tb = tiebreak_values(score_block, record, name)
    return (
        -float(score),
        -int(tb["review_volume"]),
        -float(tb["recent_90_weighted_sentiment"]),
        -float(tb["category_normalised_score"]),
        tb["first_indexed_date"],
        tb["venue_name"],
    )


def deciding_rule(current: dict[str, Any], previous: dict[str, Any] | None) -> str | None:
    """Return the tie-break rule that placed current after previous.

    Only returns a rule when the current and previous venue share the same
    rounded RCS value. This is used for transparent report/public output copy.
    """
    if not previous:
        return None
    if round(float(current.get("rcs_final") or current.get("score") or 0), 3) != round(float(previous.get("rcs_final") or previous.get("score") or 0), 3):
        return None

    checks = [
        ("higher review volume", "review_volume", True),
        ("higher recent-90-day weighted sentiment", "recent_90_weighted_sentiment", True),
        ("higher category-normalised score", "category_normalised_score", True),
        ("earliest first-indexed date", "first_indexed_date", False),
        ("alphabetical venue name", "venue_name", False),
    ]
    for label, field, higher_better in checks:
        a = current.get("tie_break", {}).get(field)
        b = previous.get("tie_break", {}).get(field)
        if a == b:
            continue
        if a in (MISSING_LOW, MISSING_LATE_DATE, None, "") and b in (MISSING_LOW, MISSING_LATE_DATE, None, ""):
            continue
        return label
    return "alphabetical venue name"


def explanation_for_venue(current: dict[str, Any], previous: dict[str, Any] | None) -> str | None:
    rule = deciding_rule(current, previous)
    if not rule:
        return None
    return f"Joint score / rank resolved by tie-break rules: {rule}."
