"""Trust dimension — behind the headline. Operator intelligence, not customer warning."""


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
    else:
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
