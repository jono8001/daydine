"""Monthly Movement Summary — what changed, what's stable, what's worsening."""


DIM_ORDER = ["experience", "visibility", "trust", "conversion"]
DIM_NAMES = {d: d.title() for d in DIM_ORDER}

# Delta significance thresholds
_NEGLIGIBLE = 0.2
_NOTABLE = 0.5


def _delta_read(dim, delta, score, peer_avg):
    """Interpret a dimension delta in context of peer position."""
    if delta is None:
        return None
    gap = score - peer_avg if score is not None and peer_avg is not None else None
    above_peers = gap is not None and gap > 0

    if abs(delta) < _NEGLIGIBLE:
        if above_peers:
            return "Stable strength"
        elif gap is not None:
            return "Persistent gap"
        return "No change"
    elif delta > 0:
        if above_peers:
            return "Strengthening lead"
        return "Closing gap"
    else:
        if above_peers:
            return "Lead narrowing"
        return "Falling further behind"


def build_monthly_movement(w, scorecard, benchmarks, venue_rec,
                           prior_snapshot, snapshot_deltas, month_str):
    """Render the Monthly Movement Summary section."""
    w("## Monthly Movement Summary\n")

    if not prior_snapshot:
        w("*This is the first report with month-over-month tracking. "
          "All metrics are baselined. Next month's report will show deltas, "
          "trends, and movement context.*\n")
        return

    prior_month = prior_snapshot.get("month", "?")
    w(f"**Period:** {prior_month} → {month_str}\n")

    deltas = snapshot_deltas or {}
    cur_sc = scorecard
    pri_sc = prior_snapshot.get("scorecard", {})
    cur_sig = {
        "google_review_count": scorecard.get("google_reviews"),
        "google_rating": scorecard.get("google_rating"),
    }
    pri_sig = prior_snapshot.get("signals", {})

    ring1 = (benchmarks or {}).get("ring1_local", {})
    ring1_ov = ring1.get("dimensions", {}).get("overall", {})

    # --- What Changed ---
    w("### What Changed This Month\n")
    changes = []

    # Overall score
    d = deltas.get("score_overall")
    cur_overall = cur_sc.get("overall")
    pri_overall = pri_sc.get("overall")
    if d is not None and cur_overall is not None:
        if abs(d) < _NEGLIGIBLE:
            changes.append(f"Overall score: {cur_overall:.1f} (no change)")
        else:
            changes.append(f"Overall score: {pri_overall:.1f} → {cur_overall:.1f} ({d:+.1f})")

    # Google reviews
    grc = cur_sig.get("google_review_count")
    pri_grc = pri_sig.get("google_review_count")
    if grc is not None and pri_grc is not None:
        delta_grc = int(grc) - int(pri_grc)
        if delta_grc > 0:
            velocity = "healthy acquisition" if delta_grc >= 10 else "moderate growth"
            changes.append(f"Google reviews: {pri_grc} → {grc} (+{delta_grc}) — {velocity}")
        elif delta_grc == 0:
            changes.append(f"Google reviews: {grc} (no new reviews)")
        else:
            changes.append(f"Google reviews: {pri_grc} → {grc} ({delta_grc}) — unusual decline")

    # Key dimension scores
    ring1_dims = ring1.get("dimensions", {})
    for dim in DIM_ORDER:
        d = deltas.get(f"score_{dim}")
        cur_v = cur_sc.get(dim)
        pri_v = pri_sc.get(dim)
        peer_avg = ring1_dims.get(dim, {}).get("peer_mean")
        if d is not None and cur_v is not None:
            read = _delta_read(dim, d, cur_v, peer_avg)
            if abs(d) < _NEGLIGIBLE:
                changes.append(f"{dim.title()}: {cur_v:.1f} (no change) — {read}")
            else:
                changes.append(f"{dim.title()}: {pri_v:.1f} → {cur_v:.1f} ({d:+.1f}) — {read}")

    # Peer position
    rank_change = deltas.get("local_rank_change")
    cur_rank = ring1_ov.get("rank")
    cur_of = ring1_ov.get("of")
    if rank_change is not None and cur_rank:
        if rank_change == 0:
            changes.append(f"Local peer position: #{cur_rank} of {cur_of} (unchanged)")
        elif rank_change > 0:
            changes.append(f"Local peer position: improved to #{cur_rank} of {cur_of} (+{rank_change} places)")
        else:
            changes.append(f"Local peer position: dropped to #{cur_rank} of {cur_of} ({rank_change} places)")

    # Demand capture
    dc_improved = deltas.get("demand_capture_improved", [])
    dc_worsened = deltas.get("demand_capture_worsened", [])
    if dc_improved:
        changes.append(f"Demand capture improved: {'; '.join(dc_improved)}")
    if dc_worsened:
        changes.append(f"Demand capture worsened: {'; '.join(dc_worsened)}")
    if not dc_improved and not dc_worsened:
        cur_dc = {d: v for d, v in (scorecard.get("_demand_capture", {}) or {}).items()}
        # Count from current snapshot if available
        changes.append("Demand capture: no dimensions changed since last month")

    if changes:
        for c in changes[:10]:
            w(f"- {c}")
    else:
        w("- No significant changes detected")
    w("")

    # --- What Is Stable ---
    w("### What Is Stable\n")
    stable_items = []
    for dim in DIM_ORDER:
        d = deltas.get(f"score_{dim}")
        cur_v = cur_sc.get(dim)
        if d is not None and abs(d) < _NEGLIGIBLE and cur_v is not None:
            stable_items.append(f"{dim.title()} ({cur_v:.1f})")
    if stable_items:
        w(f"- {', '.join(stable_items)} — unchanged this month")
    else:
        w("- No dimensions were stable (all showed movement)")
    w("")

    # --- What Is Worsening ---
    w("### What Is Worsening\n")
    worsening = []
    for dim in DIM_ORDER:
        d = deltas.get(f"score_{dim}")
        if d is not None and d < -_NEGLIGIBLE:
            cur_v = cur_sc.get(dim)
            worsening.append(f"{dim.title()}: {d:+.1f} to {cur_v:.1f}")
    if dc_worsened:
        for dw in dc_worsened:
            worsening.append(f"Demand capture: {dw}")
    if worsening:
        for item in worsening:
            w(f"- {item}")
    else:
        w("- None detected this month")
    w("")
