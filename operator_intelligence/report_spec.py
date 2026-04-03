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
    """Determine review confidence tier from available data.

    Source counting: Google and TripAdvisor are independent platforms.
    Google review text is NOT a separate source from Google ratings —
    it's the same platform. Each platform counts once.
    """
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

    # Count independent review platforms (not data fields)
    ta_count = review_intel.get("review_count_ta") or 0
    google_text = text_count - ta_count  # Google review texts
    if google_text > 0 or review_intel.get("has_narrative"):
        sources += 1  # Google (one platform, regardless of text + rating)
    if ta_count > 0:
        sources += 1  # TripAdvisor (independent platform)

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
                description="Two-layer model: Reputation Baseline (full sample with stated scope) "
                            "and Recent Movement (date-filtered if dates available, honest fallback if not). "
                            "Must not imply all reviews are from the current month."),
    SectionSpec("conversion_friction", "Conversion Friction Analysis", mandatory=True, min_lines=3,
                description="Specific barriers between customer interest and completed visit"),
    SectionSpec("recommendation_tracker", "Recommendation Tracker", mandatory=True, min_lines=2,
                description="Full lifecycle table or statement about carried-forward recs"),
    SectionSpec("market_intelligence", "Competitive Market Intelligence", mandatory=True, min_lines=4,
                description="Peer position, competitor movement, dimension gaps vs local market, density and share-leakage signals, commercial implications of market context"),
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
# Commercial Consequence Framework
# ---------------------------------------------------------------------------
# Major findings and actions should carry a brief commercial consequence
# block where external data supports an estimate. This makes the report
# actionable — operators can weigh cost-of-inaction against cost-to-fix.
#
# Rules:
#   1. Prefer ranges over single-point estimates.
#   2. Label confidence honestly — never imply precision that isn't there.
#   3. If evidence is too weak, use the honest fallback wording.
#   4. All estimates are from external/public data only.
#   5. Keep blocks compact (2-4 lines max per finding).

@dataclass
class CommercialConsequence:
    """Structured commercial impact estimate for a finding or action."""
    value_at_stake: str          # e.g. "£200–£600/month" or "Not estimable"
    implementation_cost: str     # e.g. "Low (< 1 hour)", "Medium (1–2 days)"
    payback: str                 # e.g. "Immediate", "< 1 month", "1–3 months"
    confidence: str              # One of CONSEQUENCE_CONFIDENCE_LEVELS
    basis: str                   # 1-line note: what the estimate rests on


# Confidence levels for commercial estimates (strongest → weakest)
CONSEQUENCE_CONFIDENCE_LEVELS = [
    "bounded",       # Range derived from observable data with stated assumptions
    "directional",   # Direction is clear, magnitude is approximate
    "indicative",    # Rough order-of-magnitude from category averages
    "not_estimable", # Cannot estimate from external data
]

# Implementation cost bands
COST_BANDS = {
    "zero":   "Zero cost (profile update)",
    "low":    "Low (< 1 hour, no spend)",
    "medium": "Medium (1–2 days or < £200)",
    "high":   "High (multi-week project or £500+)",
}

# Payback bands
PAYBACK_BANDS = {
    "immediate":  "Immediate (same week)",
    "short":      "< 1 month",
    "medium":     "1–3 months",
    "long":       "3–12 months",
    "long_cycle":  "Long-cycle (12+ months)",
}

# Honest fallback — use when evidence is insufficient for any estimate
CONSEQUENCE_NOT_ESTIMABLE = (
    "Commercial impact not robustly estimable from current external evidence."
)

# Sections where commercial consequence blocks should appear when feasible:
#   - Management Priorities (per action)
#   - Conversion Friction Analysis (per friction point)
#   - Revenue Left on the Table (per leakage item)
#   - Competitive Market Intelligence (market-level consequence)
#
# Sections where consequence is NOT expected:
#   - Dimension Scorecard (pure data)
#   - Evidence Appendix (raw signals)
#   - Watch List (not yet actionable)
#   - Data Coverage (meta-information)


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

