"""Financial Impact Summary — the money story that opens every report."""

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

from operator_intelligence.commercial_estimates import _spend_range, _MONTHLY_COVERS


def build_financial_impact(w, venue_name, scorecard, recs, venue_rec,
                           benchmarks=None, review_intel=None):
    """Render the Financial Impact Summary — first thing the owner reads."""
    gpl = venue_rec.get("gpl")
    grc = venue_rec.get("grc") or scorecard.get("google_reviews") or 0
    gr = venue_rec.get("gr") or scorecard.get("google_rating")
    overall = scorecard.get("overall")
    conv = scorecard.get("conversion")
    trust = scorecard.get("trust")

    actions = recs.get("priority_actions", [])

    # Estimate covers and spend from price level
    spend_lo, spend_hi = _spend_range(gpl)
    covers_lo, covers_hi = _MONTHLY_COVERS.get(gpl, _MONTHLY_COVERS[2])
    avg_spend = round((spend_lo + spend_hi) / 2)
    avg_covers_weekly = round((covers_lo + covers_hi) / 2 / 4)

    # Aggregate value at risk from top priorities
    total_risk_lo = 0
    total_risk_hi = 0
    top_issues = []

    for a in actions[:3]:
        dim = a.get("dimension", "")
        title = a.get("title", "")

        # Pull from commercial estimates logic
        if dim == "conversion":
            leak_lo = round(covers_lo * spend_lo * 0.02, -1)
            leak_hi = round(covers_hi * spend_hi * 0.08, -1)
            total_risk_lo += leak_lo
            total_risk_hi += leak_hi
            top_issues.append((title, f"£{leak_lo:,.0f}–£{leak_hi:,.0f}/mo"))
        elif dim == "experience" and a.get("rec_type") == "fix":
            leak_lo = round(covers_lo * spend_lo * 0.03, -1)
            leak_hi = round(covers_hi * spend_hi * 0.10, -1)
            total_risk_lo += leak_lo
            total_risk_hi += leak_hi
            top_issues.append((title, f"£{leak_lo:,.0f}–£{leak_hi:,.0f}/mo"))
        elif dim == "experience" and a.get("rec_type") == "exploit":
            top_issues.append((title, "upside opportunity"))
        elif dim == "trust":
            top_issues.append((title, "£0–£500/mo (defensive)"))
            total_risk_hi += 500
        elif dim == "visibility":
            top_issues.append((title, "discovery protection"))

    # Weekly/monthly/annual projections
    weekly_risk_lo = round(total_risk_lo / 4, -1)
    weekly_risk_hi = round(total_risk_hi / 4, -1)
    annual_risk_lo = total_risk_lo * 12
    annual_risk_hi = total_risk_hi * 12

    # Estimate covers at risk (from conversion leakage)
    covers_at_risk_lo = round(covers_lo * 0.02 / 4)  # weekly
    covers_at_risk_hi = round(covers_hi * 0.08 / 4)

    w("### Financial Impact\n")

    # --- Money paragraph ---
    top_action = actions[0] if actions else None
    top_cost = "minimal effort" if top_action and top_action.get("rec_type") != "fix" else "low cost (< £200)"

    if total_risk_lo > 0:
        w(f"Based on publicly observable data for {venue_name}, your current "
          f"operational gaps are putting an estimated **{covers_at_risk_lo}–{covers_at_risk_hi} "
          f"covers per week** at risk — representing approximately "
          f"**£{total_risk_lo:,.0f}–£{total_risk_hi:,.0f} per month** in lost or "
          f"leaked revenue. The main drivers are: "
          + "; ".join(f"{t} ({v})" for t, v in top_issues[:3]) + ". "
          + (f"Taking action on **{top_action['title']}** could begin recovering "
             f"this within weeks at {top_cost}." if top_action else "")
          + "\n")
    else:
        w(f"Based on publicly observable data for {venue_name}, no major revenue "
          f"leakage was identified. Your operational position is sound. "
          f"The focus should be on protecting your current strengths and "
          f"closing competitive gaps.\n")

    # --- Financial Implications Table ---
    w("| Metric | Current | At Risk | Potential Recovery |")
    w("|---|---|---|---|")
    w(f"| Covers per week | ~{avg_covers_weekly} | "
      f"{covers_at_risk_lo}–{covers_at_risk_hi} at risk | "
      f"Recoverable with profile fixes |")
    w(f"| Average spend per head | ~£{avg_spend} | — | — |")
    if total_risk_lo > 0:
        w(f"| Weekly revenue impact | — | "
          f"£{weekly_risk_lo:,.0f}–£{weekly_risk_hi:,.0f} | "
          f"£{weekly_risk_lo:,.0f}–£{weekly_risk_hi:,.0f} recoverable |")
        w(f"| Monthly revenue impact | — | "
          f"£{total_risk_lo:,.0f}–£{total_risk_hi:,.0f} | "
          f"£{total_risk_lo:,.0f}–£{total_risk_hi:,.0f} recoverable |")
        w(f"| Annual projection | — | "
          f"£{annual_risk_lo:,.0f}–£{annual_risk_hi:,.0f} | "
          f"£{annual_risk_lo:,.0f}–£{annual_risk_hi:,.0f} recoverable |")
    else:
        w("| Revenue impact | — | Minimal | Protect current position |")
    w("")

    w(f"*Estimates based on UK hospitality benchmarks for price level "
      f"{'£' * int(gpl) if gpl else '££'} venues. Ranges are directional — "
      f"exact figures require your internal cover and spend data.*\n")

    # --- Recommended Action ---
    if top_action:
        from operator_intelligence.implementation_framework import _infer_cost_band, _COST_LABELS
        cost = _COST_LABELS.get(_infer_cost_band(top_action), "low cost")
        w(f"**Recommended Action:** {top_action['title']}. "
          f"Estimated cost: {cost}. "
          f"Expected payback: within 1 month.\n")
