"""Priority actions, watch list, what-not-to-do, recommendation tracker, data coverage."""

import glob
import json
import re
from pathlib import Path

from operator_intelligence.review_analysis import (
    analyse_reviews, ASPECT_LABELS,
)


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

    # Separate action items from maintenance/deprioritised items
    action_cards = [c for c in cards if not c.get("is_deprioritised")]
    maintenance_cards = [c for c in cards if c.get("is_deprioritised")]

    # Action cards — top priority first, limit to top 5 for readability
    for i, card in enumerate(action_cards[:5], 1):
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

    # Maintenance items (deprioritised — consistent with Executive Summary)
    if maintenance_cards:
        w("### Maintenance Items (deprioritised this month)\n")
        w("*These items are designated 'do not prioritise' in the Executive Summary. "
          "They are ongoing postures, not active action items.*\n")
        for card in maintenance_cards:
            w(f"- **{card['title']}** — {card['expected_upside']}. "
              f"Maintain current approach; no active effort required.")
        w("")

    # Compact index for remaining action items
    if len(action_cards) > 5:
        w("### Additional Active Recommendations\n")
        w("| # | Recommendation | Status | Target | Cost |")
        w("|--:|---------------|--------|--------|------|")
        for i, card in enumerate(action_cards[5:], 6):
            w(f"| {i} | {card['title'][:45]} | {card['status_label']} "
              f"| {card['target_date']} | {card['cost_label']} |")
        w("")

    # Resolved count
    all_recs = recs.get("all_recs", [])
    resolved = [r for r in all_recs if r.get("status") in ("resolved", "completed")]
    if resolved:
        w(f"*{len(resolved)} recommendation(s) resolved/completed.*\n")


PROCESSED_DIR = Path("data/processed")


def _venue_slug(name):
    """Derive a file-system slug from a venue name.

    Must match the naming convention used by the Playwright review collectors
    which replace apostrophes and special chars with underscores.
    """
    slug = name.lower().strip()
    # Replace apostrophes and hyphens with underscores (matches collector convention)
    slug = slug.replace("'", "_").replace("\u2019", "_")
    slug = re.sub(r"[^\w\s]", "", slug)
    slug = re.sub(r"[\s]+", "_", slug)
    # Collapse multiple underscores
    slug = re.sub(r"_+", "_", slug)
    return slug.strip("_")


