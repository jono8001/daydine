"""
operator_intelligence/report_generator.py — Monthly & Quarterly Report Output

Two report modes:
  A. Narrative-rich: venues with actual review text get deep sentiment analysis
  B. Structured-signal: venues without review text get signal-led diagnosis

Both modes produce premium operator-grade intelligence reports.
"""

import csv
import json
import os
from datetime import datetime

from operator_intelligence.scorecard import DIMENSION_WEIGHTS
from operator_intelligence.peer_benchmarking import format_peer_summary
from operator_intelligence.review_delta import ASPECT_LABELS


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _arrow(delta):
    if delta is None:
        return ""
    if delta > 0.3:
        return " ▲"
    if delta < -0.3:
        return " ▼"
    if abs(delta) > 0:
        return " →"
    return " ―"


def _fmt(val, fmt=".1f"):
    if val is None:
        return "—"
    return f"{val:{fmt}}"


def _fmt_delta(delta):
    if delta is None:
        return "—"
    return f"{delta:+.1f}"


DIM_ORDER = ["experience", "visibility", "trust", "conversion", "prestige"]


# ---------------------------------------------------------------------------
# Section 1: Header + Executive Summary
# ---------------------------------------------------------------------------

def _section_executive_summary(w, venue_name, month_str, scorecard, deltas,
                                benchmarks, review_intel, recs):
    """Write header and executive summary. Commercially written, not robotic."""
    now = datetime.utcnow().strftime("%d %B %Y")
    overall = scorecard.get("overall")

    w(f"# {venue_name} — Operator Intelligence Report")
    w(f"*{month_str} | Generated {now} | DayDine Premium*\n")
    w("---\n")
    w("## Executive Summary\n")

    # Overall score with delta
    od = deltas.get("overall") if deltas else None
    if overall is not None:
        w(f"**Overall Operator Score: {overall:.1f} / 10**{_arrow(od)}")
        if od is not None:
            direction = "up" if od > 0 else "down" if od < 0 else "unchanged"
            w(f"*{_fmt_delta(od)} vs prior month ({direction})*\n")
        else:
            w("*Baseline month — no prior period for comparison*\n")

    # Identify strongest and weakest dimension
    dim_scores = {d: scorecard.get(d) for d in DIM_ORDER if scorecard.get(d) is not None}
    if dim_scores:
        strongest = max(dim_scores, key=dim_scores.get)
        weakest = min(dim_scores, key=dim_scores.get)
        gap = dim_scores[strongest] - dim_scores[weakest]
        w(f"**Strongest dimension:** {strongest.title()} ({dim_scores[strongest]:.1f}). "
          f"**Weakest:** {weakest.title()} ({dim_scores[weakest]:.1f}). "
          f"Internal gap: {gap:.1f} points.\n")

    # Peer position — prose, not bullet list
    peer_lines = format_peer_summary(benchmarks) if benchmarks else []
    if peer_lines:
        w(f"**Competitive position:** {peer_lines[0]}")
        if len(peer_lines) > 1:
            for pl in peer_lines[1:]:
                w(f"  {pl}")
        w("")

    # Key risk or opportunity — one sentence
    actions = recs.get("priority_actions", [])
    if actions:
        top = actions[0]
        w(f"**Top priority this month:** {top['title']} "
          f"({top['dimension'].title()} dimension, "
          f"expected upside: {top['expected_upside']}).\n")

    # Data coverage one-liner
    has_narrative = review_intel.get("has_narrative", False) if review_intel else False
    grc = scorecard.get("google_reviews") or 0
    if has_narrative:
        n_reviews = review_intel.get("reviews_analyzed", 0)
        w(f"*This report includes narrative analysis from {n_reviews} customer reviews.*\n")
    else:
        w(f"*Based on structured signals ({grc} Google reviews aggregated, "
          f"no individual review text collected yet). "
          f"Narrative depth will increase with review text enrichment.*\n")


# ---------------------------------------------------------------------------
# Stub for remaining sections — will be added in subsequent steps
# ---------------------------------------------------------------------------

