"""Operational & Risk Alerts section builder."""

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


def build_risk_alerts(w, venue_rec):
    """Render the Operational & Risk Alerts section."""
    from operator_intelligence.risk_detection import scan_reviews_for_risks

    result = scan_reviews_for_risks(venue_rec)

    w("## Operational & Risk Alerts\n")
    w("> This section flags issues that go beyond normal review themes. "
      "These are patterns that could represent legal liability, operational "
      "failure, or reputational damage requiring direct action.\n")

    if result["clean"]:
        w("### No Operational or Risk Alerts This Period\n")
        w(f"No review patterns in the {result['reviews_scanned']} reviews scanned "
          "indicate legal, safety, staffing, or operational risks above normal levels. "
          "This is a positive signal. Standard theme analysis follows below.\n")
        return result

    for alert in result["alerts"]:
        severity = alert["severity"]
        icon = "🔴" if severity == "red" else "🟡"

        w(f"### {icon} {alert['label']}\n")

        # What we found
        w(f"**What we found:** {alert['review_count']} review(s) in this period "
          f"contain language indicating {alert['label'].lower()}. "
          f"Keywords detected: {', '.join(alert['keywords_found'][:5])}.\n")

        # Evidence
        w(f"**Evidence:**")
        for quote in alert["quotes"][:3]:
            w(f'- *"{quote}"*')
        w("")

        # Why it matters / consequence
        if severity == "red":
            w(f"**Why this matters:** {alert['consequence']} "
              "We recommend seeking specific professional advice on this matter.\n")
            w(f"**Recommended action:** Investigate these specific incidents immediately. "
              "Review your accessibility and inclusion policies. "
              "Respond to the affected reviews professionally and empathetically.\n")
        else:
            w(f"**What to watch for:** If this pattern continues next month, "
              "it escalates from a warning to a structural issue requiring direct action.\n")
            w(f"**Suggested action:** {alert['consequence']} "
              "Review operations for the specific pattern identified.\n")

    return result
