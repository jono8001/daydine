"""
operator_intelligence/v4_report_generator.py — V4 Operator Report Generator.

Produces the V4-native monthly operator report per
docs/DayDine-V4-Report-Spec.md.

Entry point:
    generate_v4_monthly_report(inputs: ReportInputs) -> (report_text, qa_dict)

Mode branching (spec §3):
    rankable_a      -> full report (primary league)
    rankable_b      -> full report (secondary league, caveats if single-platform)
    directional_c   -> full report with peer sections replaced + demoted
    profile_only_d  -> profile stub
    closed          -> closure notice
    temp_closed     -> full report with temporary-closure flag

All section renderers are plain functions `_render_<name>(out, inputs)`
where `out` is a `list.append` callable. The orchestrator below composes
them in the order prescribed by the spec.

Reuses surviving V3.4 helpers:
    - review_analysis, review_delta   (profile narrative)
    - segment_analysis                (segment narrative)
    - risk_detection                  (risk alerts)
    - peer_benchmarking               (market position / competitive)
    - demand_capture_audit            (demand capture audit block)
    - recommendations                 (management priorities / watch list)
    - commercial_estimates            (financial impact sizing)
    - builders.event_forecast         (next-30-days forecast)
"""
from __future__ import annotations

from typing import Callable, Optional

from operator_intelligence.v4_adapter import (
    ReportInputs,
    MODE_RANKABLE_A, MODE_RANKABLE_B, MODE_DIRECTIONAL_C,
    MODE_PROFILE_ONLY_D, MODE_CLOSED, MODE_TEMP_CLOSED,
)
from operator_intelligence.v4_report_spec import (
    validate_v4_report, to_qa_dict,
)

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_score(x: Optional[float]) -> str:
    if x is None:
        return "—"
    return f"{x:.3f}"


def _fmt_score2(x: Optional[float]) -> str:
    if x is None:
        return "—"
    return f"{x:.2f}"


def _pc(num: Optional[float]) -> str:
    if num is None:
        return "—"
    return f"{num:.1f}%"


def _class_banner_compact(inputs: ReportInputs) -> str:
    cls = inputs.confidence_class
    mode = inputs.report_mode
    if mode == MODE_CLOSED:
        return "Closed"
    if mode == MODE_PROFILE_ONLY_D:
        return f"{cls} · insufficient evidence"
    if mode == MODE_DIRECTIONAL_C:
        reason = _directional_c_reason(inputs)
        return f"{cls} · {reason}"
    if mode == MODE_RANKABLE_B and inputs.single_platform():
        return f"{cls} · single-platform"
    return cls


def _directional_c_reason(inputs: ReportInputs) -> str:
    """Short reason text for the Directional-C banner (spec §4.3)."""
    if inputs.entity_match_status == "ambiguous":
        return "entity match ambiguous"
    if inputs.entity_match_status == "none":
        return "unmatched entity"
    if not inputs.customer.available or len(inputs.customer.platforms) == 0:
        return "no customer-platform evidence"
    # Thin reviews check — any platform under 5 with no other >=30
    any_thin = any(
        int(p.get("count") or 0) < 5 for p in inputs.customer.platforms.values()
    )
    any_big = any(
        int(p.get("count") or 0) >= 30
        for p in inputs.customer.platforms.values()
    )
    if any_thin and not any_big:
        return "thin review evidence"
    families_present = sum([
        inputs.trust.available,
        inputs.customer.available,
        inputs.commercial.available,
    ])
    if families_present <= 1:
        return "only one primary evidence family present"
    return "directional evidence"


# ---------------------------------------------------------------------------
# Section: Header
# ---------------------------------------------------------------------------

def _render_header(out: Callable[[str], None], inputs: ReportInputs) -> None:
    """H1 + metadata line (spec §4.1)."""
    out(f"# {inputs.name} — Monthly Intelligence Report")
    out(
        f"*{inputs.month_str} · Engine {inputs.engine_version} · "
        f"{_class_banner_compact(inputs)}*"
    )
    out("")

    # Trading names / legal entity disclosure
    if inputs.fsa_name and inputs.fsa_name != inputs.name:
        out(f"*FSA legal entity:* {inputs.fsa_name}")
    if inputs.trading_names:
        tn = ", ".join(inputs.trading_names)
        out(f"*Also trading as:* {tn}")

    # Temporary closure flag
    if inputs.report_mode == MODE_TEMP_CLOSED:
        out("")
        out("> ⚠️ **Temporarily closed** — excluded from league tables until "
            "reopened. Score preserved.")

    out("")
    out("---")
    out("")


# ---------------------------------------------------------------------------
# Section: V4 Score Card (spec §4.2)
# ---------------------------------------------------------------------------

def _platform_signal_line(inputs: ReportInputs) -> str:
    if not inputs.customer.available:
        return "no customer-platform evidence"
    parts = []
    for name, p in inputs.customer.platforms.items():
        parts.append(
            f"{name.capitalize()} {int(p.get('count') or 0)} @ "
            f"{float(p.get('raw') or 0):.1f}"
        )
    return " · ".join(parts)


def _cr_signal_line(inputs: ReportInputs) -> str:
    r = inputs.venue_record
    menu = inputs.menu_record or {}
    web = "web ✓" if r.get("web") else "web ✗"
    if (menu.get("has_menu_online") or r.get("has_menu_online")):
        menu_s = "menu ✓"
    else:
        menu_s = "menu ✗"
    goh = r.get("goh") or []
    days = sum(1 for line in goh if isinstance(line, str) and ":" in line
               and line.split(":", 1)[1].strip())
    hours_s = f"hours {days}/7"
    booking = (r.get("booking_url") or r.get("reservation_url")
                or r.get("reservable") or r.get("phone") or r.get("tel"))
    booking_s = "booking ✓" if booking else "booking —"
    return f"{web} · {menu_s} · {hours_s} · {booking_s}"


def _render_score_card(out: Callable[[str], None], inputs: ReportInputs) -> None:
    """V4 headline score card (spec §4.2). Suppressed in Profile-only-D and
    Closed modes (caller enforces mode before invoking)."""
    out(f"**V4 Score: {_fmt_score(inputs.rcs_v4_final)} / 10** "
        f"· {inputs.confidence_class}")
    out("")
    out("| Component | Score | Evidence |")
    out("|---|---:|---|")

    # Trust row
    if inputs.trust.available:
        trust_evidence = ("compliance; not food quality · "
                           f"signals used: {inputs.trust.signals_used}")
        # Surface any active stale cap on the Trust row
        stale_codes = [c.get("code") for c in inputs.caps_applied
                        if c.get("code", "").startswith("STALE-")]
        if stale_codes:
            trust_evidence += f" · cap: {', '.join(stale_codes)}"
        out(f"| Trust & Compliance | {_fmt_score(inputs.trust.score)} | "
            f"{trust_evidence} |")
    else:
        out("| Trust & Compliance | — | insufficient evidence |")

    # Customer Validation row
    if inputs.customer.available:
        out(f"| Customer Validation | {_fmt_score(inputs.customer.score)} | "
            f"{_platform_signal_line(inputs)} |")
    else:
        out("| Customer Validation | — | insufficient evidence |")

    # Commercial Readiness row
    if inputs.commercial.available:
        out(f"| Commercial Readiness | {_fmt_score(inputs.commercial.score)} | "
            f"{_cr_signal_line(inputs)} |")
    else:
        out("| Commercial Readiness | — | no observability |")

    # Distinction row (only if positive)
    if inputs.distinction_value and inputs.distinction_value > 0:
        srcs = ", ".join(inputs.distinction_sources) or "award"
        out(f"| Distinction modifier | +{inputs.distinction_value:.2f} | {srcs} |")

    out("")