def _section_scorecard(w, scorecard, deltas, benchmarks):
    """Compact scorecard table + interpretive commentary per dimension."""
    w("## Dimension Scorecard\n")
    w("| Dimension | Score | Δ | Peer Avg | Gap | Read |")
    w("|-----------|------:|--:|---------:|----:|------|")

    # Get ring1 peer data for comparison
    ring1_dims = {}
    if benchmarks:
        ring1 = benchmarks.get("ring1_local") or benchmarks.get("ring2_catchment") or {}
        ring1_dims = ring1.get("dimensions", {})

    for dim in DIM_ORDER:
        score = scorecard.get(dim)
        delta = deltas.get(dim) if deltas else None
        peer = ring1_dims.get(dim, {})
        peer_avg = peer.get("peer_mean")
        gap = round(score - peer_avg, 1) if score is not None and peer_avg is not None else None

        # Interpretive read
        if score is None:
            read = "No data"
        elif gap is not None and gap >= 1.5:
            read = "Clear strength"
        elif gap is not None and gap >= 0.3:
            read = "Above peers"
        elif gap is not None and gap <= -1.5:
            read = "Significant gap"
        elif gap is not None and gap <= -0.3:
            read = "Below peers"
        elif score >= 8.0:
            read = "Strong"
        elif score <= 4.0:
            read = "Needs work"
        else:
            read = "In line"

        w(f"| {dim.title()} | {_fmt(score)} | {_fmt_delta(delta)} "
          f"| {_fmt(peer_avg)} | {_fmt(gap, '+.1f') if gap is not None else '—'} | {read} |")

    overall = scorecard.get("overall")
    od = deltas.get("overall") if deltas else None
    w(f"| **Overall** | **{_fmt(overall)}** | **{_fmt_delta(od)}** | | | |")
    w("")


def _section_performance_diagnosis(w, scorecard, deltas, benchmarks, review_intel):
    """Interpretive diagnosis — the core insight section. Not a table dump."""
    w("## Performance Diagnosis\n")

    dim_scores = {d: scorecard.get(d) for d in DIM_ORDER if scorecard.get(d) is not None}
    if not dim_scores:
        w("*Insufficient signal data for diagnosis.*\n")
        return

    # Strongest dimensions with evidence
    sorted_dims = sorted(dim_scores.items(), key=lambda x: -x[1])
    strong = [(d, s) for d, s in sorted_dims if s >= 7.5]
    weak = [(d, s) for d, s in sorted_dims if s < 5.5]
    mid = [(d, s) for d, s in sorted_dims if 5.5 <= s < 7.5]

    if strong:
        w("**Strengths:**\n")
        for dim, score in strong:
            w(f"- **{dim.title()} ({score:.1f})**: {_explain_strength(dim, score, scorecard)}")
        w("")

    if weak:
        w("**Vulnerabilities:**\n")
        for dim, score in weak:
            w(f"- **{dim.title()} ({score:.1f})**: {_explain_weakness(dim, score, scorecard)}")
        w("")

    if mid and not weak:
        # Even strong venues have something to work on
        lowest = sorted_dims[-1]
        w("**Development area:**\n")
        w(f"- **{lowest[0].title()} ({lowest[1]:.1f})**: "
          f"While not a weakness, this is your lowest-scoring dimension "
          f"and the clearest area for incremental improvement.\n")

    # Peer gap analysis
    ring1 = (benchmarks or {}).get("ring1_local") or (benchmarks or {}).get("ring2_catchment")
    if ring1 and ring1.get("dimensions"):
        dims = ring1["dimensions"]
        biggest_lead = None
        biggest_lag = None
        for dim in DIM_ORDER:
            d = dims.get(dim)
            if d and d.get("peer_mean") is not None:
                gap = d["score"] - d["peer_mean"]
                if biggest_lead is None or gap > biggest_lead[1]:
                    biggest_lead = (dim, gap)
                if biggest_lag is None or gap < biggest_lag[1]:
                    biggest_lag = (dim, gap)
        if biggest_lead and biggest_lead[1] > 0.5:
            w(f"**Biggest competitive advantage:** {biggest_lead[0].title()} "
              f"(+{biggest_lead[1]:.1f} vs peer average). Protect this.\n")
        if biggest_lag and biggest_lag[1] < -0.5:
            w(f"**Biggest competitive gap:** {biggest_lag[0].title()} "
              f"({biggest_lag[1]:+.1f} vs peer average). This is where peers are winning.\n")


