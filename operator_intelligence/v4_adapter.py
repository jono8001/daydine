"""
operator_intelligence/v4_adapter.py — V4 Report data-model adapter.

Builds a stable `ReportInputs` dataclass from:
  - a V4 scoring payload (`rcs_scoring_v4.V4Score.to_dict()` shape)
  - the raw venue record (from stratford_establishments.json)
  - optional side inputs (menu, editorial, review intel, peer benchmarks,
    prior-month snapshot, recommendations, risk-detection result,
    entity-resolution report)

Guardrails (per docs/DayDine-V4-Report-Spec.md §2.3 / §10):
  * Refuses to construct if any forbidden-score-driver field is present on
    the venue record's score-driving surface. Narrative fields (g_reviews,
    ta_reviews) are allowed and kept on the `narrative` sub-block so every
    builder sees them clearly labelled as profile-only.
  * Derives the five report modes (Rankable-A / Rankable-B /
    Directional-C / Profile-only-D / Closed) from the V4 payload itself.
    No secondary heuristics.

The adapter does not compute scores. The V4 score is already computed by
`rcs_scoring_v4.py`; this module only reshapes it for report consumption.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# Mirror of rcs_scoring_v4.FORBIDDEN_FIELDS (spec §2.3). Duplicated here so
# the report layer does not depend on the scoring engine at import time —
# keep these two lists in lockstep if either changes.
FORBIDDEN_SCORE_DRIVERS = frozenset({
    # review text / AI
    "review_text", "ai_summary", "ai_summaries",
    # aspect sentiment removed from V4 scoring
    "aspect_food", "aspect_service", "aspect_ambience",
    "aspect_value", "aspect_cleanliness", "aspect_sentiment",
    # V3.4 sentiment outputs
    "sentiment", "sentiment_score", "sentiment_red_flags",
    "sentiment_positives", "sentiment_aspects",
})

# Classes returned by the V4 engine
RANKABLE_A = "Rankable-A"
RANKABLE_B = "Rankable-B"
DIRECTIONAL_C = "Directional-C"
PROFILE_ONLY_D = "Profile-only-D"

# Report modes
MODE_RANKABLE_A = "rankable_a"
MODE_RANKABLE_B = "rankable_b"
MODE_DIRECTIONAL_C = "directional_c"
MODE_PROFILE_ONLY_D = "profile_only_d"
MODE_CLOSED = "closed"
MODE_TEMP_CLOSED = "temp_closed"


class ForbiddenFieldError(ValueError):
    """Raised when a forbidden score-driver field appears on the score-
    driving surface of the input. Narrative fields are unaffected."""


@dataclass
class ComponentView:
    """One of: trust_compliance, customer_validation, commercial_readiness."""
    score: Optional[float]
    available: bool
    signals_used: int = 0
    # Customer-validation-only
    platforms: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "ComponentView":
        d = d or {}
        return cls(
            score=d.get("score"),
            available=bool(d.get("available")),
            signals_used=int(d.get("signals_used") or 0),
            platforms=d.get("platforms") or {},
        )


@dataclass
class ReportInputs:
    """The only object report builders read from. One dataclass, explicit
    fields — field renames are a one-location change.

    V4-score-driving fields (left block) must come from the V4 engine
    payload only. Narrative fields (right block) are explicitly tagged
    profile-only; builders that render them carry the §7.1 "narrative
    only — not a score input" marker.
    """

    # --- Identity ---
    fhrsid: str
    name: str                      # public_name if known, else FSA `n`
    fsa_name: str                  # raw FSA `n`
    trading_names: list[str]
    alias_confidence: Optional[str]
    address: str
    postcode: str
    la: Optional[str]
    month_str: str

    # --- V4 headline (engine-authoritative) ---
    rcs_v4_final: Optional[float]
    base_score: float
    adjusted_score: float
    confidence_class: str
    rankable: bool
    league_table_eligible: bool
    entity_match_status: str
    entity_ambiguous: bool
    source_family_summary: dict[str, Any]
    penalties_applied: list[dict[str, str]]
    caps_applied: list[dict[str, str]]
    decision_trace: list[str]
    engine_version: str
    computed_at: str

    # --- V4 components ---
    trust: ComponentView
    customer: ComponentView
    commercial: ComponentView
    distinction_value: float
    distinction_sources: list[str]

    # --- Closure state ---
    business_status: Optional[str]
    fsa_closed: bool
    closure_status: Optional[str]   # "closed_permanently" | "closed_temporarily" | None

    # --- Derived mode ---
    report_mode: str

    # --- Narrative inputs (profile-only; §7.1 guardrail applies) ---
    review_intel: Optional[dict] = None
    review_delta: Optional[dict] = None
    segment_intel: Optional[dict] = None
    menu_intel: Optional[dict] = None
    risk_result: Optional[dict] = None

    # --- Supporting side inputs ---
    peer_benchmarks: Optional[dict] = None
    prior_snapshot: Optional[dict] = None
    recommendations: Optional[dict] = None
    editorial: Optional[dict] = None
    menu_record: Optional[dict] = None
    venue_record: dict = field(default_factory=dict)
    entity_resolution_note: Optional[dict] = None   # duplicate-gpid / ambiguity context

    # --- Convenience ---
    @property
    def is_rankable(self) -> bool:
        return self.rankable and self.confidence_class in {RANKABLE_A, RANKABLE_B}

    @property
    def suppress_score(self) -> bool:
        return self.rcs_v4_final is None or self.report_mode == MODE_CLOSED

    def single_platform(self) -> bool:
        if not self.customer.available:
            return False
        return len(self.customer.platforms) == 1

    def active_cap_codes(self) -> list[str]:
        return [c.get("code", "") for c in self.caps_applied]

    def active_penalty_codes(self) -> list[str]:
        return [p.get("code", "") for p in self.penalties_applied]


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def _derive_mode(v4: dict, venue_record: dict) -> str:
    """Derive the rendering mode from the V4 payload, per spec §3."""
    business_status = str(venue_record.get("business_status") or "").upper()
    fsa_closed = bool(venue_record.get("fsa_closed"))

    if v4.get("rcs_v4_final") is None:
        # Engine suppressed the score -> permanent closure by spec §7.4.
        return MODE_CLOSED
    if fsa_closed or business_status == "CLOSED_PERMANENTLY":
        return MODE_CLOSED
    if business_status == "CLOSED_TEMPORARILY":
        return MODE_TEMP_CLOSED

    cls = v4.get("confidence_class")
    if cls == RANKABLE_A:
        return MODE_RANKABLE_A
    if cls == RANKABLE_B:
        return MODE_RANKABLE_B
    if cls == DIRECTIONAL_C:
        return MODE_DIRECTIONAL_C
    if cls == PROFILE_ONLY_D:
        return MODE_PROFILE_ONLY_D
    # Unknown class => treat as profile-only-D (safest)
    return MODE_PROFILE_ONLY_D


def _closure_status(venue_record: dict) -> Optional[str]:
    if bool(venue_record.get("fsa_closed")):
        return "closed_permanently"
    status = str(venue_record.get("business_status") or "").upper()
    if status == "CLOSED_PERMANENTLY":
        return "closed_permanently"
    if status == "CLOSED_TEMPORARILY":
        return "closed_temporarily"
    return None


def _guard_forbidden_score_drivers(venue_record: dict) -> None:
    """Spec §2.3 — refuse construction if any forbidden score-driver
    field appears on the venue record. Narrative fields (g_reviews,
    ta_reviews) are allowed; they are explicitly profile-only in the
    report layer and do not trip this guard."""
    offenders = [k for k in venue_record.keys() if k in FORBIDDEN_SCORE_DRIVERS]
    if offenders:
        raise ForbiddenFieldError(
            f"V4 report adapter refuses forbidden score-driver fields on "
            f"the venue record: {sorted(offenders)}. These must not be "
            f"persisted on the scoring input (see spec §2.3)."
        )


def build_report_inputs(
    *,
    v4_score: dict,
    venue_record: dict,
    month_str: str,
    review_intel: Optional[dict] = None,
    review_delta: Optional[dict] = None,
    segment_intel: Optional[dict] = None,
    menu_intel: Optional[dict] = None,
    menu_record: Optional[dict] = None,
    editorial: Optional[dict] = None,
    peer_benchmarks: Optional[dict] = None,
    prior_snapshot: Optional[dict] = None,
    recommendations: Optional[dict] = None,
    risk_result: Optional[dict] = None,
    entity_resolution_note: Optional[dict] = None,
) -> ReportInputs:
    """Construct a validated ReportInputs from the V4 payload + side data.

    `v4_score` must be the output of V4Score.to_dict() (or the equivalent
    per-record block from stratford_rcs_v4_scores.json).
    """
    _guard_forbidden_score_drivers(venue_record)

    components = v4_score.get("components") or {}
    modifiers = v4_score.get("modifiers") or {}
    audit = v4_score.get("audit") or {}
    distinction = modifiers.get("distinction") or {}
    srcfam = v4_score.get("source_family_summary") or {}

    closure = _closure_status(venue_record)
    mode = _derive_mode(v4_score, venue_record)

    # Defensive override for closure states (spec §7.4).
    # If the scoring engine was not re-run after a closure flag landed on
    # the venue record, the V4 payload may still report
    # `rankable=True / league_table_eligible=True`. The report renderer
    # must not trust those flags when a closure state is active — the
    # closure banner would otherwise contradict the inline rankability
    # line. Adapter normalises here so every downstream consumer sees
    # the same closure-correct flags.
    payload_rankable = bool(v4_score.get("rankable"))
    payload_league = bool(v4_score.get("league_table_eligible"))
    payload_final = v4_score.get("rcs_v4_final")
    if closure == "closed_permanently":
        payload_rankable = False
        payload_league = False
        payload_final = None  # spec §7.4 row 1: no score published
    elif closure == "closed_temporarily":
        # Spec §7.4 row 2: score preserved; league eligibility off.
        payload_league = False

    public_name = venue_record.get("public_name") or venue_record.get("n") or ""
    fsa_name = venue_record.get("n") or public_name

    return ReportInputs(
        # Identity
        fhrsid=str(v4_score.get("fhrsid") or venue_record.get("id") or ""),
        name=public_name,
        fsa_name=fsa_name,
        trading_names=list(venue_record.get("trading_names") or []),
        alias_confidence=venue_record.get("alias_confidence"),
        address=venue_record.get("a") or "",
        postcode=venue_record.get("pc") or "",
        la=venue_record.get("la"),
        month_str=month_str,
        # Headline (closure-corrected)
        rcs_v4_final=payload_final,
        base_score=float(v4_score.get("base_score") or 0.0),
        adjusted_score=float(v4_score.get("adjusted_score") or 0.0),
        confidence_class=v4_score.get("confidence_class") or "",
        rankable=payload_rankable,
        league_table_eligible=payload_league,
        entity_match_status=v4_score.get("entity_match_status") or "",
        entity_ambiguous=bool(venue_record.get("entity_ambiguous")),
        source_family_summary=dict(srcfam),
        penalties_applied=list(v4_score.get("penalties_applied") or []),
        caps_applied=list(v4_score.get("caps_applied") or []),
        decision_trace=list(audit.get("decision_trace") or []),
        engine_version=audit.get("engine_version") or "v4.0.0",
        computed_at=audit.get("computed_at") or "",
        # Components
        trust=ComponentView.from_dict(components.get("trust_compliance")),
        customer=ComponentView.from_dict(components.get("customer_validation")),
        commercial=ComponentView.from_dict(components.get("commercial_readiness")),
        distinction_value=float(distinction.get("value") or 0.0),
        distinction_sources=list(distinction.get("sources") or []),
        # Closure
        business_status=venue_record.get("business_status"),
        fsa_closed=bool(venue_record.get("fsa_closed")),
        closure_status=closure,
        # Mode
        report_mode=mode,
        # Narrative
        review_intel=review_intel,
        review_delta=review_delta,
        segment_intel=segment_intel,
        menu_intel=menu_intel,
        risk_result=risk_result,
        # Supporting
        peer_benchmarks=peer_benchmarks,
        prior_snapshot=prior_snapshot,
        recommendations=recommendations,
        editorial=editorial,
        menu_record=menu_record,
        venue_record=venue_record,
        entity_resolution_note=entity_resolution_note,
    )
