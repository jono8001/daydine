"""
operator_intelligence/builders/long_form.py — Deep interpretive sections

These builders produce the management-grade interpretive content that
makes the report feel like a retained hospitality strategy product.
Each section explains what matters, why commercially, what management
should infer, and what to do next.
"""

from operator_intelligence.peer_benchmarking import RING_DEFS
from operator_intelligence.review_delta import ASPECT_LABELS
from operator_intelligence.report_spec import MODE_NARRATIVE

DIM_ORDER = ["experience", "visibility", "trust", "conversion", "prestige"]


# ---------------------------------------------------------------------------
# Management Priorities (not just actions — interpretation of what matters)
# ---------------------------------------------------------------------------

def build_management_priorities(w, scorecard, deltas, benchmarks, recs):
    w("## Management Priorities\n")
    actions = recs.get("priority_actions", [])
    dims = {d: scorecard.get(d) for d in DIM_ORDER if scorecard.get(d) is not None}
    overall = scorecard.get("overall")

    # Frame the management question
    if overall and overall >= 8.0:
        w("Your aggregate score places you in the top tier. The management question "
          "is not *how to fix problems* but *how to sustain advantage and capture "
          "upside you're currently leaving on the table*.\n")
    elif overall and overall >= 6.5:
        w("Your score is solid but not dominant. The management question is "
          "*which specific dimension, if improved, would most change your "
          "commercial trajectory* — and which can you realistically move?\n")
    else:
        w("Your score indicates material operational gaps. The management question "
          "is *which issues are most commercially urgent* and which can be "
          "addressed within the next 30 days.\n")

    # Top 3 priorities with management framing
    for i, a in enumerate(actions[:3], 1):
        status = a.get("status", "new").upper()
        w(f"### Priority {i}: {a['title']} [{status}]\n")
        w(f"{a['description']}\n")

        # Management implication
        dim = a.get("dimension", "")
        if dim == "conversion":
            w("**Management implication:** This is a demand-capture problem. You are "
              "generating interest (experience and visibility are strong) but losing "
              "potential customers at the point they try to act on that interest. "
              "Every day this remains unresolved represents lost covers.\n")
        elif dim == "trust":
            w("**Management implication:** Trust is a foundational score. Low trust "
              "creates a ceiling on your overall position regardless of how strong "
              "other dimensions become. This should be treated as a compliance "
              "project, not a marketing initiative.\n")
        elif dim == "visibility":
            w("**Management implication:** Visibility directly drives discovery. "
              "A venue that isn't found can't convert. This is a marketing and "
              "digital operations issue that can typically be moved within 60 days.\n")
        elif dim == "experience":
            w("**Management implication:** Experience is the most commercially "
              "sensitive dimension — it drives reviews, return visits, and word-of-mouth. "
              "Improvements here compound faster than any other dimension.\n")
        elif dim == "prestige":
            w("**Management implication:** Prestige is a long-cycle investment. "
              "It doesn't drive footfall directly but supports premium pricing, "
              "media coverage, and talent recruitment.\n")

        w(f"- **Owner:** {a.get('owner', '—')} | **Confidence:** {a.get('confidence', 0):.0%}")
        w(f"- **Expected upside:** {a.get('expected_upside', '—')}")
        if a.get("evidence"):
            w(f"- **Evidence:** `{a['evidence']}`")
        if a.get("times_seen", 1) > 1:
            w(f"- *This recommendation has appeared {a['times_seen']} consecutive months.*")
        w("")


# ---------------------------------------------------------------------------
# Market Position — the full 3-ring analysis with interpretation
# ---------------------------------------------------------------------------

