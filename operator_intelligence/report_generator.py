"""
operator_intelligence/report_generator.py — Monthly & Quarterly Report Output

Generates:
  - Monthly markdown report (operator-facing, commercially written)
  - Monthly summary JSON
  - Monthly CSV row
  - Quarterly strategic summary (markdown + JSON)
"""

import csv
import json
import os
from datetime import datetime

from operator_intelligence.scorecard import DIMENSION_WEIGHTS
from operator_intelligence.peer_benchmarking import format_peer_summary
from operator_intelligence.review_delta import THEME_LABELS

# ---------------------------------------------------------------------------
# Monthly Markdown Report
# ---------------------------------------------------------------------------

def _arrow(delta):
    if delta is None:
        return ""
    if delta > 0.3:
        return " ▲"
    if delta < -0.3:
        return " ▼"
    if delta != 0:
        return " →"
    return " ―"


def _fmt_delta(delta):
    if delta is None:
        return "—"
    return f"{delta:+.1f}"


def generate_monthly_report(
    venue_name, month_str, scorecard, deltas,
    benchmarks, review_themes, review_delta,
    commercial_interp, recs, conditional_blocks=None,
):
    """Generate a full monthly markdown report. Returns string."""
    L = []
    w = L.append
    now = datetime.utcnow().strftime("%d %B %Y")

    w(f"# Operator Intelligence Report")
    w(f"## {venue_name}")
    w(f"*{month_str} | Generated {now} | DayDine Premium*\n")
    w("---\n")

    # --- 1. Executive Summary ---
    w("## 1. Executive Summary\n")
    overall = scorecard.get("overall")
    if overall is not None:
        od = deltas.get("overall") if deltas else None
        w(f"**Overall Operator Score: {overall}/10**{_arrow(od)}")
        if od is not None:
            w(f"Change from last month: {_fmt_delta(od)}\n")
        else:
            w("*First report — no prior month for comparison.*\n")

    # One-line peer position
    peer_lines = format_peer_summary(benchmarks) if benchmarks else []
    if peer_lines:
        w("**Peer Position:**")
        for pl in peer_lines:
            w(f"- {pl}")
        w("")

    # Commercial diagnosis sentence
    if commercial_interp:
        w(f"> {commercial_interp}\n")

    # --- 2. Score Movement Dashboard ---
    w("## 2. Dimension Scorecard\n")
    w("| Dimension | Score | Change | Status |")
    w("|-----------|------:|-------:|--------|")
    for dim in ["experience", "visibility", "trust", "conversion", "prestige"]:
        score = scorecard.get(dim)
        delta = deltas.get(dim) if deltas else None
        score_str = f"{score:.1f}" if score is not None else "—"
        delta_str = _fmt_delta(delta)
        status = _arrow(delta).strip() if delta is not None else "NEW"
        w(f"| {dim.title()} | {score_str} | {delta_str} | {status} |")
    w(f"| **Overall** | **{overall:.1f}** | **{_fmt_delta(deltas.get('overall') if deltas else None)}** | |")
    w("")

    # --- 3. Peer Position ---
    w("## 3. Peer Benchmarking\n")
    if benchmarks:
        for ring_key in ["ring1_local", "ring2_catchment", "ring3_uk_cohort"]:
            ring = benchmarks.get(ring_key, {})
            if ring.get("peer_count", 0) == 0:
                continue
            w(f"### {ring['label']} ({ring['peer_count']} peers)\n")
            dims = ring.get("dimensions", {})
            w("| Dimension | You | Rank | Peer Avg | Percentile |")
            w("|-----------|----:|-----:|---------:|-----------:|")
            for dim in list(DIMENSION_WEIGHTS.keys()) + ["overall"]:
                d = dims.get(dim)
                if d:
                    w(f"| {dim.title()} | {d['score']:.1f} | #{d['rank']}/{d['of']} "
                      f"| {d['peer_mean']:.1f} | P{d['percentile']} |")
            w("")

            top_peers = ring.get("top_peers", [])
            if top_peers:
                w("**Top peers:**")
                for tp in top_peers[:3]:
                    w(f"- {tp['name']} ({tp['overall']:.1f})")
                w("")
    else:
        w("*Insufficient peer data for benchmarking.*\n")

    # --- 4. Review Narrative Delta ---
    w("## 4. Review Intelligence\n")
    if review_themes:
        praise = {k: v for k, v in review_themes.get("themes", {}).items()
                  if not k.endswith("_neg") and k != "safety_risk"}
        criticism = {k: v for k, v in review_themes.get("themes", {}).items()
                     if k.endswith("_neg")}

        if praise:
            w("**What customers praise:**")
            for t, count in sorted(praise.items(), key=lambda x: -x[1]):
                w(f"- {THEME_LABELS.get(t, t)} ({count} mentions)")
            w("")
        if criticism:
            w("**What needs attention:**")
            for t, count in sorted(criticism.items(), key=lambda x: -x[1]):
                w(f"- {THEME_LABELS.get(t, t)} ({count} mentions)")
            w("")

        if review_delta and not review_delta.get("is_first_month"):
            if review_delta["new_themes"]:
                w("**New this month:** " +
                  ", ".join(THEME_LABELS.get(t, t) for t in review_delta["new_themes"]))
            if review_delta["fading_themes"]:
                w("**No longer mentioned:** " +
                  ", ".join(THEME_LABELS.get(t, t) for t in review_delta["fading_themes"]))
            w("")

        # Quotes
        pos_q = review_themes.get("quotes_positive", [])
        neg_q = review_themes.get("quotes_constructive", [])
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
    else:
        w("*No review data available for narrative analysis.*\n")

    # --- 5. Commercial Diagnosis ---
    w("## 5. Commercial Diagnosis\n")
    if commercial_interp:
        w(commercial_interp)
    else:
        w("*Insufficient data for commercial diagnosis.*")
    w("")

    # --- 6. Priority Actions ---
    w("## 6. Priority Actions\n")
    actions = recs.get("priority_actions", [])
    if actions:
        for i, a in enumerate(actions, 1):
            status_badge = f"[{a['status'].upper()}]"
            w(f"### {i}. {a['title']} {status_badge}\n")
            w(f"{a['description']}\n")
            w(f"- **Owner:** {a['owner']}")
            w(f"- **Dimension:** {a['dimension'].title()}")
            w(f"- **Expected upside:** {a['expected_upside']}")
            w(f"- **Confidence:** {a['confidence']:.0%}")
            w("")
    else:
        w("No priority actions this month — you're in strong shape.\n")

    # --- 7. Recommendation Tracker ---
    w("## 7. Recommendation Tracker\n")
    all_recs = recs.get("all_recs", [])
    active = [r for r in all_recs if r.get("status") not in ("resolved", "dropped", "completed")]
    if active:
        w("| Rec | Status | First Seen | Times | Dimension |")
        w("|-----|--------|------------|------:|-----------|")
        for r in sorted(active, key=lambda x: -x.get("priority_score", 0)):
            w(f"| {r['title'][:40]} | {r['status']} | {r.get('first_seen', '?')} "
              f"| {r.get('times_seen', 1)} | {r.get('dimension', '')} |")
        w("")

    resolved = [r for r in all_recs if r.get("status") in ("resolved", "completed")]
    if resolved:
        w(f"*{len(resolved)} recommendation(s) resolved/completed.*\n")

    # --- 8. What Not To Do ---
    w("## 8. What Not to Do This Month\n")
    dont = recs.get("what_not_to_do")
    if dont:
        w(f"**{dont['title']}**\n")
        w(f"{dont.get('_reason', dont['description'])}\n")
    else:
        w("No deprioritised actions this month.\n")

    # --- 9. Conditional Intelligence ---
    if conditional_blocks:
        w("## 9. Market Intelligence\n")
        for block in conditional_blocks:
            w(f"### {block['title']}\n")
            w(f"{block['content']}\n")

    # --- 10. Watch Items ---
    watches = recs.get("watch_items", [])
    if watches:
        w("## 10. Watch List\n")
        for wa in watches:
            w(f"- **{wa['title']}**: {wa['description']}")
        w("")

    # --- Evidence appendix ---
    w("---\n")
    w("## Appendix: Data Sources\n")
    w("| Source | Status |")
    w("|--------|--------|")
    w(f"| FSA Hygiene Rating | Rating {scorecard.get('fsa_rating', '—')} |")
    w(f"| Google Business Profile | {scorecard.get('google_rating', '—')}★ "
      f"({scorecard.get('google_reviews', 0)} reviews) |")
    w(f"| Category | {scorecard.get('category', '—')} |")
    w(f"| Postcode | {scorecard.get('postcode', '—')} |")
    w("")
    w(f"*Report generated by DayDine Operator Intelligence v1.0 — {month_str}*")

    return "\n".join(L)


