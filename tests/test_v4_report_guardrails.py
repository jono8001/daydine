#!/usr/bin/env python3
"""
tests/test_v4_report_guardrails.py — V4 report guardrail tests.

Exercises the two-layer validation from `operator_intelligence.v4_report_spec`:

  Structural checks — mandatory sections, mandatory banners, score
                       precision rules, penalty/cap cross-reference.
  Narrative guardrails — banned score-driver language, V3-era tier
                         framing, Directional-C / D / Closed handling,
                         financial-impact discipline.

Written to run without pytest:

  python -m tests.test_v4_report_guardrails

Exits non-zero on any assertion failure. Each test is a plain function
named `test_*`; the dispatcher at the bottom collects them, runs them,
and prints a summary.

The tests stub a `ReportInputs` object with the minimum V4 shape
required to drive each guardrail. We do not exercise the full
generator here — just the validator — so the tests stay fast and
deterministic.
"""
from __future__ import annotations

import sys
import traceback
from dataclasses import replace

from operator_intelligence.v4_adapter import (
    ComponentView, ReportInputs,
    MODE_RANKABLE_A, MODE_RANKABLE_B, MODE_DIRECTIONAL_C,
    MODE_PROFILE_ONLY_D, MODE_CLOSED, MODE_TEMP_CLOSED,
)
from operator_intelligence.v4_report_spec import validate_v4_report


# ---------------------------------------------------------------------------
# ReportInputs factories (minimal valid shells per mode)
# ---------------------------------------------------------------------------

def _base_inputs(mode: str, **overrides) -> ReportInputs:
    """Build a minimally valid ReportInputs for a given mode."""
    trust = ComponentView(score=8.0, available=True, signals_used=5)
    customer = ComponentView(
        score=7.5, available=True,
        platforms={"google": {"raw": 4.3, "count": 412,
                                "shrunk": 4.24, "weight": 1.00}},
    )
    commercial = ComponentView(score=7.0, available=True, signals_used=3)

    if mode == MODE_PROFILE_ONLY_D:
        customer = ComponentView(score=None, available=False, platforms={})
        commercial = ComponentView(score=None, available=False)
        rcs = 0.0
        cls = "Profile-only-D"
        rankable = False
        league = False
    elif mode == MODE_DIRECTIONAL_C:
        rcs = 7.2
        cls = "Directional-C"
        rankable = False
        league = False
    elif mode == MODE_RANKABLE_A:
        rcs = 8.0
        cls = "Rankable-A"
        rankable = True
        league = True
    elif mode == MODE_RANKABLE_B:
        rcs = 7.5
        cls = "Rankable-B"
        rankable = True
        league = True
    elif mode == MODE_CLOSED:
        rcs = None
        cls = "Rankable-B"
        rankable = False
        league = False
    elif mode == MODE_TEMP_CLOSED:
        rcs = 7.5
        cls = "Rankable-B"
        rankable = True
        league = False
    else:
        raise ValueError(f"unknown mode {mode!r}")

    inputs = ReportInputs(
        fhrsid="TESTFHR",
        name="Test Venue",
        fsa_name="Test Venue",
        trading_names=[],
        alias_confidence=None,
        address="1 Test Lane",
        postcode="TS1 1AA",
        la="Test LA",
        month_str="2026-04",
        rcs_v4_final=rcs,
        base_score=rcs or 0.0,
        adjusted_score=rcs or 0.0,
        confidence_class=cls,
        rankable=rankable,
        league_table_eligible=league,
        entity_match_status="confirmed",
        entity_ambiguous=False,
        source_family_summary={
            "fsa": "present",
            "customer_platforms": list(customer.platforms.keys()),
            "commercial": "full" if commercial.available else "absent",
            "companies_house": "unmatched",
        },
        penalties_applied=[],
        caps_applied=[],
        decision_trace=["TrustCompliance=8.00", "final=7.50"],
        engine_version="v4.0.0",
        computed_at="2026-04-17T00:00:00Z",
        trust=trust,
        customer=customer,
        commercial=commercial,
        distinction_value=0.0,
        distinction_sources=[],
        business_status=None,
        fsa_closed=False,
        closure_status=None,
        report_mode=mode,
        venue_record={"id": "TESTFHR", "n": "Test Venue", "r": 5,
                       "rd": "2025-10-01", "web": True,
                       "grc": 412, "gr": 4.3},
    )
    if overrides:
        inputs = replace(inputs, **overrides)
    return inputs