# ---------------------------------------------------------------------------
# Section: Score, Confidence & Rankability Basis (spec §5.3)
# ---------------------------------------------------------------------------

def _rankability_note(inputs: ReportInputs) -> str:
    if inputs.report_mode == MODE_RANKABLE_A:
        return ("Strong multi-source evidence. Eligible for the primary "
                "league table.")
    if inputs.report_mode == MODE_RANKABLE_B:
        base = ("Acceptable evidence. Eligible for the secondary league "
                "table.")
        if inputs.single_platform():
            base += (" Single customer platform — peer comparisons are "
                     "directional.")
        return base
    if inputs.report_mode == MODE_DIRECTIONAL_C:
        reason = _directional_c_reason(inputs)
        return (f"Not league-ranked — {reason}. Narrative below is "
                f"indicative; peer comparisons are suppressed.")
    if inputs.report_mode == MODE_PROFILE_ONLY_D:
        return "Insufficient evidence for a published score. Profile only."
    if inputs.report_mode == MODE_CLOSED:
        return "Venue is closed; no score is published."
    if inputs.report_mode == MODE_TEMP_CLOSED:
        return ("Acceptable evidence, but venue is temporarily closed — "
                "excluded from league tables until reopened.")
    return ""


def _render_confidence_basis(out: Callable[[str], None],
                              inputs: ReportInputs) -> None:
    out("## Score, Confidence & Rankability Basis")
    out("")
    out(f"**Confidence class:** {inputs.confidence_class}")
    out(f"**Rankable:** {'Yes' if inputs.rankable else 'No'}  ·  "
        f"**League-eligible:** {'Yes' if inputs.league_table_eligible else 'No'}")
    out(f"**Entity match:** {inputs.entity_match_status}")
    if inputs.entity_ambiguous:
        out("**Entity ambiguity flag:** set — see entity-resolution note.")
    out("")
    out(_rankability_note(inputs))
    out("")

    # Source-family summary
    sfs = inputs.source_family_summary or {}
    out("**Primary evidence families present:**")
    out(f"- FSA / FHRS: {sfs.get('fsa', 'absent')}")
    platforms = sfs.get("customer_platforms") or []
    out(f"- Customer platforms: {', '.join(platforms) if platforms else 'none'}")
    out(f"- Commercial readiness: {sfs.get('commercial', 'absent')}")
    out(f"- Companies House: {sfs.get('companies_house', 'unmatched')}")
    out("")

    # Entity-resolution context if ambiguous
    if inputs.entity_ambiguous and inputs.entity_resolution_note:
        note = inputs.entity_resolution_note
        fhrsids = [str(f) for f in (note.get("fhrsids") or [])]
        names = note.get("names") or []
        others = [str(f) for f in fhrsids if str(f) != inputs.fhrsid]
        if others:
            # Pair with names where available (positional)
            pairs = []
            for i, fid in enumerate(fhrsids):
                if str(fid) == inputs.fhrsid:
                    continue
                name = names[i] if i < len(names) else ""
                pairs.append(f"{fid}" + (f" ({name})" if name else ""))
            out(f"**Ambiguity context:** this venue shares identifiers with "
                f"{len(others)} other FHRS record(s): "
                + ", ".join(pairs) + ".")
            out("")


# ---------------------------------------------------------------------------
# Section: How the Score Was Formed (spec §9 / §5.18)
# ---------------------------------------------------------------------------

def _render_decision_trace(out: Callable[[str], None],
                            inputs: ReportInputs) -> None:
    """Compact decision trace block. Suppressed when rcs_v4_final is None."""
    if inputs.rcs_v4_final is None:
        return

    out("## How the Score Was Formed")
    out("")
    out("*Your V4 score was formed as follows:*")
    out("")
    out("```")
    for line in inputs.decision_trace:
        out(line)
    out("```")
    out("")

    if inputs.penalties_applied or inputs.caps_applied:
        out("**Penalties and caps applied**")
        out("")
        out("| Code | Effect | Reason |")
        out("|---|---|---|")
        for p in inputs.caps_applied:
            out(f"| {p.get('code', '')} | {p.get('effect', '')} | "
                f"{p.get('reason', '')} |")
        for p in inputs.penalties_applied:
            out(f"| {p.get('code', '')} | {p.get('effect', '')} | "
                f"{p.get('reason', '')} |")
        out("")

    out(f"*Engine version: {inputs.engine_version} · "
        f"Computed at: {inputs.computed_at}*")
    out("")


# ---------------------------------------------------------------------------
# Section: Trust & Compliance (spec §5.5)
# ---------------------------------------------------------------------------

def _render_trust_compliance(out: Callable[[str], None],
                              inputs: ReportInputs) -> None:
    out("## Trust & Compliance")
    out("")
    out(f"**Component score:** {_fmt_score(inputs.trust.score)} / 10  "
        f"·  *compliance signal; not food quality.*")
    out("")
    if not inputs.trust.available:
        out("FSA / FHRS record not usable for this venue "
            "(unscored rating or missing data).")
        out("")
        return

    r = inputs.venue_record
    fsa_rating = r.get("r")
    fsa_rating_str = str(fsa_rating) if fsa_rating is not None else "—"
    sh = r.get("sh") if r.get("sh") is not None else "—"
    ss = r.get("ss") if r.get("ss") is not None else "—"
    sm = r.get("sm") if r.get("sm") is not None else "—"
    rd = r.get("rd") or "—"

    out("**FHRS decomposition**")
    out("")
    out("| Signal | Value |")
    out("|---|---:|")
    out(f"| FHRS headline rating (0–5) | {fsa_rating_str} |")
    out(f"| Food hygiene sub-score | {sh} |")
    out(f"| Structural compliance sub-score | {ss} |")
    out(f"| Confidence in management sub-score | {sm} |")
    out(f"| Last inspection date | {rd} |")
    out("")

    # Stale-inspection callouts from caps_applied
    stale = [c for c in inputs.caps_applied if c.get("code", "").startswith("STALE-")]
    if stale:
        out("**Active caps on Trust component**")
        for s in stale:
            out(f"- `{s.get('code')}`: {s.get('effect')} — {s.get('reason')}")
        out("")

    # Companies House row (if any CH penalty / cap fired)
    ch = [p for p in inputs.penalties_applied + inputs.caps_applied
           if p.get("code", "").startswith("CH-")]
    if ch:
        out("**Business-viability risk signals (Companies House)**")
        for e in ch:
            out(f"- `{e.get('code')}`: {e.get('effect')} — {e.get('reason')}")
        out("")


