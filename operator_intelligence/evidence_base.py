"""
operator_intelligence/evidence_base.py — Evidence Base & Data Basis

Defines three tiers of evidence and computes metadata about what
the report can and cannot claim from each tier. Provides platform
divergence analysis and review velocity where data supports it.
"""

# ============================================================================
# LEGACY (V3.4) — NOT PART OF THE ACTIVE V4 PATH
# ----------------------------------------------------------------------------
# This module is part of the DayDine V3.4 scoring / reporting layer. V4 is
# now the active model (`rcs_scoring_v4.py` + `operator_intelligence/v4_*.py`).
# This file is retained only for rollback, comparison against V4 output
# (via `compare_v3_v4.py`), and historical reference.
#
# Do NOT import this module from any V4 code path. The boundary check in
# `tests/test_v4_legacy_boundary.py` enforces this.
#
# See `docs/DayDine-Legacy-Quarantine-Note.md` for conditions under which
# this file becomes safe to delete.
# ============================================================================


def compute_evidence_base(venue_rec, review_intel=None):
    """Compute the three-tier evidence base for a venue.

    Returns dict with evidence_tiers, platform_divergence,
    review_velocity, and coverage_ratio.
    """
    # Raw counts
    gr = venue_rec.get("gr")
    grc = venue_rec.get("grc") or 0
    ta_rating = venue_rec.get("ta")
    trc = venue_rec.get("trc") or 0

    g_text_count = sum(1 for r in venue_rec.get("g_reviews", [])
                       if (r.get("text") or "").strip())
    ta_text_count = sum(1 for r in venue_rec.get("ta_reviews", [])
                        if (r.get("text") or "").strip())
    deep_total = g_text_count + ta_text_count
    aggregate_total = grc + trc

    coverage_pct = round(deep_total / max(1, aggregate_total) * 100, 1)

    # Structural sources
    structural_sources = []
    if venue_rec.get("r") is not None:
        structural_sources.append("FSA inspection record")
    if venue_rec.get("gpid"):
        structural_sources.append("Google Business Profile")
    if venue_rec.get("web") or venue_rec.get("fb") or venue_rec.get("ig"):
        structural_sources.append("Web presence checks")

    # Tier 1: Deep analysis
    tier_1 = {
        "description": "Full text analysed — aspect tagging, sentiment, segment classification",
        "google_count": g_text_count,
        "tripadvisor_count": ta_text_count,
        "total": deep_total,
        "coverage_of_total": f"{coverage_pct}%",
        "selection_method": "Most recent available via API",
        "what_this_tells_you": (
            "Detailed theme and sentiment patterns from recent guests. "
            "Strong for identifying specific issues and praise points. Not a census."
        ),
        "confidence": "High for recent themes, moderate for long-term patterns",
    }

    # Tier 2: Aggregate signals
    # Rating stability note
    if grc >= 500:
        stability = (f"A {gr}/5 across {grc:,} reviews is extremely stable — "
                     "individual reviews have negligible impact on the aggregate.")
    elif grc >= 100:
        stability = (f"A {gr}/5 across {grc} reviews is stable — "
                     "sustained patterns needed to shift the average.")
    elif grc >= 20:
        stability = f"At {grc} reviews, the rating is moderately stable but can shift."
    else:
        stability = f"At {grc} reviews, the rating is volatile."

    tier_2 = {
        "description": "Rating and volume statistics — no text analysis",
        "google_total_reviews": grc,
        "google_rating": gr,
        "tripadvisor_total_reviews": trc,
        "tripadvisor_rating": ta_rating,
        "total_known_reviews": aggregate_total,
        "rating_stability": stability,
        "what_this_tells_you": (
            f"Overall reputation trajectory. {stability} "
            f"{'The gap between Google and TripAdvisor may reflect different guest demographics.' if gr and ta_rating and abs(float(gr) - float(ta_rating)) >= 0.2 else ''}"
        ),
        "confidence": "High for reputation baseline, cannot identify specific themes",
    }

    # Tier 3: Structural signals
    tier_3 = {
        "description": "Non-review data — FSA, GBP completeness, operational signals",
        "sources": structural_sources,
        "source_count": len(structural_sources),
        "what_this_tells_you": (
            "Compliance, discoverability, and operational readiness. "
            "Independent of guest opinion."
        ),
        "confidence": "High — factual data, not subjective",
    }

    # Platform divergence
    platform_divergence = None
    if gr is not None and ta_rating is not None:
        diff = round(float(gr) - float(ta_rating), 1)
        if abs(diff) >= 0.2:
            if diff > 0:
                hypothesis = (
                    f"TripAdvisor's smaller, more tourist-weighted sample "
                    f"({trc} reviews) may explain the lower average. "
                    f"Tourist expectations can differ from local regulars."
                )
            else:
                hypothesis = (
                    f"Google's larger but algorithmically curated sample "
                    f"may surface different review profiles than TripAdvisor."
                )
            platform_divergence = {
                "google_rating": gr,
                "tripadvisor_rating": ta_rating,
                "difference": diff,
                "direction": "Google higher" if diff > 0 else "TripAdvisor higher",
                "hypothesis": hypothesis,
            }

    return {
        "evidence_tiers": {
            "tier_1_deep_analysis": tier_1,
            "tier_2_aggregate_signals": tier_2,
            "tier_3_structural_signals": tier_3,
        },
        "platform_divergence": platform_divergence,
        "coverage_ratio": coverage_pct,
        "deep_analysed": deep_total,
        "aggregate_total": aggregate_total,
    }