def _valid_fi_block() -> str:
    """A minimally spec-compliant Financial Impact section."""
    return (
        "## Financial Impact & Value at Stake\n\n"
        "**Confidence: Moderate.** Figures are directional. Exact numbers "
        "require internal cover and spend data.\n\n"
        "| Metric | Current | At stake | Notes |\n"
        "|---|---|---|---|\n"
        "| Monthly | — | £400 – £1,800 | directional |\n\n"
        "**Recommended action cost band:** £200 – £1,000\n"
        "**Expected payback window:** 1 – 3 months\n\n"
    )


def _full_rankable_report(inputs: ReportInputs) -> str:
    """A minimally valid Rankable-A / Rankable-B report skeleton."""
    return (
        f"# {inputs.name} — Monthly Intelligence Report\n"
        f"*{inputs.month_str} · Engine v4.0.0 · {inputs.confidence_class}*\n\n"
        "## Executive Summary\nSomething.\n\n"
        + _valid_fi_block() +
        "## Score, Confidence & Rankability Basis\nBasis.\n\n"
        "## Operational & Risk Alerts\nNone.\n\n"
        "## Trust & Compliance\nOK.\n\n"
        "## Customer Validation\nOK.\n\n"
        "## Commercial Readiness\nOK.\n\n"
        "## Market Position\nOK.\n\n"
        "## Competitive Market Intelligence\nOK.\n\n"
        "## Management Priorities\nOK.\n\n"
        "## Watch List\nOK.\n\n"
        "## What Not to Do This Month\nOK.\n\n"
        "## Profile Narrative & Reputation Signals\nOK.\n\n"
        "## Implementation Framework\nOK.\n\n"
        "## Next-Month Monitoring Plan\nOK.\n\n"
        "## Data Basis / Coverage & Confidence\nOK.\n\n"
        "## Evidence Appendix\nOK.\n\n"
        "## How the Score Was Formed\nOK.\n"
    )


def _directional_c_report_body(inputs: ReportInputs) -> str:
    return (
        f"# {inputs.name} — Monthly Intelligence Report\n"
        f"*{inputs.month_str} · Engine v4.0.0 · Directional-C · "
        f"thin review evidence*\n\n"
        "## Executive Summary\nUnblock.\n\n"
        "## Financial Impact & Value at Stake\n"
        "Financial impact is not rendered while this venue is classified "
        "Directional.\n\n"
        "## Score, Confidence & Rankability Basis\n"
        "Not league-ranked — thin review evidence. Narrative below is "
        "indicative.\n\n"
        "## Why this venue isn't league-ranked yet\nThin reviews.\n\n"
        "## Operational & Risk Alerts\nNone.\n\n"
        "## Trust & Compliance\nOK.\n\n"
        "## Customer Validation\nOK.\n\n"
        "## Commercial Readiness\nOK.\n\n"
        "## Management Priorities\nOK.\n\n"
        "## Watch List\nOK.\n\n"
        "## What Not to Do This Month\nOK.\n\n"
        "## Profile Narrative & Reputation Signals\nOK.\n\n"
        "## Implementation Framework\nOK.\n\n"
        "## Next-Month Monitoring Plan\nOK.\n\n"
        "## Data Basis / Coverage & Confidence\nOK.\n\n"
        "## Evidence Appendix\nOK.\n\n"
        "## How the Score Was Formed\nOK.\n"
    )


def _profile_only_d_report_body(inputs: ReportInputs) -> str:
    return (
        f"# {inputs.name} — Monthly Intelligence Report\n"
        f"*{inputs.month_str} · Engine v4.0.0 · Profile-only-D · "
        f"insufficient evidence*\n\n"
        "## Score, Confidence & Rankability Basis\n"
        "Insufficient evidence for a published score. Profile only.\n\n"
        "## Profile Stub\nStub.\n\n"
        "## How to unlock full scoring\nTodo.\n\n"
        "## Data Basis / Coverage & Confidence\nOK.\n\n"
        "## Evidence Appendix\nOK.\n"
    )


