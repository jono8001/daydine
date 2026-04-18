"""Trust dimension — behind the headline. Operator intelligence, not customer warning."""

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

from datetime import datetime


def build_trust_detail(w, venue_rec, scorecard, benchmarks):
    """Render the 'Trust — Behind the Headline' subsection."""
    from operator_intelligence.fsa_intelligence import generate_fsa_intelligence

    fsa = generate_fsa_intelligence(venue_rec, scorecard, benchmarks)
    decomp = fsa["decomposition"]
    reinsp = fsa["reinspection"]
    commercial = fsa["commercial"]
    headline = decomp.get("headline_gap")
    r = venue_rec.get("r")

    if not decomp.get("subcomponents"):
        return  # no FSA data

    w("### Trust Dimension — Behind the Headline\n")

    # What customers see vs what we see
    if headline:
        w(f"**What customers see:** FSA {headline['customer_sees']} — "
          f"{'the top hygiene mark. This is a strong public signal and should be protected.' if r and int(r) >= 5 else 'below top mark. Visible to customers.'}\n")
        w(f"**What the data shows behind it:**\n")

    # Subcomponent table
    w("| Subcomponent | Score | Status | Note |")
    w("|---|---|---|---|")
    _status_icons = {
        True: "⚠️ Action possible",
        False: "✅ Strong",
    }
    for c in decomp["subcomponents"]:
        score = c["score_contribution"]
        status = _status_icons.get(c["actionable"], "—")
        if score >= 9.0:
            status = "✅ Strong"
        elif score >= 7.0:
            status = "✅ Adequate"
        elif score >= 5.0:
            status = "⚠️ Room to improve"
        else:
            status = "⚠️ Significant drag"
        note = c["interpretation"]
        if len(note) > 80:
            note = note[:77] + "..."
        w(f"| {c['label']} | {score:.1f}/10 | {status} | {note} |")
    w("")

    # Biggest drag
    drag = decomp.get("biggest_drag")
    if drag:
        w(f"**Biggest drag:** {drag['label']}. {drag['interpretation']}\n")

    # Peer context
    peer = decomp.get("peer_comparison")
    if peer:
        gap = abs(peer["gap_to_leader"])
        if gap >= 1.0:
            # Find the leader name
            ring1 = (benchmarks or {}).get("ring1_local", {})
            top_peers = ring1.get("top_peers", [])
            leader = top_peers[0]["name"] if top_peers else "the leader"
            leader_trust = top_peers[0].get("trust") if top_peers else None
            w(f"**Peer context:** {leader}'s trust lead "
              f"(+{gap:.1f}) is largely built on a more recent inspection, "
              f"not a better rating — all local peers also hold FSA 5/5.\n")

    # What you can do — tone-gated
    w("**What you can do:**\n")
    if r and int(r) >= 5:
        # 5/5 venue: optional, opportunity-framed
        if reinsp["reinspection_recommended"]:
            recovery = reinsp["score_recovery_estimate"]
            peers_beaten = reinsp["peers_overtaken"]
            w(f"1. **Request voluntary reinspection** (free, 4–8 weeks) — "
              f"would recover ~{recovery:.1f} trust points"
              + (f" and overtake {peers_beaten} peers" if peers_beaten else "")
              + f". {reinsp['risk_note']}")
        w("2. **Display your 5/5 prominently** — physical sticker at entrance, "
          "add to Google Business Profile, mention in review responses. Costs nothing.")
        w("3. **Do nothing** — viable. The 5/5 headline protects you with customers. "
          "The gap is competitive, not critical.")
    elif r is not None:
        # Below 5: more urgent
        w(f"1. **Address specific inspection points** — review the last report and "
          f"fix each item. A move to {int(r)+1}/5 unlocks material score improvement.")
        w(f"2. **Request re-inspection** once fixes are complete. "
          f"{reinsp['cost_context']}")
    w("")

    # Commercial read — proportionate
    if commercial:
        upside = commercial.get("upside_if_fixed", {})
        if r and int(r) >= 5:
            w(f"**Commercial read:** This is not a revenue problem today. "
              f"It's a competitive vulnerability — and an easy win if you want it. "
              f"Estimated score recovery: +{reinsp['score_recovery_estimate']:.1f} on trust, "
              f"+{reinsp['overall_score_impact']:.1f} on overall "
              f"({scorecard.get('overall', 0):.1f} → {upside.get('overall_score_after', 0):.1f}).\n")
        else:
            w(f"**Commercial read:** An FSA rating below 5 is actively visible to "
              f"customers and affects booking decisions. "
              f"Addressing this is a revenue protection priority.\n")

    # Business Health Signals sub-section
    _build_business_health(w, venue_rec)


