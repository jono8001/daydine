"""
operator_intelligence/consistency_checker.py — Cross-Section Consistency Checker

Runs after all report sections are generated. Detects contradictions
between sections — priority conflicts, tone mismatches, numeric
inconsistencies, and classification disagreements.
"""

import re


def check_consistency(report_text, recs, scorecard):
    """Run all consistency checks against the assembled report.

    Returns dict with contradictions_found, warnings, and clean status.
    """
    contradictions = []
    warnings = []

    # 1. Priority vs "Do not prioritise" conflict
    contradictions += _check_priority_conflicts(report_text, recs)

    # 2. Numeric contradictions (same metric, different values)
    contradictions += _check_numeric_consistency(report_text, scorecard)

    # 3. Classification contradictions (FIX in one place, WATCH in another)
    warnings += _check_classification_consistency(report_text)

    # 4. Tone contradictions (not urgent + urgent language on same topic)
    warnings += _check_tone_consistency(report_text)

    return {
        "contradictions_found": contradictions,
        "warnings": warnings,
        "clean": len(contradictions) == 0,
        "contradiction_count": len(contradictions),
        "warning_count": len(warnings),
    }


def _check_priority_conflicts(report_text, recs):
    """Check that 'do not prioritise' items don't appear as high-priority actions."""
    issues = []
    dont = recs.get("what_not_to_do")
    if not dont:
        return issues

    dont_title = dont.get("title", "").lower().strip()
    if not dont_title:
        return issues

    # Search for this title in action/priority contexts
    # Look for the title near "Priority: High" or "[FIX"
    text_lower = report_text.lower()
    title_positions = [m.start() for m in re.finditer(re.escape(dont_title), text_lower)]

    for pos in title_positions:
        context = text_lower[max(0, pos - 100):pos + 200]
        # Skip if in the "do not prioritise" line itself
        if "do not prioritise" in context or "deprioritised" in context:
            continue
        # Skip "What Not to Do" section
        if "what not to do" in context:
            continue
        # Check for high-priority language nearby
        if "priority: high" in context or "[fix" in context:
            issues.append({
                "type": "priority_conflict",
                "item": dont.get("title"),
                "detail": "Item designated 'do not prioritise' appears with high-priority language",
                "severity": "high",
                "position": pos,
            })

    return issues


def _check_numeric_consistency(report_text, scorecard):
    """Check that the same metric shows the same value where explicitly labelled."""
    issues = []

    # Check overall score: look for "Overall score: X.X" or "overall: X.X/10"
    overall = scorecard.get("overall")
    if overall is not None:
        score_str = f"{overall:.1f}"
        # Only match explicitly labelled "overall" scores, not dimension scores
        overall_mentions = re.findall(
            r'(?:overall\s+score[:\s]+)(\d+\.\d)/10', report_text.lower())
        for mention in overall_mentions:
            if abs(float(mention) - overall) >= 0.1:
                issues.append({
                    "type": "numeric_mismatch",
                    "item": f"Overall score: '{mention}/10' vs scorecard {score_str}/10",
                    "severity": "high",
                })
                break

    # Check Google rating: only match "Google" within 10 chars of "X.X/5"
    gr = scorecard.get("google_rating")
    if gr is not None:
        gr_str = str(gr)
        # Match "X.X/5 Google" or "Google X.X/5" within tight proximity
        for match in re.finditer(r'(\d\.\d)/5', report_text):
            val = match.group(1)
            context = report_text[max(0, match.start() - 20):match.end() + 20].lower()
            # Must mention Google, not TripAdvisor, and not be a peer comparison
            if ("google" in context and "tripadvisor" not in context
                    and "vs your" not in context and "their" not in context
                    and "competitor" not in context):
                if abs(float(val) - float(gr)) >= 0.1:
                    issues.append({
                        "type": "numeric_mismatch",
                        "item": f"Google rating: '{val}/5' vs data {gr_str}/5",
                        "severity": "high",
                    })
                    break

    return issues


def _check_classification_consistency(report_text):
    """Check that items aren't tagged with conflicting classifications."""
    warnings = []

    # Extract all [FIX], [WATCH], [EXPLOIT], [PROTECT] tags with their titles
    tags = re.findall(r'(?:###?\s+.*?)([\w\s—\'\.]+?)\s*\[(FIX|WATCH|EXPLOIT|PROTECT|MAINTAIN)', report_text)

    # Group by normalised title
    title_tags = {}
    for title, tag in tags:
        clean = title.strip().lower()[:40]
        if clean not in title_tags:
            title_tags[clean] = set()
        title_tags[clean].add(tag.upper())

    for title, tag_set in title_tags.items():
        if len(tag_set) > 1:
            warnings.append({
                "type": "classification_conflict",
                "item": title.strip(),
                "tags_found": list(tag_set),
                "detail": f"Item has multiple classifications: {', '.join(tag_set)}",
                "severity": "medium",
            })

    return warnings


def _check_tone_consistency(report_text):
    """Check for tone contradictions on the same topic."""
    warnings = []

    # Check trust tone: if one place says "not urgent" and another says urgent
    trust_sections = []
    for pattern in [r'trust.*?(?:not urgent|not a.*?problem|not critical|viable)',
                    r'trust.*?(?:urgent|critical|crisis|immediate)']:
        matches = re.findall(pattern, report_text.lower()[:5000])
        trust_sections.extend(matches)

    not_urgent = any("not" in m for m in trust_sections)
    urgent = any(m for m in trust_sections if "not" not in m and
                 any(w in m for w in ["urgent", "critical", "crisis", "immediate"]))

    if not_urgent and urgent:
        warnings.append({
            "type": "tone_conflict",
            "topic": "trust",
            "detail": "Trust is described as both 'not urgent' and 'urgent' in different sections",
            "severity": "medium",
        })

    return warnings