def _load_peer_review_themes(peer_name):
    """Load review themes for a peer venue from data/processed/ files.

    Looks for files matching data/processed/{slug}_*_combined.json,
    loads reviews, runs aspect NLP, and returns top praise/complaints.

    Returns {"top_praise": [...], "top_complaints": [...], "review_count": N}
    or None if no data found.
    """
    slug = _venue_slug(peer_name)
    pattern = str(PROCESSED_DIR / f"{slug}_*_combined.json")
    matches = glob.glob(pattern)
    if not matches:
        return None

    # Use the most recent file
    matches.sort(reverse=True)
    try:
        with open(matches[0], "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

    reviews_raw = data.get("reviews", [])
    if not reviews_raw:
        return None

    # Build review tuples for analyse_reviews
    review_items = []
    for r in reviews_raw:
        text = r.get("text", "")
        rating = r.get("rating")
        date_str = r.get("date")
        source = r.get("source")
        if text:
            review_items.append({"text": text, "rating": rating,
                                 "date": date_str, "source": source})

    if not review_items:
        return None

    analysis = analyse_reviews(review_items)
    if not analysis:
        return None

    # Extract top 3 praise and top 3 complaints
    praise = []
    for theme in analysis.get("praise_themes", [])[:3]:
        label = theme.get("label", "")
        mentions = theme.get("mentions", 0)
        praise.append({"label": label, "mentions": mentions,
                        "aspect": theme.get("aspect", "")})

    complaints = []
    for theme in analysis.get("criticism_themes", [])[:3]:
        label = theme.get("label", "")
        mentions = theme.get("mentions", 0)
        complaints.append({"label": label, "mentions": mentions,
                            "aspect": theme.get("aspect", "")})

    return {
        "top_praise": praise,
        "top_complaints": complaints,
        "review_count": analysis.get("reviews_analyzed", 0),
    }


def _build_strategic_reads(peer_themes, own_review_intel):
    """Generate strategic reads comparing peer weaknesses to own strengths.

    Returns list of one-sentence strategic read strings.
    """
    reads = []
    own_analysis = (own_review_intel or {}).get("analysis") or {}
    own_aspect_scores = own_analysis.get("aspect_scores", {})

    for peer_name, themes in peer_themes.items():
        if not themes or not themes.get("top_complaints"):
            continue

        for complaint in themes["top_complaints"]:
            aspect = complaint.get("aspect", "")
            label = complaint.get("label", "")
            mentions = complaint.get("mentions", 0)
            if not aspect or mentions < 2:
                continue

            # Check if we have a strength in the same aspect
            own = own_aspect_scores.get(aspect, {})
            own_pos = own.get("positive", 0)
            own_neg = own.get("negative", 0)
            own_score = own.get("score")

            if own_pos > 0 and own_score is not None and own_score >= 7.0:
                reads.append(
                    f"{peer_name} guests frequently complain about "
                    f"{label.lower()} ({mentions}x). Your {label.lower()} "
                    f"scores {own_score:.1f}/10. This is an exploitable gap "
                    f"\u2014 highlight this strength in your listing and "
                    f"review responses."
                )
                break  # One read per peer

    return reads


def build_competitive_market_intelligence(w, scorecard, benchmarks, blocks,
                                          prior_snapshot=None, venue_rec=None,
                                          review_intel=None, all_data=None):
    """Mandatory Competitive Market Intelligence section — lens 4.

    Always produces output. Uses peer benchmarks as the primary source,
    conditional blocks as supplementary alerts. When peer review data
    is available, shows guest theme comparison with strategic reads.
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

        # Position movement vs prior month
        prior_pp = (prior_snapshot or {}).get("peer_position", {})
        prior_rank = prior_pp.get("local_rank")
        prior_of = prior_pp.get("local_of")
        cur_rank = ov.get("rank")
        if prior_rank and cur_rank:
            if cur_rank == prior_rank:
                w(f"**Movement:** Unchanged from last month (#{cur_rank}).\n")
            elif cur_rank < prior_rank:
                w(f"**Movement:** Improved from #{prior_rank} to #{cur_rank} "
                  f"since last month.\n")
            else:
                w(f"**Movement:** Dropped from #{prior_rank} to #{cur_rank} "
                  f"since last month.\n")
        elif not prior_snapshot:
            pass  # baseline month, no movement to report
        else:
            w("**Movement:** Prior month position data unavailable.\n")

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

        # Competitor guest intelligence
        _render_competitor_guest_intel(w, ring, review_intel)
    else:
        w("*Insufficient peer data for competitive analysis. "
          "Market intelligence will strengthen as more establishments are scored.*\n")

    # Supplementary conditional blocks (compliance risk, visibility gap, etc.)
    if blocks:
        for b in blocks:
            w(f"### {b['title']}\n")
            w(f"{b['content']}\n")


def _render_competitor_guest_intel(w, ring, review_intel):
    """Render 'What Your Competitors' Guests Are Saying' sub-section."""
    top_peers = ring.get("top_peers", [])
    if not top_peers:
        return

    # Try to load review themes for each peer
    peer_themes = {}
    has_any_themes = False
    for peer in top_peers[:5]:
        name = peer.get("name", "")
        if not name:
            continue
        themes = _load_peer_review_themes(name)
        if themes:
            peer_themes[name] = themes
            has_any_themes = True

    if not has_any_themes:
        w("### Competitive Position\n")
        w("*Competitor guest intelligence will populate as review data is "
          "collected for local peers. Score comparison above.*\n")
        return

    w("### What Your Competitors' Guests Are Saying\n")

    w("| Competitor | Score | Their top praise | Their main complaint | Your edge |")
    w("|---|---|---|---|---|")

    strategic_reads = _build_strategic_reads(peer_themes, review_intel)

    own_analysis = (review_intel or {}).get("analysis") or {}
    own_aspect_scores = own_analysis.get("aspect_scores", {})

    for peer in top_peers[:5]:
        name = peer.get("name", "")
        overall = peer.get("overall")
        score_str = f"{overall:.1f}" if overall is not None else "\u2014"
        themes = peer_themes.get(name)

        if not themes:
            w(f"| {name} | {score_str} | *No review data* | *No review data* | \u2014 |")
            continue

        # Format top praise
        if themes["top_praise"]:
            top_p = themes["top_praise"][0]
            praise_str = f"{top_p['label']} ({top_p['mentions']}x)"
        else:
            praise_str = "\u2014"

        # Format top complaint
        if themes["top_complaints"]:
            top_c = themes["top_complaints"][0]
            complaint_str = f"{top_c['label']} ({top_c['mentions']}x)"
            complaint_aspect = top_c.get("aspect", "")
        else:
            complaint_str = "\u2014"
            complaint_aspect = ""

        # Determine "your edge"
        edge_str = "\u2014"
        if complaint_aspect:
            own = own_aspect_scores.get(complaint_aspect, {})
            own_score = own.get("score")
            if own_score is not None and own_score >= 7.0:
                own_label = ASPECT_LABELS.get(
                    complaint_aspect,
                    complaint_aspect.replace("_", " ").title())
                edge_str = f"Stronger {own_label.lower()} ({own_score:.1f}/10)"

        w(f"| {name} | {score_str} | {praise_str} | {complaint_str} | {edge_str} |")

    w("")

    # Strategic reads
    if strategic_reads:
        w("**Strategic reads:**\n")
        for read in strategic_reads:
            w(f"- {read}")
        w("")


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