# ---------------------------------------------------------------------------
# Section: Customer Validation (spec §5.6)
# ---------------------------------------------------------------------------

def _render_customer_validation(out: Callable[[str], None],
                                  inputs: ReportInputs) -> None:
    out("## Customer Validation")
    out("")
    out(f"**Component score:** {_fmt_score(inputs.customer.score)} / 10  "
        f"·  *public rating metadata; shrinkage applied to low-count evidence.*")
    out("")

    if not inputs.customer.available or not inputs.customer.platforms:
        out("No customer-platform evidence present (no Google / TripAdvisor / "
            "OpenTable ratings and counts).")
        out("")
        return

    out("| Platform | Raw rating | Reviews | Shrunk rating | Coverage weight |")
    out("|---|---:|---:|---:|---:|")
    for name, p in inputs.customer.platforms.items():
        raw = float(p.get("raw") or 0)
        count = int(p.get("count") or 0)
        shrunk = float(p.get("shrunk") or 0)
        weight = float(p.get("weight") or 0)
        out(f"| {name.capitalize()} | {raw:.1f} | {count} | "
            f"{shrunk:.2f} | {weight:.2f} |")
    out("")

    # Shrinkage note when material
    material_shrinks = [
        (n, p) for n, p in inputs.customer.platforms.items()
        if abs(float(p.get("raw") or 0) - float(p.get("shrunk") or 0)) >= 0.3
    ]
    if material_shrinks:
        parts = []
        for n, p in material_shrinks:
            parts.append(
                f"{n.capitalize()} raw {float(p.get('raw') or 0):.1f} → "
                f"shrunk {float(p.get('shrunk') or 0):.2f} "
                f"(count {int(p.get('count') or 0)})"
            )
        out("*Shrinkage note:* " + "; ".join(parts) + ". "
            "Bayesian shrinkage pulls low-count ratings toward the platform "
            "prior. This is a designed property of V4 Customer Validation.")
        out("")

    if inputs.single_platform():
        out("*Single customer platform — this class is capped at Rankable-B "
            "regardless of score. Peer comparisons are directional.*")
        out("")


# ---------------------------------------------------------------------------
# Section: Commercial Readiness / Demand Capture (spec §5.7)
# ---------------------------------------------------------------------------

def _render_commercial_readiness(out: Callable[[str], None],
                                   inputs: ReportInputs) -> None:
    out("## Commercial Readiness / Demand Capture Audit")
    out("")
    out(f"**Component score:** {_fmt_score(inputs.commercial.score)} / 10  "
        f"·  *can a guest find and book; not a food-quality signal.*")
    out("")

    if not inputs.commercial.available:
        out("No commercial-readiness evidence observable for this venue "
            "(no Google place record, no menu data, no website signal).")
        out("")
        return

    r = inputs.venue_record
    menu = inputs.menu_record or {}
    website = bool(r.get("web"))
    menu_online = bool(menu.get("has_menu_online") or r.get("has_menu_online"))
    goh = r.get("goh") or []
    days_with_hours = sum(
        1 for line in goh if isinstance(line, str) and ":" in line
        and line.split(":", 1)[1].strip()
    )
    booking = bool(
        r.get("booking_url") or r.get("reservation_url")
        or r.get("reservable") or r.get("phone") or r.get("tel")
    )

    out("**Commercial Readiness sub-signals (V4 scoring inputs)**")
    out("")
    out("| Sub-signal | Value | In score |")
    out("|---|---|---:|")
    out(f"| Website present | {'Yes' if website else 'No'} | 25% |")
    out(f"| Menu online | {'Yes' if menu_online else 'No'} | 25% |")
    out(f"| Opening-hours completeness | {days_with_hours}/7 days | 25% |")
    out(f"| Booking / contact path | "
        f"{'Yes' if booking else 'No (observed: phone or reservable absent)'} "
        f"| 25% |")
    out("")

    # Demand capture audit extension — narrative only, not in score
    demand = _build_demand_capture_audit(inputs)
    if demand:
        out("**Demand Capture Audit** — outside-in customer-journey check. "
            "*Narrative only — does not feed the score.*")
        out("")
        out("| Dimension | Verdict | Note |")
        out("|---|---|---|")
        for dim in demand.get("dimensions", []):
            out(f"| {dim.get('dimension')} | {dim.get('verdict')} | "
                f"{dim.get('note', '')} |")
        out("")


def _build_demand_capture_audit(inputs: ReportInputs) -> Optional[dict]:
    """Call the existing V3.4 demand-capture audit, with minimal shims.
    Silent-fail if the helper refuses the inputs — this is narrative only."""
    try:
        from operator_intelligence.demand_capture_audit import (
            run_demand_capture_audit,
        )
        # The V3.4 audit expects (venue_rec, scorecard, benchmarks,
        # review_intel). The scorecard / benchmarks it reads are used only
        # for verdict colouring; we pass a minimal stub keyed on the V4
        # score so nothing V3.4-specific leaks into the verdicts.
        scorecard_stub = {
            "overall": inputs.rcs_v4_final or 0.0,
            "google_rating": _safe_float(inputs.venue_record.get("gr")),
            "google_reviews": _safe_int(inputs.venue_record.get("grc")),
            "fsa_rating": _safe_int(inputs.venue_record.get("r")),
        }
        return run_demand_capture_audit(
            inputs.venue_record,
            scorecard_stub,
            inputs.peer_benchmarks or {},
            inputs.review_intel or {},
        )
    except Exception:
        return None


def _safe_int(x):
    try:
        return int(x) if x is not None else None
    except (ValueError, TypeError):
        return None


def _safe_float(x):
    try:
        return float(x) if x is not None else None
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Section: Financial Impact & Value at Stake (spec §5.2 / §6)
# ---------------------------------------------------------------------------