def _explain_strength(dim, score, scorecard):
    """Evidence-based explanation for a strong dimension."""
    if dim == "experience":
        gr = scorecard.get("google_rating")
        return (f"Google rating of {gr}/5 reflects consistently positive customer experience. "
                "This is a genuine earned strength, not a scoring artefact.") if gr else \
               "High FSA compliance scores indicate strong operational standards."
    if dim == "trust":
        fsa = scorecard.get("fsa_rating")
        return (f"FSA rating {fsa}/5 with strong sub-scores across hygiene, structural, "
                "and management compliance. Recent inspection adds freshness.")
    if dim == "visibility":
        grc = scorecard.get("google_reviews") or 0
        return (f"{grc} Google reviews and strong profile completeness "
                "give you significant search discovery advantage.")
    if dim == "conversion":
        return "Good operational readiness — hours published, ordering options available."
    if dim == "prestige":
        return "Editorial recognition or premium positioning differentiates you from peers."
    return "Strong performance across available signals."


def _explain_weakness(dim, score, scorecard):
    """Evidence-based explanation for a weak dimension."""
    if dim == "experience":
        gr = scorecard.get("google_rating")
        if gr and float(gr) < 4.0:
            return (f"Google rating of {gr}/5 signals customer dissatisfaction. "
                    "This is the most commercially impactful dimension to improve.")
        return "Low experience score suggests gaps in food quality or service delivery."
    if dim == "trust":
        fsa = scorecard.get("fsa_rating")
        if fsa and int(fsa) < 5:
            return (f"FSA rating of {fsa}/5 materially caps this score. "
                    "A re-inspection targeting rating 5 is the single highest-impact action.")
        return "Inspection age or compliance sub-scores are dragging this down."
    if dim == "visibility":
        grc = scorecard.get("google_reviews") or 0
        return (f"Only {grc} Google reviews limits discovery. "
                "You may be invisible to customers searching 'near me'.")
    if dim == "conversion":
        return ("Missing operational signals — opening hours, delivery options, or "
                "online menu not detected. Customers may not be able to find or use you.")
    if dim == "prestige":
        return ("No editorial recognition detected. Not critical for most operators, "
                "but limits premium positioning potential.")
    return "Below threshold across available signals."