def build_market_position(w, scorecard, benchmarks):
    w("## Market Position\n")

    if not benchmarks:
        w("*Insufficient peer data for market position analysis.*\n")
        return

    overall = scorecard.get("overall")
    cat = scorecard.get("category", "Unknown")

    w(f"**Category:** {cat}\n")

    for ring_key in ["ring1_local", "ring2_catchment", "ring3_uk_cohort"]:
        ring = benchmarks.get(ring_key, {})
        if ring.get("peer_count", 0) == 0:
            continue

        label = ring["label"]
        peer_count = ring["peer_count"]
        dims = ring.get("dimensions", {})
        ov = dims.get("overall", {})

        # Section header with summary line
        if ring_key == "ring1_local":
            w(f"### Local Competitive Set ({peer_count} peers within 5 miles)\n")
        elif ring_key == "ring2_catchment":
            w(f"### Extended Catchment ({peer_count} peers within 15 miles)\n")
        else:
            w(f"### UK Category Cohort ({peer_count} peers in {cat})\n")

        # Position statement
        if ov:
            rank = ov.get("rank")
            of = ov.get("of")
            pct = ov.get("percentile")
            peer_avg = ov.get("peer_mean")
            peer_top = ov.get("peer_top")

            w(f"**Position:** #{rank} of {of} (Percentile {pct})\n")

            if pct and pct >= 80:
                w(f"You are in the top quintile of this peer set. Your overall score "
                  f"of {overall:.1f} exceeds the peer average of {peer_avg:.1f} by "
                  f"{overall - peer_avg:.1f} points. The competitive risk here is "
                  f"complacency — the nearest competitor scores {peer_top:.1f}.\n")
            elif pct and pct >= 50:
                w(f"You sit above the median but below the top tier. Your {overall:.1f} "
                  f"compares to a peer average of {peer_avg:.1f}. The gap to the top "
                  f"({peer_top:.1f}) is {peer_top - overall:.1f} points — closeable "
                  f"with focused improvement on your weakest dimension.\n")
            else:
                w(f"You are below the median of your peer set. At {overall:.1f} vs "
                  f"peer average {peer_avg:.1f}, competitors are outperforming you. "
                  f"The top performer scores {peer_top:.1f}. Customers in this area "
                  f"have demonstrably better-rated alternatives.\n")

        # Dimension comparison — only the noteworthy gaps
        notable = []
        for dim in DIM_ORDER:
            d = dims.get(dim)
            if d and d.get("peer_mean") is not None:
                gap = d["score"] - d["peer_mean"]
                if abs(gap) >= 0.5:
                    notable.append((dim, d["score"], d["peer_mean"], gap))

        if notable:
            w("**Dimension gaps vs peers:**\n")
            for dim, score, peer_avg, gap in sorted(notable, key=lambda x: -x[3]):
                direction = "above" if gap > 0 else "below"
                w(f"- {dim.title()}: {score:.1f} ({gap:+.1f} {direction} peer avg {peer_avg:.1f})")
            w("")

        # Top peers
        top_peers = ring.get("top_peers", [])
        if top_peers:
            w("**Closest competitors:**\n")
            for tp in top_peers[:5]:
                gap = overall - tp["overall"] if overall else 0
                w(f"- {tp['name']} ({tp['overall']:.1f}) — "
                  f"{'you lead by' if gap > 0 else 'leads you by'} {abs(gap):.1f}")
            w("")


# ---------------------------------------------------------------------------
# Dimension-by-Dimension Diagnosis
# ---------------------------------------------------------------------------

_DIM_CONTEXT = {
    "experience": {
        "what": "Customer-facing quality — food, service, ambience as perceived by guests",
        "why": "Drives reviews, repeat visits, and word-of-mouth. The most commercially impactful dimension.",
        "signals": "Google rating, TripAdvisor rating, FSA food hygiene sub-score, sentiment analysis",
    },
    "visibility": {
        "what": "How easily customers can discover you online",
        "why": "No visibility = no new customers. Controls top-of-funnel demand generation.",
        "signals": "Google review count, photo count, GBP completeness, web/social presence, TripAdvisor presence",
    },
    "trust": {
        "what": "Food safety compliance and regulatory confidence",
        "why": "A hygiene rating below 5 is visible to customers. Low trust creates a hard ceiling on overall score.",
        "signals": "FSA hygiene rating, structural compliance, management confidence, inspection recency",
    },
    "conversion": {
        "what": "Operational readiness to capture demand",
        "why": "Converts interest into visits. Missing hours/menu/ordering options cause drop-off at purchase intent.",
        "signals": "Opening hours, menu online, delivery/takeaway, reservations, price level",
    },
    "prestige": {
        "what": "Editorial recognition and premium positioning",
        "why": "Supports premium pricing and differentiation. Long-cycle investment, not urgent for most.",
        "signals": "Michelin mentions, AA rating, local awards, price positioning",
    },
}


