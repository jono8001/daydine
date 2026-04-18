"""
operator_intelligence/v4_wording.py — Sanctioned phrase builders.

The V3.4 generator produced strong claims by default. V4 reverses the
polarity: claims start hedged and upgrade only when the evidence
supports it. This module provides the phrase builders the generator
calls, so the tier / class ceiling is enforced at the source rather
than patched up afterwards by the QA layer.

Every helper is a pure string builder. No I/O, no globals beyond the
tier / class tables below. If you need to add a new sanctioned phrase,
add it here rather than inlining it in the generator.

Mapping rules (spec §7, §8):
  * Review-text tier (anecdotal / indicative / directional / established)
    bounds how strongly review-derived claims may be phrased.
  * V4 class demotes the tier by one step for Directional-C and for
    Profile-only-D (spec §8.2).
  * Peer language is gated on `league_table_eligible`.
  * Financial language is gated on confidence label (High / Moderate /
    Low / None).
"""
from __future__ import annotations

from operator_intelligence.v4_adapter import (
    ReportInputs,
    MODE_RANKABLE_A, MODE_RANKABLE_B, MODE_DIRECTIONAL_C,
    MODE_PROFILE_ONLY_D, MODE_CLOSED, MODE_TEMP_CLOSED,
)

# ---------------------------------------------------------------------------
# Review-text tier ceiling (spec §8.2)
# ---------------------------------------------------------------------------

TIER_ORDER = ["Anecdotal", "Indicative", "Directional", "Established"]


def review_tier_from_count(count: int) -> str:
    """Raw review-text tier from count. Class demotion is applied
    separately via `cap_tier_for_class`."""
    if count < 5:
        return "Anecdotal"
    if count < 15:
        return "Indicative"
    if count < 50:
        return "Directional"
    return "Established"


def cap_tier_for_class(tier: str, mode: str) -> str:
    """Apply class-level ceiling to a review-text tier (spec §8.2).

    Directional-C and Profile-only-D demote by one step. Rankable-A /
    Rankable-B / temp_closed pass through unchanged. Closed is rarely
    called in narrative context.
    """
    if mode in {MODE_DIRECTIONAL_C, MODE_PROFILE_ONLY_D}:
        idx = TIER_ORDER.index(tier) if tier in TIER_ORDER else 0
        return TIER_ORDER[max(0, idx - 1)]
    return tier


def effective_review_tier(inputs: ReportInputs, review_count: int) -> str:
    """Convenience: raw tier with class demotion applied."""
    return cap_tier_for_class(
        review_tier_from_count(review_count), inputs.report_mode
    )


# ---------------------------------------------------------------------------
# Review-phrasing builders
# ---------------------------------------------------------------------------

# Max strength of the word that kicks off a review-derived claim. Stronger
# words need stronger tiers (spec §8.4).
_OPENER_BY_TIER = {
    "Anecdotal": "A handful of reviews mention",
    "Indicative": "Recent reviews mention",
    "Directional": "Review evidence is directional:",
    "Established": "Reviews consistently note",
}


def review_opener(tier: str) -> str:
    """Sanctioned opener for a review-derived claim."""
    return _OPENER_BY_TIER.get(tier, _OPENER_BY_TIER["Anecdotal"])


def soften_review_claim(tier: str, claim: str) -> str:
    """Wrap a raw theme / observation with a tier-appropriate opener.

    The generator passes a naked theme string like "service", "value for
    money", "pricing concerns" and gets back a sentence-safe wrapping.
    """
    opener = review_opener(tier)
    return f"{opener} {claim}".rstrip(".")


# "Consistently" / "routinely" / "repeatedly" are Established-tier words.
# "Often" / "frequently" are Directional-tier. Below that we use weaker
# qualifiers. The generator asks for a qualifier and gets a safe one.

