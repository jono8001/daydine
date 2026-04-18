"""
operator_intelligence/v4_recommendations.py — V4-native recommendation engine.

Generates the recommendations payload the V4 report renderers consume:
`{priority_actions, watch_items, what_not_to_do, all_recs}`.

Replaces the V3.4 path (`operator_intelligence/recommendations.py` +
`generate_action_cards`) for V4 reports. Inputs are V4-only — the
generator reads the V4 components, confidence class, rankability,
penalties / caps, entity match, and Commercial Readiness sub-signals
from `ReportInputs`. It does not consume review text, sentiment,
aspect scores, AI summaries, photo count, price level, or any signal
the V4 spec marks as profile-only.

Output schema (per recommendation):
    rec_type           "fix" | "exploit" | "protect" | "watch" | "ignore"
    targets_component  V4 component name ("Trust & Compliance" /
                       "Customer Validation" / "Commercial Readiness" /
                       "Distinction" / "Entity / Identity")
    title              short imperative title
    rationale          one-sentence why
    evidence           list of evidence anchors (each maps to a V4 field
                       or penalty/cap code)
    priority_score     int 0-100 (higher = sooner)
    cost_band          "zero" | "low" | "medium" | "high"
    payback            "< 1 month" | "1-3 months" | "3-6 months" | "6-12 months"
    expected_upside    component-language only ("lifts Commercial
                       Readiness when phone publishes"); never an
                       rcs_v4_final movement number.
    status             "new" | "ongoing" | "stale" | "chronic" (V3.4
                       lifecycle support; new is default)
    times_seen         int (1 by default)

This generator does not emit a V3.4-shaped `dimension` field. The V4
renderer and the V4 action-card builder both read `targets_component`
directly. If a legacy consumer needs the V3.4 dimension label, it
should do the mapping at the consumption boundary — not here.
"""
from __future__ import annotations

from typing import Iterable, Optional

from operator_intelligence.v4_adapter import (
    ReportInputs,
    MODE_RANKABLE_A, MODE_RANKABLE_B, MODE_DIRECTIONAL_C,
    MODE_PROFILE_ONLY_D, MODE_CLOSED, MODE_TEMP_CLOSED,
)


def _rec(rec_type: str, component: str, title: str, rationale: str,
          evidence: list[str], priority: int, cost_band: str,
          payback: str, expected_upside: str) -> dict:
    return {
        "rec_type": rec_type,
        "targets_component": component,
        "title": title,
        "rationale": rationale,
        "evidence": list(evidence),
        "priority_score": int(priority),
        "cost_band": cost_band,
        "payback": payback,
        "expected_upside": expected_upside,
        "status": "new",
        "times_seen": 1,
    }


# ---------------------------------------------------------------------------
# Helpers — Commercial Readiness sub-signal inspection
# ---------------------------------------------------------------------------

def _cr_signals(inputs: ReportInputs) -> dict:
    r = inputs.venue_record
    menu = inputs.menu_record or {}
    goh = r.get("goh") or []
    days_with_hours = sum(
        1 for line in goh if isinstance(line, str) and ":" in line
        and line.split(":", 1)[1].strip()
    )
    return {
        "website": bool(r.get("web")),
        "website_observed": bool(r.get("web_url")),
        "menu_online": bool(menu.get("has_menu_online")
                              or r.get("has_menu_online")),
        "hours_days": days_with_hours,
        "phone": bool(r.get("phone") or r.get("tel")),
        "booking_url": bool(r.get("booking_url") or r.get("reservation_url")),
        "reservable": bool(r.get("reservable")),
    }


def _has_cap(inputs: ReportInputs, code_prefix: str) -> bool:
    return any(c.get("code", "").startswith(code_prefix)
                for c in inputs.caps_applied)


def _has_penalty(inputs: ReportInputs, code_prefix: str) -> bool:
    return any(p.get("code", "").startswith(code_prefix)
                for p in inputs.penalties_applied)


# ---------------------------------------------------------------------------
# Priority / consequence builders, by V4 component
# ---------------------------------------------------------------------------

