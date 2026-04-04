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

    w(f"# {venue_name} — External Blind-Spot Report")
    w(f"*{month_str} | Generated {now} | DayDine Premium*\n")
    w("---\n")
    w("## Executive Summary\n")

    # --- Lead with top leaks / actions / risk ---
    actions = recs.get("priority_actions", [])
    watches = recs.get("watch_items", [])
    dont = recs.get("what_not_to_do")

    if actions:
        w("**What needs attention now:**\n")
        for i, a in enumerate(actions[:3], 1):
            rt = a.get("rec_type", "action").upper()
            w(f"{i}. **{a['title']}** [{rt}] — {a.get('expected_upside', '')}")
        w("")

    if watches:
        w("**Watch this month:**")
        for wa in watches[:2]:
            w(f"- {wa['title']}")
        w("")

    if dont:
        w(f"**Do not prioritise:** {dont['title']}\n")

    # --- Score as context, not hero ---
    od = deltas.get("overall") if deltas else None
    if overall is not None:
        if od is not None:
            direction = "up" if od > 0 else "down" if od < 0 else "unchanged"
            w(f"**Overall score: {overall:.1f}/10** ({_fmt_delta(od)} vs prior month, {direction})")
        else:
            w(f"**Overall score: {overall:.1f}/10** (baseline month — no prior comparison)")

    # Headline dimension — strongest and weakest (excluding prestige)
    headline_dims = [d for d in DIM_ORDER if d != "prestige"]
    dims = {d: scorecard.get(d) for d in headline_dims if scorecard.get(d) is not None}
    if dims:
        strongest = max(dims, key=dims.get)
        weakest = min(dims, key=dims.get)
        w(f" | Strongest: {strongest.title()} ({dims[strongest]:.1f})"
          f" | Weakest: {weakest.title()} ({dims[weakest]:.1f})")
    w("")

    peer_lines = format_peer_summary(benchmarks) if benchmarks else []
    if peer_lines:
        w(f"**Competitive position:** {peer_lines[0]}")
        for pl in peer_lines[1:]:
            w(f"  {pl}")
        w("")

    w("*This report uses publicly observable data only — no internal systems required. "
      "See Data Basis below for full evidence breakdown.*\n")