_FREQUENCY_BY_TIER = {
    "Anecdotal": "in a handful of reviews",
    "Indicative": "in several reviews",
    "Directional": "often",
    "Established": "consistently",
}


def frequency_qualifier(tier: str) -> str:
    """Return the safest frequency qualifier for the tier."""
    return _FREQUENCY_BY_TIER.get(tier, _FREQUENCY_BY_TIER["Anecdotal"])


# ---------------------------------------------------------------------------
# Class-appropriate peer / position language
# ---------------------------------------------------------------------------

def peer_claim_allowed(inputs: ReportInputs) -> bool:
    """Peer claims require a league-eligible Rankable class and a peer
    benchmarks payload."""
    return (
        inputs.league_table_eligible
        and inputs.report_mode in {MODE_RANKABLE_A, MODE_RANKABLE_B}
        and (inputs.peer_benchmarks or {}).get("ring1_local") is not None
    )


def leadership_language(inputs: ReportInputs) -> str:
    """How strongly may we describe a venue's market position?

    Rankable-A  -> 'well-positioned in the category' is allowed, but we
                   hold back 'category leader' unless explicit evidence
                   supports it (that wording triggers a guardrail
                   warning outside Rankable-A).
    Rankable-B  -> 'performs well locally' is the ceiling.
    anything else -> no leadership claim.
    """
    if inputs.report_mode == MODE_RANKABLE_A:
        return "well-positioned in the category"
    if inputs.report_mode == MODE_RANKABLE_B:
        return "performs well locally"
    return ""


# ---------------------------------------------------------------------------
# Class-appropriate commercial-consequence language
# ---------------------------------------------------------------------------

_COMMERCIAL_MOOD = {
    MODE_RANKABLE_A: "may",
    MODE_RANKABLE_B: "may",
    MODE_DIRECTIONAL_C: "could",
    MODE_PROFILE_ONLY_D: None,
    MODE_CLOSED: None,
    MODE_TEMP_CLOSED: "may",
}


def commercial_mood(inputs: ReportInputs) -> str:
    """Return the modal verb for commercial-consequence sentences.
    Avoids the absolute 'will lose / will recover' phrasing that the
    GUARD_ABSOLUTE_COMMERCIAL_LANGUAGE rule flags."""
    return _COMMERCIAL_MOOD.get(inputs.report_mode) or "could"


# ---------------------------------------------------------------------------
# Financial-impact confidence ladder
# ---------------------------------------------------------------------------

def financial_impact_confidence(inputs: ReportInputs) -> str | None:
    """Derive the High / Moderate / Low / None label for the Financial
    Impact section (spec §6.3).

    Return None means the section must fall back to the §6.4 honest
    fallback wording. Cost band, payback and explicit confidence tag
    become mandatory when this returns non-None.
    """
    if inputs.report_mode in {MODE_PROFILE_ONLY_D, MODE_CLOSED,
                                MODE_TEMP_CLOSED}:
        return None

    cr = inputs.commercial
    cv = inputs.customer
    if not cr.available:
        return None

    r = inputs.venue_record
    web_observed = bool(r.get("web_url"))
    phone_observed = bool(r.get("phone") or r.get("tel"))
    big_plat = any(
        int(p.get("count") or 0) >= 30 for p in cv.platforms.values()
    ) if cv.available else False

    # High: Rankable-A + all three families + observed web AND phone +
    # CR >= 7.0
    if (inputs.report_mode == MODE_RANKABLE_A
            and web_observed and phone_observed
            and (cr.score or 0) >= 7.0):
        return "High"

    # Moderate: Rankable-* + CR >= 6 + (web OR phone observed) + big_plat
    if (inputs.report_mode in {MODE_RANKABLE_A, MODE_RANKABLE_B}
            and (cr.score or 0) >= 6.0
            and (web_observed or phone_observed)
            and big_plat):
        return "Moderate"

    # Anything else that reaches this function is Low
    return "Low"