# Phrases that imply temporal freshness without date evidence
# These should trigger warnings, not hard failures, because they may be
# valid once date filtering is implemented.
TEMPORAL_OVERCLAIM_PHRASES = [
    "this month's reviews",
    "reviews from this month",
    "reviews received this month",
    "in the last 30 days",       # only valid if date filtering is active
    "recent reviews show",       # only valid if reviews are date-sorted
    "recent reviews suggest",
]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    passed: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def validate_report(report_text, mode, recs, review_intel, scorecard=None):
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

    # --- Launch-critical section: Competitive Market Intelligence ---
    # This is the new mandatory section — flag clearly if missing
    if "## Competitive Market Intelligence" not in report_text:
        result.errors.append(
            "MISSING_LAUNCH_SECTION: 'Competitive Market Intelligence' is mandatory "
            "for the zero-integration launch product")
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

    # --- Temporal overclaim detection ---
    for phrase in TEMPORAL_OVERCLAIM_PHRASES:
        if phrase in text_lower:
            result.warnings.append(
                f"TEMPORAL_OVERCLAIM: '{phrase}' implies date-filtered freshness — "
                f"only valid if review dates are available and filtering is active")

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

    # --- Source-count consistency ---
    rc = assess_review_confidence(review_intel) if review_intel else None
    if rc:
        # Check: report claims "from N sources" but actual source count differs
        ta_count = review_intel.get("review_count_ta") or 0 if review_intel else 0
        actual_platforms = 0
        if rc.review_text_count - ta_count > 0:
            actual_platforms += 1
        if ta_count > 0:
            actual_platforms += 1
        if rc.source_count != actual_platforms:
            result.warnings.append(
                f"SOURCE_COUNT_MISMATCH: ReviewConfidence reports {rc.source_count} sources "
                f"but {actual_platforms} platforms contributed review text")

        # Check for overclaiming on anecdotal evidence
        if rc.tier == "anecdotal":
            strong_claim_phrases = [
                "consistently value", "known for", "well-established strength",
                "defining elements", "settled guest perception",
            ]
            for phrase in strong_claim_phrases:
                if phrase in text_lower:
                    result.warnings.append(
                        f"OVERCLAIM_ON_ANECDOTAL: '{phrase}' used with only "
                        f"{rc.review_text_count} review texts (anecdotal tier)")

        # Lightweight claim-without-evidence check:
        # If report says "consistently" or "dominant theme" but confidence is
        # anecdotal or none, that's a mismatch
        if rc.tier in ("none", "anecdotal"):
            overconfident_phrases = ["dominant theme", "consistently praise",
                                     "consistently mentioned", "clear evidence"]
            for phrase in overconfident_phrases:
                if phrase in text_lower:
                    result.warnings.append(
                        f"CONFIDENCE_WORDING_MISMATCH: '{phrase}' used at "
                        f"'{rc.tier}' confidence tier — wording overstates evidence")

    # --- Review date honesty ---
    has_dated = review_intel.get("has_dated_reviews", False) if review_intel else False
    date_range = review_intel.get("date_range") if review_intel else None
    recent_window = review_intel.get("recent_window") if review_intel else None

    # Check: report says "based on review dates" but no valid dated reviews
    if not has_dated and "based on review dates" in text_lower:
        result.warnings.append(
            "TRAJECTORY_DATE_OVERCLAIM: Report says 'based on review dates' "
            "but review_intel.has_dated_reviews is False")

    # Check: report contains "30-day window" language but recent_window is None or empty
    if "30-day window" in text_lower:
        rw_count = recent_window.get("count", 0) if recent_window else 0
        if rw_count == 0:
            result.warnings.append(
                "RECENT_WINDOW_OVERCLAIM: Report references a '30-day window' "
                "but no dated reviews fall within that window")

    # Check: report has Recent Movement section with content but no dated reviews
    if "### Recent Movement" in report_text and not has_dated:
        # Extract the section
        rm_section = report_text.split("### Recent Movement")[1]
        rm_end = rm_section.find("\n### ")
        if rm_end == -1:
            rm_end = rm_section.find("\n## ")
        if rm_end != -1:
            rm_section = rm_section[:rm_end]
        # If it has substantive content (not just the degradation message)
        rm_lower = rm_section.lower()
        if "dated review" not in rm_lower and "cannot be" not in rm_lower:
            result.warnings.append(
                "RECENT_MOVEMENT_WITHOUT_DATES: Recent Movement section has "
                "content but review_intel.has_dated_reviews is False")

    # --- Commercial consequence honesty ---
    import re as _re

    # Check 1: £ estimates without a confidence label nearby
    # Look for "£X" patterns not accompanied by a confidence word within 300 chars
    _conf_words = {"bounded", "directional", "indicative", "not estimable",
                   "not robustly estimable"}
    for match in _re.finditer(r'£[\d,]+', report_text):
        pos = match.start()
        # Check surrounding context (200 chars before + 200 chars after)
        context = report_text[max(0, pos - 200):pos + 200].lower()
        if not any(cw in context for cw in _conf_words):
            # Skip Evidence Appendix (raw data, no confidence needed)
            before = report_text[:pos]
            if "## Evidence Appendix" in before:
                last_h2 = before.rindex("## ")
                if before[last_h2:last_h2 + 22] == "## Evidence Appendix":
                    continue
            result.warnings.append(
                f"ESTIMATE_WITHOUT_CONFIDENCE: £ figure near position {pos} "
                f"has no confidence label within 200 characters")

    # Check 2: Fake single-point precision (£ followed by exact number, no range)
    # Pattern: "£1,234/month" without a "–" range nearby
    for match in _re.finditer(r'£[\d,]+/mo', report_text):
        context = report_text[max(0, match.start() - 5):match.end()]
        if '–' not in context and '-' not in context:
            result.warnings.append(
                f"SINGLE_POINT_ESTIMATE: '{match.group()}' looks like a single-point "
                f"estimate — ranges are preferred for external-data products")

    # Check 3: "basis" or "based on" should appear near commercial consequence blocks
    if "commercial consequence" in text_lower:
        sections = text_lower.split("commercial consequence")
        for i, section in enumerate(sections[1:], 1):
            block = section[:300]
            if "basis:" not in block and "based on" not in block:
                result.warnings.append(
                    f"ESTIMATE_WITHOUT_BASIS: Commercial consequence block {i} "
                    f"has no basis/assumptions note")

    # --- Evidence provenance presence ---
    if "## Evidence Appendix" in report_text:
        appendix = report_text.split("## Evidence Appendix")[1]
        next_h2 = appendix.find("\n## ")
        if next_h2 != -1:
            appendix = appendix[:next_h2]
        if "| Provenance |" not in appendix and "provenance" not in appendix.lower()[:200]:
            result.warnings.append(
                "MISSING_PROVENANCE: Evidence Appendix does not include provenance column")

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
    rc = assess_review_confidence(review_intel) if review_intel else None
    confidence_level = _compute_confidence(scorecard, review_intel)

    # Count independent sources for the QA record
    independent_sources = []
    if scorecard.get("fsa_rating") is not None:
        independent_sources.append("FSA")
    if scorecard.get("google_rating") is not None:
        independent_sources.append("Google")
    if review_intel and review_intel.get("review_count_ta"):
        independent_sources.append("TripAdvisor")

    # Check provenance presence in evidence appendix
    has_provenance = ("| Provenance |" in report_text
                      if "## Evidence Appendix" in report_text else False)

    # Review date metadata
    has_dated = review_intel.get("has_dated_reviews", False) if review_intel else False
    date_range = review_intel.get("date_range") if review_intel else None
    recent_window = review_intel.get("recent_window") if review_intel else None
    analysis = review_intel.get("analysis") if review_intel else None

    # Count future-dated reviews (dates after report month)
    future_excluded = 0
    if analysis and month_str:
        try:
            from datetime import datetime as _dt
            ceil = _dt.strptime(month_str, "%Y-%m")
            if ceil.month == 12:
                ceil = ceil.replace(year=ceil.year + 1, month=1)
            else:
                ceil = ceil.replace(month=ceil.month + 1)
            ceiling_str = ceil.strftime("%Y-%m-%d")
            for r in analysis.get("per_review", []):
                d = (r.get("date") or "")[:10]
                if d and d >= ceiling_str:
                    future_excluded += 1
        except (ValueError, TypeError):
            pass

    # Which sources have usable dates?
    dates_by_source = {}
    if analysis:
        for r in analysis.get("per_review", []):
            src = r.get("source") or "unknown"
            has_d = bool(r.get("date"))
            if src not in dates_by_source:
                dates_by_source[src] = {"total": 0, "dated": 0}
            dates_by_source[src]["total"] += 1
            if has_d:
                dates_by_source[src]["dated"] += 1

    # Compute valid-filtered view (excluding future-dated reviews)
    valid_dated_reviews = []
    valid_date_range = None
    if analysis and month_str:
        try:
            from datetime import datetime as _dt2, timedelta as _td
            _c = _dt2.strptime(month_str, "%Y-%m")
            if _c.month == 12:
                _c = _c.replace(year=_c.year + 1, month=1)
            else:
                _c = _c.replace(month=_c.month + 1)
            _cs = _c.strftime("%Y-%m-%d")
            valid_dated_reviews = [
                r for r in analysis.get("per_review", [])
                if r.get("date") and r["date"][:10] < _cs
            ]
            if valid_dated_reviews:
                vdates = sorted(r["date"][:10] for r in valid_dated_reviews)
                valid_date_range = {"earliest": vdates[0], "latest": vdates[-1]}
                # Valid recent window: 30 days back from latest valid date
                _lat = _dt2.strptime(vdates[-1], "%Y-%m-%d")
                _cut = (_lat - _td(days=30)).strftime("%Y-%m-%d")
                valid_recent = [r for r in valid_dated_reviews if r["date"][:10] >= _cut]
                valid_recent_count = len(valid_recent)
                valid_recent_sources = list(set(r.get("source") or "unknown" for r in valid_recent))
            else:
                valid_recent_count = 0
                valid_recent_sources = []
        except (ValueError, TypeError):
            valid_recent_count = 0
            valid_recent_sources = []
    else:
        valid_recent_count = 0
        valid_recent_sources = []

    review_dates_qa = {
        "has_dated_reviews": has_dated,
        "date_range": date_range,
        "valid_date_range": valid_date_range,
        "dates_by_source": dates_by_source,
        "future_dated_excluded": future_excluded,
        "recent_window_available": bool(recent_window and recent_window.get("count", 0) > 0),
        "recent_window_count": recent_window.get("count", 0) if recent_window else 0,
        "recent_window_sources": recent_window.get("sources", []) if recent_window else [],
        "recent_window_valid_count": valid_recent_count,
        "recent_window_valid_sources": valid_recent_sources,
        "dated_trajectory_supported": (
            has_dated and future_excluded == 0
            and sum(1 for r in (analysis or {}).get("per_review", []) if r.get("date")) >= 4
        ),
    }

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
        "independent_sources": {
            "count": len(independent_sources),
            "platforms": independent_sources,
        },
        "review_confidence": {
            "tier": rc.tier if rc else "none",
            "review_text_count": rc.review_text_count if rc else 0,
            "source_count": rc.source_count if rc else 0,
            "can_claim_themes": rc.can_claim_themes if rc else False,
            "can_claim_proposition": rc.can_claim_proposition if rc else False,
        } if rc else {"tier": "none"},
        "section_completeness": _check_section_completeness(report_text),
        "action_counts": {
            "priority_actions": len(recs.get("priority_actions", [])),
            "watch_items": len(recs.get("watch_items", [])),
            "what_not_to_do": recs.get("what_not_to_do") is not None,
        },
        "validation_passed": validation.passed,
        "validation_errors": validation.errors,
        "validation_warnings": validation.warnings,
        "confidence_level": confidence_level,
        "evidence_provenance_present": has_provenance,
        "review_dates": review_dates_qa,
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
    """Report confidence level based on independent source count.

    Independent sources (each counted at most once):
      - FSA (statutory — independent of all others)
      - Google (one platform: rating + reviews + text all count as one)
      - TripAdvisor (independent platform)
    Google review text is NOT a separate source from Google rating.
    """
    sources = 0
    if scorecard.get("fsa_rating") is not None:
        sources += 1
    if scorecard.get("google_rating") is not None:
        sources += 1  # Google counts once — rating, text, photos all same platform
    if review_intel and review_intel.get("review_count_ta"):
        sources += 1  # TripAdvisor — independent
    # has_narrative is NOT an additional source — it's Google review text

    if sources >= 3:
        return "high"
    if sources >= 2:
        return "medium"
    return "low"
