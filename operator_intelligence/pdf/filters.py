"""
Jinja2 filters used by the PDF templates.

Kept deliberately small and dependency-free — each filter answers a single
question about a value and returns a string the template can drop inline.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime


# RCS bands on the 0-10 scale, matching rcs_scoring_stratford.py / CLAUDE.md.
_BANDS = [
    (8.0, "excellent", "Excellent"),
    (6.5, "good", "Good"),
    (5.0, "satisfactory", "Generally Satisfactory"),
    (3.5, "improvement", "Improvement Necessary"),
    (2.0, "major", "Major Improvement"),
    (0.0, "urgent", "Urgent Improvement"),
]


def venue_slug(name: str) -> str:
    """ASCII, lowercase, dash-separated slug.

    Handles non-ASCII (``Café``), apostrophes (``Annie's``), ampersands
    (``Annie's_Cafe_&_Event_Catering``) and leading digits (``11-17_Salt_Beef_Bar``).
    """
    if not name:
        return "venue"
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    # Strip apostrophes before replacing non-alnum with dashes so that
    # ``Annie's`` → ``annies`` and ``Bardia's`` → ``bardias`` rather than
    # leaving a trailing ``-s`` segment.
    s = s.replace("'", "").replace("\u2019", "")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "venue"


def rcs_band(score) -> str:
    """Return the band slug (``excellent``/``good``/``satisfactory``/...) for a score.

    Used as a CSS class on the band pill on the cover + exec summary.
    """
    try:
        v = float(score)
    except (TypeError, ValueError):
        return "unknown"
    for threshold, slug, _label in _BANDS:
        if v >= threshold:
            return slug
    return "urgent"


def rcs_band_label(score) -> str:
    """Return the human-readable band label (``Good``, ``Excellent``, ...)."""
    try:
        v = float(score)
    except (TypeError, ValueError):
        return "—"
    for threshold, _slug, label in _BANDS:
        if v >= threshold:
            return label
    return "Urgent Improvement"


def pct(value, total=None) -> str:
    """Format a 0-10 score as a percentage width string for progress bars."""
    try:
        if total is None:
            total = 10.0
        v = float(value) / float(total) * 100.0
    except (TypeError, ValueError, ZeroDivisionError):
        return "0"
    return f"{max(0.0, min(100.0, v)):.1f}"


def score_fmt(value, dp: int = 1) -> str:
    """Format a numeric score; ``—`` if None/invalid."""
    if value is None:
        return "—"
    try:
        return f"{float(value):.{dp}f}"
    except (TypeError, ValueError):
        return "—"


def signed_delta(value, dp: int = 1) -> str:
    """Signed delta string: ``+0.3`` / ``-0.2`` / ``—``."""
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.{dp}f}"


def format_month(value) -> str:
    """Render ``2026-04`` as ``April 2026``; pass-through on failure."""
    if not value:
        return ""
    try:
        return datetime.strptime(str(value), "%Y-%m").strftime("%B %Y")
    except ValueError:
        return str(value)


def format_date(value) -> str:
    """Render an ISO date/datetime as ``09 April 2026``."""
    if not value:
        return ""
    try:
        s = str(value).split("T")[0]
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d %B %Y")
    except ValueError:
        return str(value)


def verdict_class(verdict) -> str:
    """CSS class for a demand-capture verdict (Clear/Partial/Missing/Broken)."""
    if not verdict:
        return "verdict-none"
    v = str(verdict).strip().lower()
    return {
        "clear": "verdict-clear",
        "partial": "verdict-partial",
        "gap": "verdict-partial",
        "missing": "verdict-missing",
        "broken": "verdict-broken",
    }.get(v, "verdict-none")


def priority_class(priority) -> str:
    """CSS class for a priority number (high/medium/low)."""
    try:
        v = float(priority)
    except (TypeError, ValueError):
        return "priority-low"
    if v >= 6.0:
        return "priority-high"
    if v >= 3.0:
        return "priority-medium"
    return "priority-low"


def priority_label(priority) -> str:
    try:
        v = float(priority)
    except (TypeError, ValueError):
        return "Low"
    if v >= 6.0:
        return "High"
    if v >= 3.0:
        return "Medium"
    return "Low"


def sentiment_bar(positive, negative) -> dict:
    """Return positive/negative/total percentages for a sentiment stacked bar."""
    try:
        p = int(positive or 0)
        n = int(negative or 0)
    except (TypeError, ValueError):
        p, n = 0, 0
    total = p + n
    if total == 0:
        return {"positive": 0, "negative": 0, "total": 0, "pos_pct": 0, "neg_pct": 0}
    return {
        "positive": p,
        "negative": n,
        "total": total,
        "pos_pct": round(p / total * 100),
        "neg_pct": round(n / total * 100),
    }


def register(env):
    """Attach every filter in this module to a Jinja2 environment."""
    env.filters["venue_slug"] = venue_slug
    env.filters["rcs_band"] = rcs_band
    env.filters["rcs_band_label"] = rcs_band_label
    env.filters["pct"] = pct
    env.filters["score_fmt"] = score_fmt
    env.filters["signed_delta"] = signed_delta
    env.filters["format_month"] = format_month
    env.filters["format_date"] = format_date
    env.filters["verdict_class"] = verdict_class
    env.filters["priority_class"] = priority_class
    env.filters["priority_label"] = priority_label
    env.filters["sentiment_bar"] = sentiment_bar
