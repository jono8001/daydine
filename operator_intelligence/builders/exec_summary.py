"""Executive summary section builder."""

from datetime import datetime
from operator_intelligence.peer_benchmarking import format_peer_summary

DIM_ORDER = ["experience", "visibility", "trust", "conversion", "prestige"]


def _fmt_delta(d):
    return f"{d:+.1f}" if d is not None else "—"


def _arrow(d):
    if d is None: return ""
    if d > 0.3: return " ▲"
    if d < -0.3: return " ▼"
    return " →" if d != 0 else " ―"


def build(w, venue_name, month_str, mode, scorecard, deltas,
          benchmarks, review_intel, recs):
    now = datetime.utcnow().strftime("%d %B %Y")
    overall = scorecard.get("overall")

    w(f"# {venue_name} — Operator Intelligence Report")
    w(f"*{month_str} | Generated {now} | DayDine Premium*\n")
    w("---\n")
    w("## Executive Summary\n")

    od = deltas.get("overall") if deltas else None
    if overall is not None:
        w(f"**Overall Operator Score: {overall:.1f} / 10**{_arrow(od)}")
        if od is not None:
            direction = "up" if od > 0 else "down" if od < 0 else "unchanged"
            w(f"*{_fmt_delta(od)} vs prior month ({direction})*\n")
        else:
            w("*Baseline month — no prior period for comparison*\n")

    dims = {d: scorecard.get(d) for d in DIM_ORDER if scorecard.get(d) is not None}
    if dims:
        strongest = max(dims, key=dims.get)
        weakest = min(dims, key=dims.get)
        gap = dims[strongest] - dims[weakest]
        w(f"**Strongest dimension:** {strongest.title()} ({dims[strongest]:.1f}). "
          f"**Weakest:** {weakest.title()} ({dims[weakest]:.1f}). "
          f"Internal gap: {gap:.1f} points.\n")

    peer_lines = format_peer_summary(benchmarks) if benchmarks else []
    if peer_lines:
        w(f"**Competitive position:** {peer_lines[0]}")
        for pl in peer_lines[1:]:
            w(f"  {pl}")
        w("")

    actions = recs.get("priority_actions", [])
    if actions:
        top = actions[0]
        rt = top.get("rec_type", "action").upper()
        w(f"**Top priority this month:** {top['title']} "
          f"[{rt}] — {top.get('expected_upside', '')}.\n")

    has_narrative = review_intel.get("has_narrative", False) if review_intel else False
    grc = scorecard.get("google_reviews") or 0
    ta_count = review_intel.get("review_count_ta") or 0 if review_intel else 0
    if has_narrative:
        n = review_intel.get("reviews_analyzed", 0)
        sources = []
        if n - ta_count > 0:
            sources.append(f"{n - ta_count} Google")
        if ta_count > 0:
            sources.append(f"{ta_count} TripAdvisor")
        source_str = " + ".join(sources) if sources else f"{n}"
        w(f"*This report includes narrative analysis from {n} customer reviews ({source_str}).*\n")
    else:
        w(f"*Based on structured signals ({grc} Google reviews aggregated, "
          f"no individual review text collected yet). "
          f"Narrative depth will increase with review text enrichment.*\n")
