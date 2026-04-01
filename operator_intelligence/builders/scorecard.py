"""Dimension scorecard table builder."""

DIM_ORDER = ["experience", "visibility", "trust", "conversion", "prestige"]


def _fmt(val):
    return f"{val:.1f}" if val is not None else "—"


def _fmt_delta(d):
    return f"{d:+.1f}" if d is not None else "—"


def _read(score, gap):
    if score is None:
        return "No data"
    if gap is not None:
        if gap >= 1.5: return "Clear strength"
        if gap >= 0.3: return "Above peers"
        if gap <= -1.5: return "Significant gap"
        if gap <= -0.3: return "Below peers"
    if score >= 8.0: return "Strong"
    if score <= 4.0: return "Needs work"
    return "In line"


def build(w, scorecard, deltas, benchmarks):
    w("## Dimension Scorecard\n")
    w("| Dimension | Score | Δ | Peer Avg | Gap | Read |")
    w("|-----------|------:|--:|---------:|----:|------|")

    ring1_dims = {}
    if benchmarks:
        ring1 = benchmarks.get("ring1_local") or benchmarks.get("ring2_catchment") or {}
        ring1_dims = ring1.get("dimensions", {})

    for dim in DIM_ORDER:
        score = scorecard.get(dim)
        delta = deltas.get(dim) if deltas else None
        peer_avg = ring1_dims.get(dim, {}).get("peer_mean")
        gap = round(score - peer_avg, 1) if score is not None and peer_avg is not None else None
        gap_str = f"{gap:+.1f}" if gap is not None else "—"

        w(f"| {dim.title()} | {_fmt(score)} | {_fmt_delta(delta)} "
          f"| {_fmt(peer_avg)} | {gap_str} | {_read(score, gap)} |")

    overall = scorecard.get("overall")
    od = deltas.get("overall") if deltas else None
    w(f"| **Overall** | **{_fmt(overall)}** | **{_fmt_delta(od)}** | | | |")
    w("")