def _section_review_intelligence(w, review_intel, review_delta):
    """Review intelligence — bifurcated by data availability."""
    w("## Review & Reputation Intelligence\n")

    if not review_intel or not review_intel.get("has_narrative"):
        # Structured-signal mode — honest about what we know
        w("**Source coverage:** No individual review text collected for this venue. "
          "The analysis below is based on aggregated rating and volume signals.\n")
        grc = review_intel.get("review_count_google") if review_intel else None
        trc = review_intel.get("review_count_ta") if review_intel else None
        ext_aspects = review_intel.get("aspects") if review_intel else None

        if grc is not None:
            if grc >= 500:
                w(f"- **Review volume ({grc} Google reviews):** Strong social proof. "
                  "High volume provides confidence that the aggregate rating is stable "
                  "and resistant to individual outlier reviews.")
            elif grc >= 100:
                w(f"- **Review volume ({grc} Google reviews):** Adequate base for "
                  "rating stability. Continue encouraging reviews to build further authority.")
            elif grc >= 20:
                w(f"- **Review volume ({grc} Google reviews):** Moderate. A few negative "
                  "reviews can materially shift your rating at this volume. "
                  "Active review generation would reduce volatility.")
            else:
                w(f"- **Review volume ({grc} Google reviews):** Low. Your rating is "
                  "fragile — a single 1-star review could drop your average significantly. "
                  "This is a priority gap.")

        if trc is not None and trc > 0:
            w(f"- **TripAdvisor:** {trc} reviews present — adds cross-platform credibility.")
        elif trc == 0 or trc is None:
            w("- **TripAdvisor:** No presence detected. For hospitality venues, "
              "TripAdvisor absence is a missed discovery channel.")

        # External sentiment data if available
        if ext_aspects and isinstance(ext_aspects, dict):
            w("\n**Pre-computed aspect sentiment** (from prior enrichment run):\n")
            aspects = ext_aspects.get("aspects", ext_aspects)
            if isinstance(aspects, dict):
                for asp, data in aspects.items():
                    if isinstance(data, dict):
                        score = data.get("score", data.get("sentiment"))
                        pos = data.get("positive_mentions", data.get("positive", 0))
                        neg = data.get("negative_mentions", data.get("negative", 0))
                        w(f"- **{asp.replace('_', ' ').title()}:** {score}/10 "
                          f"({pos} positive, {neg} negative mentions)")

        w("\n*To unlock full review narrative analysis, run the Google Places review "
          "text enrichment pipeline (`enrich_google_stratford.py` with review text enabled).*\n")
        return

    # Narrative-rich mode — real review text available
    n_reviews = review_intel.get("reviews_analyzed", 0)
    w(f"**Based on {n_reviews} customer reviews with full text analysis.**\n")

    # Aspect sentiment table
    aspects = review_intel.get("aspect_scores", {})
    if aspects:
        w("### Sentiment by Topic\n")
        w("| Topic | Score | Positive | Negative | Read |")
        w("|-------|------:|---------:|---------:|------|")
        for asp, data in sorted(aspects.items(), key=lambda x: -x[1].get("sentiment", 0)):
            sent = data.get("sentiment", 0)
            pos = data.get("positive", 0)
            neg = data.get("negative", 0)
            label = ASPECT_LABELS.get(asp, asp.replace("_", " ").title())
            if sent >= 8.0:
                read = "Strength"
            elif sent >= 6.0:
                read = "Positive"
            elif sent >= 4.0:
                read = "Mixed"
            else:
                read = "Concern"
            w(f"| {label} | {sent:.1f}/10 | {pos} | {neg} | {read} |")
        w("")

    # Praise themes with quotes
    praise = review_intel.get("praise_themes", [])
    if praise:
        w("### What Customers Praise\n")
        for theme in praise:
            w(f"**{theme['label']}** ({theme['mentions']} mentions)")
            for q in theme.get("quotes", []):
                w(f'> *"{q}"*')
            w("")

    # Criticism themes with quotes
    criticism = review_intel.get("criticism_themes", [])
    if criticism:
        w("### What Needs Attention\n")
        for theme in criticism:
            w(f"**{theme['label']}** ({theme['mentions']} mentions)")
            for q in theme.get("quotes", []):
                w(f'> *"{q}"*')
            w("")

    # Strongest quotes overall
    pos_q = review_intel.get("strongest_positive_quotes", [])
    neg_q = review_intel.get("strongest_constructive_quotes", [])
    if pos_q or neg_q:
        w("### Key Quotes\n")
        if pos_q:
            w("**Strongest positive:**")
            for q in pos_q[:2]:
                w(f'> *"{q}"*')
            w("")
        if neg_q:
            w("**Strongest constructive:**")
            for q in neg_q[:2]:
                w(f'> *"{q}"*')
            w("")

    # Delta vs prior month
    if review_delta and review_delta.get("has_delta"):
        w("### Narrative Shifts vs Prior Month\n")
        new_asp = review_delta.get("new_aspects", [])
        fading = review_delta.get("fading_aspects", [])
        shifts = review_delta.get("aspect_shifts", {})

        if new_asp:
            labels = [ASPECT_LABELS.get(a, a) for a in new_asp]
            w(f"**Emerging topics:** {', '.join(labels)} — "
              "these were not mentioned last month and may indicate a shift "
              "in customer experience or expectations.\n")
        if fading:
            labels = [ASPECT_LABELS.get(a, a) for a in fading]
            w(f"**Fading topics:** {', '.join(labels)} — "
              "no longer appearing in recent reviews. If these were complaints, "
              "that may signal resolution.\n")
        if shifts:
            for asp, shift in shifts.items():
                if abs(shift["change"]) >= 2.0:
                    direction = "improved" if shift["change"] > 0 else "declined"
                    w(f"- **{ASPECT_LABELS.get(asp, asp)}** {direction} "
                      f"({shift['prev']:.0f} → {shift['current']:.0f})")
            w("")