# ---------------------------------------------------------------------------
# Fallback wording (spec §6.4)
# ---------------------------------------------------------------------------

FINANCIAL_IMPACT_FALLBACK_THIN = (
    "*Financial impact cannot be robustly estimated this month.* "
    "Commercial Readiness evidence is thin — website inferred rather "
    "than observed, and no booking-path signal — which is where most "
    "recoverable revenue shows up in the model. Once booking-path "
    "evidence lands (a published phone number, an observed reservable "
    "attribute, or a linked booking widget) the next report will "
    "include a Moderate-confidence estimate. Recommended action: "
    "publish a reachable phone number."
)

FINANCIAL_IMPACT_FALLBACK_DIRECTIONAL = (
    "*Financial impact is not rendered while this venue is classified "
    "Directional.* The headline score is indicative, not league-ranked, "
    "so any £ figure here would carry the same uncertainty. See "
    "\"Why this venue isn't league-ranked yet\" above for the unblock "
    "path."
)


# ---------------------------------------------------------------------------
# Financial Impact range-width tolerance (spec §6, pilot-hardening pass)
# ---------------------------------------------------------------------------
#
# A £ range with a suspiciously narrow or mechanically wide spread
# signals that the rendered figures aren't anchored in evidence the
# confidence label can support. We check both boundary conditions and
# return a short operator-facing line describing the range's health.
#
# Thresholds (tuned so the current post-calibration CR-driven sizing
# lands squarely in "within-tolerance"):
#
#   High confidence:     ratio 2.0 – 4.0, min-spread £400
#   Moderate confidence: ratio 2.0 – 5.0, min-spread £200
#   Low confidence:      ratio 1.8 – 6.0, min-spread £100
#
# Outside those bounds we emit a tolerance warning. Inside, we emit a
# short confirming line so the reader can see the range was checked.

_FI_TOLERANCE_BOUNDS = {
    "High":     {"ratio_min": 2.0, "ratio_max": 4.0, "min_spread": 400},
    "Moderate": {"ratio_min": 2.0, "ratio_max": 5.0, "min_spread": 200},
    "Low":      {"ratio_min": 1.8, "ratio_max": 6.0, "min_spread": 100},
}


def financial_impact_range_check(low: float, high: float,
                                   confidence: str) -> dict:
    """Check the (low, high) £ range against tolerance bounds for the
    given confidence label. Returns a dict with:

        ok          bool  — within tolerance for the confidence tier
        ratio       float — high / max(low, 1)
        spread      float — high − low
        status      "within" | "narrow" | "wide" | "tiny_spread" | "no_range"
        message     short operator-facing line to render under the table

    Never raises; falls back to a neutral message on unknown confidence
    labels.
    """
    if low is None or high is None or low <= 0:
        return {
            "ok": False,
            "ratio": None,
            "spread": None,
            "status": "no_range",
            "message": "*Range: not available.*",
        }

    spread = high - low
    ratio = high / max(low, 1)
    bounds = _FI_TOLERANCE_BOUNDS.get(confidence) or _FI_TOLERANCE_BOUNDS["Low"]

    if spread < bounds["min_spread"]:
        return {
            "ok": False, "ratio": ratio, "spread": spread,
            "status": "tiny_spread",
            "message": (
                f"*Range width £{int(spread)} (ratio {ratio:.1f}×) — "
                f"narrower than the evidence typically supports at "
                f"**{confidence}** confidence. Treat as illustrative "
                f"only; the narrow band is a rendering artefact, not "
                f"a claim of precision.*"
            ),
        }
    if ratio < bounds["ratio_min"]:
        return {
            "ok": False, "ratio": ratio, "spread": spread,
            "status": "narrow",
            "message": (
                f"*Range ratio {ratio:.1f}× — narrower than typical "
                f"for **{confidence}** confidence. The figures cluster "
                f"tightly because only one or two CR sub-signals drive "
                f"the estimate; a wider range would more honestly "
                f"reflect the uncertainty.*"
            ),
        }
    if ratio > bounds["ratio_max"]:
        return {
            "ok": False, "ratio": ratio, "spread": spread,
            "status": "wide",
            "message": (
                f"*Range ratio {ratio:.1f}× — wider than typical for "
                f"**{confidence}** confidence. Multiple weakly-"
                f"anchored inputs stacked up; the midpoint is not a "
                f"reliable centre. Use the low end as a conservative "
                f"floor and the high end as a ceiling.*"
            ),
        }
    return {
        "ok": True, "ratio": ratio, "spread": spread,
        "status": "within",
        "message": (
            f"*Range ratio {ratio:.1f}× and spread £{int(spread)} — "
            f"within the expected band for **{confidence}** confidence. "
            f"The figures are directional; internal cover and spend "
            f"data would tighten them.*"
        ),
    }


