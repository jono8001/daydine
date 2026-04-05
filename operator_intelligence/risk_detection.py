"""
operator_intelligence/risk_detection.py — Dedicated Risk Detection Layer

Scans raw review data for operational, legal, and reputational risks.
Independent of theme classification — catches patterns that get diluted
across themes.

Six risk categories: 3 RED FLAG (any mention), 3 AMBER WARNING (threshold-based).
"""

import re


# ---------------------------------------------------------------------------
# Risk taxonomy — thresholds and keyword patterns
# ---------------------------------------------------------------------------

RISK_CATEGORIES = {
    # RED FLAG — any single mention triggers
    "legal_regulatory": {
        "label": "Legal & Regulatory Risk",
        "severity": "red",
        "threshold": 1,
        "keywords": [
            "food poisoning", "ill after", "sick after eating", "cockroach", "rat ",
            "mouse", "hair in my", "foreign object", "raw chicken", "undercooked chicken",
            "allergen", "allergic reaction", "cross contamin", "anaphyla", "epipen",
            "environmental health", "trading standards", "solicitor", "sue",
            "report to", "health hazard", "food standards",
        ],
        "consequence": "Could trigger Environmental Health investigation or legal action.",
    },
    "staff_conduct": {
        "label": "Staff Conduct Risk",
        "severity": "red",
        "threshold": 1,  # but pattern at 2+
        "keywords": [
            "aggressive", "hostile", "confrontational", "discriminat", "racist",
            "sexist", "harass", "threaten", "inappropriate behaviour",
            "appalled", "turned away", "refused entry",
            "made to feel unwelcome", "not welcome",
            "disabled", "wheelchair", "walker", "mobility",
            "could not have a table", "couldn't sit",
        ],
        # Filter: "disabled" in positive context should not trigger
        "require_negative_context": True,
        "consequence": "Could constitute discrimination under the Equality Act 2010.",
    },
    "safety_premises": {
        "label": "Safety & Premises Risk",
        "severity": "red",
        "threshold": 1,
        "keywords": [
            "fell over", "tripped on", "slipped", "injury", "injured",
            "broken chair", "broken glass", "cut myself",
            "fire exit blocked", "overcrowd", "unsanitary", "filthy",
            "mould", "mold",
        ],
        # Explicit: "trip to Stratford" is NOT a safety issue
        "false_positive_filters": ["trip to", "our trip", "day trip", "next trip",
                                    "business trip", "trip away"],
        "consequence": "Could result in injury claim or premises licence review.",
    },
    # AMBER WARNING — threshold-based
    "staffing_pattern": {
        "label": "Staffing / Operational Failure Pattern",
        "severity": "amber",
        "threshold": 3,
        "keywords": [
            "understaffed", "only one person", "couldn't find staff",
            "no one around", "waited 40", "waited 30", "waited an hour",
            "lost our order", "forgot our order", "wrong order",
            "lost reservation", "no record of booking",
            "new staff", "untrained", "didn't know what they were doing",
        ],
        "consequence": "Suggests systemic operational issue, not a one-off bad night.",
    },
    "reputation_trajectory": {
        "label": "Reputation Trajectory Risk",
        "severity": "amber",
        "threshold": 3,
        "keywords": [
            "used to be good", "gone downhill", "won't return", "never again",
            "not what it was", "declining", "worse than before",
            "last time we come", "not coming back",
        ],
        "consequence": "Pattern of declining guest satisfaction — revenue risk if sustained.",
    },
    "financial_value": {
        "label": "Financial / Value Risk",
        "severity": "amber",
        "threshold": 3,
        "keywords": [
            "overpriced", "rip off", "rip-off", "not worth it",
            "overcharged", "wrong bill", "hidden charge", "extortionate",
            "too expensive for what you get",
        ],
        "consequence": "Value perception driving customers to competitors.",
    },
}


def _is_false_positive(text_lower, cat_def, keyword_matched):
    """Check if a keyword match is a false positive."""
    filters = cat_def.get("false_positive_filters", [])
    for fp in filters:
        if fp in text_lower:
            return True
    return False


def _has_negative_context(text_lower, rating):
    """Check if the review has negative context (for categories that require it)."""
    if rating is not None and rating <= 2:
        return True
    negative_signals = ["appalled", "disgust", "awful", "terrible", "worst",
                        "never again", "avoid", "complained", "unacceptable",
                        "refused", "turned away", "could not", "couldn't"]
    return any(sig in text_lower for sig in negative_signals)


def scan_reviews_for_risks(venue_rec):
    """Scan all raw reviews for risk indicators.

    Returns dict with:
      alerts: list of active risk alerts (above threshold)
      all_hits: all individual review-risk matches (for audit)
      clean: bool — True if no alerts
    """
    reviews = []
    for field in ["g_reviews", "ta_reviews"]:
        for i, rev in enumerate(venue_rec.get(field, [])):
            text = (rev.get("text") or "").strip()
            if text:
                reviews.append({
                    "text": text,
                    "rating": rev.get("rating"),
                    "source": "Google" if field == "g_reviews" else "TripAdvisor",
                    "index": i,
                })

    # Scan each review against each risk category
    category_hits = {cat: [] for cat in RISK_CATEGORIES}

    for rev in reviews:
        text_lower = rev["text"].lower()
        rating = rev["rating"]

        for cat_key, cat_def in RISK_CATEGORIES.items():
            matched_keywords = []
            for kw in cat_def["keywords"]:
                if kw in text_lower:
                    # Check for false positives
                    if _is_false_positive(text_lower, cat_def, kw):
                        continue
                    # Check if negative context required
                    if cat_def.get("require_negative_context"):
                        if not _has_negative_context(text_lower, rating):
                            continue
                    matched_keywords.append(kw)

            if matched_keywords:
                category_hits[cat_key].append({
                    "review_text": rev["text"],
                    "rating": rating,
                    "source": rev["source"],
                    "keywords_matched": matched_keywords,
                    "snippet": rev["text"][:150],
                })

    # Build alerts for categories that meet their threshold
    alerts = []
    for cat_key, cat_def in RISK_CATEGORIES.items():
        hits = category_hits[cat_key]
        if len(hits) >= cat_def["threshold"]:
            # Pick the most illustrative quotes
            quotes = []
            for h in hits[:3]:
                # Extract the sentence containing the keyword
                text = h["review_text"]
                for kw in h["keywords_matched"]:
                    pos = text.lower().find(kw)
                    if pos >= 0:
                        start = max(0, pos - 40)
                        end = min(len(text), pos + len(kw) + 80)
                        snippet = text[start:end].strip()
                        if start > 0:
                            snippet = "..." + snippet
                        if end < len(text):
                            snippet = snippet + "..."
                        quotes.append(snippet)
                        break
                else:
                    quotes.append(h["snippet"][:120])

            alerts.append({
                "category": cat_key,
                "label": cat_def["label"],
                "severity": cat_def["severity"],
                "review_count": len(hits),
                "threshold": cat_def["threshold"],
                "consequence": cat_def["consequence"],
                "quotes": quotes[:3],
                "keywords_found": list(set(
                    kw for h in hits for kw in h["keywords_matched"]
                )),
            })

    return {
        "alerts": sorted(alerts, key=lambda a: (0 if a["severity"] == "red" else 1, -a["review_count"])),
        "all_hits": {k: len(v) for k, v in category_hits.items()},
        "reviews_scanned": len(reviews),
        "clean": len(alerts) == 0,
    }