# ---------------------------------------------------------------------------
# Monthly JSON/CSV output
# ---------------------------------------------------------------------------

def generate_monthly_json(venue_name, month_str, scorecard, deltas, recs):
    """Structured JSON summary for API/dashboard consumption."""
    return {
        "venue": venue_name,
        "month": month_str,
        "scorecard": {k: scorecard.get(k) for k in
                      list(DIMENSION_WEIGHTS.keys()) + ["overall"]},
        "deltas": deltas,
        "priority_actions": [
            {"title": a["title"], "status": a["status"],
             "priority": a["priority_score"], "dimension": a["dimension"]}
            for a in recs.get("priority_actions", [])
        ],
        "watch_items": [
            {"title": w["title"], "status": w["status"]}
            for w in recs.get("watch_items", [])
        ],
        "active_recommendations": sum(
            1 for r in recs.get("all_recs", [])
            if r.get("status") not in ("resolved", "dropped", "completed")),
    }


def write_monthly_csv_row(venue_name, month_str, scorecard, csv_path):
    """Append one row to the monthly CSV."""
    fields = ["month", "venue", "experience", "visibility", "trust",
              "conversion", "prestige", "overall"]
    row = {"month": month_str, "venue": venue_name}
    for dim in list(DIMENSION_WEIGHTS.keys()) + ["overall"]:
        row[dim] = scorecard.get(dim)

    write_header = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


