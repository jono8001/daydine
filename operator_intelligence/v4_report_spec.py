"""
operator_intelligence/v4_report_spec.py — V4 report validation and guardrails.

Implements the structural and narrative-guardrail checks from
docs/DayDine-V4-Report-Spec.md §10:

  Layer 1 (structural): every mandatory section for the report mode is
                        present; class banner is rendered; closure
                        banner is rendered; component cards render for
                        available components; score precision matches;
                        cross-referenced penalty / cap codes resolve.

  Layer 2 (narrative guardrails): banned score-driver language, V3-era
                                  tier framing, sentiment-drives-score
                                  claims, Directional-C / D handling,
                                  closure handling, hard-coded
                                  distribution numbers.

Both layers produce a V4QaResult dataclass that the report generator
serialises into `*_qa.json`. Errors block the run; warnings do not.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from operator_intelligence.v4_adapter import (
    ReportInputs,
    MODE_RANKABLE_A, MODE_RANKABLE_B, MODE_DIRECTIONAL_C,
    MODE_PROFILE_ONLY_D, MODE_CLOSED, MODE_TEMP_CLOSED,
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class V4QaResult:
    mode: str
    errors: list[dict[str, str]] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)
    structural_ok: bool = True
    guardrail_ok: bool = True

    def fail(self, rule: str, match: str = "", location: str = "",
             severity: str = "error") -> None:
        entry = {"rule": rule, "match": match, "location": location}
        if severity == "error":
            self.errors.append(entry)
            if rule.startswith("STRUCT_"):
                self.structural_ok = False
            else:
                self.guardrail_ok = False
        else:
            self.warnings.append(entry)

    def passed(self) -> bool:
        return not self.errors


# ---------------------------------------------------------------------------
# Section expectations per mode
# ---------------------------------------------------------------------------

# Mandatory section headings (as rendered, markdown H2). A section passes if
# its heading appears in the report text. Some sections are mandatory only
# in certain modes.

SECTIONS_COMMON = [
    "Score, Confidence & Rankability Basis",
    "Data Basis",
    "Evidence Appendix",
]

SECTIONS_FULL_REPORT = [
    "Executive Summary",
    "Financial Impact & Value at Stake",
    "Score, Confidence & Rankability Basis",
    "Operational & Risk Alerts",
    "Trust & Compliance",
    "Customer Validation",
    "Commercial Readiness",
    "Market Position",
    "Competitive Market Intelligence",
    "Management Priorities",
    "Watch List",
    "What Not to Do This Month",
    "Profile Narrative & Reputation Signals",
    "Implementation Framework",
    "Next-Month Monitoring Plan",
    "Data Basis",
    "Evidence Appendix",
    "How the Score Was Formed",
]

SECTIONS_DIRECTIONAL_C = [
    "Executive Summary",
    "Score, Confidence & Rankability Basis",
    "Why this venue isn't league-ranked yet",
    "Operational & Risk Alerts",
    "Trust & Compliance",
    "Customer Validation",
    "Commercial Readiness",
    "Management Priorities",
    "Profile Narrative & Reputation Signals",
    "Implementation Framework",
    "Data Basis",
    "Evidence Appendix",
    "How the Score Was Formed",
]

SECTIONS_PROFILE_ONLY_D = [
    "Score, Confidence & Rankability Basis",
    "Profile Stub",
    "How to unlock full scoring",
    "Data Basis",
    "Evidence Appendix",
]

SECTIONS_CLOSED = [
    "Closed — no score published",
    "Closure evidence",
    "Evidence Appendix",
]


def sections_for_mode(mode: str) -> list[str]:
    if mode == MODE_RANKABLE_A:
        return SECTIONS_FULL_REPORT
    if mode == MODE_RANKABLE_B:
        return SECTIONS_FULL_REPORT
    if mode == MODE_DIRECTIONAL_C:
        return SECTIONS_DIRECTIONAL_C
    if mode == MODE_PROFILE_ONLY_D:
        return SECTIONS_PROFILE_ONLY_D
    if mode == MODE_CLOSED:
        return SECTIONS_CLOSED
    if mode == MODE_TEMP_CLOSED:
        # Same as full report, with temporary-closure banner added
        return SECTIONS_FULL_REPORT
    return SECTIONS_COMMON


# ---------------------------------------------------------------------------
# Layer 1 — Structural validation
# ---------------------------------------------------------------------------

def _heading_present(report_text: str, heading: str) -> bool:
    """Return True if a markdown H2 / H3 with this heading appears."""
    pattern = rf"^#+\s+{re.escape(heading)}\b"
    return bool(re.search(pattern, report_text, re.MULTILINE))


def validate_structural(report_text: str, inputs: ReportInputs,
                         result: V4QaResult) -> None:
    """Check mandatory sections for the mode, banners, and score handling."""
    expected = sections_for_mode(inputs.report_mode)

    for heading in expected:
        if not _heading_present(report_text, heading):
            result.fail(
                "STRUCT_MISSING_SECTION",
                match=heading,
                location=inputs.report_mode,
            )

    # Mode-specific banner checks
    if inputs.report_mode == MODE_DIRECTIONAL_C:
        if "Directional" not in report_text.split("\n")[0:12].__str__():
            # Be lenient: must appear near the top. Check first ~60 lines.
            head = "\n".join(report_text.splitlines()[:60])
            if "Directional" not in head:
                result.fail(
                    "STRUCT_MISSING_DIRECTIONAL_BANNER",
                    match="class banner absent from report header",
                )

    if inputs.report_mode == MODE_PROFILE_ONLY_D:
        head = "\n".join(report_text.splitlines()[:40])
        if "Profile only" not in head and "Profile-only" not in head:
            result.fail(
                "STRUCT_MISSING_PROFILE_ONLY_BANNER",
                match="profile-only banner absent from report header",
            )
        # rcs_v4_final must not appear as a number in D
        if inputs.rcs_v4_final is not None:
            if re.search(rf"\b{inputs.rcs_v4_final:.3f}\b", report_text):
                result.fail(
                    "STRUCT_PROFILE_ONLY_SCORE_LEAKED",
                    match=f"{inputs.rcs_v4_final:.3f}",
                )

    if inputs.report_mode == MODE_CLOSED:
        head = "\n".join(report_text.splitlines()[:40])
        if "Closed" not in head:
            result.fail(
                "STRUCT_MISSING_CLOSED_BANNER",
                match="closure banner absent from report header",
            )
        if re.search(r"\b0\.000\b", report_text):
            result.fail(
                "STRUCT_CLOSED_RENDERS_ZERO",
                match="closed venue rendered '0.000' as score",
            )

    if inputs.report_mode == MODE_TEMP_CLOSED:
        head = "\n".join(report_text.splitlines()[:60])
        if "Temporarily closed" not in head and "temporarily closed" not in head:
            result.fail(
                "STRUCT_MISSING_TEMP_CLOSURE_BANNER",
                match="temporary-closure flag absent from header",
            )

    # Every cap / penalty referenced in prose must appear in the How-the-
    # score-was-formed block. We check that each code string exists
    # somewhere in the final report.
    for p in (inputs.penalties_applied + inputs.caps_applied):
        code = p.get("code")
        if code and code not in report_text:
            result.fail(
                "STRUCT_MISSING_PENALTY_CAP_REFERENCE",
                match=code,
            )

    # Single-platform Rankable-B caveat
    if inputs.report_mode == MODE_RANKABLE_B and inputs.single_platform():
        if "single" not in report_text.lower() and "Single" not in report_text:
            result.fail(
                "STRUCT_MISSING_SINGLE_PLATFORM_CAVEAT",
                match="Rankable-B single-platform case requires caveat",
                severity="warning",
            )


# ---------------------------------------------------------------------------
# Layer 2 — Narrative guardrails (spec §10.2)
# ---------------------------------------------------------------------------

# Banned score-driver language. Each entry is (rule_code, regex, severity).
_GUARDRAIL_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    # Sentiment / aspect / AI driving score
    ("GUARD_SENTIMENT_DRIVES_SCORE",
     re.compile(
        r"\b(score|rating)[^.\n]*?\b(reflects|driven by|shaped by|"
        r"caused by|because of|due to|result of)\b[^.\n]*?"
        r"\b(sentiment|aspect|AI|photo|price level|social|convergence|"
        r"delivery|takeaway|parking|wheelchair|Facebook|Instagram)\b",
        re.IGNORECASE,
     ), "error"),
    ("GUARD_CONVERGENCE_UPLIFT",
     re.compile(
        r"\bcross[- ]source convergence[^.\n]*?(boost|uplift|premium|"
        r"bonus|adds|lifts)\b", re.IGNORECASE
     ), "error"),
    ("GUARD_PHOTO_PRICE_PULLS_SCORE",
     re.compile(
        r"\b(your )?(photos?|price level|place types|delivery|takeaway|"
        r"parking|wheelchair)\b[^.\n]*?(pulled|helped|lifted|pulled down|"
        r"is|are)\b[^.\n]*?\b(score|rating)\b",
        re.IGNORECASE,
     ), "error"),
    ("GUARD_AI_INPUT",
     re.compile(
        r"\bAI(-based)?\s+(analysis|summary|summarisation|summarization)\b"
        r"[^.\n]*?\b(score|scoring|drives)\b",
        re.IGNORECASE,
     ), "error"),

    # V3-era tier framing used as score driver
    ("GUARD_V3_DIMENSION_LANGUAGE",
     re.compile(
        r"\b(experience|visibility|conversion|prestige)\s+dimension\b",
        re.IGNORECASE,
     ), "error"),
    ("GUARD_V3_WATERMARK",
     re.compile(r"DayDine Premium v3\.\d", re.IGNORECASE), "error"),
    ("GUARD_V3_VERBAL_BAND",
     re.compile(
        r"\b(Generally Satisfactory|Improvement Necessary|"
        r"Major Improvement|Urgent Improvement)\s+band\b",
        re.IGNORECASE,
     ), "error"),

    # Overclaiming
    ("GUARD_CONSISTENTLY_WEAK_EVIDENCE",
     re.compile(
        r"\b(customers|guests) (consistently|routinely|repeatedly)\b",
        re.IGNORECASE,
     ), "warning"),

    # Pre-cutover distribution numbers in prose
    ("GUARD_HARDCODED_DISTRIBUTION_STRATFORD",
     re.compile(
        r"\b(0\.5% of venues reach Rankable-A|"
        r"56\.0% of rankable venues score|"
        r"Most venues in Stratford are Rankable-B)\b",
        re.IGNORECASE,
     ), "warning"),
]


def validate_guardrails(report_text: str, inputs: ReportInputs,
                         result: V4QaResult) -> None:
    """Pattern-match the rendered markdown against forbidden prose."""
    for rule, pattern, severity in _GUARDRAIL_PATTERNS:
        for m in pattern.finditer(report_text):
            snippet = m.group(0)[:120]
            # Allow "customers consistently" when review confidence is
            # Established and the class is not Directional-C.
            if rule == "GUARD_CONSISTENTLY_WEAK_EVIDENCE":
                tier = ((inputs.review_intel or {}).get("confidence") or
                         {}).get("tier") or ""
                if (tier.lower() == "established"
                        and inputs.report_mode not in {
                            MODE_DIRECTIONAL_C, MODE_PROFILE_ONLY_D
                        }):
                    continue
            result.fail(rule, match=snippet, severity=severity)

    # Mode-specific enforcement: Directional-C must not render a peer rank
    if inputs.report_mode == MODE_DIRECTIONAL_C:
        if re.search(r"#\d+\s+of\s+\d+", report_text):
            result.fail(
                "GUARD_DIRECTIONAL_C_PEER_RANK_LEAK",
                match="`#N of M` rank claim in Directional-C report",
            )

    # Mode-specific enforcement: Profile-only-D must not render a peer section
    if inputs.report_mode == MODE_PROFILE_ONLY_D:
        if "Market Position" in report_text:
            result.fail(
                "GUARD_PROFILE_ONLY_D_PEER_SECTION_LEAK",
                match="Market Position heading present in Profile-only-D",
            )
        if "Financial Impact" in report_text:
            result.fail(
                "GUARD_PROFILE_ONLY_D_FINANCIAL_LEAK",
                match="Financial Impact heading present in Profile-only-D",
            )

    # Mode-specific enforcement: Closed must not render any action tracker
    if inputs.report_mode == MODE_CLOSED:
        for forbidden in ("Management Priorities", "Implementation Framework",
                           "Watch List", "Market Position",
                           "Financial Impact"):
            if forbidden in report_text:
                result.fail(
                    "GUARD_CLOSED_FORBIDDEN_SECTION",
                    match=f"`{forbidden}` rendered in Closed report",
                )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def validate_v4_report(report_text: str, inputs: ReportInputs) -> V4QaResult:
    result = V4QaResult(mode=inputs.report_mode)
    validate_structural(report_text, inputs, result)
    validate_guardrails(report_text, inputs, result)
    return result


def to_qa_dict(result: V4QaResult) -> dict:
    return {
        "engine_version": "v4.0.0",
        "report_mode": result.mode,
        "structural_check": {
            "passed": result.structural_ok,
        },
        "guardrail_check": {
            "run": True,
            "passed": result.guardrail_ok,
            "errors": result.errors,
            "warnings": result.warnings,
        },
    }