def _closed_report_body(inputs: ReportInputs) -> str:
    return (
        f"# {inputs.name} — Monthly Intelligence Report\n"
        f"*{inputs.month_str} · Engine v4.0.0 · Closed*\n\n"
        "## Closed — no score published\n"
        "This venue is flagged as permanently closed. No V4 score has "
        "been published.\n\n"
        "## Closure evidence\n"
        "| Source | Value |\n|---|---|\n"
        "| FSA closure flag | True |\n"
        "| Closure status (derived) | closed_permanently |\n\n"
        "## Evidence Appendix\nOK.\n"
    )


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------

def _expect_pass(report_text: str, inputs: ReportInputs,
                  label: str) -> None:
    result = validate_v4_report(report_text, inputs)
    errors = result.errors
    if errors:
        print(f"  FAIL {label} — unexpected errors:")
        for e in errors:
            print(f"    {e['rule']}: {e.get('match', '')}")
        raise AssertionError(f"expected pass, got errors for {label}")


def _expect_error(report_text: str, inputs: ReportInputs, rule: str,
                   label: str) -> None:
    result = validate_v4_report(report_text, inputs)
    codes = [e["rule"] for e in result.errors]
    if rule not in codes:
        print(f"  FAIL {label} — expected {rule}, got errors: {codes}")
        raise AssertionError(f"expected {rule} for {label}")


def _expect_warning(report_text: str, inputs: ReportInputs, rule: str,
                     label: str) -> None:
    result = validate_v4_report(report_text, inputs)
    codes = [w["rule"] for w in result.warnings]
    if rule not in codes:
        print(f"  FAIL {label} — expected warning {rule}, got warnings: {codes}")
        raise AssertionError(f"expected warning {rule} for {label}")


# ---------------------------------------------------------------------------
# Positive tests — valid reports should pass
# ---------------------------------------------------------------------------

def test_rankable_a_minimal_passes():
    inputs = _base_inputs(MODE_RANKABLE_A)
    text = _full_rankable_report(inputs)
    _expect_pass(text, inputs, "Rankable-A minimal report passes")


def test_directional_c_minimal_passes():
    inputs = _base_inputs(MODE_DIRECTIONAL_C)
    text = _directional_c_report_body(inputs)
    _expect_pass(text, inputs, "Directional-C minimal report passes")


def test_profile_only_d_minimal_passes():
    inputs = _base_inputs(MODE_PROFILE_ONLY_D)
    text = _profile_only_d_report_body(inputs)
    _expect_pass(text, inputs, "Profile-only-D minimal report passes")


def test_closed_minimal_passes():
    inputs = _base_inputs(MODE_CLOSED)
    text = _closed_report_body(inputs)
    _expect_pass(text, inputs, "Closed minimal report passes")


# ---------------------------------------------------------------------------
# Negative tests — banned score-driver language
# ---------------------------------------------------------------------------

def test_sentiment_drives_score_caught():
    inputs = _base_inputs(MODE_RANKABLE_A)
    text = _full_rankable_report(inputs).replace(
        "## Customer Validation\nOK.",
        "## Customer Validation\nThe score reflects sentiment in recent reviews."
    )
    _expect_error(text, inputs, "GUARD_SENTIMENT_DRIVES_SCORE",
                   "sentiment drives score caught")


def test_convergence_uplift_caught():
    inputs = _base_inputs(MODE_RANKABLE_A)
    text = _full_rankable_report(inputs).replace(
        "## Market Position\nOK.",
        "## Market Position\nCross-source convergence adds an uplift to the score."
    )
    _expect_error(text, inputs, "GUARD_CONVERGENCE_UPLIFT",
                   "convergence uplift caught")


def test_photo_price_pulls_score_caught():
    inputs = _base_inputs(MODE_RANKABLE_A)
    text = _full_rankable_report(inputs).replace(
        "## Market Position\nOK.",
        "## Market Position\nYour photos helped your rating this month."
    )
    _expect_error(text, inputs, "GUARD_PHOTO_PRICE_PULLS_SCORE",
                   "photos-pulls-score caught")


def test_v3_dimension_language_caught():
    inputs = _base_inputs(MODE_RANKABLE_A)
    text = _full_rankable_report(inputs).replace(
        "## Trust & Compliance\nOK.",
        "## Trust & Compliance\nThe experience dimension is strong."
    )
    _expect_error(text, inputs, "GUARD_V3_DIMENSION_LANGUAGE",
                   "V3 dimension language caught")


