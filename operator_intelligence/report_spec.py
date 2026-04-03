"""
operator_intelligence/report_spec.py — Formal Report Specification

Defines:
  - Required and conditional sections
  - Minimum content rules per section
  - Report modes (structured-signal vs narrative-rich)
  - Quality validation rules
  - Anti-generic phrase detection
  - QA artifact generation
"""

from dataclasses import dataclass, field
from typing import List, Optional

# ---------------------------------------------------------------------------
# Report Modes
# ---------------------------------------------------------------------------

MODE_STRUCTURED = "structured_signal"   # No review text — signal-led diagnosis
MODE_NARRATIVE = "narrative_rich"       # Has review text — full sentiment analysis


def detect_report_mode(review_intel):
    """Determine report mode from available data."""
    if review_intel and review_intel.get("has_narrative"):
        return MODE_NARRATIVE
    return MODE_STRUCTURED


# ---------------------------------------------------------------------------
# Review Confidence Tiers
# ---------------------------------------------------------------------------
# Governs how assertively the report can make claims from review data.
# Based on: review text count, source breadth, rating volume.

@dataclass
class ReviewConfidence:
    tier: str              # "anecdotal", "indicative", "directional", "established"
    review_text_count: int
    source_count: int      # how many independent sources (Google, TA, etc.)
    rating_volume: int     # aggregate review count (not text count)
    can_claim_themes: bool
    can_claim_proposition: bool
    can_claim_trajectory: bool
    qualifier: str         # prefix for claims at this confidence level


def assess_review_confidence(review_intel):
    """Determine review confidence tier from available data."""
    if not review_intel:
        return ReviewConfidence(
            tier="none", review_text_count=0, source_count=0, rating_volume=0,
            can_claim_themes=False, can_claim_proposition=False,
            can_claim_trajectory=False, qualifier="no review data available")

    text_count = 0
    sources = 0
    analysis = review_intel.get("analysis")
    if analysis:
        text_count = analysis.get("reviews_analyzed", 0)

    if review_intel.get("has_narrative"):
        sources += 1
    vol_signals = review_intel.get("volume_signals", {})
    rating_volume = vol_signals.get("review_count", 0)

    # Tier assignment
    # "anecdotal": 1-5 texts from 1 source — can observe, cannot conclude
    # "indicative": 6-15 texts or 2+ sources — can identify directions
    # "directional": 16-30 texts from 2+ sources — can make supported claims
    # "established": 30+ texts from 2+ sources — can state with confidence

    if text_count == 0:
        return ReviewConfidence(
            tier="none", review_text_count=0, source_count=sources,
            rating_volume=rating_volume,
            can_claim_themes=False, can_claim_proposition=False,
            can_claim_trajectory=False,
            qualifier="no review text available")

    if text_count <= 5 and sources <= 1:
        return ReviewConfidence(
            tier="anecdotal", review_text_count=text_count, source_count=sources,
            rating_volume=rating_volume,
            can_claim_themes=True, can_claim_proposition=False,
            can_claim_trajectory=False,
            qualifier="from a limited sample")

    if text_count <= 15:
        return ReviewConfidence(
            tier="indicative", review_text_count=text_count, source_count=sources,
            rating_volume=rating_volume,
            can_claim_themes=True, can_claim_proposition=True,
            can_claim_trajectory=False,
            qualifier="based on early evidence")

    if text_count <= 30:
        can_prop = sources >= 2
        return ReviewConfidence(
            tier="directional", review_text_count=text_count, source_count=sources,
            rating_volume=rating_volume,
            can_claim_themes=True, can_claim_proposition=can_prop,
            can_claim_trajectory=True,
            qualifier="supported by moderate evidence")

    return ReviewConfidence(
        tier="established", review_text_count=text_count, source_count=sources,
        rating_volume=rating_volume,
        can_claim_themes=True, can_claim_proposition=True,
        can_claim_trajectory=True,
        qualifier="well-supported by review evidence")