def _trust_recs(inputs: ReportInputs) -> list[dict]:
    out: list[dict] = []
    r = inputs.venue_record
    fhrs = r.get("r")
    try:
        fhrs_int = int(fhrs) if fhrs is not None else None
    except (TypeError, ValueError):
        fhrs_int = None

    # FHRS rating-driven actions
    if fhrs_int is not None:
        if fhrs_int <= 1:
            out.append(_rec(
                "fix", "Trust & Compliance",
                "Address the food hygiene rating",
                "FHRS rating ≤ 1 hard-caps the V4 score at 2.0 and is the "
                "single most material score-mover for this venue.",
                evidence=[f"FHRS rating: {fhrs_int}",
                          "Cap P1 (hard cap 2.0) active"],
                priority=98, cost_band="medium",
                payback="3-6 months",
                expected_upside="lifts Trust & Compliance and removes the "
                                "hard cap on the headline once the next "
                                "inspection lands.",
            ))
        elif fhrs_int == 2:
            out.append(_rec(
                "fix", "Trust & Compliance",
                "Address the food hygiene rating",
                "FHRS rating 2 hard-caps the V4 score at 4.0.",
                evidence=[f"FHRS rating: {fhrs_int}",
                          "Cap P2 (hard cap 4.0) active"],
                priority=92, cost_band="medium",
                payback="3-6 months",
                expected_upside="lifts Trust & Compliance and removes the "
                                "P2 cap once the next inspection lands.",
            ))
        elif fhrs_int == 3:
            out.append(_rec(
                "watch", "Trust & Compliance",
                "Plan FHRS rating uplift to 4 or 5",
                "FHRS rating 3 caps the achievable Trust & Compliance "
                "ceiling and limits headline-score upside.",
                evidence=[f"FHRS rating: {fhrs_int}"],
                priority=45, cost_band="medium",
                payback="6-12 months",
                expected_upside="lifts Trust & Compliance ceiling.",
            ))

    # Stale-inspection caps
    if _has_cap(inputs, "STALE-2Y"):
        out.append(_rec(
            "fix", "Trust & Compliance",
            "Request an FHRS re-inspection",
            "Last FHRS inspection was over two years ago; the V4 engine "
            "has soft-capped Trust & Compliance at 7.0.",
            evidence=[f"Last inspection: {r.get('rd', '—')}",
                      "Cap STALE-2Y active"],
            priority=72, cost_band="low",
            payback="3-6 months",
            expected_upside="removes the STALE-2Y soft cap once a fresh "
                            "inspection lands.",
        ))
    if _has_cap(inputs, "STALE-3Y"):
        out.append(_rec(
            "fix", "Trust & Compliance",
            "FHRS re-inspection is overdue",
            "Last FHRS inspection was over three years ago; Trust is "
            "currently reduced by 15% of its pre-cap value.",
            evidence=[f"Last inspection: {r.get('rd', '—')}",
                      "Cap STALE-3Y multiplier active"],
            priority=82, cost_band="low",
            payback="3-6 months",
            expected_upside="restores the 15% Trust reduction once a "
                            "fresh inspection lands.",
        ))
    if _has_cap(inputs, "STALE-5Y"):
        out.append(_rec(
            "fix", "Trust & Compliance",
            "Trigger an FHRS re-inspection — venue is league-excluded",
            "Last FHRS inspection was over five years ago; Trust is hard-"
            "capped at 5.0 and the venue is excluded from default league "
            "tables until inspection refreshes.",
            evidence=[f"Last inspection: {r.get('rd', '—')}",
                      "Cap STALE-5Y hard cap + league exclusion"],
            priority=95, cost_band="low",
            payback="6-12 months",
            expected_upside="restores Trust & Compliance ceiling and "
                            "league eligibility once a fresh inspection "
                            "lands.",
        ))

    # Companies House
    if _has_cap(inputs, "CH-1"):
        out.append(_rec(
            "fix", "Trust & Compliance",
            "Resolve the Companies House dissolution",
            "The registered company is dissolved; the V4 engine has "
            "hard-capped the score at 3.0 until a valid trading entity is "
            "confirmed.",
            evidence=["Cap CH-1 (dissolved) active"],
            priority=97, cost_band="high",
            payback="6-12 months",
            expected_upside="removes the CH-1 cap once a valid entity is "
                            "confirmed.",
        ))
    if _has_cap(inputs, "CH-2"):
        out.append(_rec(
            "fix", "Trust & Compliance",
            "Resolve the Companies House liquidation/administration status",
            "The company is in liquidation or administration; the V4 "
            "engine has capped the score at 5.0.",
            evidence=["Cap CH-2 active"],
            priority=90, cost_band="high",
            payback="6-12 months",
            expected_upside="removes the CH-2 cap once status clears.",
        ))
    if _has_penalty(inputs, "CH-3"):
        out.append(_rec(
            "fix", "Trust & Compliance",
            "File overdue statutory accounts",
            "Companies House accounts are overdue; the V4 engine has "
            "deducted -0.30 absolute from the headline.",
            evidence=["Penalty CH-3 (-0.30 absolute) active"],
            priority=70, cost_band="low",
            payback="< 1 month",
            expected_upside="restores the 0.30 absolute deduction once "
                            "accounts file.",
        ))
    if _has_penalty(inputs, "CH-4"):
        out.append(_rec(
            "watch", "Trust & Compliance",
            "Stabilise director changes",
            "Three or more director changes in the trailing 12 months "
            "trigger an 8% multiplier on the score.",
            evidence=["Penalty CH-4 (×0.92 multiplier) active"],
            priority=40, cost_band="medium",
            payback="6-12 months",
            expected_upside="restores the 8% multiplier once director "
                            "churn falls below the threshold.",
        ))
    return out