def test_v3_verbal_band_caught():
    inputs = _base_inputs(MODE_RANKABLE_A)
    text = _full_rankable_report(inputs).replace(
        "## Executive Summary\nSomething.",
        "## Executive Summary\nThis venue sits in the Generally Satisfactory band."
    )
    _expect_error(text, inputs, "GUARD_V3_VERBAL_BAND_AS_LABEL",
                   "V3 verbal band caught")


def test_red_flag_caps_score_caught():
    inputs = _base_inputs(MODE_RANKABLE_A)
    text = _full_rankable_report(inputs).replace(
        "## Operational & Risk Alerts\nNone.",
        "## Operational & Risk Alerts\nRed-flag phrases cap the score."
    )
    _expect_error(text, inputs, "GUARD_RED_FLAG_CAPS_SCORE",
                   "red-flag caps score caught")


# ---------------------------------------------------------------------------
# Negative tests — class handling
# ---------------------------------------------------------------------------

def test_directional_c_without_caveat_caught():
    inputs = _base_inputs(MODE_DIRECTIONAL_C)
    text = (
        f"# {inputs.name} — Monthly Intelligence Report\n"
        f"*{inputs.month_str} · Engine v4.0.0*\n\n"
        "## Executive Summary\nUnblock.\n\n"
        "## Score, Confidence & Rankability Basis\nCaveats missing.\n\n"
        "## Why this venue isn't league-ranked yet\nOK.\n\n"
        "## Operational & Risk Alerts\nNone.\n\n"
        "## Trust & Compliance\nOK.\n\n## Customer Validation\nOK.\n\n"
        "## Commercial Readiness\nOK.\n\n## Management Priorities\nOK.\n\n"
        "## Profile Narrative & Reputation Signals\nOK.\n\n"
        "## Implementation Framework\nOK.\n\n"
        "## Data Basis / Coverage & Confidence\nOK.\n\n"
        "## Evidence Appendix\nOK.\n\n"
        "## How the Score Was Formed\nOK.\n"
    )
    _expect_error(text, inputs, "GUARD_CLASS_C_MISSING_CAVEAT",
                   "Directional-C missing caveat caught")


def test_directional_c_peer_rank_leak_caught():
    inputs = _base_inputs(MODE_DIRECTIONAL_C)
    text = _directional_c_report_body(inputs).replace(
        "## Trust & Compliance\nOK.",
        "## Trust & Compliance\nThis venue ranks #3 of 10 in the local peer ring."
    )
    _expect_error(text, inputs, "GUARD_CLASS_C_RANK_LEAK",
                   "Directional-C peer rank leak caught")


def test_profile_only_d_score_headline_caught():
    inputs = _base_inputs(MODE_PROFILE_ONLY_D)
    text = (
        f"# {inputs.name} — Monthly Intelligence Report\n"
        f"*{inputs.month_str} · Engine v4.0.0 · Profile-only-D · "
        f"insufficient evidence*\n\n"
        "**V4 Score:** 5.123 / 10 · Profile-only-D.\n\n"
        "## Score, Confidence & Rankability Basis\n"
        "Insufficient evidence for a published score. Profile only.\n\n"
        "## Profile Stub\nStub.\n\n"
        "## How to unlock full scoring\nTodo.\n\n"
        "## Data Basis / Coverage & Confidence\nOK.\n\n"
        "## Evidence Appendix\nOK.\n"
    )
    _expect_error(text, inputs, "GUARD_CLASS_D_SCORE_HEADLINE",
                   "Profile-only-D score headline caught")


def test_profile_only_d_peer_section_caught():
    inputs = _base_inputs(MODE_PROFILE_ONLY_D)
    text = _profile_only_d_report_body(inputs) + (
        "\n## Market Position\nRank #1 of 3.\n"
    )
    _expect_error(text, inputs, "GUARD_CLASS_D_PEER_SECTION",
                   "Profile-only-D peer section caught")


def test_closed_renders_zero_caught():
    inputs = _base_inputs(MODE_CLOSED)
    text = _closed_report_body(inputs).replace(
        "No V4 score has been published.",
        "**V4 Score:** 0.000 / 10. No V4 score has been published."
    )
    _expect_error(text, inputs, "GUARD_CLASS_CLOSED_ZERO_SCORE",
                   "Closed renders zero caught")


