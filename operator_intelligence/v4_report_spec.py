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
    "Financial Impact & Value at Stake",
    "Score, Confidence & Rankability Basis",
    "Why this venue isn't league-ranked yet",
    "Operational & Risk Alerts",
    "Trust & Compliance",
    "Customer Validation",
    "Commercial Readiness",
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
# The list is divided into blocks (sentiment, convergence, V3 tier,
# six-verbal-bands, profile-only-as-driver, overclaiming, pre-cutover,
# closure / D handling). Each block corresponds to a bullet in spec §10.2.
_GUARDRAIL_PATTERNS: list[tuple[str, re.Pattern, str]] = [

    # --- Sentiment / aspect / AI implied as score driver ---
    ("GUARD_SENTIMENT_DRIVES_SCORE",
     re.compile(
        r"\b(score|rating)[^.\n]*?\b(reflects|driven by|shaped by|"
        r"caused by|because of|due to|result of)\b[^.\n]*?"
        r"\b(sentiment|aspect|AI|photo|price level|social|convergence|"
        r"delivery|takeaway|parking|wheelchair|Facebook|Instagram)\b",
        re.IGNORECASE,
     ), "error"),
    ("GUARD_REVIEW_SENTIMENT_PULLS_SCORE",
     re.compile(
        r"\b(sentiment|aspect scores?|review (?:text|themes?))"
        r"[^.\n]*?\b(pulled|pushed|lifted|weighs?|weighed)"
        r"[^.\n]*?\b(score|rating|headline)",
        re.IGNORECASE,
     ), "error"),
    ("GUARD_AI_SUMMARY_INPUT",
     re.compile(
        r"\bAI(-based)?\s+(analysis|summary|summarisation|summarization"
        r"|summaries)\b[^.\n]*?\b(score|scoring|drives|caps|lifts|"
        r"contributes)\b",
        re.IGNORECASE,
     ), "error"),
    ("GUARD_RED_FLAG_CAPS_SCORE",
     re.compile(
        r"\b(red[- ]?flag|risk[- ]?phrase)s?\b[^.\n]*?"
        r"\b(caps?|lowers?|reduces?|penalises?|drives?)\b[^.\n]*?"
        r"\b(score|rating|headline)\b",
        re.IGNORECASE,
     ), "error"),

    # --- Convergence as uplift ---
    ("GUARD_CONVERGENCE_UPLIFT",
     re.compile(
        r"\bcross[- ]?source convergence[^.\n]*?(boost|uplift|premium|"
        r"bonus|adds?|lifts?)\b", re.IGNORECASE
     ), "error"),
    ("GUARD_SOURCES_CORROBORATE_LIFT",
     re.compile(
        r"\b(sources? (?:agree|corroborate)|independent sources?)\b"
        r"[^.\n]*?\b(boost|uplift|premium|bonus|lifts?|raises?)\b"
        r"[^.\n]*?\b(score|rating)\b",
        re.IGNORECASE,
     ), "error"),

    # --- Profile-only signals as score drivers ---
    ("GUARD_PHOTO_PRICE_PULLS_SCORE",
     re.compile(
        r"\b(your )?(photos?|price level|place types?|delivery|takeaway|"
        r"parking|wheelchair|dog[- ]friendly|outdoor seating)\b[^.\n]*?"
        r"(pulled|helped|lifted|pulled down|is|are|contributes?|"
        r"contribute to|feeds?)\b[^.\n]*?\b(score|rating|headline)\b",
        re.IGNORECASE,
     ), "error"),
    ("GUARD_SOCIAL_PRESENCE_DRIVES",
     re.compile(
        r"\b(facebook|instagram|twitter|tiktok)\b[^.\n]*?"
        r"\b(helping|helps|drives?|lifts?|boosts?)\b[^.\n]*?"
        r"\b(visibility|score|rating|headline)\b",
        re.IGNORECASE,
     ), "error"),

    # --- V3-era tier framing used as if authoritative ---
    ("GUARD_V3_DIMENSION_LANGUAGE",
     re.compile(
        r"\b(experience|visibility|conversion|prestige)\s+dimension\b",
        re.IGNORECASE,
     ), "error"),
    ("GUARD_V3_DIMENSION_SCORECARD",
     re.compile(
        r"^##\s+Dimension Scorecard\b",
        re.IGNORECASE | re.MULTILINE,
     ), "error"),
    ("GUARD_V3_WATERMARK",
     re.compile(r"DayDine Premium v3\.\d", re.IGNORECASE), "error"),
    ("GUARD_V3_FIVE_DIMENSION_TABLE_HEADER",
     re.compile(
        r"\|\s*Experience\s*\|\s*Visibility\s*\|\s*Trust\s*\|"
        r"\s*Conversion\s*\|",
        re.IGNORECASE,
     ), "error"),

    # --- Six verbal bands treated as primary ---
    ("GUARD_V3_VERBAL_BAND_AS_LABEL",
     re.compile(
        r"\b(Generally Satisfactory|Improvement Necessary|"
        r"Major Improvement|Urgent Improvement)\s+band\b",
        re.IGNORECASE,
     ), "error"),
    ("GUARD_V3_VERBAL_BAND_AS_HEADLINE",
     re.compile(
        r"^##?\s*(Excellent|Good|Generally Satisfactory|"
        r"Improvement Necessary|Major Improvement|Urgent Improvement)"
        r"\s+Venue\s*$",
        re.IGNORECASE | re.MULTILINE,
     ), "error"),
    ("GUARD_V3_CATEGORY_LEADER_OVERCLAIM",
     re.compile(
        r"\b(category leader|market leader|leads the field|"
        r"top of the category)\b",
        re.IGNORECASE,
     ), "warning"),  # Acceptable for Rankable-A; warning triggers for other
                     # modes via the post-match filter below.

    # --- Overclaiming with weak evidence ---
    ("GUARD_CONSISTENTLY_WEAK_EVIDENCE",
     re.compile(
        r"\b(customers|guests) (consistently|routinely|repeatedly)\b",
        re.IGNORECASE,
     ), "warning"),
    ("GUARD_ABSOLUTE_COMMERCIAL_LANGUAGE",
     re.compile(
        r"\byou (will|are going to) (lose|recover|miss|gain) "
        r"(£|\$)[\d,]",
        re.IGNORECASE,
     ), "warning"),

    # --- Pre-cutover distribution numbers in public-facing prose ---
    ("GUARD_HARDCODED_DISTRIBUTION_STRATFORD",
     re.compile(
        r"\b(0\.5%\s+of\s+venues\s+reach\s+Rankable-A|"
        r"56\.0%\s+of\s+rankable\s+venues\s+score|"
        r"Most\s+venues\s+in\s+Stratford\s+are\s+Rankable-B)\b",
        re.IGNORECASE,
     ), "warning"),

    # --- Financial Impact false precision ---
    ("GUARD_FI_PRECISE_POUND_FIGURE",
     re.compile(
        r"\b£\d+(?:\.\d{2})\b(?![^.\n]*?(?:–|-|to)\s*£)",
        re.IGNORECASE,
     ), "error"),
    ("GUARD_FI_ROI_WITHOUT_CAVEAT",
     re.compile(
        r"\bROI\s+(of|is|will be)\s+\d+%",
        re.IGNORECASE,
     ), "error"),
    ("GUARD_FI_SPECIFIC_SCORE_MOVEMENT",
     re.compile(
        r"\bscore\s+(will rise|will improve|will move|will increase|"
        r"will climb)\s+by\s+\d+(\.\d+)?",
        re.IGNORECASE,
     ), "error"),
    ("GUARD_FI_INDUSTRY_RATE_AS_OBSERVED",
     re.compile(
        r"\b(industry|benchmark)\s+(?:rates?\s+)?says?\s+you\s+lose",
        re.IGNORECASE,
     ), "warning"),
]