# Wording rules per tier — used by builders to select appropriate language
CONFIDENCE_LANGUAGE = {
    "none": {
        "theme_verb": "cannot be assessed from available data",
        "proposition_verb": "cannot be determined",
        "strong": "",  # never used
        "hedge": "No review text is available for this venue. ",
    },
    "anecdotal": {
        "theme_verb": "appears in the limited sample",
        "proposition_verb": "may be emerging as",
        "strong": "In the small sample available, ",
        "hedge": "Based on a limited sample of {n} reviews (Google's 'most relevant' selection), ",
    },
    "indicative": {
        "theme_verb": "is consistently mentioned",
        "proposition_verb": "is becoming associated with",
        "strong": "Early evidence suggests ",
        "hedge": "Across {n} reviews, ",
    },
    "directional": {
        "theme_verb": "is a recurring theme",
        "proposition_verb": "is increasingly known for",
        "strong": "Review evidence consistently points to ",
        "hedge": "Across {n} reviews from {s} sources, ",
    },
    "established": {
        "theme_verb": "is a well-established strength",
        "proposition_verb": "is known for",
        "strong": "Customers consistently highlight ",
        "hedge": "",  # no hedging needed
    },
}


# ---------------------------------------------------------------------------
# Section Definitions
# ---------------------------------------------------------------------------

@dataclass
class SectionSpec:
    key: str
    title: str
    mandatory: bool
    min_lines: int           # Minimum non-empty lines of content
    requires_narrative: bool = False  # Only in narrative-rich mode
    description: str = ""


MONTHLY_SECTIONS = [
    SectionSpec("executive_summary", "Executive Summary", mandatory=True, min_lines=5,
                description="Overall score, strongest/weakest dimension, peer position, top priority, data coverage statement"),
    SectionSpec("management_priorities", "Management Priorities", mandatory=True, min_lines=9,
                description="Top 3 priorities with management implications, owner, evidence, upside"),
    SectionSpec("watch_list", "Watch List", mandatory=True, min_lines=2,
                description="Exactly 2 watch items with title and description"),
    SectionSpec("what_not_to_do", "What Not to Do This Month", mandatory=True, min_lines=2,
                description="1 deprioritised action with reasoning"),
    SectionSpec("market_position", "Market Position", mandatory=True, min_lines=5,
                description="3-ring peer analysis with interpretation and competitor list"),
    SectionSpec("scorecard", "Dimension Scorecard", mandatory=True, min_lines=7,
                description="5 dimensions with score, delta, peer avg, gap, interpretive read"),
    SectionSpec("dimension_diagnosis", "Dimension-by-Dimension Diagnosis", mandatory=True, min_lines=10,
                description="Per-dimension what/why/signals/action with peer comparison"),
    SectionSpec("commercial_diagnosis", "Commercial Diagnosis", mandatory=True, min_lines=2,
                description="Evidence-backed commercial interpretation of scores and position"),
    SectionSpec("public_vs_reality", "Public Proof vs Operational Reality", mandatory=True, min_lines=4,
                description="Alignment analysis between public signals and operational depth"),
    SectionSpec("review_intelligence", "Review & Reputation Intelligence", mandatory=True, min_lines=3,
                description="Narrative-rich: aspect sentiment, quotes, themes. Structured: volume analysis"),
    SectionSpec("conversion_friction", "Conversion Friction Analysis", mandatory=True, min_lines=3,
                description="Specific barriers between customer interest and completed visit"),
    SectionSpec("recommendation_tracker", "Recommendation Tracker", mandatory=True, min_lines=2,
                description="Full lifecycle table or statement about carried-forward recs"),
    SectionSpec("market_intelligence", "Market Intelligence", mandatory=False, min_lines=2,
                description="Conditional: competitive density, compliance risk, visibility gap"),
    SectionSpec("monitoring_plan", "Next-Month Monitoring Plan", mandatory=True, min_lines=3,
                description="Specific metrics to track with baselines and targets"),
    SectionSpec("data_coverage", "Data Coverage & Confidence", mandatory=True, min_lines=5,
                description="Source inventory, confidence level, unlock recommendations"),
    SectionSpec("evidence_appendix", "Evidence Appendix", mandatory=True, min_lines=5,
                description="Raw signal values with sources"),
]

SECTION_KEYS = [s.key for s in MONTHLY_SECTIONS]
MANDATORY_KEYS = [s.key for s in MONTHLY_SECTIONS if s.mandatory]


# ---------------------------------------------------------------------------
# Action / Recommendation Structure Requirements
# ---------------------------------------------------------------------------

REQUIRED_ACTION_FIELDS = ["title", "description", "owner", "dimension",
                          "expected_upside", "confidence", "evidence"]

REQUIRED_REC_FIELDS = ["rec_id", "title", "status", "dimension",
                       "first_seen", "times_seen", "priority_score"]

ACTION_COUNT = 3
WATCH_COUNT = 2
DONT_COUNT = 1


