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

_REC_TYPE_LABELS = {
    "fix": "FIX", "exploit": "EXPLOIT", "protect": "PROTECT",
    "watch": "WATCH", "ignore": "IGNORE",
    "action": "ACTION",  # backward compat
}


def build_management_priorities(w, scorecard, deltas, benchmarks, recs):
    w("## Management Priorities\n")
    actions = recs.get("priority_actions", [])
    overall = scorecard.get("overall")

    # Frame the management question from the venue's actual situation
    fix_count = sum(1 for a in actions if a.get("rec_type") == "fix")
    exploit_count = sum(1 for a in actions if a.get("rec_type") == "exploit")

    if fix_count >= 2:
        w("Multiple operational issues need attention. The management question "
          "is *which fix prevents the most commercial damage this month* — "
          "sequence matters more than ambition.\n")
    elif exploit_count >= 2 and overall and overall >= 7.0:
        w("The fundamentals are sound. The management question is not "
          "*what to fix* but *what untapped strength to lean into* — "
          "and which opportunity has the highest return for effort.\n")
    elif overall and overall >= 8.0:
        w("You're operating in the top tier. The management question is "
          "*how to sustain this and capture the upside you're currently "
          "leaving on the table*.\n")
    elif overall and overall >= 6.5:
        w("The score is solid but not dominant. The management question is "
          "*which specific lever, if pulled, would most change your "
          "commercial trajectory* — and which can you realistically move?\n")
    else:
        w("Material operational gaps exist. The management question is "
          "*which issues are most commercially urgent* and which can be "
          "addressed within the next 30 days.\n")

    # Top 3 priorities — use rec_type and management_implication from rec itself
    for i, a in enumerate(actions[:3], 1):
        status = a.get("status", "new").upper()
        rt = _REC_TYPE_LABELS.get(a.get("rec_type", "action"), "ACTION")
        w(f"### Priority {i}: {a['title']} [{rt} | {status}]\n")
        w(f"{a['description']}\n")

        # Use recommendation's own management implication if it has one,
        # otherwise fall back to dimension-based framing
        mgmt_impl = a.get("management_implication")
        if mgmt_impl:
            w(f"**Management implication:** {mgmt_impl}\n")
        else:
            dim = a.get("dimension", "")
            _DIM_IMPLICATIONS = {
                "conversion": ("This is a demand-capture problem. Interest is being "
                               "generated but lost at the point customers try to act. "
                               "Every day unresolved represents lost covers."),
                "trust": ("Trust is foundational. Low trust creates a ceiling on "
                          "overall position regardless of other strengths. Treat as "
                          "a compliance project, not a marketing initiative."),
                "visibility": ("Visibility drives discovery. A venue that isn't "
                               "found can't convert. Typically moveable within 60 days."),
                "experience": ("Experience is the most commercially sensitive dimension "
                               "— it drives reviews, return visits, and word-of-mouth. "
                               "Improvements here compound faster than any other."),
                "prestige": ("Long-cycle investment. Doesn't drive footfall directly "
                             "but supports premium pricing and talent recruitment."),
            }
            impl = _DIM_IMPLICATIONS.get(dim)
            if impl:
                w(f"**Management implication:** {impl}\n")

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

    # Detect ring overlap — if ring2 and ring3 have same peer count and same
    # top peer, compress ring3 into a one-liner instead of repeating
    prev_ring_peers = None
    prev_ring_top = None

    for ring_key in ["ring1_local", "ring2_catchment", "ring3_uk_cohort"]:
        ring = benchmarks.get(ring_key, {})
        if ring.get("peer_count", 0) == 0:
            continue

        label = ring["label"]
        peer_count = ring["peer_count"]
        dims = ring.get("dimensions", {})
        top_peers = ring.get("top_peers", [])
        top_name = top_peers[0]["name"] if top_peers else None

        # If this ring is essentially identical to the previous one, compress it
        if prev_ring_peers == peer_count and prev_ring_top == top_name:
            w(f"### {label}\n")
            w(f"*Same competitive set as above ({peer_count} peers). "
              f"In this market, the catchment and category cohort overlap completely.*\n")
            continue

        prev_ring_peers = peer_count
        prev_ring_top = top_name
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