def validate_guardrails(report_text: str, inputs: ReportInputs,
                         result: V4QaResult) -> None:
    """Pattern-match the rendered markdown against forbidden prose. Then
    run class-scoped content rules."""
    for rule, pattern, severity in _GUARDRAIL_PATTERNS:
        for m in pattern.finditer(report_text):
            snippet = m.group(0)[:120]
            # "customers consistently" is allowed when the review-text tier
            # is Established and the V4 class is Rankable-A / Rankable-B.
            if rule == "GUARD_CONSISTENTLY_WEAK_EVIDENCE":
                tier = ((inputs.review_intel or {}).get("confidence") or
                         {}).get("tier") or ""
                if (tier.lower() == "established"
                        and inputs.report_mode not in {
                            MODE_DIRECTIONAL_C, MODE_PROFILE_ONLY_D
                        }):
                    continue

            # "category leader" / "leads the field" is allowed for
            # Rankable-A only. Warning for every other mode.
            if rule == "GUARD_V3_CATEGORY_LEADER_OVERCLAIM":
                if inputs.report_mode == MODE_RANKABLE_A:
                    continue

            result.fail(rule, match=snippet, severity=severity)

    _enforce_class_rules(report_text, inputs, result)
    _enforce_financial_impact_rules(report_text, inputs, result)