def _customer_recs(inputs: ReportInputs) -> list[dict]:
    out: list[dict] = []
    cv = inputs.customer

    if not cv.available:
        out.append(_rec(
            "fix", "Customer Validation",
            "Establish public customer-platform evidence",
            "No customer-platform evidence is observable for this venue. "
            "One Google or TripAdvisor profile with five or more reviews "
            "moves the venue out of insufficient-evidence territory.",
            evidence=["Customer Validation component: unavailable"],
            priority=88, cost_band="low",
            payback="1-3 months",
            expected_upside="enables the Customer Validation component "
                            "and lifts the achievable confidence class.",
        ))
        return out

    counts = [(name, int(p.get("count") or 0))
               for name, p in cv.platforms.items()]
    counts.sort(key=lambda x: -x[1])
    top_name, top_count = counts[0]
    platform_count = len(counts)

    # Single-platform → recommend a second
    if platform_count == 1:
        out.append(_rec(
            "fix", "Customer Validation",
            "Add a second customer-platform listing",
            "Customer Validation is currently single-platform; spec §4.4 "
            "caps the venue at Rankable-B regardless of score until a "
            "second platform is present.",
            evidence=[f"Only platform present: {top_name}"],
            priority=78, cost_band="low",
            payback="1-3 months",
            expected_upside="raises the achievable confidence class to "
                            "Rankable-A.",
        ))

    # Any platform with N<5 with no other platform N>=30
    big_other = any(c >= 30 for _, c in counts)
    thin_platforms = [(n, c) for n, c in counts if c < 5]
    if thin_platforms and not big_other:
        names = ", ".join(n for n, _ in thin_platforms)
        out.append(_rec(
            "fix", "Customer Validation",
            f"Grow review volume above 5 on {names}",
            "Spec §4.5 caps any venue with a platform under 5 reviews "
            "at Directional-C unless another platform has at least 30 "
            "reviews.",
            evidence=[f"Thin platforms: {names}"],
            priority=68, cost_band="low",
            payback="1-3 months",
            expected_upside="lifts the venue out of Directional-C if "
                            "thin-platform cap is the only blocker.",
        ))

    # Below n_cap on the top platform → watch
    if top_count < 30:
        out.append(_rec(
            "watch", "Customer Validation",
            f"Continue growing visible review volume on {top_name}",
            "The top customer platform is below the threshold where "
            "shrinkage stops dominating the shrunk rating.",
            evidence=[f"Top platform count: {top_name} ({top_count})"],
            priority=35, cost_band="zero",
            payback="3-6 months",
            expected_upside="reduces shrinkage pull on Customer Validation.",
        ))
    return out


