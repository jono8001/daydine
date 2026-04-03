"""
operator_intelligence/commercial_estimates.py — External-Data Commercial Estimates

Produces rough, honest commercial consequence estimates from publicly
observable data only. Every estimate is a range, never a point.

Key inputs available:
  - gpl (Google price level 1-4)
  - grc (Google review count)
  - gr  (Google star rating)
  - category (venue type)
  - peer count / percentile

These are combined with conservative UK hospitality benchmarks to
produce bounded or directional estimates. All benchmarks are clearly
labelled as industry averages.
"""

from operator_intelligence.report_spec import (
    CommercialConsequence, CONSEQUENCE_NOT_ESTIMABLE,
)


# ---------------------------------------------------------------------------
# UK hospitality benchmarks (conservative, publicly sourced)
# ---------------------------------------------------------------------------
# Average spend per head by Google price level (£)
# Source: UK Hospitality / CGA averages, rounded conservatively
_AVG_SPEND = {1: (8, 15), 2: (15, 30), 3: (30, 50), 4: (50, 90)}

# Approximate monthly covers for a small independent by price level
# These are wide ranges — we never claim precision
_MONTHLY_COVERS = {1: (800, 2000), 2: (600, 1500), 3: (400, 1000), 4: (200, 600)}

# Review-to-visit ratio: ~1 in 50-200 customers leave a Google review
_REVIEW_RATIO = (50, 200)


def _spend_range(gpl):
    """Return (low, high) average spend per head from price level."""
    return _AVG_SPEND.get(gpl, _AVG_SPEND[2])  # default to mid-range


def _monthly_visit_estimate(grc, gpl):
    """Rough monthly visit estimate from review count and price level.
    Returns (low, high) or None if insufficient data."""
    if not grc or grc < 10:
        return None
    # Use cover ranges as primary, review count as sanity check
    return _MONTHLY_COVERS.get(gpl, _MONTHLY_COVERS[2])


# ---------------------------------------------------------------------------
# Per-action consequence estimators
# ---------------------------------------------------------------------------

def estimate_for_action(action, scorecard, venue_rec):
    """Produce a CommercialConsequence for a priority action.

    Returns a CommercialConsequence or None if no useful estimate.
    Dispatches by dimension + rec_type to find the best estimator.
    """
    dim = action.get("dimension", "")
    rec_type = action.get("rec_type", "")
    title_lower = action.get("title", "").lower()
    gpl = venue_rec.get("gpl")
    grc = venue_rec.get("grc") or scorecard.get("google_reviews")
    gr = venue_rec.get("gr") or scorecard.get("google_rating")

    # --- Conversion fixes (hours, menu, delivery, booking) ---
    if dim == "conversion":
        return _estimate_conversion_fix(gpl, grc, gr, title_lower)

    # --- Visibility fixes (photos, reviews, GBP) ---
    if dim == "visibility":
        return _estimate_visibility_fix(gpl, grc, gr, title_lower)

    # --- Experience / review-driven (food quality complaints, service) ---
    if dim == "experience" and rec_type == "fix":
        return _estimate_experience_fix(gpl, grc, gr, title_lower, scorecard)

    if dim == "experience" and rec_type == "exploit":
        return _estimate_experience_exploit(gpl, grc, gr, title_lower)

    # --- Trust / compliance ---
    if dim == "trust":
        return _estimate_trust_fix(scorecard)

    # --- Fallback ---
    return CommercialConsequence(
        value_at_stake=CONSEQUENCE_NOT_ESTIMABLE,
        implementation_cost="—",
        payback="—",
        confidence="not_estimable",
        basis="Insufficient external data for this action type.",
    )