# ---------------------------------------------------------------------------
# Compact decision-trace summary helpers (spec §9)
# ---------------------------------------------------------------------------

def one_line_score_summary(inputs: ReportInputs) -> str:
    """A one-line, operator-facing summary of how the score was formed.

    Intended to sit above the full decision trace block. Much more
    compact than dumping the engine's trace lines.
    """
    if inputs.rcs_v4_final is None:
        return ""
    parts: list[str] = []
    if inputs.trust.available:
        parts.append(f"Trust {inputs.trust.score:.2f}")
    if inputs.customer.available:
        parts.append(f"Customer {inputs.customer.score:.2f}")
    if inputs.commercial.available:
        parts.append(f"Commercial {inputs.commercial.score:.2f}")
    mods = []
    if inputs.distinction_value and inputs.distinction_value > 0:
        mods.append(f"+{inputs.distinction_value:.2f} distinction")
    caps = [c.get("code") for c in inputs.caps_applied]
    pens = [p.get("code") for p in inputs.penalties_applied]
    if caps:
        mods.append(f"caps: {', '.join(caps)}")
    if pens:
        mods.append(f"penalties: {', '.join(pens)}")
    tail = "; ".join(mods)
    core = " + ".join(parts)
    if tail:
        return f"**Formed from:** {core}. {tail}. Final: {inputs.rcs_v4_final:.3f}."
    return f"**Formed from:** {core}. Final: {inputs.rcs_v4_final:.3f}."


# ---------------------------------------------------------------------------
# Penalty / cap registry (spec §7 / §9)
# ---------------------------------------------------------------------------
#
# Single source of truth for operator-facing explanations of every code
# the V4 scoring engine emits in `penalties_applied` or `caps_applied`.
# Each entry carries:
#
#   kind           "cap" | "penalty"
#   severity       "blocking" | "high" | "medium" | "low"
#                  Used for colouring / ordering in the decision trace
#                  and to prioritise a matched rec in the recommendations
#                  engine.
#   targets_component  The V4 component primarily affected. Report
#                  sections that render a penalty row next to a
#                  component card can filter by this.
#   short          One-sentence operator-facing headline. Safe to render
#                  inside narrow table cells.
#   long           Longer operator-facing explanation. Used by the
#                  "How the Score Was Formed" section and the
#                  Trust & Compliance / CR diagnostic blocks.
#
# Any code the engine emits MUST have an entry here. If an unknown code
# appears at render time, `penalty_explanation()` returns a structured
# fallback that names the code and points the reader at the decision
# trace — never a silent empty cell.
#
# Adding a new code: add the entry here; the guardrail test
# `test_penalty_registry_covers_all_engine_codes` (to be added with the
# next engine change) enforces parity.