def _fi_confidence_label(inputs: ReportInputs) -> Optional[str]:
    """Derive the mandatory confidence label for Financial Impact (spec §6.3).

    Returns None if the section should be suppressed entirely.
    """
    if inputs.report_mode in {MODE_PROFILE_ONLY_D, MODE_CLOSED, MODE_TEMP_CLOSED}:
        return None

    cr = inputs.commercial
    cv = inputs.customer
    if not cr.available:
        return None

    r = inputs.venue_record
    web_observed = bool(r.get("web_url"))  # observed, not inferred
    phone_observed = bool(r.get("phone") or r.get("tel"))

    # High: Rankable-A, all three families, CR >= 7, observed web AND phone
    if (inputs.report_mode == MODE_RANKABLE_A
            and web_observed and phone_observed
            and (cr.score or 0) >= 7.0):
        return "High"

    # Moderate: Rankable-* with CR >= 6 and (website or phone observed) and
    # at least one platform with >=30 reviews
    big_plat = any(
        int(p.get("count") or 0) >= 30 for p in cv.platforms.values()
    ) if cv.available else False
    if (inputs.report_mode in {MODE_RANKABLE_A, MODE_RANKABLE_B}
            and (cr.score or 0) >= 6.0
            and (web_observed or phone_observed)
            and big_plat):
        return "Moderate"

    # Directional-C renders only at Low and only if CR is available
    if inputs.report_mode == MODE_DIRECTIONAL_C:
        return "Low"

    # Otherwise Low
    return "Low"


def _render_financial_impact(out: Callable[[str], None],
                              inputs: ReportInputs) -> None:
    out("## Financial Impact & Value at Stake")
    out("")

    conf = _fi_confidence_label(inputs)
    if conf is None:
        # Directional-C fallback is handled by conf = "Low" above; this
        # branch only hits when CR is unavailable or mode is D / Closed.
        out("*Financial impact cannot be robustly estimated for this venue.* "
            "Commercial Readiness evidence is unavailable, which is where "
            "most recoverable revenue shows up in the model. See the Score, "
            "Confidence & Rankability Basis section above.")
        out("")
        return

    # Use commercial_estimates when available; fall back to a range derived
    # from the CR gap.
    gaps = _cr_gaps(inputs)
    value_range, cost_band, payback = _fi_estimate(inputs, gaps)

    out(f"**Confidence: {conf}.** Figures are directional. Exact numbers "
        f"require internal cover and spend data.")
    out("")

    if gaps:
        out("*Observed commercial-readiness gaps driving this estimate:*")
        for g in gaps:
            out(f"- {g}")
        out("")

    if value_range:
        low, high = value_range
        annual_low = low * 12
        annual_high = high * 12
        out("| Metric | Current | At stake | Notes |")
        out("|---|---|---|---|")
        out(f"| Monthly revenue impact | — | £{low:,.0f} – £{high:,.0f} | "
            "subject to gap closure |")
        out(f"| Annual projection | — | £{annual_low:,.0f} – £{annual_high:,.0f} | "
            "directional |")
        out("")

    if cost_band:
        out(f"**Recommended action cost band:** {cost_band}")
    if payback:
        out(f"**Expected payback window:** {payback}")
    out("")

    # Directional-C wrapper caveat
    if inputs.report_mode == MODE_DIRECTIONAL_C:
        out("> *Directional-C:* the headline score is not league-ranked. "
            "These figures are illustrative only — treat as a ceiling on "
            "what better evidence could unlock, not a target.")
        out("")


def _cr_gaps(inputs: ReportInputs) -> list[str]:
    r = inputs.venue_record
    gaps = []
    if not r.get("web"):
        gaps.append("no website evidence")
    if not (inputs.menu_record or {}).get("has_menu_online") \
            and not r.get("has_menu_online"):
        gaps.append("no online menu")
    goh = r.get("goh") or []
    if not goh:
        gaps.append("no published opening hours")
    if not (r.get("booking_url") or r.get("reservation_url")
             or r.get("reservable") or r.get("phone") or r.get("tel")):
        gaps.append("no reachable booking / contact path")
    return gaps


def _fi_estimate(inputs: ReportInputs, gaps: list[str]
                  ) -> tuple[Optional[tuple[float, float]],
                             Optional[str], Optional[str]]:
    """Return (monthly_range £, cost_band, payback) or (None, None, None).

    Uses commercial_estimates helpers where possible, with conservative
    fallbacks. Never emits a point estimate.
    """
    if not gaps:
        return None, None, None
    try:
        from operator_intelligence.commercial_estimates import (
            _spend_range, _MONTHLY_COVERS,
        )
        gpl = inputs.venue_record.get("gpl")
        try:
            gpl_int = int(gpl) if gpl is not None else 2
        except (ValueError, TypeError):
            gpl_int = 2
        spend_low, spend_high = _spend_range(gpl_int)
        covers_low, covers_high = _MONTHLY_COVERS.get(
            gpl_int, _MONTHLY_COVERS[2])
    except Exception:
        spend_low, spend_high = 15, 35
        covers_low, covers_high = 600, 1500

    # Per-gap leakage: ~2% of monthly covers at risk per observed gap
    per_gap_pct = 0.02
    gap_count = len(gaps)
    leak_low = covers_low * per_gap_pct * gap_count * spend_low
    leak_high = covers_high * per_gap_pct * gap_count * spend_high * 1.5

    # Cost band derivation: website/menu/hours are low-cost; booking-path is
    # higher where it implies integration
    cost_band = "< £200 (profile updates)"
    payback = "< 1 month"
    if "no reachable booking / contact path" in gaps:
        cost_band = "£200 – £1,000 (booking widget / published phone)"
        payback = "1 – 3 months"

    return (round(leak_low), round(leak_high)), cost_band, payback


# ---------------------------------------------------------------------------
# Section: Market Position (spec §5.8) — Rankable-* with league only
# ---------------------------------------------------------------------------

def _render_market_position(out: Callable[[str], None],
                              inputs: ReportInputs) -> None:
    bm = inputs.peer_benchmarks or {}
    ring1 = bm.get("ring1_local") or {}
    ring2 = bm.get("ring2_catchment") or {}
    ring3 = bm.get("ring3_uk_cohort") or {}

    out("## Market Position")
    out("")

    if not inputs.league_table_eligible:
        # Rankable but not league-eligible: render a compact explainer
        reasons = []
        if inputs.closure_status == "closed_temporarily":
            reasons.append("venue is temporarily closed")
        if any(c.get("code", "").startswith("STALE-")
                for c in inputs.caps_applied):
            reasons.append("stale-inspection cap active")
        if (inputs.confidence_class in {"Rankable-A", "Rankable-B"}
                and not inputs.customer.available):
            reasons.append("no customer-platform evidence")
        out("*League-table placement suppressed while this venue is "
            "excluded from the default league: "
            + (", ".join(reasons) if reasons else "see the Score, "
              "Confidence & Rankability Basis section above")
            + ".*")
        out("")
        return

    def _ring_row(label: str, ring: dict) -> str:
        dims = ring.get("dimensions") or {}
        ov = dims.get("overall") or {}
        rank = ov.get("rank")
        of_ = ov.get("of")
        pct = ov.get("peer_mean")
        top = ov.get("peer_top")
        if rank and of_:
            return (f"| {label} | #{rank} of {of_} | "
                    f"{_fmt_score2(pct)} | {_fmt_score2(top)} |")
        return f"| {label} | — | — | — |"

    out("| Peer ring | Position | Peer avg | Peer top |")
    out("|---|---|---:|---:|")
    out(_ring_row("Local (5 mi)", ring1))
    out(_ring_row("Catchment (15 mi)", ring2))
    out(_ring_row("UK category cohort", ring3))
    out("")
    out("*Peer pool scoped to Rankable-A ∪ Rankable-B where data allows. "
        "Directional-C venues are counted separately.*")
    out("")