def build_dimension_diagnosis(w, scorecard, deltas, benchmarks):
    w("## Dimension-by-Dimension Diagnosis\n")

    ring1 = (benchmarks or {}).get("ring1_local") or (benchmarks or {}).get("ring2_catchment") or {}
    ring1_dims = ring1.get("dimensions", {})

    for dim in DIM_ORDER:
        score = scorecard.get(dim)
        if score is None:
            continue

        ctx = _DIM_CONTEXT.get(dim, {})
        delta = deltas.get(dim) if deltas else None
        peer = ring1_dims.get(dim, {})
        peer_avg = peer.get("peer_mean")
        peer_pct = peer.get("percentile")

        w(f"### {dim.title()} — {score:.1f}/10\n")
        w(f"*{ctx.get('what', '')}*\n")

        # Score interpretation
        if score >= 8.0:
            w(f"**Assessment: Strong.** This is a genuine competitive strength at {score:.1f}.")
        elif score >= 6.0:
            w(f"**Assessment: Adequate.** At {score:.1f}, this is functional but not distinctive.")
        elif score >= 4.0:
            w(f"**Assessment: Weak.** At {score:.1f}, this dimension is actively limiting your overall position.")
        else:
            w(f"**Assessment: Critical.** At {score:.1f}, this represents a material operational gap.")

        # Peer comparison
        if peer_avg is not None:
            gap = score - peer_avg
            if gap >= 1.0:
                w(f" You lead peers by {gap:.1f} points (peer avg {peer_avg:.1f}).")
            elif gap <= -1.0:
                w(f" You trail peers by {abs(gap):.1f} points (peer avg {peer_avg:.1f}).")
            elif abs(gap) < 0.3:
                w(f" In line with peers (avg {peer_avg:.1f}).")
            else:
                w(f" Slightly {'above' if gap > 0 else 'below'} peer average ({peer_avg:.1f}).")

        # Delta
        if delta is not None and abs(delta) >= 0.3:
            direction = "improved" if delta > 0 else "declined"
            w(f" {direction.title()} {abs(delta):.1f} points vs prior month.")

        w("")

        # Why it matters
        w(f"**Why it matters:** {ctx.get('why', '')}\n")

        # What drives it
        w(f"**Driven by:** {ctx.get('signals', '')}\n")

        # Management action
        if score < 6.0:
            w(f"**Action required:** This score requires active intervention. "
              f"Review the Priority Actions section for specific steps.\n")
        elif score >= 8.0 and peer_avg and score - peer_avg >= 1.0:
            w(f"**Protect this advantage.** Competitors scoring {peer_avg:.1f} on average "
              f"means this is a genuine differentiator worth maintaining.\n")
        w("")


# ---------------------------------------------------------------------------
# Public Proof vs Operational Reality
# ---------------------------------------------------------------------------