def test_closed_has_action_tracker_caught():
    inputs = _base_inputs(MODE_CLOSED)
    text = _closed_report_body(inputs) + (
        "\n## Management Priorities\nFix something.\n"
    )
    _expect_error(text, inputs, "GUARD_CLASS_CLOSED_FORBIDDEN_SECTION",
                   "Closed has action tracker caught")


def test_entity_ambiguity_not_surfaced_caught():
    inputs = _base_inputs(MODE_DIRECTIONAL_C, entity_ambiguous=True)
    text = _directional_c_report_body(inputs)  # no Ambiguity context
    _expect_error(text, inputs, "GUARD_ENTITY_AMBIGUITY_NOT_SURFACED",
                   "entity ambiguity not surfaced caught")


def test_rankable_b_single_platform_caveat_missing_caught():
    inputs = _base_inputs(MODE_RANKABLE_B)  # platforms only Google by default
    text = _full_rankable_report(inputs)  # no 'single-platform' phrase
    _expect_warning(text, inputs, "GUARD_CLASS_B_SINGLE_PLATFORM_CAVEAT_MISSING",
                     "Rankable-B single-platform caveat missing caught")


# ---------------------------------------------------------------------------
# Negative tests — Financial Impact discipline
# ---------------------------------------------------------------------------

def test_fi_missing_confidence_label_caught():
    inputs = _base_inputs(MODE_RANKABLE_A)
    text = _full_rankable_report(inputs).replace(
        "**Confidence: Moderate.**",
        "This is going to make you money.",
    )
    _expect_error(text, inputs, "GUARD_FI_CONFIDENCE_LABEL_MISSING",
                   "FI missing confidence label caught")


def test_fi_missing_cost_band_caught():
    inputs = _base_inputs(MODE_RANKABLE_A)
    text = _full_rankable_report(inputs).replace(
        "**Recommended action cost band:** £200 – £1,000\n",
        "",
    )
    _expect_error(text, inputs, "GUARD_FI_COST_BAND_MISSING",
                   "FI missing cost band caught")


def test_fi_missing_payback_caught():
    inputs = _base_inputs(MODE_RANKABLE_A)
    text = _full_rankable_report(inputs).replace(
        "**Expected payback window:** 1 – 3 months\n\n",
        "",
    )
    _expect_error(text, inputs, "GUARD_FI_PAYBACK_MISSING",
                   "FI missing payback caught")


def test_fi_bare_pound_figure_warned():
    inputs = _base_inputs(MODE_RANKABLE_A)
    text = _full_rankable_report(inputs).replace(
        "| Monthly | — | £400 – £1,800 | directional |",
        "| Monthly | £2,345.67 | — | precise |",
    )
    _expect_warning(text, inputs, "GUARD_FI_BARE_POUND_FIGURE",
                     "FI bare pound figure warned")


def test_fi_roi_without_caveat_caught():
    inputs = _base_inputs(MODE_RANKABLE_A)
    text = _full_rankable_report(inputs).replace(
        "**Recommended action cost band:** £200 – £1,000\n",
        "**Recommended action cost band:** £200 – £1,000\n"
        "ROI of 240% on this spend.\n",
    )
    _expect_error(text, inputs, "GUARD_FI_ROI_WITHOUT_CAVEAT",
                   "FI ROI without caveat caught")


def test_fi_specific_score_movement_caught():
    inputs = _base_inputs(MODE_RANKABLE_A)
    text = _full_rankable_report(inputs).replace(
        "**Expected payback window:** 1 – 3 months\n\n",
        "**Expected payback window:** 1 – 3 months\n"
        "The score will rise by 1.2 points after this change.\n\n",
    )
    _expect_error(text, inputs, "GUARD_FI_SPECIFIC_SCORE_MOVEMENT",
                   "FI specific score movement caught")


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

def _collect_tests():
    return [
        (name, fn) for name, fn in globals().items()
        if name.startswith("test_") and callable(fn)
    ]


def main() -> int:
    tests = _collect_tests()
    failures = []
    for name, fn in tests:
        try:
            fn()
            print(f"ok   {name}")
        except AssertionError as e:
            failures.append((name, str(e)))
            print(f"FAIL {name} — {e}")
        except Exception as e:
            failures.append((name, f"{type(e).__name__}: {e}"))
            print(f"ERR  {name} — {type(e).__name__}: {e}")
            traceback.print_exc()
    print()
    print(f"Ran {len(tests)} tests — {len(failures)} failures.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