# ---------------------------------------------------------------------------
# Section: Competitive Market Intelligence (spec §5.9)
# ---------------------------------------------------------------------------

def _render_competitive_intel(out: Callable[[str], None],
                                inputs: ReportInputs) -> None:
    bm = inputs.peer_benchmarks or {}
    ring1 = bm.get("ring1_local") or {}
    peer_count = ring1.get("peer_count") or 0

    out("## Competitive Market Intelligence")
    out("")

    alerts = []
    if peer_count >= 10:
        alerts.append(
            f"**Competitive density:** {peer_count} direct competitors "
            f"within 5 mi. Differentiation is commercially critical; "
            f"lean on Distinction, Customer Validation top-of-band, and "
            f"Commercial Readiness to stand apart."
        )
    fsa_rating = inputs.venue_record.get("r")
    try:
        fsa_rating_int = int(fsa_rating) if fsa_rating is not None else None
    except (ValueError, TypeError):
        fsa_rating_int = None
    if fsa_rating_int is not None and fsa_rating_int <= 3:
        alerts.append(
            f"**Compliance risk:** FHRS rating {fsa_rating_int} materially "
            f"constrains the Trust & Compliance component and may suppress "
            f"organic Google discovery."
        )
    if (inputs.commercial.score or 0) < 5.0 and inputs.commercial.available:
        alerts.append(
            "**Commercial Readiness gap:** missing customer-path signals "
            "leave recoverable revenue on the table. See the Commercial "
            "Readiness section above."
        )

    if alerts:
        for a in alerts:
            out(f"- {a}")
    else:
        out("No structural competitive-intelligence alerts this month.")
    out("")


# ---------------------------------------------------------------------------
# Section: Management Priorities (spec §5.10)
# ---------------------------------------------------------------------------

def _dimension_to_component(dim: str) -> str:
    """Map legacy V3.4 dimension codes onto V4 component names."""
    mapping = {
        "trust": "Trust & Compliance",
        "experience": "Customer Validation",
        "visibility": "Customer Validation",
        "conversion": "Commercial Readiness",
        "prestige": "Distinction",
    }
    return mapping.get((dim or "").lower(), "Commercial Readiness")


def _render_management_priorities(out: Callable[[str], None],
                                    inputs: ReportInputs) -> None:
    out("## Management Priorities")
    out("")
    recs = inputs.recommendations or {}
    priorities = (recs.get("priority_actions") or [])[:3]

    if inputs.report_mode == MODE_DIRECTIONAL_C:
        # Lead with the unblock-to-rankable action
        unblock = _directional_unblock_action(inputs)
        out(f"### Priority 1 — Unblock to rankable")
        out("")
        out(unblock)
        out("")
        if priorities:
            out("*Additional priorities below are subject to the unblock "
                "above landing first.*")
            out("")

    if not priorities and inputs.report_mode != MODE_DIRECTIONAL_C:
        out("No ranked priorities this month.")
        out("")
        return

    for i, p in enumerate(priorities, start=1):
        title = p.get("title") or "(untitled)"
        dim = p.get("dimension") or ""
        component = _dimension_to_component(dim)
        status = p.get("status") or "new"
        rec_type = (p.get("rec_type") or "").upper() or "ACTION"
        out(f"### Priority {i}: {title} [{rec_type} | {status.upper()}]")
        out("")
        rationale = p.get("rationale") or p.get("detail") or ""
        if rationale:
            out(rationale)
            out("")
        out(f"*Targets component: {component}. V4 components feed the "
            f"headline — this priority is how the score moves in the "
            f"direction observed evidence supports.*")
        out("")


def _directional_unblock_action(inputs: ReportInputs) -> str:
    if inputs.entity_match_status == "ambiguous":
        return ("Disambiguate the FHRS record. Ambiguity caps this venue at "
                "Directional-C regardless of rating or readiness. See the "
                "Score, Confidence & Rankability Basis section for the "
                "conflicting records.")
    if inputs.entity_match_status == "none":
        return ("Resolve the entity match. This venue has neither a confirmed "
                "FHRS record nor a confirmed Google Place ID in the pipeline.")
    if not inputs.customer.available:
        return ("Establish public customer-platform evidence. A single "
                "venue platform profile with at least five reviews moves "
                "this venue out of Directional-C into Rankable-B.")
    # Thin reviews default
    return ("Grow visible review volume on at least one platform above 30. "
            "Current evidence is below the threshold that separates "
            "directional from league-ranked.")


# ---------------------------------------------------------------------------
# Section: Watch List (spec §5.11)
# ---------------------------------------------------------------------------

def _render_watch_list(out: Callable[[str], None],
                         inputs: ReportInputs) -> None:
    out("## Watch List")
    out("")
    recs = inputs.recommendations or {}
    watch = recs.get("watch_items") or []
    if not watch:
        out("No explicit watch items this month. Default monitoring: "
            "FHRS inspection recency, Customer Validation platform counts, "
            "and any new Companies House filings.")
        out("")
        return
    for w in watch[:5]:
        title = w.get("title") or "(untitled)"
        status = w.get("status") or "ongoing"
        out(f"- **{title}** ({status}).")
    out("")


# ---------------------------------------------------------------------------
# Section: What Not to Do This Month (spec §5.12)
# ---------------------------------------------------------------------------

def _render_what_not_to_do(out: Callable[[str], None],
                             inputs: ReportInputs) -> None:
    out("## What Not to Do This Month")
    out("")
    recs = inputs.recommendations or {}
    dont = recs.get("what_not_to_do") or []
    rendered = []
    for d in dont[:3]:
        title = d.get("title") or ""
        if title:
            rendered.append(f"- **Don't prioritise:** {title}.")
    # V4-specific perennial items
    if inputs.customer.available:
        counts = [int(p.get("count") or 0)
                   for p in inputs.customer.platforms.values()]
        max_count = max(counts) if counts else 0
        if max_count and max_count < 400:
            rendered.append(
                "- **Don't chase new reviews purely to lift the score.** "
                "Customer Validation shrinkage dampens the effect until "
                "volume clears the platform's n_cap / 2 threshold."
            )
    rendered.append(
        "- **Don't treat photos, price level, social presence, delivery, "
        "takeaway, parking, or wheelchair access as score levers.** "
        "In V4 they are profile attributes only — changing them does not "
        "move the headline."
    )
    for r in rendered:
        out(r)
    out("")


# ---------------------------------------------------------------------------
# Section: Implementation Framework (spec §5.14)
# ---------------------------------------------------------------------------