def _build_business_health(w, venue_rec):
    """Render Business Health Signals sub-section from Companies House data."""
    venue_rec = venue_rec or {}
    ch_number = venue_rec.get("ch_company_number")

    w("### Business Health Signals\n")

    if not ch_number or ch_number == "no_match":
        w("*Companies House data not yet matched for this venue. "
          "This will populate once the collection script is run with a valid "
          "API key. If you know your Companies House registration number, "
          "contact us to link it manually.*\n")
        # Still show FSA inspection recency if available
        _render_inspection_recency_standalone(w, venue_rec)
        return

    w("| Signal | Status | Detail |")
    w("|---|---|---|")

    # 1. Companies House status
    ch_status = venue_rec.get("ch_status", "unknown")
    incorporated = venue_rec.get("ch_incorporated", "")
    if ch_status == "active":
        years_trading = ""
        if incorporated:
            try:
                inc_date = datetime.fromisoformat(incorporated)
                years = (datetime.now() - inc_date).days // 365
                years_trading = f", {years} years trading"
            except (ValueError, TypeError):
                pass
        inc_year = incorporated[:4] if incorporated else "unknown"
        w(f"| Companies House | \u2705 Active | Incorporated {inc_year}{years_trading} |")
    elif ch_status == "dissolved":
        w(f"| Companies House | \U0001f534 Dissolved | Company dissolved — investigate |")
    elif ch_status in ("liquidation", "administration", "voluntary-arrangement",
                       "insolvency-proceedings"):
        w(f"| Companies House | \U0001f534 {ch_status.replace('-', ' ').title()} | "
          f"Active insolvency proceedings |")
    else:
        w(f"| Companies House | \u2796 {ch_status.title()} | Status: {ch_status} |")

    # 2. Accounts filing
    accounts_overdue = venue_rec.get("ch_accounts_overdue", False)
    accounts_due = venue_rec.get("ch_accounts_due", "")
    last_filed = venue_rec.get("ch_last_accounts_filed", "")

    if accounts_overdue:
        overdue_days = 0
        if accounts_due:
            try:
                due_date = datetime.fromisoformat(accounts_due)
                overdue_days = (datetime.now() - due_date).days
            except (ValueError, TypeError):
                pass
        if overdue_days > 0:
            w(f"| Accounts filing | \u26a0\ufe0f Overdue | Overdue by {overdue_days} days. "
              f"Late filing penalty \u00a3150\u2013\u00a31,500. "
              f"File at companieshouse.gov.uk immediately |")
        else:
            w(f"| Accounts filing | \u26a0\ufe0f Overdue | Accounts overdue. "
              f"File at companieshouse.gov.uk immediately |")
    elif last_filed and accounts_due:
        last_str = last_filed[:10] if len(last_filed) >= 10 else last_filed
        due_str = accounts_due[:10] if len(accounts_due) >= 10 else accounts_due
        # Format for readability
        try:
            last_display = datetime.fromisoformat(last_filed).strftime("%b %Y")
            due_display = datetime.fromisoformat(accounts_due).strftime("%b %Y")
            w(f"| Accounts filing | \u2705 Current | Last filed {last_display}, "
              f"next due {due_display} |")
        except (ValueError, TypeError):
            w(f"| Accounts filing | \u2705 Current | Last filed {last_str}, "
              f"next due {due_str} |")
    elif last_filed:
        w(f"| Accounts filing | \u2705 Filed | Last filed {last_filed[:10]} |")
    else:
        w(f"| Accounts filing | \u2796 Unknown | No accounts data available |")

    # 3. Directors
    directors = venue_rec.get("ch_directors")
    dir_changes = venue_rec.get("director_changes_12m", 0)
    if directors is not None:
        if dir_changes >= 3:
            w(f"| Directors | \u26a0\ufe0f Churn | {directors} active director(s), "
              f"{dir_changes} changes in 12 months |")
        else:
            w(f"| Directors | \u2705 | {directors} active director(s) |")
    else:
        w(f"| Directors | \u2796 Unknown | No officer data available |")

    # 4. Insolvency
    insolvency = venue_rec.get("ch_insolvency", False)
    if insolvency:
        w(f"| Insolvency record | \U0001f534 Flag | Insolvency events on record — "
          f"investigate at Companies House |")
    else:
        w(f"| Insolvency record | \u2705 Clean | No insolvency events on record |")

    # 5. FSA inspection recency
    _render_inspection_recency_row(w, venue_rec)

    w("")

    # Accounts overdue callout
    if accounts_overdue:
        overdue_days = 0
        if accounts_due:
            try:
                due_date = datetime.fromisoformat(accounts_due)
                overdue_days = (datetime.now() - due_date).days
            except (ValueError, TypeError):
                pass
        if overdue_days > 0:
            w(f"\u26a0\ufe0f **Accounts overdue by {overdue_days} days.** "
              f"Companies House will issue a late filing penalty of "
              f"\u00a3150\u2013\u00a31,500 depending on how late. "
              f"File at companieshouse.gov.uk immediately.\n")