# ---------------------------------------------------------------------------
# Quarterly Report
# ---------------------------------------------------------------------------

def generate_quarterly_report(venue_name, quarter_str, monthly_cards, recs_history):
    """Strategic quarterly summary from 3 monthly snapshots."""
    L = []
    w = L.append

    w(f"# Quarterly Strategic Review")
    w(f"## {venue_name}")
    w(f"*{quarter_str} | DayDine Premium*\n")
    w("---\n")

    months = sorted(monthly_cards.keys())
    if not months:
        w("*No monthly data available for this quarter.*")
        return "\n".join(L)

    # Trend table
    w("## Dimension Trends\n")
    w("| Dimension | " + " | ".join(months) + " | Trend |")
    w("|-----------|" + "|".join(["------:" for _ in months]) + "|-------|")

    for dim in list(DIMENSION_WEIGHTS.keys()) + ["overall"]:
        vals = [monthly_cards[m].get(dim) for m in months]
        val_strs = [f"{v:.1f}" if v is not None else "—" for v in vals]
        # Trend: compare first and last available
        available = [v for v in vals if v is not None]
        if len(available) >= 2:
            diff = available[-1] - available[0]
            trend = "▲ Improving" if diff > 0.3 else "▼ Declining" if diff < -0.3 else "→ Stable"
        else:
            trend = "—"
        w(f"| {dim.title()} | " + " | ".join(val_strs) + f" | {trend} |")
    w("")

    # Recommendation lifecycle summary
    w("## Recommendation Outcomes\n")
    if recs_history:
        resolved = sum(1 for r in recs_history if r.get("status") in ("resolved", "completed"))
        active = sum(1 for r in recs_history if r.get("status") in ("new", "ongoing", "escalated"))
        escalated = sum(1 for r in recs_history if r.get("status") == "escalated")
        w(f"- **{resolved}** recommendations resolved or completed")
        w(f"- **{active}** still active ({escalated} escalated)")
    else:
        w("*No recommendation history for this quarter.*")
    w("")

    w(f"*Generated by DayDine Operator Intelligence v1.0*")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Conditional intelligence blocks
# ---------------------------------------------------------------------------

def generate_conditional_blocks(venue, scorecard, benchmarks):
    """Generate conditional intelligence sections when relevant."""
    blocks = []

    # Competitor density warning
    ring1 = benchmarks.get("ring1_local", {}) if benchmarks else {}
    if ring1.get("peer_count", 0) >= 10:
        blocks.append({
            "title": "Competitive Density Alert",
            "content": (f"There are {ring1['peer_count']} direct competitors "
                        "within 5 miles in your category. This is a dense market "
                        "— differentiation and visibility are critical."),
        })

    # Compliance note
    fsa = scorecard.get("fsa_rating")
    if fsa is not None and int(fsa) <= 3:
        blocks.append({
            "title": "Compliance Risk",
            "content": (f"Your FSA rating of {fsa} is below the threshold "
                        "customers expect. This directly impacts Trust score "
                        "and may trigger Google search suppression."),
        })

    # Visibility opportunity
    vis = scorecard.get("visibility")
    if vis is not None and vis < 4.0:
        blocks.append({
            "title": "Visibility Gap",
            "content": ("Your online visibility score is significantly below "
                        "average. Customers searching for your category may "
                        "not find you. Prioritise Google Business Profile "
                        "and review generation."),
        })

    return blocks