def _commercial_recs(inputs: ReportInputs) -> list[dict]:
    out: list[dict] = []
    cr = inputs.commercial
    if not cr.available:
        out.append(_rec(
            "fix", "Commercial Readiness",
            "Establish a public customer-path footprint",
            "No Commercial Readiness evidence is observable — no Google "
            "place record, no menu data, no website signal.",
            evidence=["Commercial Readiness component: unavailable"],
            priority=80, cost_band="medium",
            payback="1-3 months",
            expected_upside="enables the Commercial Readiness component.",
        ))
        return out

    sigs = _cr_signals(inputs)

    # Booking / contact path is the highest-leverage CR sub-signal because
    # it carries 25% of the component weight and is the most-often
    # missing signal in the pipeline today.
    if not (sigs["phone"] or sigs["booking_url"] or sigs["reservable"]):
        out.append(_rec(
            "fix", "Commercial Readiness",
            "Publish a reachable phone number or booking link",
            "The booking / contact path sub-signal carries 25% of the "
            "Commercial Readiness component weight and is currently "
            "absent.",
            evidence=["No phone / reservation_url / reservable observed"],
            priority=66, cost_band="low",
            payback="< 1 month",
            expected_upside="adds 25% of the Commercial Readiness "
                            "component once a contact path publishes.",
        ))

    if not sigs["website"]:
        out.append(_rec(
            "fix", "Commercial Readiness",
            "Publish a venue website",
            "The website-present sub-signal carries 25% of the Commercial "
            "Readiness component weight and is currently absent.",
            evidence=["web=False"],
            priority=58, cost_band="low",
            payback="1-3 months",
            expected_upside="adds 25% of the Commercial Readiness "
                            "component.",
        ))

    if not sigs["menu_online"]:
        out.append(_rec(
            "fix", "Commercial Readiness",
            "Publish the menu online",
            "The menu-online sub-signal carries 25% of the Commercial "
            "Readiness component weight and is currently absent.",
            evidence=["has_menu_online=False"],
            priority=55, cost_band="zero",
            payback="< 1 month",
            expected_upside="adds 25% of the Commercial Readiness "
                            "component.",
        ))

    if sigs["hours_days"] < 7:
        out.append(_rec(
            "fix", "Commercial Readiness",
            "Complete Google opening hours for all 7 days",
            "Opening-hours completeness is currently "
            f"{sigs['hours_days']}/7; the sub-signal carries 25% of the "
            "Commercial Readiness component.",
            evidence=[f"Days with hours: {sigs['hours_days']}/7"],
            priority=50, cost_band="zero",
            payback="< 1 month",
            expected_upside="lifts opening-hours completeness toward "
                            "the 25% sub-signal ceiling.",
        ))
    return out


def _distinction_recs(inputs: ReportInputs) -> list[dict]:
    out: list[dict] = []
    if inputs.distinction_value > 0:
        out.append(_rec(
            "protect", "Distinction",
            "Maintain editorial recognition currency",
            "An editorial distinction is in force; ensure the listing "
            "remains current to preserve the modifier.",
            evidence=[f"Distinction sources: "
                      f"{', '.join(inputs.distinction_sources)}"],
            priority=30, cost_band="low",
            payback="ongoing",
            expected_upside="preserves the active distinction modifier "
                            "(currently +%.2f)."
                              % inputs.distinction_value,
        ))
    return out


def _entity_recs(inputs: ReportInputs) -> list[dict]:
    out: list[dict] = []
    if inputs.entity_match_status == "ambiguous":
        out.append(_rec(
            "fix", "Entity / Identity",
            "Disambiguate the FHRS entity",
            "The FHRS record shares identifiers with other records; "
            "spec §8.4 caps the venue at Directional-C until "
            "disambiguated.",
            evidence=["entity_match_status: ambiguous",
                      "entity_ambiguous flag set"],
            priority=85, cost_band="low",
            payback="< 1 month",
            expected_upside="raises the achievable confidence class to "
                            "Rankable-B.",
        ))
    elif inputs.entity_match_status == "none":
        out.append(_rec(
            "fix", "Entity / Identity",
            "Resolve the entity match",
            "Neither a confirmed FHRS record nor a confirmed Google "
            "Place ID is in the pipeline.",
            evidence=["entity_match_status: none"],
            priority=99, cost_band="medium",
            payback="1-3 months",
            expected_upside="enables a published score.",
        ))
    elif inputs.entity_match_status == "probable":
        out.append(_rec(
            "watch", "Entity / Identity",
            "Confirm the FHRS / Google identifier match",
            "The entity match is probable rather than confirmed; "
            "raising it to confirmed strengthens audit confidence.",
            evidence=["entity_match_status: probable"],
            priority=20, cost_band="low",
            payback="< 1 month",
            expected_upside="strengthens entity confidence.",
        ))
    return out


