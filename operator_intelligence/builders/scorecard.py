"""Dimension scorecard table builder."""

# ============================================================================
# LEGACY (V3.4) — NOT PART OF THE ACTIVE V4 PATH
# ----------------------------------------------------------------------------
# This module is part of the DayDine V3.4 scoring / reporting layer. V4 is
# now the active model (`rcs_scoring_v4.py` + `operator_intelligence/v4_*.py`).
# This file is retained only for rollback, comparison against V4 output
# (via `compare_v3_v4.py`), and historical reference.
#
# Do NOT import this module from any V4 code path. The boundary check in
# `tests/test_v4_legacy_boundary.py` enforces this.
#
# See `docs/DayDine-Legacy-Quarantine-Note.md` for conditions under which
# this file becomes safe to delete.
# ============================================================================

DIM_ORDER = ["experience", "visibility", "trust", "conversion", "prestige"]
HEADLINE_DIMS = ["experience", "visibility", "trust", "conversion"]


def _fmt(val):
    return f"{val:.1f}" if val is not None else "—"


def _fmt_delta(d):
    return f"{d:+.1f}" if d is not None else "—"


def _read(score, gap, delta=None):
    """Interpret score position, incorporating direction of change when available."""
    if score is None:
        return "No data"
    above = gap is not None and gap >= 0.3
    below = gap is not None and gap <= -0.3
    moving_up = delta is not None and delta >= 0.2
    moving_down = delta is not None and delta <= -0.2
    stable = delta is not None and abs(delta) < 0.2

    if moving_up and above: return "Strengthening lead"
    if moving_up and below: return "Closing gap"
    if moving_down and above: return "Lead narrowing"
    if moving_down and below: return "Falling further behind"
    if stable and above: return "Stable strength"
    if stable and below: return "Persistent gap"

    # Fallback: no delta or no peer data
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

    for dim in HEADLINE_DIMS:
        score = scorecard.get(dim)
        delta = deltas.get(dim) if deltas else None
        peer_avg = ring1_dims.get(dim, {}).get("peer_mean")
        gap = round(score - peer_avg, 1) if score is not None and peer_avg is not None else None
        gap_str = f"{gap:+.1f}" if gap is not None else "—"

        w(f"| {dim.title()} | {_fmt(score)} | {_fmt_delta(delta)} "
          f"| {_fmt(peer_avg)} | {gap_str} | {_read(score, gap, delta)} |")

    overall = scorecard.get("overall")
    od = deltas.get("overall") if deltas else None
    w(f"| **Overall** | **{_fmt(overall)}** | **{_fmt_delta(od)}** | | | |")
    w("")

    # Prestige as footnote — tracked but not a headline lever
    prest = scorecard.get("prestige")
    if prest is not None:
        prest_peer = ring1_dims.get("prestige", {}).get("peer_mean")
        note = f"{_fmt(prest)}/10"
        if prest_peer is not None:
            note += f" (peer avg {_fmt(prest_peer)})"
        w(f"*Prestige (editorial recognition): {note} — tracked but not a headline "
          f"operational lever for most independents.*\n")
