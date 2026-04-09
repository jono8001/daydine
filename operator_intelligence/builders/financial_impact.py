"""Financial Impact Summary — the money story that opens every report."""

from operator_intelligence.commercial_estimates import (
    _spend_range, estimate_weekly_covers, _conversion_leak_pct,
)


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

    # Estimate covers and spend from price level + review count
    spend_lo, spend_hi = _spend_range(gpl)
    covers_lo, covers_hi, covers_note = estimate_weekly_covers(gpl, grc)
    avg_spend = round((spend_lo + spend_hi) / 2)
    avg_covers_weekly = round((covers_lo + covers_hi) / 2)

    # Monthly covers from weekly
    monthly_covers_lo = covers_lo * 4
    monthly_covers_hi = covers_hi * 4

    # Conversion-score-driven leak percentage
    leak_pct_lo, leak_pct_hi = _conversion_leak_pct(conv)

    # Aggregate value at risk from top priorities
    total_risk_lo = 0
    total_risk_hi = 0
    top_issues = []

    for a in actions[:3]:
        dim = a.get("dimension", "")
        title = a.get("title", "")

        if dim == "conversion":
            val_lo = round(monthly_covers_lo * spend_lo * leak_pct_lo, -1)
            val_hi = round(monthly_covers_hi * spend_hi * leak_pct_hi, -1)
            total_risk_lo += val_lo
            total_risk_hi += val_hi
            top_issues.append((title, f"£{val_lo:,.0f}–£{val_hi:,.0f}/mo"))
        elif dim == "experience" and a.get("rec_type") == "fix":
            val_lo = round(monthly_covers_lo * spend_lo * 0.03, -1)
            val_hi = round(monthly_covers_hi * spend_hi * 0.10, -1)
            total_risk_lo += val_lo
            total_risk_hi += val_hi
            top_issues.append((title, f"£{val_lo:,.0f}–£{val_hi:,.0f}/mo"))
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

    # Covers at risk (weekly, from conversion leakage)
    covers_at_risk_lo = round(covers_lo * leak_pct_lo)
    covers_at_risk_hi = round(covers_hi * leak_pct_hi)

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
    w("| Metric | Estimate | Basis |")
    w("|---|---|---|")
    w(f"| Estimated weekly covers | ~{covers_lo}–{covers_hi} | {covers_note} |")
    w(f"| Average spend per head | ~£{avg_spend} | UK hospitality benchmark for price level {'£' * int(gpl) if gpl else '££'} |")
    w(f"| Covers at risk per week | {covers_at_risk_lo}–{covers_at_risk_hi} | "
      f"Conversion score {conv:.1f}/10 → {leak_pct_lo:.0%}–{leak_pct_hi:.0%} leakage |"
      if conv is not None else
      f"| Covers at risk per week | {covers_at_risk_lo}–{covers_at_risk_hi} | "
      f"Default 3–7% leakage (no conversion score) |")
    if total_risk_lo > 0:
        w(f"| Weekly revenue at risk | £{weekly_risk_lo:,.0f}–£{weekly_risk_hi:,.0f} | "
          f"Recoverable with priority action fixes |")
        w(f"| Monthly revenue at risk | £{total_risk_lo:,.0f}–£{total_risk_hi:,.0f} | "
          f"Aggregate across top 3 priorities |")
        w(f"| Annual projection | £{annual_risk_lo:,.0f}–£{annual_risk_hi:,.0f} | "
          f"If current gaps persist 12 months |")
    else:
        w("| Revenue impact | Minimal | Protect current position |")
    w("")

    w(f"*All estimates are directional ranges derived from external data only. "
      f"Exact figures require your internal cover and spend data.*\n")

    # --- Recommended Action ---
    if top_action:
        from operator_intelligence.implementation_framework import _infer_cost_band, _COST_LABELS
        cost = _COST_LABELS.get(_infer_cost_band(top_action), "low cost")
        w(f"**Recommended Action:** {top_action['title']}. "
          f"Estimated cost: {cost}. "
          f"Expected payback: within 1 month.\n")