def _watch_recs(inputs: ReportInputs) -> list[dict]:
    """Lower-leverage items that don't merit a top-priority FIX."""
    out: list[dict] = []

    # Trust mid-band watch
    if inputs.trust.available and 6.0 < (inputs.trust.score or 0) < 7.5:
        out.append(_rec(
            "watch", "Trust & Compliance",
            "Watch Trust & Compliance for slide",
            "Trust component is mid-band; small inspection or CH-data "
            "movements could push it below 6.0 and trigger a band shift.",
            evidence=[f"Trust score: {inputs.trust.score:.2f}"],
            priority=25, cost_band="zero",
            payback="ongoing",
            expected_upside="early-warning detection if Trust drops.",
        ))

    # CR mid-band watch
    if inputs.commercial.available and 5.0 < (inputs.commercial.score or 0) < 7.5:
        out.append(_rec(
            "watch", "Commercial Readiness",
            "Watch Commercial Readiness for sub-signal regression",
            "Commercial Readiness is mid-band; sub-signals like opening "
            "hours can degrade silently if the GBP profile is not "
            "reviewed monthly.",
            evidence=[f"CR score: {inputs.commercial.score:.2f}"],
            priority=22, cost_band="zero",
            payback="ongoing",
            expected_upside="early-warning detection if CR drops.",
        ))
    return out


def _what_not_to_do_perennials(inputs: ReportInputs) -> list[dict]:
    """V4-perennial items teaching the operator which V3-era levers
    no longer move the score."""
    out: list[dict] = []
    out.append(_rec(
        "ignore", "Customer Validation",
        "Don't chase reviews purely to lift the score",
        "Customer Validation Bayesian shrinkage dampens the per-review "
        "effect on the shrunk rating until volume clears the platform "
        "n_cap / 2 threshold; review-volume growth is a long-game watch "
        "item, not a fix.",
        evidence=["Spec §4.2 Bayesian shrinkage"],
        priority=12, cost_band="zero",
        payback="—",
        expected_upside="—",
    ))
    out.append(_rec(
        "ignore", "Customer Validation",
        "Don't treat photos, price level, social, delivery, takeaway, "
        "parking, or wheelchair access as score levers",
        "These are profile attributes only in V4; changing them does "
        "not move the headline.",
        evidence=["Spec §2.3 forbidden score drivers"],
        priority=10, cost_band="zero",
        payback="—",
        expected_upside="—",
    ))
    return out


# ---------------------------------------------------------------------------
# Per-class generation
# ---------------------------------------------------------------------------

def _generate_for_full_report(inputs: ReportInputs) -> list[dict]:
    """Rankable-A / Rankable-B / temp_closed."""
    out: list[dict] = []
    out.extend(_trust_recs(inputs))
    out.extend(_customer_recs(inputs))
    out.extend(_commercial_recs(inputs))
    out.extend(_distinction_recs(inputs))
    out.extend(_entity_recs(inputs))
    return out


def _generate_for_directional_c(inputs: ReportInputs) -> list[dict]:
    """Directional-C — entity / unblock action leads, others follow."""
    out: list[dict] = []
    # Unblock-to-rankable always tops the list. _entity_recs already
    # produces the right shape for ambiguous / none / probable.
    out.extend(_entity_recs(inputs))
    out.extend(_customer_recs(inputs))
    out.extend(_trust_recs(inputs))
    out.extend(_commercial_recs(inputs))
    out.extend(_distinction_recs(inputs))
    return out