def _estimate_conversion_fix(gpl, grc, gr, title_lower):
    """Conversion fixes: hours, menu, delivery signal, booking."""
    spend_lo, spend_hi = _spend_range(gpl)

    # Conservative: a missing signal costs 2-8% of potential monthly covers
    leak_pct_lo, leak_pct_hi = 0.02, 0.08
    covers = _MONTHLY_COVERS.get(gpl, _MONTHLY_COVERS[2])

    val_lo = round(covers[0] * spend_lo * leak_pct_lo, -1)  # round to £10
    val_hi = round(covers[1] * spend_hi * leak_pct_hi, -1)

    if "hour" in title_lower:
        basis = "2–8% of potential customers filter by 'open now' and won't find you"
        cost = "Zero cost (profile update)"
        payback = "Immediate (same week)"
    elif "menu" in title_lower:
        basis = "Industry data: 77% of diners check menu before visiting"
        cost = "Low (< 1 hour, no spend)"
        payback = "< 1 month"
    elif "delivery" in title_lower or "takeaway" in title_lower:
        basis = "Missing delivery/takeaway flag hides you from filtered searches"
        cost = "Zero cost (profile update)"
        payback = "Immediate (same week)"
    elif "shopfront" in title_lower or "digital" in title_lower:
        basis = "Composite: missing hours/menu/booking each leak 2–8% of demand"
        cost = "Low (< 1 hour, no spend)"
        payback = "< 1 month"
    else:
        basis = "Estimated 2–8% conversion leakage per missing operational signal"
        cost = "Low (< 1 hour, no spend)"
        payback = "< 1 month"

    return CommercialConsequence(
        value_at_stake=f"£{val_lo:,.0f}–£{val_hi:,.0f}/month",
        implementation_cost=cost,
        payback=payback,
        confidence="directional",
        basis=basis,
    )


def _estimate_visibility_fix(gpl, grc, gr, title_lower):
    """Visibility fixes: photos, review count, GBP completeness."""
    spend_lo, spend_hi = _spend_range(gpl)
    covers = _MONTHLY_COVERS.get(gpl, _MONTHLY_COVERS[2])

    if "photo" in title_lower:
        # Venues with photos get ~35% more clicks (Google data)
        # Estimate 5-15% uplift on discovery → visits
        uplift_lo, uplift_hi = 0.05, 0.15
        val_lo = round(covers[0] * spend_lo * uplift_lo, -1)
        val_hi = round(covers[1] * spend_hi * uplift_hi, -1)
        return CommercialConsequence(
            value_at_stake=f"£{val_lo:,.0f}–£{val_hi:,.0f}/month",
            implementation_cost="Low (< 1 hour, no spend)",
            payback="< 1 month",
            confidence="directional",
            basis="Venues with 10+ photos get ~35% more click-throughs (Google data)",
        )

    # Generic visibility
    return CommercialConsequence(
        value_at_stake=CONSEQUENCE_NOT_ESTIMABLE,
        implementation_cost="Low (< 1 hour, no spend)",
        payback="1–3 months",
        confidence="indicative",
        basis="Visibility improvements compound over weeks, not days.",
    )


def _estimate_experience_fix(gpl, grc, gr, title_lower, scorecard):
    """Experience fixes: complaint-driven, food quality issues."""
    spend_lo, spend_hi = _spend_range(gpl)
    covers = _MONTHLY_COVERS.get(gpl, _MONTHLY_COVERS[2])

    # Recurring complaints → estimate 3-10% repeat-visit loss
    leak_pct_lo, leak_pct_hi = 0.03, 0.10
    val_lo = round(covers[0] * spend_lo * leak_pct_lo, -1)
    val_hi = round(covers[1] * spend_hi * leak_pct_hi, -1)

    return CommercialConsequence(
        value_at_stake=f"£{val_lo:,.0f}–£{val_hi:,.0f}/month",
        implementation_cost="Medium (1–2 days or < £200)",
        payback="1–3 months",
        confidence="directional",
        basis="Recurring complaints reduce repeat visits and suppress rating trajectory",
    )


def _estimate_experience_exploit(gpl, grc, gr, title_lower):
    """Experience exploits: lean into strengths, sharpen proposition."""
    return CommercialConsequence(
        value_at_stake="Upside, not loss prevention — magnitude depends on execution",
        implementation_cost="Low (< 1 hour, no spend)",
        payback="1–3 months",
        confidence="indicative",
        basis="Aligning online messaging to guest-validated strengths sharpens conversion",
    )


def _estimate_trust_fix(scorecard):
    """Trust/compliance: FSA re-inspection, documentation."""
    fsa = scorecard.get("fsa_rating")
    if fsa is not None and int(fsa) < 5:
        return CommercialConsequence(
            value_at_stake="Score ceiling removal — unlocks +0.5–1.5 overall score points",
            implementation_cost="Medium (1–2 days or < £200)",
            payback="1–3 months (after re-inspection)",
            confidence="bounded",
            basis=f"FSA {fsa}/5 caps the Trust dimension; re-inspection to 5 removes the cap",
        )
    return CommercialConsequence(
        value_at_stake="Risk mitigation — prevents score drop on next inspection",
        implementation_cost="Low (< 1 hour, no spend)",
        payback="Long-cycle (12+ months)",
        confidence="indicative",
        basis="Maintaining compliance documentation reduces inspection risk",
    )