def _render_implementation_framework(out: Callable[[str], None],
                                       inputs: ReportInputs) -> None:
    out("## Implementation Framework")
    out("")
    try:
        from operator_intelligence.implementation_framework import (
            generate_action_cards,
        )
        cards = generate_action_cards(inputs.recommendations or {},
                                       inputs.month_str) or []
    except Exception:
        cards = []

    if not cards:
        out("No active action cards this month.")
        out("")
        return

    out("| Action | Targets component | Status | Target date | Cost band | "
        "Expected upside | Next milestone |")
    out("|---|---|---|---|---|---|---|")
    for c in cards[:6]:
        title = c.get("title") or ""
        comp = _dimension_to_component(c.get("dimension") or "")
        status = c.get("status_label") or c.get("status") or "new"
        target = c.get("target_date") or "—"
        cost = c.get("cost_band") or "—"
        upside = c.get("expected_upside") or "—"
        milestone = c.get("next_milestone") or "—"
        out(f"| {title} | {comp} | {status} | {target} | {cost} | "
            f"{upside} | {milestone} |")
    out("")
    out("*Upside claims cite the observable path they depend on; they "
        "do not forecast a specific `rcs_v4_final` movement.*")
    out("")


# ---------------------------------------------------------------------------
# Section: Next-Month Monitoring Plan (spec §5.15)
# ---------------------------------------------------------------------------

def _render_monitoring_plan(out: Callable[[str], None],
                              inputs: ReportInputs) -> None:
    out("## Next-Month Monitoring Plan")
    out("")
    items = []
    if inputs.customer.available:
        platforms = list(inputs.customer.platforms.keys())
        items.append(
            "Track review-count movement on: "
            + ", ".join(p.capitalize() for p in platforms) + "."
        )
    items.append("Monitor FHRS re-inspection activity (check quarterly).")
    if any(c.get("code", "").startswith("STALE-")
             for c in inputs.caps_applied):
        items.append(
            "Priority: FHRS re-inspection would lift an active stale cap "
            "on Trust & Compliance."
        )
    if inputs.entity_ambiguous:
        items.append(
            "Priority: entity disambiguation — an unambiguous match moves "
            "this venue out of Directional-C."
        )
    items.append(
        "Watch confidence-class movement: any shift between "
        "Directional-C ↔ Rankable-B is a material evidence event."
    )
    for i in items:
        out(f"- {i}")
    out("")


# ---------------------------------------------------------------------------
# Section: Executive Summary (spec §5.1)
# ---------------------------------------------------------------------------

def _render_executive_summary(out: Callable[[str], None],
                                inputs: ReportInputs) -> None:
    out("## Executive Summary")
    out("")

    # Lead action(s)
    recs = inputs.recommendations or {}
    priorities = (recs.get("priority_actions") or [])[:3]

    if inputs.report_mode == MODE_DIRECTIONAL_C:
        out("**What you should fix now:**")
        out("")
        out("1. " + _directional_unblock_action(inputs).split(". ")[0] + ".")
        for i, p in enumerate(priorities[:2], start=2):
            title = p.get("title") or ""
            rec_type = (p.get("rec_type") or "ACTION").upper()
            out(f"{i}. **{title}** [{rec_type}]")
        out("")
    elif priorities:
        out("**What you should fix now:**")
        out("")
        for i, p in enumerate(priorities, start=1):
            title = p.get("title") or ""
            rec_type = (p.get("rec_type") or "ACTION").upper()
            detail = p.get("detail") or p.get("rationale") or ""
            tail = f" — {detail[:120]}" if detail else ""
            out(f"{i}. **{title}** [{rec_type}]{tail}")
        out("")

    # Watch
    watch = recs.get("watch_items") or []
    if watch:
        out("**Watch this month:**")
        for w in watch[:2]:
            out(f"- {w.get('title') or ''}")
        out("")

    # Score summary — never first
    if not inputs.suppress_score:
        out(f"**V4 Score:** {_fmt_score(inputs.rcs_v4_final)} / 10 · "
            f"{inputs.confidence_class}.")
    else:
        out(f"**Score:** not published — see Score, Confidence & "
            f"Rankability Basis below.")

    # Component availability summary (replaces V3.4 strongest / weakest)
    avail_bits = []
    for label, c in [("Trust", inputs.trust),
                      ("Customer Validation", inputs.customer),
                      ("Commercial Readiness", inputs.commercial)]:
        if c.available:
            avail_bits.append(f"{label} {_fmt_score2(c.score)}")
        else:
            avail_bits.append(f"{label} unavailable")
    out("**Components:** " + "; ".join(avail_bits) + ".")

    # Any active caps / penalties
    caps = inputs.caps_applied + inputs.penalties_applied
    if caps:
        codes = ", ".join(sorted({p.get("code", "") for p in caps if p.get("code")}))
        out(f"**Active caps / penalties:** {codes}.")

    # Peer position — only if league-eligible
    if inputs.league_table_eligible and inputs.peer_benchmarks:
        ring1 = (inputs.peer_benchmarks.get("ring1_local") or {})
        dims = ring1.get("dimensions") or {}
        ov = dims.get("overall") or {}
        rank = ov.get("rank")
        of_ = ov.get("of")
        if rank and of_:
            out(f"**Local (5 mi) peer position:** #{rank} of {of_} "
                "(peer pool scoped to league-eligible venues).")
    out("")
    out("*External-evidence diagnosis. No POS or internal data required. "
        "See Data Basis below.*")
    out("")


# ---------------------------------------------------------------------------
# Section: Operational & Risk Alerts (spec §5.4)
# ---------------------------------------------------------------------------

def _render_risk_alerts(out: Callable[[str], None],
                          inputs: ReportInputs) -> None:
    out("## Operational & Risk Alerts")
    out("")
    out("> *Legal, safety, or reputational red flags detected in review "
        "text. Narrative only — these do not feed the V4 score (spec §7.1).*")
    out("")
    risk = inputs.risk_result or {}
    alerts = risk.get("alerts") or []
    if not alerts:
        out("No operational or risk alerts above baseline this period.")
        out("")
        return
    for a in alerts[:5]:
        label = a.get("label") or a.get("category") or "alert"
        severity = a.get("severity") or "yellow"
        cnt = a.get("review_count") or 0
        out(f"- **[{severity.upper()}] {label}** — {cnt} review(s) matched.")
    out("")


# ---------------------------------------------------------------------------
# Section: Profile Narrative & Reputation Signals (spec §5.13)
# ---------------------------------------------------------------------------