def build_public_vs_reality(w, scorecard):
    w("## Public Proof vs Operational Reality\n")
    w("This section compares what customers see (public signals) against "
      "what the data reveals about operational depth.\n")

    gr = scorecard.get("google_rating")
    grc = scorecard.get("google_reviews") or 0
    fsa = scorecard.get("fsa_rating")
    exp = scorecard.get("experience")
    trust = scorecard.get("trust")
    vis = scorecard.get("visibility")
    conv = scorecard.get("conversion")

    w("| Aspect | Public Signal | Operational Reality |")
    w("|--------|-------------|---------------------|")

    # Google rating vs Experience score
    if gr:
        gr_read = "Strong" if float(gr) >= 4.5 else "Good" if float(gr) >= 4.0 else "Weak"
        exp_read = "Strong" if exp and exp >= 8.0 else "Adequate" if exp and exp >= 6.0 else "Weak"
        aligned = "Aligned" if gr_read == exp_read else "Gap"
        w(f"| Customer Rating | {gr}/5 Google ({gr_read}) | Experience {exp:.1f}/10 ({exp_read}) — {aligned} |")

    # FSA rating vs Trust score
    if fsa:
        fsa_read = "Top mark" if int(fsa) == 5 else "Acceptable" if int(fsa) >= 3 else "Concern"
        trust_read = "Strong" if trust and trust >= 8.0 else "Adequate" if trust and trust >= 6.0 else "Weak"
        w(f"| Hygiene Rating | FSA {fsa}/5 ({fsa_read}) | Trust {trust:.1f}/10 ({trust_read}) |")

    # Review volume vs Visibility
    if grc > 0:
        vol_read = "High" if grc >= 500 else "Moderate" if grc >= 100 else "Low"
        vis_read = "Strong" if vis and vis >= 8.0 else "Adequate" if vis and vis >= 6.0 else "Weak"
        w(f"| Review Volume | {grc} reviews ({vol_read}) | Visibility {vis:.1f}/10 ({vis_read}) |")

    # Operational accessibility
    conv_read = "Ready" if conv and conv >= 7.0 else "Partial" if conv and conv >= 5.0 else "Gaps"
    w(f"| Booking/Ordering | What customers can find | Conversion {conv:.1f}/10 ({conv_read}) |")

    w("")

    # Interpretation
    if gr and exp and trust:
        gr_f = float(gr)
        if gr_f >= 4.5 and trust >= 8.0:
            w("**Interpretation:** Public perception and operational reality are well-aligned. "
              "Your public ratings are backed by genuine compliance strength. This is sustainable.\n")
        elif gr_f >= 4.0 and trust < 7.0:
            w("**Interpretation:** Public perception outpaces operational depth. "
              "Your Google rating looks good, but compliance scores suggest underlying "
              "risks that could surface in the next inspection or incident. "
              "Address Trust before it becomes a public problem.\n")
        elif gr_f < 4.0 and trust >= 8.0:
            w("**Interpretation:** Operational reality is stronger than public perception. "
              "Your compliance is solid but customers aren't seeing it reflected in their "
              "experience. This is a service delivery or communication gap.\n")


# ---------------------------------------------------------------------------
# Conversion Friction Analysis
# ---------------------------------------------------------------------------

def build_conversion_analysis(w, scorecard, venue_rec):
    w("## Conversion Friction Analysis\n")
    w("This section identifies specific barriers between customer interest and a completed visit or order.\n")

    conv = scorecard.get("conversion")
    goh = venue_rec.get("goh")
    has_menu = venue_rec.get("has_menu_online")
    gty = venue_rec.get("gty", [])
    has_delivery = "food_delivery" in gty or "meal_takeaway" in gty if isinstance(gty, list) else False
    gpl = venue_rec.get("gpl")

    friction_points = []

    if not goh or (isinstance(goh, list) and len(goh) < 7):
        days = len(goh) if isinstance(goh, list) else 0
        friction_points.append(("Opening hours incomplete",
            f"Only {days}/7 days listed. Customers filtering 'open now' may not find you.",
            "Publish full 7-day hours on Google Business Profile."))

    if not has_menu:
        friction_points.append(("No online menu",
            "77% of diners check the menu before visiting. Without one, you lose "
            "consideration at the research stage.",
            "Upload menu to Google Business Profile or link to your website menu."))

    if not has_delivery:
        friction_points.append(("No delivery/takeaway signal",
            "Google Maps filters for 'delivery' and 'takeaway'. If you offer these "
            "services but haven't flagged them, you're invisible to that search intent.",
            "Update Google Business Profile service attributes."))

    if gpl is None:
        friction_points.append(("No price level set",
            "Price level helps customers self-select. Without it, price-sensitive "
            "and premium-seeking customers alike may skip you.",
            "Set price level on Google Business Profile."))

    if friction_points:
        w("| Friction Point | Impact | Fix |")
        w("|---------------|--------|-----|")
        for title, impact, fix in friction_points:
            w(f"| {title} | {impact} | {fix} |")
        w("")

        w(f"**{len(friction_points)} friction point(s) identified.** "
          f"Each one represents a leak in your conversion funnel where "
          f"interested customers drop off before reaching you.\n")
    else:
        w("No major conversion friction points detected. Your operational "
          "signals (hours, menu, ordering options) are well-configured.\n")

    if conv is not None:
        if conv >= 7.0:
            w("**Overall conversion readiness: Good.** Your operational profile "
              "supports customer discovery and action.\n")
        elif conv >= 5.0:
            w("**Overall conversion readiness: Partial.** Some signals are present "
              "but gaps remain. Each missing element is a percentage of potential "
              "customers who never reach you.\n")
        else:
            w("**Overall conversion readiness: Poor.** Multiple operational signals "
              "are missing. This is likely costing you measurable footfall.\n")