def _dim_management_action(dim, score, peer_avg, scorecard):
    """Return dimension-specific management guidance. Never generic."""
    gap = score - peer_avg if peer_avg is not None else 0

    if dim == "experience":
        if score >= 8.0 and gap >= 1.0:
            return ("Your experience advantage is real but perishable. It depends on "
                    "consistency across every service. One bad month of staffing or supply "
                    "issues can erode this faster than it was built.")
        if score >= 8.0:
            return ("Strong experience but peers are close. Monitor your most recent "
                    "reviews for early signs of drift — the last 10 reviews matter more "
                    "than the aggregate.")
        if score < 6.0:
            gr = scorecard.get("google_rating")
            return (f"At {gr}/5 Google, customers are telling you something specific. "
                    "Read the 3 most recent negative reviews and identify the recurring theme. "
                    "That theme is your highest-ROI operational fix." if gr else
                    "Experience is the dimension customers feel directly. Prioritise "
                    "front-of-house training and menu quality review.")
        return None

    if dim == "visibility":
        if score >= 8.0 and gap >= 1.0:
            return ("Your visibility lead is a competitive moat. Maintain it by continuing "
                    "to respond to reviews and keeping your profile current. Competitors "
                    "will eventually invest here.")
        if score < 6.0:
            grc = scorecard.get("google_reviews") or 0
            return (f"At {grc} reviews, you are likely invisible in 'near me' and category "
                    "searches. This is fixable within 60 days with a systematic review "
                    "request programme.")
        return None

    if dim == "trust":
        fsa = scorecard.get("fsa_rating")
        if score >= 8.0:
            return ("Strong trust position. Maintain documentation rigour — the next "
                    "unannounced inspection should confirm, not surprise.")
        if fsa and int(fsa) < 5:
            return (f"FSA {fsa} is the binding constraint. Request a re-inspection once "
                    "you've addressed the specific points from the last report. A move "
                    "to 5 unlocks material score improvement.")
        return "Inspection age may be dragging this down. Recent compliance is not reflected in the score yet."

    if dim == "conversion":
        if score < 5.0:
            return ("Multiple conversion signals are missing. Walk through the customer "
                    "journey on Google Maps and your website — can a new customer find your "
                    "hours, see your menu, and book or order in under 60 seconds? If not, "
                    "that's your fix list.")
        if score < 7.0:
            return ("Some operational signals present, but gaps remain. Each missing element "
                    "is a percentage of potential customers who never complete their intent.")
        return None

    if dim == "prestige":
        if score < 2.0 and scorecard.get("overall", 0) >= 7.5:
            return ("Your operational quality would support a credible awards submission. "
                    "This is a long-cycle play — start with local food guides and AA "
                    "before targeting Michelin.")
        if score < 2.0:
            return ("Low prestige is normal for most operators and not commercially urgent. "
                    "Focus on Experience and Trust first — prestige follows quality.")
        return None

    return None


HEADLINE_DIMS = ["experience", "visibility", "trust", "conversion"]


def build_dimension_diagnosis(w, scorecard, deltas, benchmarks):
    w("## Dimension-by-Dimension Diagnosis\n")

    ring1 = (benchmarks or {}).get("ring1_local") or (benchmarks or {}).get("ring2_catchment") or {}
    ring1_dims = ring1.get("dimensions", {})

    for dim in HEADLINE_DIMS:
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

        # Management action — varied per dimension, never generic
        _action = _dim_management_action(dim, score, peer_avg, scorecard)
        if _action:
            w(f"**Management note:** {_action}\n")
        w("")

    # Prestige — compact note, not full diagnosis
    prest = scorecard.get("prestige")
    if prest is not None:
        peer_prest = ring1_dims.get("prestige", {}).get("peer_mean")
        w("### Prestige (Editorial Recognition)\n")
        w(f"*Score: {prest:.1f}/10"
          + (f" | Peer avg: {peer_prest:.1f}" if peer_prest is not None else "")
          + "*\n")
        if prest < 2.0 and (scorecard.get("overall") or 0) >= 7.5:
            w("Your operational quality would support a credible awards submission, "
              "but this is a long-cycle play — not an operational priority. "
              "Focus on the four headline dimensions first.\n")
        elif prest < 2.0:
            w("Low prestige is normal for most independents and does not affect "
              "footfall, discovery, or day-to-day revenue. Not commercially urgent.\n")
        else:
            w("Editorial recognition present. This supports premium positioning "
              "but is not an operational lever — protect it through quality consistency.\n")


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
    w("These are **externally observable leading indicators** — all trackable "
      "without internal systems. Changes here signal whether actions are landing.\n")

    w("| Indicator | Current | What Movement Means | Source |")
    w("|-----------|---------|---------------------|--------|")

    gr = scorecard.get("google_rating")
    if gr:
        w(f"| Google star rating | {gr}/5 | Drop below {float(gr):.1f} = experience drift; "
          f"rise = guest improvements landing | Google Maps |")

    grc = scorecard.get("google_reviews")
    if grc:
        velocity = "10+ new reviews/month = healthy momentum"
        w(f"| Google review count | {grc} | {velocity} | Google Maps |")

    fsa = scorecard.get("fsa_rating")
    if fsa is not None:
        from rcs_scoring_stratford import days_since
        rd = scorecard.get("_rd") or ""
        age = days_since(rd)
        if int(fsa) < 5:
            w(f"| FSA hygiene rating | {fsa}/5 | Re-inspection result = immediate score impact | FSA website |")
        elif age and age > 365:
            months = round(age / 30)
            w(f"| FSA inspection age | {months} months | Next unannounced visit = score-sensitive event | FSA website |")

    ta = scorecard.get("_ta_rating")
    if ta is not None:
        w(f"| TripAdvisor rating | {ta}/5 | Divergence from Google = cross-source risk flag | TripAdvisor |")

    # Review sentiment trajectory — external leading indicator
    if gr and float(gr) >= 4.0:
        w(f"| Latest 5 Google reviews | Check manually | 2+ negative in latest 5 = early warning of rating decline | Google Maps |")

    # Competitive movement
    w("| Nearest competitor rating | Check top 3 | Competitor improvement narrows your lead | Google Maps |")

    w("")
    w("**Review date:** First week of next month. All indicators are publicly "
      "observable — no operator login or internal data required.\n")


