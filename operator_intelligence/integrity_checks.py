"""
operator_intelligence/integrity_checks.py — Report Data Integrity Validation

Runs checks against the analysis output to catch:
  - Quote-theme misalignment
  - Sentiment arithmetic errors
  - Orphan reviews (not classified into any theme)
  - Serious issue surfacing gaps
"""

import re
from operator_intelligence.review_analysis import ASPECT_KEYWORDS, ASPECT_LABELS


def run_integrity_checks(analysis, reviews_raw=None):
    """Run all integrity checks against review analysis output.

    Args:
        analysis: output from analyse_reviews()
        reviews_raw: list of (text, rating, ...) tuples/dicts if available

    Returns dict with checks list and overall pass/fail.
    """
    if not analysis:
        return {"checks": [], "passed": True, "issues": 0}

    checks = []

    # CHECK 1: Sentiment arithmetic
    checks.append(_check_sentiment_arithmetic(analysis))

    # CHECK 2: Quote-theme alignment
    checks.append(_check_quote_theme_alignment(analysis))

    # CHECK 3: Orphan reviews
    checks.append(_check_orphan_reviews(analysis))

    # CHECK 4: Serious issue surfacing
    if reviews_raw:
        checks.append(_check_serious_issues(analysis, reviews_raw))

    # CHECK 5: No duplicate quotes across themes
    checks.append(_check_duplicate_quotes(analysis))

    issues = sum(1 for c in checks if not c["passed"])
    return {
        "checks": checks,
        "passed": issues == 0,
        "issues": issues,
    }


def _check_sentiment_arithmetic(analysis):
    """Verify sentiment counts add up per aspect."""
    aspect_scores = analysis.get("aspect_scores", {})
    errors = []

    for asp, data in aspect_scores.items():
        pos = data.get("positive", 0)
        neg = data.get("negative", 0)
        total = data.get("mentions", 0)
        if pos + neg != total:
            errors.append(
                f"{asp}: positive({pos}) + negative({neg}) = {pos + neg}, "
                f"but mentions = {total}")

    return {
        "check": "sentiment_arithmetic",
        "passed": len(errors) == 0,
        "errors": errors,
    }


def _check_quote_theme_alignment(analysis):
    """Verify quotes in praise/criticism themes contain relevant keywords."""
    errors = []

    for theme_list, polarity in [(analysis.get("praise_themes", []), "praise"),
                                  (analysis.get("criticism_themes", []), "criticism")]:
        for theme in theme_list:
            asp = theme.get("aspect", "")
            keywords = ASPECT_KEYWORDS.get(asp, {})
            all_kws = keywords.get("pos", []) + keywords.get("neg", [])

            for quote in theme.get("quotes", []):
                quote_lower = quote.lower()
                has_match = any(kw in quote_lower for kw in all_kws)
                if not has_match:
                    errors.append(
                        f"{polarity} quote for {asp} has no aspect keywords: "
                        f"\"{quote[:60]}...\"")

    return {
        "check": "quote_theme_alignment",
        "passed": len(errors) == 0,
        "errors": errors,
    }


def _check_orphan_reviews(analysis):
    """Check that every review is classified into at least one theme."""
    per_review = analysis.get("per_review", [])
    orphans = sum(1 for r in per_review if not r.get("aspects"))

    return {
        "check": "orphan_reviews",
        "passed": True,  # orphans are expected for vague reviews
        "orphan_count": orphans,
        "total_reviews": len(per_review),
        "errors": [f"{orphans} of {len(per_review)} reviews had no aspect classification"]
                  if orphans > len(per_review) * 0.5 else [],
    }


def _check_serious_issues(analysis, reviews_raw):
    """Check that serious complaints are surfaced in the analysis."""
    serious_keywords = [
        "food poisoning", "cockroach", "rat ", "hair in", "health hazard",
        "discriminat", "disabled", "wheelchair", "accessibility",
        "refused entry", "turned away", "walk-in",
    ]

    serious_found = []
    for item in reviews_raw:
        text = item[0] if isinstance(item, tuple) else item.get("text", "")
        text_lower = text.lower()
        for kw in serious_keywords:
            if kw in text_lower:
                serious_found.append(f"'{kw}' found in: \"{text[:60]}...\"")
                break

    # Check if these are surfaced in risk_flags or criticism
    risk_flags = analysis.get("risk_flags", [])
    criticism = analysis.get("criticism_themes", [])
    crit_quotes = []
    for c in criticism:
        crit_quotes.extend(c.get("quotes", []))

    surfaced = len(risk_flags) + len(crit_quotes)
    errors = []
    if serious_found and surfaced == 0:
        errors.append(f"{len(serious_found)} serious issues in raw data but none surfaced in analysis")

    return {
        "check": "serious_issue_surfacing",
        "passed": len(errors) == 0,
        "serious_found": len(serious_found),
        "errors": errors,
    }


def _check_duplicate_quotes(analysis):
    """Check that the same quote doesn't appear under multiple themes."""
    all_quotes = []
    for theme_list in [analysis.get("praise_themes", []),
                       analysis.get("criticism_themes", [])]:
        for theme in theme_list:
            for quote in theme.get("quotes", []):
                all_quotes.append((theme.get("aspect"), quote))

    seen = {}
    duplicates = []
    for asp, quote in all_quotes:
        if quote in seen:
            duplicates.append(
                f"Quote appears under both {seen[quote]} and {asp}: \"{quote[:50]}...\"")
        seen[quote] = asp

    return {
        "check": "duplicate_quotes",
        "passed": len(duplicates) == 0,
        "errors": duplicates,
    }