def _section_commercial_diagnosis(w, scorecard, deltas, benchmarks, review_intel):
    """Evidence-backed commercial interpretation — not generic platitudes."""
    w("## Commercial Diagnosis\n")

    lines = []
    dim_scores = {d: scorecard.get(d) for d in DIM_ORDER if scorecard.get(d) is not None}
    overall = scorecard.get("overall")
    gr = scorecard.get("google_rating")
    grc = scorecard.get("google_reviews") or 0
    fsa = scorecard.get("fsa_rating")

    # Rating vs volume analysis
    if gr is not None:
        gr = float(gr)
        if gr >= 4.5 and grc >= 100:
            lines.append(f"A {gr}/5 Google rating across {grc} reviews represents "
                         "genuine earned reputation — this is a real competitive asset "
                         "that drives discovery and conversion.")
        elif gr >= 4.0 and grc < 50:
            lines.append(f"Your {gr}/5 rating looks solid but is based on only {grc} reviews. "
                         "At this volume, the rating is volatile — a cluster of negative "
                         "reviews could move it materially. Building volume is protective.")
        elif gr < 4.0 and grc >= 100:
            lines.append(f"A {gr}/5 rating across {grc} reviews is a persistent signal, "
                         "not an anomaly. This rating is suppressing discovery — Google "
                         "prioritises 4.0+ venues in local search results.")
        elif gr < 4.0:
            lines.append(f"Google rating of {gr}/5 is below the threshold where "
                         "most customers will consider visiting. This is the single "
                         "most commercially urgent metric to improve.")

    # Trust vs experience gap
    trust = dim_scores.get("trust")
    experience = dim_scores.get("experience")
    if trust is not None and experience is not None:
        gap = trust - experience
        if gap > 2.0:
            lines.append("Your Trust score significantly exceeds your Experience score. "
                         "This means compliance is strong but the customer-facing experience "
                         "isn't matching — operational standards are good but the product "
                         "or service delivery needs attention.")
        elif gap < -2.0:
            lines.append("Experience outscores Trust by a wide margin. Customers enjoy "
                         "the venue but compliance scores are lagging — an FSA re-inspection "
                         "or addressing structural concerns would bring Trust in line.")

    # Conversion gap
    conversion = dim_scores.get("conversion")
    if conversion is not None and conversion < 5.0:
        lines.append("Low Conversion score means potential customers can't easily "
                     "find your hours, order online, or confirm you're open. "
                     "This creates friction at the point of purchase intent.")

    # Peer position implication
    ring1 = (benchmarks or {}).get("ring1_local") or (benchmarks or {}).get("ring2_catchment")
    if ring1 and ring1.get("dimensions", {}).get("overall"):
        pct = ring1["dimensions"]["overall"].get("percentile")
        if pct is not None:
            if pct >= 80:
                lines.append(f"At P{pct} locally, you're in the top tier of your competitive set. "
                             "The focus should be on protecting position and building prestige, "
                             "not fixing fundamentals.")
            elif pct <= 30:
                lines.append(f"At P{pct} locally, you're being outperformed by the majority "
                             "of direct competitors. Customers have better-scored alternatives "
                             "within walking distance.")

    if not lines:
        lines.append("Limited signal data constrains diagnosis depth. "
                     "Additional data enrichment would unlock more specific insights.")

    for line in lines:
        w(line + "\n")

def _section_priority_actions(w, recs):
    pass

def _section_watch_list(w, recs):
    pass

def _section_what_not_to_do(w, recs):
    pass

def _section_recommendation_tracker(w, recs):
    pass

def _section_conditional_intelligence(w, conditional_blocks):
    pass

def _section_data_coverage(w, scorecard, review_intel):
    pass


# ---------------------------------------------------------------------------
# Main report assembly
# ---------------------------------------------------------------------------

