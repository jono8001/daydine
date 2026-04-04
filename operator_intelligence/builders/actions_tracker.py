"""Priority actions, watch list, what-not-to-do, recommendation tracker, data coverage."""


def build_priority_actions(w, recs):
    w("## Priority Actions\n")
    for i, a in enumerate(recs.get("priority_actions", [])[:3], 1):
        status = a.get("status", "new").upper()
        w(f"### {i}. {a['title']} [{status}]\n")
        w(f"{a['description']}\n")
        w(f"- **Owner:** {a.get('owner', '—')} | **Dimension:** {a.get('dimension', '—').title()}")
        w(f"- **Expected upside:** {a.get('expected_upside', '—')} | "
          f"**Confidence:** {a.get('confidence', 0):.0%}")
        if a.get("evidence"):
            w(f"- **Evidence:** `{a['evidence']}`")
        if a.get("times_seen", 1) > 1:
            w(f"- *Appeared {a['times_seen']} consecutive months.*")
        w("")


def build_watch_list(w, recs):
    w("## Watch List\n")
    for wa in recs.get("watch_items", [])[:2]:
        w(f"**{wa['title']}** [{wa.get('status', 'new').upper()}]\n")
        w(f"{wa['description']}\n")


def build_what_not_to_do(w, recs):
    w("## What Not to Do This Month\n")
    dont = recs.get("what_not_to_do")
    if dont:
        w(f"**{dont['title']}**\n")
        w(f"{dont.get('_reason', dont.get('description', ''))}\n")


def build_recommendation_tracker(w, recs, month_str=None):
    """Implementation Framework — structured action cards replacing the flat tracker."""
    from operator_intelligence.implementation_framework import generate_action_cards

    cards = generate_action_cards(recs, month_str or "2026-04")

    w("## Implementation Framework\n")

    if not cards:
        w("First reporting month — all recommendations are new in the priorities above.\n")
        return

    # Summary
    chronic = sum(1 for c in cards if c["times_seen"] >= 12)
    overdue = sum(1 for c in cards if 6 <= c["times_seen"] < 12)
    stale = sum(1 for c in cards if 3 <= c["times_seen"] < 6)
    new_count = sum(1 for c in cards if c["times_seen"] < 3)

    summary_parts = []
    if chronic:
        summary_parts.append(f"**{chronic} chronic** (12+ months)")
    if overdue:
        summary_parts.append(f"**{overdue} overdue** (6–11 months)")
    if stale:
        summary_parts.append(f"**{stale} stale** (3–5 months)")
    if new_count:
        summary_parts.append(f"**{new_count} new/recent**")
    w(f"{len(cards)} active items: {', '.join(summary_parts)}.\n")

    # Action cards — top priority first, limit to top 5 for readability
    for i, card in enumerate(cards[:5], 1):
        w(f"### Action {i}: {card['title']}")
        w(f"**Status:** {card['status_label']} | **Priority:** "
          f"{'High' if card['priority_score'] >= 7 else 'Medium' if card['priority_score'] >= 4 else 'Standard'}")
        w(f"**Target date:** {card['target_date']} | "
          f"**Cost:** {card['cost_label']} | "
          f"**Expected upside:** {card['expected_upside']}")
        w(f"**Owner:** {card['owner_guidance']}")
        w(f"**Next milestone:** {card['next_milestone']}")
        w(f"**Success measure:** {card['success_measure']}")

        # Barrier diagnosis (3+ months only)
        if card["barrier"]:
            cat, label, explanation = card["barrier"]
            w(f"**Barrier diagnosis ({label}):** {explanation}")

        w("")

    # Compact index for remaining items
    if len(cards) > 5:
        w("### Additional Active Recommendations\n")
        w("| # | Recommendation | Status | Target | Cost |")
        w("|--:|---------------|--------|--------|------|")
        for i, card in enumerate(cards[5:], 6):
            w(f"| {i} | {card['title'][:45]} | {card['status_label']} "
              f"| {card['target_date']} | {card['cost_label']} |")
        w("")

    # Resolved count
    all_recs = recs.get("all_recs", [])
    resolved = [r for r in all_recs if r.get("status") in ("resolved", "completed")]
    if resolved:
        w(f"*{len(resolved)} recommendation(s) resolved/completed.*\n")