# ---------------------------------------------------------------------------
# Anti-Generic Rules — phrases that indicate shallow output
# ---------------------------------------------------------------------------

BANNED_PHRASES = [
    "no priority actions this month",
    "no priority actions",
    "you're in strong shape",
    "keep doing what you're doing",
    "keep up the good work",
    "customers like your food",
    "customers respond well to your food quality",
    "generally positive",
    "nothing to worry about",
    "no significant changes",
    "no concerns identified",
    "no issues detected",
    "everything looks good",
    "maintain current trajectory",  # acceptable in watch, not in actions
    "no specific watch items",
    "no deprioritised actions",
    "continue to perform well",
    "on the right track",
    "strong performance across all dimensions",
]

# Phrases allowed in watch items but not in actions/diagnosis
WATCH_ONLY_PHRASES = [
    "maintain current trajectory",
    "monitor for further",
]

# Phrases that indicate fabricated review intelligence
FABRICATED_REVIEW_PHRASES = [
    "mentions)",  # "(3 mentions)" without review text
]

# Phrases that indicate score-led rather than proposition-led thinking
SCORE_LED_PHRASES = [
    "trust below peer average",
    "experience below peer average",
    "visibility below peer average",
    "conversion readiness gap vs peers",
]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    passed: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def validate_report(report_text, mode, recs, review_intel):
    """Validate a generated report against quality rules.
    Returns ValidationResult."""
    result = ValidationResult()
    lines = report_text.split("\n")
    text_lower = report_text.lower()

    # --- Section presence ---
    for spec in MONTHLY_SECTIONS:
        if not spec.mandatory:
            continue
        # Check section header exists
        if f"## {spec.title}" not in report_text:
            result.errors.append(f"MISSING_SECTION: '{spec.title}' not found in report")
            result.passed = False

    # --- Action counts ---
    actions = recs.get("priority_actions", [])
    watches = recs.get("watch_items", [])
    dont = recs.get("what_not_to_do")

    if len(actions) < ACTION_COUNT:
        result.errors.append(f"INSUFFICIENT_ACTIONS: {len(actions)} actions, need {ACTION_COUNT}")
        result.passed = False
    if len(watches) < WATCH_COUNT:
        result.errors.append(f"INSUFFICIENT_WATCHES: {len(watches)} watches, need {WATCH_COUNT}")
        result.passed = False
    if not dont:
        result.errors.append("MISSING_DONT: No 'what not to do' item")
        result.passed = False

    # --- Action field completeness ---
    for i, action in enumerate(actions):
        for field_name in REQUIRED_ACTION_FIELDS:
            if not action.get(field_name):
                result.warnings.append(f"ACTION_{i+1}_MISSING_FIELD: '{field_name}'")

    # --- Anti-generic phrase detection ---
    for phrase in BANNED_PHRASES:
        if phrase in text_lower:
            result.errors.append(f"BANNED_PHRASE: '{phrase}'")
            result.passed = False

    # --- Score-led phrase detection (warnings, not errors) ---
    for phrase in SCORE_LED_PHRASES:
        if phrase in text_lower:
            result.warnings.append(f"SCORE_LED_PHRASE: '{phrase}' — consider more proposition-led language")

    # --- Fabricated review intelligence ---
    if mode == MODE_STRUCTURED:
        has_narrative = review_intel.get("has_narrative", False) if review_intel else False
        if not has_narrative:
            for phrase in FABRICATED_REVIEW_PHRASES:
                # Check if mention counts appear outside the data coverage section
                sections_before_coverage = report_text.split("## Data Coverage")[0]
                if "## Review" in sections_before_coverage:
                    review_section = sections_before_coverage.split("## Review")[1]
                    if "## " in review_section:
                        review_section = review_section.split("## ")[0]
                    if phrase in review_section.lower() and "reviews)" not in review_section.lower():
                        result.warnings.append(f"POSSIBLE_FABRICATION: '{phrase}' in review section without review text")

    # --- Strategic sharpness checks ---
    # Check recommendation titles are not just dimension labels
    for i, action in enumerate(actions):
        title_lower = action.get("title", "").lower()
        for dim in ["trust", "experience", "visibility", "conversion", "prestige"]:
            if title_lower == f"{dim} below peer average" or title_lower == f"{dim} gap":
                result.warnings.append(
                    f"GENERIC_REC_TITLE: Action {i+1} title '{action['title']}' "
                    f"reads like a dimension label, not a management recommendation")

    # Check diagnosis has layered analysis (primary + secondary)
    if "## Commercial Diagnosis" in report_text:
        diag_section = report_text.split("## Commercial Diagnosis")[1]
        # Find the next H2 section (not H3)
        import re
        next_h2 = re.search(r'\n## [^#]', diag_section)
        if next_h2:
            diag_section = diag_section[:next_h2.start()]
        if "### Primary Constraint" not in diag_section and "### Main Bottleneck" not in diag_section:
            result.warnings.append("FLAT_DIAGNOSIS: Commercial diagnosis lacks structured constraint analysis")

    # Check for overclaiming on anecdotal evidence
    rc = assess_review_confidence(review_intel) if review_intel else None
    if rc and rc.tier == "anecdotal":
        strong_claim_phrases = [
            "consistently value", "known for", "well-established strength",
            "defining elements", "settled guest perception",
        ]
        for phrase in strong_claim_phrases:
            if phrase in text_lower:
                result.warnings.append(
                    f"OVERCLAIM_ON_ANECDOTAL: '{phrase}' used with only "
                    f"{rc.review_text_count} review texts (anecdotal tier)")

    # --- Report length ---
    content_lines = [l for l in lines if l.strip() and not l.startswith("#") and not l.startswith("|") and not l.startswith("---")]
    if len(content_lines) < 20:
        result.warnings.append(f"THIN_REPORT: Only {len(content_lines)} content lines")
    if len(content_lines) < 10:
        result.errors.append(f"TOO_SHORT: Only {len(content_lines)} content lines, minimum 10")
        result.passed = False

    # --- Recommendation tracker ---
    if "No active recommendations" in report_text and len(actions) > 0:
        result.warnings.append("TRACKER_MISMATCH: Actions exist but tracker says none")

    return result


