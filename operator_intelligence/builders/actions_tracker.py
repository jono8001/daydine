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


def build_recommendation_tracker(w, recs):
    w("## Recommendation Tracker\n")
    all_recs = recs.get("all_recs", [])
    active = [r for r in all_recs if r.get("status") not in ("resolved", "dropped", "completed")]
    resolved = [r for r in all_recs if r.get("status") in ("resolved", "completed")]
    if active:
        w("| # | Recommendation | Status | Since | Months | Owner | Dimension |")
        w("|--:|---------------|--------|-------|-------:|-------|-----------|")
        for i, r in enumerate(sorted(active, key=lambda x: -x.get("priority_score", 0)), 1):
            w(f"| {i} | {r['title'][:50]} | {r['status']} | {r.get('first_seen', '—')} "
              f"| {r.get('times_seen', 1)} | {r.get('owner', '—')} | {r.get('dimension', '—')} |")
        w("")
    else:
        w("First reporting month — all recommendations are new above.\n")
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
    sources = [
        ("FSA Hygiene Rating", f"Rating {fsa}/5" if fsa else "Not available", fsa is not None),
        ("Google Business Profile", f"{gr}★ ({grc} reviews)" if gr else "Not available", gr is not None),
        ("Google Review Text",
         f"{review_intel.get('reviews_analyzed', 0)} reviews analyzed" if has_narr else "Not collected",
         has_narr),
        ("TripAdvisor",
         f"{review_intel.get('review_count_ta', 0)} reviews analysed" if review_intel and review_intel.get("review_count_ta") else "Not collected",
         bool(review_intel and review_intel.get("review_count_ta"))),
        ("Companies House", "Not checked", False),
    ]
    w("| Source | Status | Available |")
    w("|--------|--------|:---------:|")
    for name, status, avail in sources:
        w(f"| {name} | {status} | {'✓' if avail else '—'} |")
    w("")
    n = sum(1 for _, _, a in sources if a)
    if n >= 4:
        w("**Report confidence: High** — Multiple independent sources.\n")
    elif n >= 2:
        w("**Report confidence: Medium** — Core signals available, some dimensions limited.\n")
    else:
        w("**Report confidence: Low** — Sparse data constrains depth.\n")
    unlocks = []
    if not has_narr:
        unlocks.append("**Google review text** → sentiment-by-topic, complaint clustering, quoted evidence")
    has_ta = bool(review_intel and review_intel.get("review_count_ta"))
    if not has_ta:
        unlocks.append("**TripAdvisor enrichment** → cross-platform validation, convergence scoring")
    if unlocks:
        w("**What additional collection would unlock:**\n")
        for u in unlocks:
            w(f"- {u}")
    w("")
    w("")