def build_competitive_market_intelligence(w, scorecard, benchmarks, blocks):
    """Mandatory Competitive Market Intelligence section — lens 4.

    Always produces output. Uses peer benchmarks as the primary source,
    conditional blocks as supplementary alerts.
    """
    w("## Competitive Market Intelligence\n")

    ring1 = (benchmarks or {}).get("ring1_local") or {}
    ring2 = (benchmarks or {}).get("ring2_catchment") or {}
    ring = ring1 or ring2

    overall = scorecard.get("overall")

    if ring and ring.get("peer_count", 0) > 0:
        peer_count = ring["peer_count"]
        dims = ring.get("dimensions", {})
        ov = dims.get("overall", {})
        pct = ov.get("percentile")
        peer_avg = ov.get("peer_mean")
        peer_top = ov.get("peer_top")

        w(f"**Local market:** {peer_count} direct competitors identified.\n")

        if pct is not None and peer_avg is not None:
            if pct >= 80:
                w(f"You are in the top quintile (P{pct:.0f}). The competitive risk "
                  f"is complacency — the nearest competitor scores {peer_top:.1f}.\n")
            elif pct >= 50:
                w(f"Above the median (P{pct:.0f}) but not leading. Peer average is "
                  f"{peer_avg:.1f}; the top performer scores {peer_top:.1f}. "
                  f"The gap to the top is closeable.\n")
            else:
                w(f"Below the median (P{pct:.0f}). Customers have higher-rated "
                  f"alternatives nearby (peer avg {peer_avg:.1f}, top {peer_top:.1f}).\n")

        # Dimension-level competitive gaps
        dim_gaps = []
        for dim in ["experience", "visibility", "trust", "conversion"]:
            d = dims.get(dim, {})
            if d.get("peer_mean") is not None and d.get("score") is not None:
                gap = d["score"] - d["peer_mean"]
                if abs(gap) >= 0.5:
                    dim_gaps.append((dim, gap))

        if dim_gaps:
            leads = [(d, g) for d, g in dim_gaps if g > 0]
            lags = [(d, g) for d, g in dim_gaps if g < 0]
            if leads:
                lead_str = ", ".join(f"{d.title()} (+{g:.1f})" for d, g in sorted(leads, key=lambda x: -x[1]))
                w(f"**Where you lead:** {lead_str}")
            if lags:
                lag_str = ", ".join(f"{d.title()} ({g:+.1f})" for d, g in sorted(lags, key=lambda x: x[1]))
                w(f"**Where peers beat you:** {lag_str}")
            w("")

        # Commercial consequence of competitive position
        if pct is not None and peer_count > 0:
            share_pct = round(100 / (peer_count + 1))
            if pct < 50:
                w(f"*Commercial implication: in a {peer_count + 1}-venue market, "
                  f"a below-median position means demand is flowing to competitors. "
                  f"Each percentile point gained recaptures a share of local search traffic. "
                  f"Estimated fair share: ~{share_pct}% of local demand — "
                  f"you are likely underindexed (directional).*\n")
            elif pct < 80:
                w(f"*Commercial implication: you capture an adequate share of "
                  f"a {peer_count + 1}-venue market, but the gap to the top "
                  f"({peer_top:.1f}) represents demand you could win. "
                  f"Closing the gap typically requires 1–2 targeted dimension "
                  f"improvements (indicative).*\n")

        # Density assessment
        if peer_count >= 10:
            w(f"**Density alert:** {peer_count} competitors within range. "
              f"Differentiation is critical — competing on fundamentals alone "
              f"is insufficient in a dense market.\n")
    else:
        w("*Insufficient peer data for competitive analysis. "
          "Market intelligence will strengthen as more establishments are scored.*\n")

    # Supplementary conditional blocks (compliance risk, visibility gap, etc.)
    if blocks:
        for b in blocks:
            w(f"### {b['title']}\n")
            w(f"{b['content']}\n")


def build_data_coverage(w, scorecard, review_intel):
    w("---\n")
    w("## Data Coverage & Confidence\n")
    has_narr = review_intel.get("has_narrative", False) if review_intel else False
    fsa = scorecard.get("fsa_rating")
    gr = scorecard.get("google_rating")
    grc = scorecard.get("google_reviews")
    has_ta = bool(review_intel and review_intel.get("review_count_ta"))

    # Source inventory with provenance
    rows = [
        ("FSA Hygiene Rating", f"Rating {fsa}/5" if fsa else "Not available",
         fsa is not None, "observed" if fsa is not None else "not_assessed"),
        ("Google Business Profile", f"{gr}★ ({grc} reviews)" if gr else "Not available",
         gr is not None, "observed" if gr is not None else "not_assessed"),
        ("Google Review Text",
         f"{review_intel.get('reviews_analyzed', 0)} reviews analyzed" if has_narr else "Not collected",
         has_narr, "observed" if has_narr else "not_assessed"),
        ("TripAdvisor",
         f"{review_intel.get('review_count_ta', 0)} reviews analysed" if has_ta else "Not collected",
         has_ta, "observed" if has_ta else "not_assessed"),
        ("Companies House", "Not checked", False, "not_assessed"),
    ]
    w("| Source | Status | Provenance | Available |")
    w("|--------|--------|------------|:---------:|")
    for name, status, avail, prov in rows:
        w(f"| {name} | {status} | {prov} | {'✓' if avail else '—'} |")
    w("")

    # Confidence based on INDEPENDENT sources, not data fields
    # FSA, Google (one platform), TripAdvisor = 3 possible independent sources
    independent = 0
    if fsa is not None:
        independent += 1
    if gr is not None:
        independent += 1  # Google counts once (rating + text = same platform)
    if has_ta:
        independent += 1

    if independent >= 3:
        w(f"**Report confidence: High** — {independent} independent sources (FSA, Google, TripAdvisor).\n")
    elif independent >= 2:
        sources_named = []
        if fsa is not None: sources_named.append("FSA")
        if gr is not None: sources_named.append("Google")
        if has_ta: sources_named.append("TripAdvisor")
        w(f"**Report confidence: Medium** — {independent} independent sources "
          f"({', '.join(sources_named)}). "
          f"Additional platforms would strengthen cross-validation.\n")
    else:
        w("**Report confidence: Low** — Single source or sparse data. "
          "Findings are directional only.\n")

    unlocks = []
    if not has_narr:
        unlocks.append("**Google review text** → sentiment-by-topic, complaint clustering, quoted evidence")
    if not has_ta:
        unlocks.append("**TripAdvisor enrichment** → cross-platform validation, convergence scoring")
    if unlocks:
        w("**What additional collection would unlock:**\n")
        for u in unlocks:
            w(f"- {u}")
    w("")
    w("")