def generate_monthly_report(venue_name, month_str, scorecard, deltas,
                            benchmarks, review_intel, review_delta,
                            recs, conditional_blocks=None):
    """Generate full monthly markdown report. Returns string."""
    L = []
    w = L.append

    _section_executive_summary(w, venue_name, month_str, scorecard, deltas,
                                benchmarks, review_intel, recs)
    _section_scorecard(w, scorecard, deltas, benchmarks)
    _section_performance_diagnosis(w, scorecard, deltas, benchmarks, review_intel)
    _section_review_intelligence(w, review_intel, review_delta)
    _section_commercial_diagnosis(w, scorecard, deltas, benchmarks, review_intel)
    _section_priority_actions(w, recs)
    _section_watch_list(w, recs)
    _section_what_not_to_do(w, recs)
    _section_recommendation_tracker(w, recs)
    _section_conditional_intelligence(w, conditional_blocks)
    _section_data_coverage(w, scorecard, review_intel)

    w("")
    w(f"*Report generated by DayDine Operator Intelligence v2.0 — {month_str}*")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# JSON / CSV (unchanged)
# ---------------------------------------------------------------------------

def generate_monthly_json(venue_name, month_str, scorecard, deltas, recs):
    return {
        "venue": venue_name, "month": month_str,
        "scorecard": {k: scorecard.get(k) for k in DIM_ORDER + ["overall"]},
        "deltas": deltas,
        "priority_actions": [
            {"title": a["title"], "status": a["status"],
             "priority": a["priority_score"], "dimension": a["dimension"]}
            for a in recs.get("priority_actions", [])
        ],
        "watch_items": [
            {"title": wa["title"], "status": wa["status"]}
            for wa in recs.get("watch_items", [])
        ],
        "active_recommendations": sum(
            1 for r in recs.get("all_recs", [])
            if r.get("status") not in ("resolved", "dropped", "completed")),
    }


def write_monthly_csv_row(venue_name, month_str, scorecard, csv_path):
    fields = ["month", "venue"] + DIM_ORDER + ["overall"]
    row = {"month": month_str, "venue": venue_name}
    for dim in DIM_ORDER + ["overall"]:
        row[dim] = scorecard.get(dim)
    write_header = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def generate_quarterly_report(venue_name, quarter_str, monthly_cards, recs_history):
    L = []
    w = L.append
    w(f"# Quarterly Strategic Review — {venue_name}")
    w(f"*{quarter_str} | DayDine Premium*\n")
    w("---\n")
    months = sorted(monthly_cards.keys())
    if not months:
        w("*No monthly data available for this quarter.*")
        return "\n".join(L)
    w("## Dimension Trends\n")
    w("| Dimension | " + " | ".join(months) + " | Trend |")
    w("|-----------|" + "|".join(["------:" for _ in months]) + "|-------|")
    for dim in DIM_ORDER + ["overall"]:
        vals = [monthly_cards[m].get(dim) for m in months]
        val_strs = [_fmt(v) for v in vals]
        avail = [v for v in vals if v is not None]
        if len(avail) >= 2:
            diff = avail[-1] - avail[0]
            trend = "▲ Improving" if diff > 0.3 else "▼ Declining" if diff < -0.3 else "→ Stable"
        else:
            trend = "—"
        w(f"| {dim.title()} | " + " | ".join(val_strs) + f" | {trend} |")
    w("")
    if recs_history:
        w("## Recommendation Outcomes\n")
        resolved = sum(1 for r in recs_history if r.get("status") in ("resolved", "completed"))
        active = sum(1 for r in recs_history if r.get("status") in ("new", "ongoing", "escalated"))
        w(f"- **{resolved}** resolved/completed, **{active}** still active")
    w(f"\n*Generated by DayDine Operator Intelligence v2.0*")
    return "\n".join(L)


def generate_conditional_blocks(venue, scorecard, benchmarks):
    blocks = []
    ring1 = benchmarks.get("ring1_local", {}) if benchmarks else {}
    if ring1.get("peer_count", 0) >= 10:
        blocks.append({"title": "Competitive Density Alert",
            "content": f"There are {ring1['peer_count']} direct competitors within 5 miles in your category. Differentiation and visibility are critical."})
    fsa = scorecard.get("fsa_rating")
    if fsa is not None and int(fsa) <= 3:
        blocks.append({"title": "Compliance Risk",
            "content": f"FSA rating of {fsa} is below the threshold customers expect. This caps your Trust score and may suppress Google search visibility."})
    vis = scorecard.get("visibility")
    if vis is not None and vis < 4.0:
        blocks.append({"title": "Visibility Gap",
            "content": "Online visibility score is significantly below average. Customers searching for your category may not find you. Prioritise Google Business Profile and review generation."})
    return blocks