def _render_profile_narrative(out: Callable[[str], None],
                                inputs: ReportInputs) -> None:
    out("## Profile Narrative & Reputation Signals")
    out("")
    out("> *Narrative only — none of the material below feeds the V4 score. "
        "Review text, aspect themes, segment reads, menu intelligence, and "
        "trajectory notes are profile-only per spec §7.1 / §8.*")
    out("")

    ri = inputs.review_intel or {}
    analysis = ri.get("analysis") or {}
    reviews_analyzed = int(analysis.get("reviews_analyzed") or 0)

    # Confidence tier (review-text based, bounded by V4 class per §8.2)
    tier = _review_tier(inputs, reviews_analyzed)
    out(f"**Review-text confidence tier:** {tier}  "
        f"·  reviews analysed: {reviews_analyzed}.")
    out("")

    if reviews_analyzed == 0:
        out("*No review text is available for narrative analysis this month. "
            "The aggregate public rating (Customer Validation component, "
            "above) is the reputation signal. Review-text narrative will be "
            "possible once review text has been collected for this venue.*")
        out("")
        return

    # What they praise / what they flag — theme-level, not numeric
    praise = analysis.get("praise_themes") or []
    criticism = analysis.get("criticism_themes") or []
    if praise:
        top_praise = [p.get("theme") or p.get("label") or str(p) for p in praise[:4]]
        out("**What guests value (themes):** " + ", ".join(top_praise) + ".")
    if criticism:
        top_crit = [c.get("theme") or c.get("label") or str(c) for c in criticism[:3]]
        out("**What guests flag (themes):** " + ", ".join(top_crit) + ".")
    if praise or criticism:
        out("")

    # Trajectory (requires >= directional tier on both ends)
    rd = inputs.review_delta or {}
    if rd.get("has_delta"):
        new_aspects = rd.get("new_aspects") or []
        fading = rd.get("fading_aspects") or []
        if new_aspects or fading:
            out("**Narrative shifts this month:**")
            if new_aspects:
                out(f"- Emerging themes: {', '.join(new_aspects[:3])}.")
            if fading:
                out(f"- Receding themes: {', '.join(fading[:3])}.")
            out("")

    # Segment intelligence
    seg = inputs.segment_intel or {}
    insights = (seg.get("insights") or {}).get("segment_insights") or {}
    if insights:
        out("**Guest segments**")
        out("")
        for key, s in list(insights.items())[:4]:
            label = s.get("label") or key
            n = s.get("review_count") or 0
            if n < 2:
                continue
            praise_text = s.get("top_praise") or ""
            out(f"- **{label}** ({n} reviews): {praise_text[:160]}.")
        out("")

    # Menu intelligence (if present) — thin wrapper
    menu_intel = inputs.menu_intel or {}
    dish_mentions = menu_intel.get("dish_mentions") or []
    if dish_mentions:
        out("**Menu signals**")
        out("")
        for d in dish_mentions[:5]:
            dish = d.get("dish") or ""
            mentions = d.get("mentions") or 0
            out(f"- {dish} — mentioned in {mentions} review(s).")
        out("")


def _review_tier(inputs: ReportInputs, count: int) -> str:
    """Derive review-text confidence tier (spec §8.2) with V4 class ceiling."""
    if count < 5:
        base = "Anecdotal"
    elif count < 15:
        base = "Indicative"
    elif count < 50:
        base = "Directional"
    else:
        base = "Established"
    # Directional-C / D demote by one tier
    if inputs.report_mode in {MODE_DIRECTIONAL_C, MODE_PROFILE_ONLY_D}:
        demote = {"Established": "Directional",
                   "Directional": "Indicative",
                   "Indicative": "Anecdotal",
                   "Anecdotal": "Anecdotal"}
        base = demote[base]
    return base


# ---------------------------------------------------------------------------
# Section: Data Basis (spec §5.16)
# ---------------------------------------------------------------------------

def _render_data_basis(out: Callable[[str], None],
                         inputs: ReportInputs) -> None:
    out("## Data Basis / Coverage & Confidence")
    out("")
    sfs = inputs.source_family_summary or {}
    platforms = sfs.get("customer_platforms") or []

    out("**Source families present**")
    out("")
    out("| Family | Status | Notes |")
    out("|---|---|---|")
    out(f"| FSA / FHRS | {sfs.get('fsa', 'absent')} | Compliance ground truth. |")
    out(f"| Customer platforms | {', '.join(platforms) or 'none'} | "
        f"Public rating metadata (counts and ratings). |")
    out(f"| Commercial readiness | {sfs.get('commercial', 'absent')} | "
        f"Public customer-path signals. |")
    out(f"| Companies House | {sfs.get('companies_house', 'unmatched')} | "
        f"Business-viability risk (penalty only). |")
    out("")

    ri = inputs.review_intel or {}
    analysis = ri.get("analysis") or {}
    reviews_analyzed = int(analysis.get("reviews_analyzed") or 0)
    out(f"**Review text** — {reviews_analyzed} reviews analysed. "
        "Narrative only; not a score input.")
    out("")

    # Confidence class reminder
    out(f"**Confidence class:** {inputs.confidence_class}. "
        + _rankability_note(inputs))
    out("")


# ---------------------------------------------------------------------------
# Section: Evidence Appendix (spec §5.17)
# ---------------------------------------------------------------------------

def _render_evidence_appendix(out: Callable[[str], None],
                                inputs: ReportInputs) -> None:
    out("## Evidence Appendix")
    out("")
    out("*Factual inventory of the observable data underpinning this report.*")
    out("")
    r = inputs.venue_record
    rows: list[tuple[str, str]] = []
    # FSA
    rows.append(("FHRSID", str(inputs.fhrsid)))
    rows.append(("FSA rating (0–5)", str(r.get("r") or "—")))
    rows.append(("Last inspection date", str(r.get("rd") or "—")))
    # Google
    rows.append(("Google rating", str(r.get("gr") or "—")))
    rows.append(("Google review count", str(r.get("grc") or "—")))
    rows.append(("Google place ID", str(r.get("gpid") or "—")))
    # TripAdvisor
    rows.append(("TripAdvisor rating", str(r.get("ta") or "—")))
    rows.append(("TripAdvisor review count", str(r.get("trc") or "—")))
    rows.append(("TripAdvisor URL", str(r.get("ta_url") or "—")))
    # Commercial
    rows.append(("Website present", str(bool(r.get("web")))))
    rows.append(("Website URL (observed)", str(r.get("web_url") or "—")))
    rows.append(("Phone", str(r.get("phone") or "—")))
    rows.append(("Reservable attribute", str(r.get("reservable") or "—")))
    # Editorial / distinction
    ed = inputs.editorial or {}
    rows.append(("Michelin type", str(ed.get("michelin_type") or "—")))
    rows.append(("AA rosettes", str(ed.get("aa_rosettes") or "—")))

    out("| Field | Value |")
    out("|---|---|")
    for k, v in rows:
        out(f"| {k} | {v} |")
    out("")


# ---------------------------------------------------------------------------
# Mode orchestrators
# ---------------------------------------------------------------------------