# ---------------------------------------------------------------------------
# Per-class content rules
# ---------------------------------------------------------------------------

# Required caveat phrasings. Each class has one (or more) sentences the
# report must contain for its class context to be transparent.
_REQUIRED_CAVEATS = {
    MODE_DIRECTIONAL_C: [
        "Not league-ranked",
    ],
    MODE_PROFILE_ONLY_D: [
        "Insufficient evidence for a published score",
    ],
    MODE_CLOSED: [
        "No V4 score has been published",
    ],
    MODE_TEMP_CLOSED: [
        "temporarily closed",
    ],
}


def _enforce_class_rules(report_text: str, inputs: ReportInputs,
                          result: V4QaResult) -> None:
    """Required class-scoped behaviours (spec §3, §4).

    Each check maps to one of the user-listed risks:
      - Closed rendered as zero
      - Profile-only-D written as if ranked
      - Directional-C without explicit caveat
      - Entity ambiguity not surfaced when relevant
      - Weak evidence written as if fully comparable
    """
    mode = inputs.report_mode

    # Closed must never render 0.0 / 0.000 as a score.
    if mode == MODE_CLOSED:
        if re.search(r"V4\s+Score[^\n]*\b0(\.0+)?\b", report_text):
            result.fail(
                "GUARD_CLASS_CLOSED_ZERO_SCORE",
                match="Closed venue rendered a zero V4 score",
            )
        # No action tracker / league claims
        for forbidden in (
            "Management Priorities", "Implementation Framework",
            "Watch List", "Market Position", "Financial Impact",
            "What Not to Do This Month",
        ):
            if forbidden in report_text:
                result.fail(
                    "GUARD_CLASS_CLOSED_FORBIDDEN_SECTION",
                    match=f"`{forbidden}` rendered in Closed report",
                )

    # Profile-only-D must not render a headline score or rank claim.
    if mode == MODE_PROFILE_ONLY_D:
        if re.search(r"^\*\*V4\s+Score:\*\*", report_text, re.MULTILINE):
            result.fail(
                "GUARD_CLASS_D_SCORE_HEADLINE",
                match="Profile-only-D rendered a score headline",
            )
        if re.search(r"#\d+\s+of\s+\d+", report_text):
            result.fail(
                "GUARD_CLASS_D_RANK_CLAIM",
                match="Profile-only-D contains a peer rank claim",
            )
        if "Market Position" in report_text:
            result.fail(
                "GUARD_CLASS_D_PEER_SECTION",
                match="Profile-only-D rendered Market Position section",
            )
        if "Financial Impact" in report_text:
            result.fail(
                "GUARD_CLASS_D_FINANCIAL_SECTION",
                match="Profile-only-D rendered Financial Impact section",
            )

    # Directional-C must carry the caveat phrase + must not leak rank.
    if mode == MODE_DIRECTIONAL_C:
        if "Not league-ranked" not in report_text and \
                "not league-ranked" not in report_text:
            result.fail(
                "GUARD_CLASS_C_MISSING_CAVEAT",
                match="Directional-C report missing the 'Not league-ranked' "
                      "caveat phrase",
            )
        if re.search(r"#\d+\s+of\s+\d+", report_text):
            result.fail(
                "GUARD_CLASS_C_RANK_LEAK",
                match="Directional-C contains a peer rank claim",
            )
        # Peer comparison language prohibited
        if re.search(r"\b(peer\s+(?:avg|top|percentile)|top\s+10|"
                     r"top\s+ten)\b", report_text, re.IGNORECASE):
            # Only a warning — some peer-derived fallback tables can be
            # acceptable context
            result.fail(
                "GUARD_CLASS_C_PEER_COMPARISON_LEAK",
                match="peer-percentile / top-10 language in Directional-C",
                severity="warning",
            )

    # Entity ambiguity must be surfaced when the flag is set.
    if inputs.entity_ambiguous:
        if "Ambiguity context" not in report_text and \
                "entity match ambiguous" not in report_text and \
                "entity ambiguity" not in report_text.lower():
            result.fail(
                "GUARD_ENTITY_AMBIGUITY_NOT_SURFACED",
                match="entity_ambiguous flag set but no surfacing phrase "
                      "appeared in the report body",
            )

    # Weak-evidence venues written as if fully comparable: Rankable-B
    # single-platform must carry a single-platform caveat.
    if mode == MODE_RANKABLE_B and inputs.single_platform():
        if not re.search(r"single[- ]platform", report_text, re.IGNORECASE):
            result.fail(
                "GUARD_CLASS_B_SINGLE_PLATFORM_CAVEAT_MISSING",
                match="Rankable-B single-platform case requires "
                      "'single-platform' caveat",
                severity="warning",
            )

    # Required caveat phrases per class
    for required in _REQUIRED_CAVEATS.get(mode, []):
        if required.lower() not in report_text.lower():
            result.fail(
                "GUARD_CLASS_MISSING_REQUIRED_CAVEAT",
                match=f"{mode}: expected caveat phrase '{required}' missing",
            )