# ---------------------------------------------------------------------------
# QA Artifact
# ---------------------------------------------------------------------------

def generate_qa_artifact(venue_name, month_str, mode, report_text, validation,
                         review_intel, recs, scorecard):
    """Generate QA companion artifact for a report."""
    return {
        "venue": venue_name,
        "month": month_str,
        "report_mode": mode,
        "data_sources": {
            "fsa": scorecard.get("fsa_rating") is not None,
            "google_rating": scorecard.get("google_rating") is not None,
            "google_reviews": scorecard.get("google_reviews") or 0,
            "review_text_available": review_intel.get("has_narrative", False) if review_intel else False,
            "reviews_analyzed": review_intel.get("reviews_analyzed", 0) if review_intel else 0,
            "tripadvisor": (review_intel.get("review_count_ta") or 0) > 0 if review_intel else False,
            "companies_house": False,
        },
        "section_completeness": _check_section_completeness(report_text),
        "action_counts": {
            "priority_actions": len(recs.get("priority_actions", [])),
            "watch_items": len(recs.get("watch_items", [])),
            "what_not_to_do": recs.get("what_not_to_do") is not None,
        },
        "validation_passed": validation.passed,
        "validation_errors": validation.errors,
        "validation_warnings": validation.warnings,
        "confidence_level": _compute_confidence(scorecard, review_intel),
        "report_lines": len([l for l in report_text.split("\n") if l.strip()]),
    }


def _check_section_completeness(report_text):
    """Check which sections are present and their approximate size."""
    completeness = {}
    for spec in MONTHLY_SECTIONS:
        marker = f"## {spec.title}"
        if marker in report_text:
            # Count lines between this section and the next
            idx = report_text.index(marker)
            rest = report_text[idx + len(marker):]
            next_section = rest.find("\n## ")
            if next_section == -1:
                section_text = rest
            else:
                section_text = rest[:next_section]
            content_lines = [l for l in section_text.split("\n")
                             if l.strip() and not l.startswith("#")]
            completeness[spec.key] = {
                "present": True,
                "lines": len(content_lines),
                "meets_minimum": len(content_lines) >= spec.min_lines,
            }
        else:
            completeness[spec.key] = {
                "present": False,
                "lines": 0,
                "meets_minimum": False,
            }
    return completeness


def _compute_confidence(scorecard, review_intel):
    """Report confidence level based on data availability."""
    sources = 0
    if scorecard.get("fsa_rating") is not None:
        sources += 1
    if scorecard.get("google_rating") is not None:
        sources += 1
    if review_intel and review_intel.get("has_narrative"):
        sources += 1
    if review_intel and review_intel.get("review_count_ta"):
        sources += 1
    if sources >= 4:
        return "high"
    if sources >= 2:
        return "medium"
    return "low"
