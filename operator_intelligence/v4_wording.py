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


def penalty_explanation(code: str) -> str:
    """Short operator-facing explanation for a penalty / cap code."""
    table = {
        "CH-1": "Companies House shows this entity as dissolved; the "
                "score is hard-capped at 3.0 until a new valid entity "
                "is confirmed.",
        "CH-2": "Companies House shows the entity in liquidation or "
                "administration; the score is capped at 5.0.",
        "CH-3": "Statutory accounts are overdue at Companies House; "
                "a small absolute penalty applies.",
        "CH-4": "Three or more director changes in the last 12 months "
                "reduce the score by 8% as a viability-risk signal.",
        "STALE-2Y": "The last FHRS inspection was more than two years "
                    "ago and the rating is 3+; Trust & Compliance is "
                    "soft-capped at 7.0 until a fresh inspection.",
        "STALE-3Y": "The last FHRS inspection was more than three "
                    "years ago; Trust & Compliance is reduced by 15%.",
        "STALE-5Y": "The last FHRS inspection was more than five years "
                    "ago; Trust & Compliance is hard-capped at 5.0 and "
                    "the venue is excluded from the default league "
                    "table.",
    }
    return table.get(code, "")