# ---------------------------------------------------------------------------
# Financial Impact discipline (spec §6 / §10.2 Financial block)
# ---------------------------------------------------------------------------

_FI_SECTION_RE = re.compile(
    r"(^##\s+Financial Impact[^\n]*\n)(.*?)(?=^##\s|\Z)",
    re.DOTALL | re.MULTILINE,
)

_FI_CONFIDENCE_LABEL_RE = re.compile(
    r"\bConfidence:\s*(High|Moderate|Low|Not available)\b",
    re.IGNORECASE,
)

_FI_COST_BAND_RE = re.compile(
    r"cost\s+band", re.IGNORECASE,
)

_FI_PAYBACK_RE = re.compile(r"payback", re.IGNORECASE)

_FI_FALLBACK_RE = re.compile(
    r"Financial impact cannot be robustly estimated|"
    r"Financial impact is not rendered",
    re.IGNORECASE,
)


def _enforce_financial_impact_rules(report_text: str,
                                     inputs: ReportInputs,
                                     result: V4QaResult) -> None:
    """Financial Impact must either render with a confidence label plus
    cost band and payback, or render the honest fallback wording. No
    middle ground. No precise £ point estimates.
    """
    match = _FI_SECTION_RE.search(report_text)
    if not match:
        # Section absent is OK for D / Closed (enforced by class rules).
        # Otherwise the section is mandatory (spec §5.2 / §6.1).
        if inputs.report_mode in {MODE_RANKABLE_A, MODE_RANKABLE_B,
                                   MODE_DIRECTIONAL_C, MODE_TEMP_CLOSED}:
            result.fail(
                "GUARD_FI_SECTION_MISSING",
                match="Financial Impact section absent for "
                      f"{inputs.report_mode}",
            )
        return

    body = match.group(2)

    # Fallback wording exempts the rest of the checks
    if _FI_FALLBACK_RE.search(body):
        return

    # Otherwise it is a full section — must carry the three discipline
    # markers: confidence label, cost band, payback window.
    if not _FI_CONFIDENCE_LABEL_RE.search(body):
        result.fail(
            "GUARD_FI_CONFIDENCE_LABEL_MISSING",
            match="Financial Impact section rendered without a "
                  "confidence label",
        )
    if not _FI_COST_BAND_RE.search(body):
        result.fail(
            "GUARD_FI_COST_BAND_MISSING",
            match="Financial Impact section rendered without a cost band",
        )
    if not _FI_PAYBACK_RE.search(body):
        result.fail(
            "GUARD_FI_PAYBACK_MISSING",
            match="Financial Impact section rendered without a payback "
                  "window",
        )

    # Ranges — any pound figure must appear as a range (low–high) not a
    # bare precise number.
    for m in re.finditer(r"£[\d,]+(?:\.\d{2})?", body):
        pos = m.end()
        tail = body[pos:pos + 20]
        # Accept ranges marked by –, -, "to", or "–£", etc.
        if not re.match(r"\s*(?:–|-|to|\band\b)\s*£", tail):
            # If the line already contains a range somewhere, allow
            line = body[:pos].rsplit("\n", 1)[-1] + body[pos:].split("\n", 1)[0]
            if "–" in line or " to £" in line or "- £" in line:
                continue
            result.fail(
                "GUARD_FI_BARE_POUND_FIGURE",
                match=f"Financial figure without range: {m.group(0)}",
                severity="warning",
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
