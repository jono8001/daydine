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


def _one_thing_instruction(top_action, venue_rec):
    """Generate a specific, executable one-sentence instruction."""
    dim = top_action.get("dimension", "")
    title = top_action.get("title", "")
    venue_rec = venue_rec or {}

    if dim == "conversion":
        return (
            "Open [business.google.com](https://business.google.com) \u2192 Info \u2192 "
            "check that your booking link, menu link, and opening hours are all complete."
        ), "20 mins", "\u00a30"
    elif dim == "trust" and "hygiene" in title.lower():
        r = venue_rec.get("r", 5)
        return (
            f"Contact your local Environmental Health Officer to request a re-inspection "
            f"(your current FSA rating is {r}/5 \u2014 one level below maximum)."
        ), "15 mins to call", "\u00a30"
    elif dim == "visibility":
        return (
            "After your next 10 satisfied tables: ask guests directly for a Google review. "
            "A personal ask converts at 3\u20134x a QR code."
        ), "Ongoing \u2014 10 seconds per table", "\u00a30"
    elif dim == "experience":
        return (
            "Respond to your most recent negative review today \u2014 "
            "89% of diners read owner responses before booking."
        ), "15 mins", "\u00a30"
    else:
        return (
            top_action.get("expected_upside", "See management priorities below.")
        ), "30 mins", "\u00a30"


def build(w, venue_name, month_str, mode, scorecard, deltas,
          benchmarks, review_intel, recs, venue_rec=None):
    now = datetime.utcnow().strftime("%d %B %Y")
    overall = scorecard.get("overall")

    w(f"# {venue_name} — Monthly Intelligence Report")
    w(f"*{month_str} | Generated {now} | DayDine Premium*\n")
    w("---\n")
    w("## Executive Summary\n")

    # --- Lead with what you should do and why ---
    actions = recs.get("priority_actions", [])
    watches = recs.get("watch_items", [])
    dont = recs.get("what_not_to_do")

    if actions:
        w("**What you should fix now:**\n")
        for i, a in enumerate(actions[:3], 1):
            rt = a.get("rec_type", "action").upper()
            w(f"{i}. **{a['title']}** [{rt}] — {a.get('expected_upside', '')}")
        w("")

        # "One thing" callout — top priority distilled to a single instruction
        instruction, time_est, cost = _one_thing_instruction(actions[0], venue_rec)
        w(f"> **If you do one thing this month:** {instruction} "
          f"\u23f1 {time_est} \u00b7 \U0001f4b0 {cost}\n")

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