def _render_full_report(out: Callable[[str], None],
                          inputs: ReportInputs) -> None:
    """Rankable-A / Rankable-B / temp_closed — full section set."""
    _render_executive_summary(out, inputs)
    _render_financial_impact(out, inputs)
    _render_confidence_basis(out, inputs)
    _render_score_card(out, inputs)
    _render_risk_alerts(out, inputs)
    _render_trust_compliance(out, inputs)
    _render_customer_validation(out, inputs)
    _render_commercial_readiness(out, inputs)
    _render_market_position(out, inputs)
    _render_competitive_intel(out, inputs)
    _render_management_priorities(out, inputs)
    _render_watch_list(out, inputs)
    _render_what_not_to_do(out, inputs)
    _render_profile_narrative(out, inputs)
    _render_implementation_framework(out, inputs)
    _render_monitoring_plan(out, inputs)
    _render_data_basis(out, inputs)
    _render_evidence_appendix(out, inputs)
    _render_decision_trace(out, inputs)


def _render_directional_c_report(out: Callable[[str], None],
                                   inputs: ReportInputs) -> None:
    """Directional-C — peer sections replaced, demoted overall."""
    _render_executive_summary(out, inputs)
    _render_confidence_basis(out, inputs)
    _render_score_card(out, inputs)

    # Replacement for peer sections
    out("## Why this venue isn't league-ranked yet")
    out("")
    reason = _directional_c_reason(inputs)
    out(f"**Reason:** {reason}.")
    out("")
    out(_directional_unblock_action(inputs))
    out("")

    _render_risk_alerts(out, inputs)
    _render_trust_compliance(out, inputs)
    _render_customer_validation(out, inputs)
    _render_commercial_readiness(out, inputs)
    _render_financial_impact(out, inputs)  # renders with Low confidence
    _render_management_priorities(out, inputs)
    _render_profile_narrative(out, inputs)
    _render_implementation_framework(out, inputs)
    _render_data_basis(out, inputs)
    _render_evidence_appendix(out, inputs)
    _render_decision_trace(out, inputs)


def _render_profile_only_d_report(out: Callable[[str], None],
                                    inputs: ReportInputs) -> None:
    """Profile-only-D — profile stub, no score, no peer, no financial."""
    _render_confidence_basis(out, inputs)

    out("## Profile Stub")
    out("")
    out(f"**Name:** {inputs.name}")
    if inputs.fsa_name and inputs.fsa_name != inputs.name:
        out(f"**FSA legal entity:** {inputs.fsa_name}")
    out(f"**Address:** {inputs.address}")
    out(f"**Postcode:** {inputs.postcode}")
    r = inputs.venue_record
    if r.get("r") is not None:
        out(f"**FHRS rating:** {r.get('r')}")
    out("")

    out("## How to unlock full scoring")
    out("")
    unblock = _directional_unblock_action(inputs)
    out(unblock)
    out("")
    out("- Minimum to reach Directional-C: one primary evidence family and "
        "four or more populated signals.")
    out("- Minimum to reach Rankable-B: two primary families, seven or more "
        "populated signals, ten or more combined customer reviews, and a "
        "confirmed or probable entity match.")
    out("")

    _render_data_basis(out, inputs)
    _render_evidence_appendix(out, inputs)


def _render_closed_report(out: Callable[[str], None],
                            inputs: ReportInputs) -> None:
    """Closed — closure notice, no score, no action tracker."""
    out("## Closed — no score published")
    out("")
    out(f"This venue is flagged as permanently closed. No V4 score has been "
        f"published per spec §7.4 (closure evidence blocks the score).")
    out("")
    out("## Closure evidence")
    out("")
    out("| Source | Value |")
    out("|---|---|")
    out(f"| Google business_status | "
        f"{inputs.business_status or '—'} |")
    out(f"| FSA closure flag | {inputs.fsa_closed} |")
    out(f"| Closure status (derived) | {inputs.closure_status or '—'} |")
    out("")

    # Prior-month last known score if available
    prior = inputs.prior_snapshot or {}
    prior_score = ((prior.get("scorecard") or {}).get("overall")
                    or prior.get("rcs_v4_final"))
    if prior_score:
        out(f"*Last observed score before closure: "
            f"{float(prior_score):.3f} / 10. No longer live.*")
        out("")

    _render_evidence_appendix(out, inputs)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_v4_monthly_report(inputs: ReportInputs
                                 ) -> tuple[str, dict]:
    """Generate the V4 operator monthly report. Returns (markdown, qa_dict)."""
    lines: list[str] = []
    out = lines.append
    _render_header(out, inputs)

    if inputs.report_mode == MODE_CLOSED:
        _render_closed_report(out, inputs)
    elif inputs.report_mode == MODE_PROFILE_ONLY_D:
        _render_profile_only_d_report(out, inputs)
    elif inputs.report_mode == MODE_DIRECTIONAL_C:
        _render_directional_c_report(out, inputs)
    else:
        # Rankable-A, Rankable-B, temp_closed
        _render_full_report(out, inputs)

    out("")
    out(f"*Report generated by DayDine V4 Operator Report · "
        f"Engine {inputs.engine_version} · {inputs.month_str}*")

    report_text = "\n".join(lines)
    qa_result = validate_v4_report(report_text, inputs)
    qa_dict = to_qa_dict(qa_result)
    return report_text, qa_dict


def build_v4_report_json(inputs: ReportInputs,
                          report_text: str,
                          qa_dict: dict) -> dict:
    """Structured snapshot for prior-month delta computation."""
    return {
        "engine_version": inputs.engine_version,
        "computed_at": inputs.computed_at,
        "venue": {
            "fhrsid": inputs.fhrsid,
            "name": inputs.name,
            "fsa_name": inputs.fsa_name,
            "postcode": inputs.postcode,
        },
        "month": inputs.month_str,
        "report_mode": inputs.report_mode,
        "confidence_class": inputs.confidence_class,
        "rankable": inputs.rankable,
        "league_table_eligible": inputs.league_table_eligible,
        "entity_match_status": inputs.entity_match_status,
        "rcs_v4_final": inputs.rcs_v4_final,
        "base_score": inputs.base_score,
        "adjusted_score": inputs.adjusted_score,
        "components": {
            "trust_compliance": {
                "score": inputs.trust.score,
                "available": inputs.trust.available,
                "signals_used": inputs.trust.signals_used,
            },
            "customer_validation": {
                "score": inputs.customer.score,
                "available": inputs.customer.available,
                "platforms": inputs.customer.platforms,
            },
            "commercial_readiness": {
                "score": inputs.commercial.score,
                "available": inputs.commercial.available,
                "signals_used": inputs.commercial.signals_used,
            },
        },
        "distinction": {
            "value": inputs.distinction_value,
            "sources": inputs.distinction_sources,
        },
        "penalties_applied": inputs.penalties_applied,
        "caps_applied": inputs.caps_applied,
        "source_family_summary": inputs.source_family_summary,
        "qa": qa_dict,
    }