# ---------------------------------------------------------------------------
# Evidence Appendix
# ---------------------------------------------------------------------------

def build_evidence_appendix(w, scorecard, venue_rec):
    w("## Evidence Appendix\n")
    w("Raw signal values used to compute this report. "
      "Provenance: **observed** = directly from source API; "
      "**derived** = computed from observed data; "
      "**inferred** = estimated from indirect evidence; "
      "**not_assessed** = not yet collected.\n")

    w("| Signal | Value | Source | Provenance |")
    w("|--------|-------|--------|------------|")

    fsa = scorecard.get("fsa_rating")
    if fsa:
        w(f"| FSA Hygiene Rating | {fsa}/5 | FSA API via Firebase | observed |")
    sh = venue_rec.get("sh")
    if sh is not None:
        w(f"| Food Hygiene Sub-score | {sh}/10 | FSA | observed |")
    ss = venue_rec.get("ss")
    if ss is not None:
        w(f"| Structural Compliance | {ss}/10 | FSA | observed |")
    sm = venue_rec.get("sm")
    if sm is not None:
        w(f"| Management Confidence | {sm}/10 | FSA | observed |")
    rd = venue_rec.get("rd")
    if rd:
        w(f"| Last Inspection | {rd[:10]} | FSA | observed |")

    gr = scorecard.get("google_rating")
    if gr:
        w(f"| Google Rating | {gr}/5 | Google Places API | observed |")
    grc = scorecard.get("google_reviews")
    if grc:
        w(f"| Google Reviews | {grc} | Google Places API | observed |")
    gpc = venue_rec.get("gpc")
    if gpc is not None:
        w(f"| Google Photos | {gpc} | Google Places API | observed |")
    gpl = venue_rec.get("gpl")
    if gpl is not None:
        w(f"| Price Level | {'£' * int(gpl)} ({gpl}/4) | Google Places API | observed |")
    gbp = venue_rec.get("gbp_completeness")
    if gbp is not None:
        w(f"| GBP Completeness | {gbp}/10 | Computed | derived |")

    ta = venue_rec.get("ta")
    trc = venue_rec.get("trc")
    if ta is not None:
        w(f"| TripAdvisor Rating | {ta}/5 | TripAdvisor (Apify) | observed |")
    if trc is not None:
        w(f"| TripAdvisor Reviews | {trc} | TripAdvisor (Apify) | observed |")

    w(f"| Website | {'Yes' if venue_rec.get('web') else 'No'} | Google inference | inferred |")
    w(f"| Facebook | {'Yes' if venue_rec.get('fb') else 'No'} | Google inference | inferred |")
    w(f"| Instagram | {'Yes' if venue_rec.get('ig') else 'No'} | Google inference | inferred |")

    w(f"| Category | {scorecard.get('category', '—')} | {scorecard.get('category_source', '—')} | derived |")
    w(f"| Postcode | {scorecard.get('postcode', '—')} | FSA | observed |")
    w(f"| Companies House | — | Not checked | not_assessed |")
    w("")
