"""
operator_intelligence/legacy_boundary.py — V3.4 legacy boundary registry.

Single source of truth for which modules are **legacy V3.4** (retained
only for rollback / comparison / historical reference; must not be
imported by any V4 code path) and which are **shared narrative-only
helpers** (V3.4 origin, reused by V4 explicitly as text / theme
sources, never as score inputs).

The boundary test at `tests/test_v4_legacy_boundary.py` uses these
sets to enforce the rule. Adding a new V4 file that legitimately
needs to wrap or reuse a V3.4 helper requires adding it to
`ALLOWED_V4_TO_LEGACY_IMPORTS` with a one-line justification.

See `docs/DayDine-Legacy-Quarantine-Note.md` for the quarantine
policy and the conditions under which a legacy file becomes safe
to delete.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Legacy V3.4 modules — retained only for rollback / comparison.
# No V4 code may import these. The boundary test enforces this.
# ---------------------------------------------------------------------------

LEGACY_MODULES: frozenset[str] = frozenset({
    # Root-level V3.4 entry points
    "rcs_scoring_stratford",
    "restaurant_operator_intelligence",

    # V3.4 operator-intelligence modules
    "operator_intelligence.recommendations",
    "operator_intelligence.implementation_framework",
    "operator_intelligence.report_generator",
    "operator_intelligence.report_spec",
    "operator_intelligence.scorecard",
    "operator_intelligence.peer_benchmarking",
    "operator_intelligence.commercial_estimates",
    "operator_intelligence.evidence_base",
    "operator_intelligence.fsa_intelligence",
    "operator_intelligence.consistency_checker",
    "operator_intelligence.integrity_checks",
    "operator_intelligence.competitor_strategy",
    "operator_intelligence.category_validation",
    "operator_intelligence.seasonal_context",

    # V3.4 section builders
    "operator_intelligence.builders",
    "operator_intelligence.builders.actions_tracker",
    "operator_intelligence.builders.data_basis",
    "operator_intelligence.builders.diagnosis",
    "operator_intelligence.builders.event_forecast",
    "operator_intelligence.builders.exec_summary",
    "operator_intelligence.builders.financial_impact",
    "operator_intelligence.builders.long_form",
    "operator_intelligence.builders.menu_intelligence",
    "operator_intelligence.builders.monthly_movement",
    "operator_intelligence.builders.review_section",
    "operator_intelligence.builders.risk_alerts",
    "operator_intelligence.builders.scorecard",
    "operator_intelligence.builders.segment_section",
    "operator_intelligence.builders.trust_detail",
    "operator_intelligence.builders.venue_identity",
})


# ---------------------------------------------------------------------------
# Shared narrative-only helpers. V3.4 origin; V4 reuses these as text /
# theme sources only. They are NOT legacy in the "must not import" sense
# but they are NOT V4-native either.
# ---------------------------------------------------------------------------

SHARED_NARRATIVE_MODULES: frozenset[str] = frozenset({
    "operator_intelligence.review_analysis",
    "operator_intelligence.review_delta",
    "operator_intelligence.segment_analysis",
    "operator_intelligence.risk_detection",
    "operator_intelligence.demand_capture_audit",
})


# ---------------------------------------------------------------------------
# Explicit allow-list for V4 → legacy imports. Each entry documents a
# legitimate wrapper / adapter path that the boundary test exempts.
# ---------------------------------------------------------------------------

# Format: importing_v4_module -> set of legacy modules it is allowed to import.
# If you need to add an entry, add a comment explaining the wrapper pattern
# and why a direct V4-native rewrite would not be cleaner.
ALLOWED_V4_TO_LEGACY_IMPORTS: dict[str, frozenset[str]] = {
    # v4_demand_capture_audit wraps the V3.4 7-dimension audit. The
    # wrapper classifies each dimension as CR-linked vs diagnostic and
    # enforces V4 framing at the render boundary; the underlying
    # auditor helpers are text-only heuristics that work unchanged.
    "operator_intelligence.v4_demand_capture_audit": frozenset({
        "operator_intelligence.demand_capture_audit",
    }),
}


# ---------------------------------------------------------------------------
# Helpers for the boundary test
# ---------------------------------------------------------------------------

def is_v4_module(dotted: str) -> bool:
    """Return True if this dotted module name is a V4 module."""
    last = dotted.rsplit(".", 1)[-1]
    return last.startswith("v4_")


def is_legacy_module(dotted: str) -> bool:
    """Return True if this dotted module name is quarantined V3.4."""
    return dotted in LEGACY_MODULES


def is_shared_narrative(dotted: str) -> bool:
    """Return True if this dotted module is a shared narrative helper."""
    return dotted in SHARED_NARRATIVE_MODULES


def is_allowed_v4_to_legacy_import(importer: str, target: str) -> bool:
    """Return True if the importer is explicitly allowed to import the
    target legacy module."""
    allowed = ALLOWED_V4_TO_LEGACY_IMPORTS.get(importer, frozenset())
    return target in allowed