def _render_inspection_recency_row(w, venue_rec):
    """Add FSA inspection recency as a row in the business health table."""
    rd = venue_rec.get("rd")
    if not rd:
        w("| FSA inspection recency | \u2796 Unknown | No inspection date on record |")
        return

    try:
        inspection_date = datetime.fromisoformat(rd.replace("Z", "+00:00"))
        days_ago = (datetime.now() - inspection_date.replace(tzinfo=None)).days
        months_ago = days_ago // 30
    except (ValueError, TypeError):
        w("| FSA inspection recency | \u2796 Unknown | Inspection date not parseable |")
        return

    if months_ago > 24:
        w(f"| FSA inspection recency | \U0001f534 Overdue | Last inspected {months_ago} months ago "
          f"\u2014 re-inspection likely overdue |")
    elif months_ago > 18:
        w(f"| FSA inspection recency | \u26a0\ufe0f Watch | Last inspected {months_ago} months ago "
          f"\u2014 re-inspection likely within 6 months |")
    else:
        w(f"| FSA inspection recency | \u2705 Recent | Last inspected {months_ago} months ago |")


def _render_inspection_recency_standalone(w, venue_rec):
    """Render FSA inspection recency as a standalone note when no CH data."""
    rd = venue_rec.get("rd")
    if not rd:
        return

    try:
        inspection_date = datetime.fromisoformat(rd.replace("Z", "+00:00"))
        days_ago = (datetime.now() - inspection_date.replace(tzinfo=None)).days
        months_ago = days_ago // 30
    except (ValueError, TypeError):
        return

    if months_ago > 24:
        w(f"\U0001f534 **FSA inspection recency:** Last inspected {months_ago} months ago "
          f"\u2014 re-inspection likely overdue.\n")
    elif months_ago > 18:
        w(f"\u26a0\ufe0f **FSA inspection recency:** Last inspected {months_ago} months ago "
          f"\u2014 re-inspection likely within 6 months.\n")