# ---------------------------------------------------------------------------
# Next-Month Monitoring Plan
# ---------------------------------------------------------------------------

def build_monitoring_plan(w, scorecard, recs):
    w("## Next-Month Monitoring Plan\n")
    w("Track these specific metrics before the next report to measure progress:\n")

    actions = recs.get("priority_actions", [])
    watches = recs.get("watch_items", [])

    w("| What to Monitor | Current Baseline | Target | Owner |")
    w("|----------------|-----------------|--------|-------|")

    gr = scorecard.get("google_rating")
    if gr:
        w(f"| Google rating | {gr}/5 | Maintain or improve | Front-of-house |")

    grc = scorecard.get("google_reviews")
    if grc:
        target = int(grc) + 10
        w(f"| Google review count | {grc} | {target}+ | Marketing |")

    fsa = scorecard.get("fsa_rating")
    if fsa and int(fsa) < 5:
        w(f"| FSA hygiene rating | {fsa} | Request re-inspection | Compliance |")

    for a in actions[:2]:
        w(f"| {a['title'][:40]} | Action raised | Complete | {a.get('owner', '—')} |")

    for wa in watches[:1]:
        w(f"| {wa['title'][:40]} | Watch raised | Monitor | {wa.get('owner', '—')} |")

    w("")
    w("**Review date:** First week of next month. Compare these baselines "
      "against updated data to measure whether actions had impact.\n")


# ---------------------------------------------------------------------------
# Evidence Appendix
# ---------------------------------------------------------------------------

def build_evidence_appendix(w, scorecard, venue_rec):
    w("## Evidence Appendix\n")
    w("Raw signal values used to compute this report.\n")

    w("| Signal | Value | Source |")
    w("|--------|-------|--------|")

    fsa = scorecard.get("fsa_rating")
    if fsa:
        w(f"| FSA Hygiene Rating | {fsa}/5 | FSA API via Firebase |")
    sh = venue_rec.get("sh")
    if sh is not None:
        w(f"| Food Hygiene Sub-score | {sh}/10 | FSA |")
    ss = venue_rec.get("ss")
    if ss is not None:
        w(f"| Structural Compliance | {ss}/10 | FSA |")
    sm = venue_rec.get("sm")
    if sm is not None:
        w(f"| Management Confidence | {sm}/10 | FSA |")
    rd = venue_rec.get("rd")
    if rd:
        w(f"| Last Inspection | {rd[:10]} | FSA |")

    gr = scorecard.get("google_rating")
    if gr:
        w(f"| Google Rating | {gr}/5 | Google Places API |")
    grc = scorecard.get("google_reviews")
    if grc:
        w(f"| Google Reviews | {grc} | Google Places API |")
    gpc = venue_rec.get("gpc")
    if gpc is not None:
        w(f"| Google Photos | {gpc} | Google Places API |")
    gpl = venue_rec.get("gpl")
    if gpl is not None:
        w(f"| Price Level | {'£' * int(gpl)} ({gpl}/4) | Google Places API |")
    gbp = venue_rec.get("gbp_completeness")
    if gbp is not None:
        w(f"| GBP Completeness | {gbp}/10 | Computed |")

    w(f"| Website | {'Yes' if venue_rec.get('web') else 'No'} | Inferred |")
    w(f"| Facebook | {'Yes' if venue_rec.get('fb') else 'No'} | Inferred |")
    w(f"| Instagram | {'Yes' if venue_rec.get('ig') else 'No'} | Inferred |")

    w(f"| Category | {scorecard.get('category', '—')} | {scorecard.get('category_source', '—')} |")
    w(f"| Postcode | {scorecard.get('postcode', '—')} | FSA |")
    w("")
