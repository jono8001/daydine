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
    pass

def _section_performance_diagnosis(w, scorecard, deltas, benchmarks, review_intel):
    pass

def _section_review_intelligence(w, review_intel, review_delta):
    pass

def _section_commercial_diagnosis(w, scorecard, deltas, benchmarks, review_intel):
    pass

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