PENALTY_REGISTRY = {
    # Companies House (penalty-only tier, spec §7.2)
    "CH-1": {
        "kind": "cap",
        "severity": "blocking",
        "targets_component": "Trust & Compliance",
        "short": "Companies House shows this entity as dissolved; score "
                 "hard-capped at 3.0.",
        "long":  "Companies House shows this entity as dissolved; the "
                 "score is hard-capped at 3.0 until a new valid entity "
                 "is confirmed.",
    },
    "CH-2": {
        "kind": "cap",
        "severity": "high",
        "targets_component": "Trust & Compliance",
        "short": "Companies House shows the entity in liquidation or "
                 "administration; score capped at 5.0.",
        "long":  "Companies House shows the entity in liquidation or "
                 "administration; the score is capped at 5.0 until the "
                 "status clears.",
    },
    "CH-3": {
        "kind": "penalty",
        "severity": "medium",
        "targets_component": "Trust & Compliance",
        "short": "Statutory accounts are overdue at Companies House; "
                 "a small absolute penalty applies.",
        "long":  "Statutory accounts are overdue at Companies House "
                 "beyond the 90-day threshold; a -0.30 absolute "
                 "penalty applies to the headline until accounts file.",
    },
    "CH-4": {
        "kind": "penalty",
        "severity": "low",
        "targets_component": "Trust & Compliance",
        "short": "Three or more director changes in the last 12 months "
                 "reduce the score by 8%.",
        "long":  "Three or more director changes in the trailing 12 "
                 "months trigger a 0.92 multiplier on the adjusted "
                 "score, treated as a viability-risk signal.",
    },
    # Stale inspection (spec §7.3)
    "STALE-2Y": {
        "kind": "cap",
        "severity": "medium",
        "targets_component": "Trust & Compliance",
        "short": "Last FHRS inspection >2 years ago with rating ≥3; "
                 "Trust soft-capped at 7.0.",
        "long":  "The last FHRS inspection was more than two years ago "
                 "and the rating is 3 or higher; Trust & Compliance is "
                 "soft-capped at 7.0 until a fresh inspection lands.",
    },
    "STALE-3Y": {
        "kind": "cap",
        "severity": "high",
        "targets_component": "Trust & Compliance",
        "short": "Last FHRS inspection >3 years ago; Trust reduced by 15%.",
        "long":  "The last FHRS inspection was more than three years "
                 "ago; Trust & Compliance is reduced by 15% until a "
                 "fresh inspection lands.",
    },
    "STALE-5Y": {
        "kind": "cap",
        "severity": "blocking",
        "targets_component": "Trust & Compliance",
        "short": "Last FHRS inspection >5 years ago; Trust hard-capped "
                 "at 5.0 and venue excluded from league tables.",
        "long":  "The last FHRS inspection was more than five years "
                 "ago; Trust & Compliance is hard-capped at 5.0 and "
                 "the venue is excluded from the default league table "
                 "until a fresh inspection lands.",
    },
}


def penalty_entry(code: str) -> dict:
    """Structured registry lookup. Returns the full entry for `code`,
    or a `kind=unknown` placeholder when the code is not registered.

    The placeholder is deliberately informative: it names the code and
    points the reader at the decision trace so the report never
    silently drops a penalty."""
    if code in PENALTY_REGISTRY:
        return dict(PENALTY_REGISTRY[code])
    return {
        "kind": "unknown",
        "severity": "medium",
        "targets_component": None,
        "short": (f"Penalty / cap code `{code}` applied — see the "
                  "decision trace for the effect and reason."),
        "long":  (f"The scoring engine emitted penalty / cap code "
                  f"`{code}`. No operator-facing explanation is "
                  "registered for this code in `v4_wording.PENALTY_"
                  "REGISTRY`. The decision-trace block below preserves "
                  "the raw effect and reason as emitted by the engine."),
    }


def penalty_explanation(code: str) -> str:
    """Backwards-compatible: returns the short explanation string.

    Existing consumers (decision-trace table, action-card builder)
    continue to work unchanged. New consumers that need severity /
    targets_component / long form should call `penalty_entry` directly.
    """
    return penalty_entry(code).get("short") or ""