def _generate_for_temp_closed(inputs: ReportInputs) -> list[dict]:
    """Temp-closed — focus is reopening preparedness."""
    out: list[dict] = []
    out.append(_rec(
        "fix", "Commercial Readiness",
        "Maintain accurate temporary-closure messaging",
        "While `business_status = CLOSED_TEMPORARILY` is set, ensure "
        "the public profile communicates the closure window and any "
        "expected reopening date so customers do not arrive to a "
        "closed venue.",
        evidence=["business_status: CLOSED_TEMPORARILY"],
        priority=82, cost_band="zero",
        payback="< 1 month",
        expected_upside="prevents reputation damage from confused "
                        "arrivals.",
    ))
    # Then standard CR / Trust priorities for when reopening lands
    out.extend(_trust_recs(inputs))
    out.extend(_commercial_recs(inputs))
    out.extend(_entity_recs(inputs))
    return out


def _select_priority_actions(all_recs: list[dict],
                              inputs: ReportInputs) -> list[dict]:
    """Top-3 actionable recs (FIX / EXPLOIT / PROTECT only)."""
    actionable = [r for r in all_recs
                   if r["rec_type"] in {"fix", "exploit", "protect"}]
    actionable.sort(key=lambda r: -r["priority_score"])
    # For Directional-C the top must be the unblock action — already
    # naturally happens because entity / unblock recs carry priority 85+
    return actionable[:3]


def _select_watch_items(all_recs: list[dict]) -> list[dict]:
    """Top-3 watch items."""
    watches = [r for r in all_recs if r["rec_type"] == "watch"]
    watches.sort(key=lambda r: -r["priority_score"])
    return watches[:3]


def _select_what_not_to_do(all_recs: list[dict]) -> list[dict]:
    """All ignore-type items (the V4 perennials)."""
    return [r for r in all_recs if r["rec_type"] == "ignore"]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_v4_recommendations(inputs: ReportInputs, *,
                                  history_root: Optional[str] = None,
                                  disable_history: bool = False) -> dict:
    """Build the recommendations payload the V4 renderers consume.

    Returns `{priority_actions, watch_items, what_not_to_do, all_recs}`.
    Suppressed (empty payload) for Profile-only-D and Closed.

    History persistence (spec follow-up, closes the main pilot warning):
    actionable candidates (fix / exploit / protect / watch) are merged
    against `history/v4_recommendations/<fhrsid>.json` before the
    priority selection, so `status` and `times_seen` reflect continuity
    across runs. See `v4_recommendations_history.apply_history` for
    the identity / lifecycle rules. `ignore`-type perennials are not
    persisted.

    Args:
      history_root: override the default history storage root.
      disable_history: read/write nothing to disk and return
        decorated candidates as if this were a first-ever run. Used by
        the reproducibility-sensitive sample runner and by tests.
    """
    if inputs.report_mode in {MODE_PROFILE_ONLY_D, MODE_CLOSED}:
        return {
            "priority_actions": [],
            "watch_items": [],
            "what_not_to_do": [],
            "all_recs": [],
        }

    if inputs.report_mode == MODE_DIRECTIONAL_C:
        candidates = _generate_for_directional_c(inputs)
    elif inputs.report_mode == MODE_TEMP_CLOSED:
        candidates = _generate_for_temp_closed(inputs)
    else:
        candidates = _generate_for_full_report(inputs)

    # Always add watch + what-not-to-do perennials
    candidates.extend(_watch_recs(inputs))
    candidates.extend(_what_not_to_do_perennials(inputs))

    # Merge with history before selection, so the priority actions
    # / watch items / implementation framework cards carry stable
    # first_seen / times_seen / status values.
    from operator_intelligence.v4_recommendations_history import (
        generate_and_persist,
    )
    generate_and_persist(
        candidates,
        venue_id=inputs.fhrsid,
        month_str=inputs.month_str,
        report_mode=inputs.report_mode,
        history_root=history_root,
        disable_persistence=disable_history,
    )

    return {
        "priority_actions": _select_priority_actions(candidates, inputs),
        "watch_items": _select_watch_items(candidates),
        "what_not_to_do": _select_what_not_to_do(candidates),
        "all_recs": candidates,
    }
