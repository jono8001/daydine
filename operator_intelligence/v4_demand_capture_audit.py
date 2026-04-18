"""
operator_intelligence/v4_demand_capture_audit.py — V4-aware Demand Capture Audit.

A V4-native wrapper over `operator_intelligence.demand_capture_audit` that
classifies each of the seven audit dimensions by their relationship to
the V4 scoring contract:

  - **CR-linked**: the dimension directly overlaps with a Commercial
    Readiness sub-signal (spec §5.1). Verdicts here help the operator
    diagnose *why* a CR sub-signal reads the way it does. They do not
    themselves feed the V4 score — only the four CR sub-signals do.

  - **Diagnostic**: the dimension is a broader customer-path observation
    the report preserves for commercial value but which the V4 engine
    does not consume. Rendered under a "narrative only" banner.

CR-linked mapping:

    Booking Friction   -> CR sub-signal: booking / contact path
    Menu Visibility    -> CR sub-signal: menu online

Diagnostic (profile-only narrative):

    CTA Clarity, Photo Mix & Quality, Proposition Clarity,
    Mobile Usability, Promise vs Path

Inputs are V4-only: the underlying audit reads the venue record and
review-intel side channel. The V3.4 `scorecard` stub is no longer
passed — the audit module tolerates empty scorecard / benchmarks.
Peer context in `_audit_photos` falls back to its built-in assumption
of ~10 peer photos when no benchmark data is available; that is the
same behaviour V3.4 used when peer photo counts were unavailable.
"""
from __future__ import annotations

from typing import Any, Optional

from operator_intelligence.v4_adapter import ReportInputs


# Dimension → CR sub-signal (if CR-linked).
_CR_LINK = {
    "Booking Friction": "booking / contact path",
    "Menu Visibility":  "menu online",
}


def _classify(dimension_result: dict) -> dict:
    name = dimension_result.get("dimension") or ""
    cr_sub = _CR_LINK.get(name)
    dimension_result["cr_linked"] = cr_sub is not None
    dimension_result["cr_sub_signal"] = cr_sub
    return dimension_result


def run_v4_demand_capture_audit(inputs: ReportInputs) -> Optional[dict]:
    """Run the audit with V4 inputs only. Returns a dict shaped as:

        {
            "dimensions": [...],              # all 7, in canonical order
            "cr_linked_dimensions": [...],    # subset (2) that map onto CR
            "diagnostic_dimensions": [...],   # subset (5) narrative-only
            "summary": {...}                  # verdict counts
        }

    Returns `None` if the underlying audit refuses the inputs — this
    is a narrative-only block and silent-fail is acceptable.
    """
    try:
        from operator_intelligence.demand_capture_audit import (
            run_demand_capture_audit,
        )
    except ImportError:
        return None

    # Pass empty peer-benchmarks / scorecard — the audit uses them only
    # for verdict colouring in one dimension (Photo Mix & Quality) and
    # tolerates missing data gracefully. No V3.4 scorecard stub is
    # constructed; the V4 report layer has already decided the V4
    # components are authoritative.
    try:
        raw = run_demand_capture_audit(
            inputs.venue_record,
            {},                          # scorecard: empty
            inputs.peer_benchmarks or {},
            inputs.review_intel or {},
        )
    except Exception:
        return None
    if not raw:
        return None

    dims = [_classify(d) for d in (raw.get("dimensions") or [])]
    return {
        "dimensions": dims,
        "cr_linked_dimensions": [d for d in dims if d.get("cr_linked")],
        "diagnostic_dimensions": [d for d in dims if not d.get("cr_linked")],
        "summary": raw.get("summary") or {},
    }
