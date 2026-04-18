"""
operator_intelligence/segment_analysis.py — Guest Segment Classifier

Classifies each review into guest segments based on textual signals.
Deterministic keyword/pattern-based — no LLM calls.
Honest: reviews with no segment signal are "unattributed", not guessed.
"""

# ============================================================================
# SHARED — NARRATIVE / PROFILE-ONLY HELPER (V3.4 origin, reused by V4)
# ----------------------------------------------------------------------------
# This module produces narrative / profile-only output. The V4 report layer
# reuses it as a text / theme source (see `operator_intelligence/v4_report_
# generator.py`) — NEVER as a score input. V4 scoring does not consume
# sentiment, aspect scores, review text, photo count, price level, social
# presence, or any other forbidden input defined in `docs/DayDine-V4-
# Scoring-Spec.md` §2.3 / `docs/DayDine-V4-Report-Spec.md` §2.3.
#
# Changes here must keep the output shape stable so V4 consumers do not
# break. See spec §8 for the narrative rules.
# ============================================================================

import re


# ---------------------------------------------------------------------------
# Segment definitions with keyword patterns
# ---------------------------------------------------------------------------

SEGMENTS = {
    "theatre_goers": {
        "label": "Theatre-Goers / Event Visitors",
        "keywords": [
            "rsc", "theatre", "theater", "show", "performance",
            "pre-theatre", "pre theatre", "pre-theater", "post-show",
            "matinee", "interval", "curtain", "before the play",
            "after the show", "before the show", "royal shakespeare",
            "shakespeare", "swan theatre", "playhouse",
        ],
    },
    "couples": {
        "label": "Couples & Occasion Diners",
        "keywords": [
            "anniversary", "birthday", "date night", "romantic",
            "celebration", "special occasion", "valentine",
            "just the two of us", "proposal", "treat", "our wedding",
            "wedding anniversary", "engaged", "honeymoon",
            "my wife", "my husband", "my partner", "my girlfriend",
            "my boyfriend", "together for",
        ],
    },
    "tourists": {
        "label": "Tourists & Visitors",
        "keywords": [
            "visiting", "holiday", "weekend away", "trip to stratford",
            "first time here", "first visit", "stumbled upon",
            "tourist", "travelled from", "traveled from",
            "recommended by hotel", "staying nearby", "passing through",
            "on holiday", "short break", "city break", "day trip",
            "not local", "from out of town", "visiting the area",
            "came to stratford", "trip to the area",
        ],
    },
    "locals": {
        "label": "Locals & Regulars",
        "keywords": [
            "regular", "local", "come here often", "our go-to",
            "been coming for years", "neighbourhood", "neighborhood",
            "live nearby", "weekly", "usual", "always come here",
            "our favourite", "our favorite", "return visit",
            "second visit", "third visit", "we always",
            "been before", "came back", "return customer",
        ],
    },
    "business": {
        "label": "Business & Group Diners",
        "keywords": [
            "work lunch", "colleagues", "conference", "business meeting",
            "team lunch", "team dinner", "group booking", "corporate",
            "christmas party", "large party", "work event",
            "business lunch", "business dinner", "office lunch",
        ],
    },
    "family": {
        "label": "Family Diners",
        "keywords": [
            "children", "kids", "family meal", "family lunch",
            "family dinner", "highchair", "high chair",
            "child-friendly", "child friendly", "grandparents",
            "with the grandparents", "family occasion",
            "with our children", "with the kids", "toddler",
            "baby", "pushchair", "pram",
        ],
    },
}


def classify_review(text, review_id=None):
    """Classify a single review into guest segments.

    Returns dict with:
      review_id: str or int
      segments: list of segment keys
      segment_evidence: list of matched keyword strings
      confidence: "high" (2+ matches or very specific), "medium" (1 match),
                  "low" (weak match)
    """
    text_lower = text.lower()
    matched_segments = {}  # segment_key -> list of matched keywords

    for seg_key, seg_def in SEGMENTS.items():
        matches = []
        for kw in seg_def["keywords"]:
            if kw in text_lower:
                matches.append(kw)
        if matches:
            matched_segments[seg_key] = matches

    if not matched_segments:
        return {
            "review_id": review_id,
            "segments": [],
            "segment_evidence": [],
            "confidence": None,
        }

    # Determine confidence
    total_matches = sum(len(m) for m in matched_segments.values())
    # Very specific keywords get high confidence even with 1 match
    high_specificity = {"rsc", "royal shakespeare", "anniversary",
                        "wedding anniversary", "pre-theatre", "pre theatre",
                        "honeymoon", "proposal", "christmas party"}
    has_specific = any(kw in high_specificity
                       for matches in matched_segments.values()
                       for kw in matches)

    if total_matches >= 2 or has_specific:
        confidence = "high"
    else:
        confidence = "medium"

    all_evidence = []
    for matches in matched_segments.values():
        all_evidence.extend(matches)

    return {
        "review_id": review_id,
        "segments": list(matched_segments.keys()),
        "segment_evidence": all_evidence,
        "confidence": confidence,
    }


def classify_all_reviews(venue_rec):
    """Classify all reviews for a venue.

    Returns dict with:
      classifications: list of per-review dicts
      segment_distribution: {segment_key: count}
      unattributed_count: int
      total_reviews: int
    """
    reviews = []
    for field in ["g_reviews", "ta_reviews"]:
        for i, rev in enumerate(venue_rec.get(field, [])):
            text = (rev.get("text") or "").strip()
            if text:
                rid = f"{field}_{i}"
                classification = classify_review(text, review_id=rid)
                classification["text"] = text
                classification["rating"] = rev.get("rating")
                classification["source"] = "google" if field == "g_reviews" else "tripadvisor"
                reviews.append(classification)

    # Distribution
    from collections import Counter
    seg_counts = Counter()
    for r in reviews:
        for seg in r["segments"]:
            seg_counts[seg] += 1
    unattributed = sum(1 for r in reviews if not r["segments"])

    return {
        "classifications": reviews,
        "segment_distribution": dict(seg_counts),
        "unattributed_count": unattributed,
        "total_reviews": len(reviews),
    }


# ---------------------------------------------------------------------------
# Segment × Aspect cross-reference
# ---------------------------------------------------------------------------

# Commercial notes per segment — what makes this segment commercially distinct
_COMMERCIAL_NOTES = {
    "theatre_goers": "This segment values speed and predictability — they have a hard deadline. Late service or unclear pre-theatre options lose them entirely.",
    "couples": "Occasion diners have high expectations and long memories. A great experience generates word-of-mouth; a disappointing one generates damaging reviews.",
    "tourists": "Tourists discover you online with no prior loyalty. Your listing, photos, and first 3 reviews are the entire decision basis.",
    "locals": "Regulars are your revenue baseline. They tolerate minor issues but notice declining consistency. Losing a regular costs 50+ future visits.",
    "business": "Business diners care about reliability and efficiency. They are repeat-booking if you deliver, and they influence colleagues.",
    "family": "Families need practical signals: highchairs, children's menu, space. Missing these isn't just inconvenient — it's exclusionary.",
}

# Unique needs per segment
_UNIQUE_NEEDS = {
    "theatre_goers": ["timing around show schedules", "quick pre-theatre menu option", "predictable service speed"],
    "couples": ["atmosphere and ambience", "attentive but not intrusive service", "occasion-worthy presentation"],
    "tourists": ["easy online discovery and booking", "clear menu and pricing", "welcoming to newcomers"],
    "locals": ["consistency across visits", "recognition and familiarity", "value for repeat custom"],
    "business": ["efficient service", "quiet enough for conversation", "reliable booking"],
    "family": ["child-friendly facilities", "flexible menu options", "relaxed pace"],
}


def _pick_quote(text, max_len=80):
    """Extract a short quote snippet."""
    sentences = re.split(r'[.!?]\s+', text)
    for s in sentences:
        s = s.strip()
        if 20 <= len(s) <= max_len:
            return s
    return text[:max_len].strip()


def generate_segment_insights(segment_data, analysis=None):
    """Cross-reference segment classifications with aspect/sentiment data.

    Args:
        segment_data: output from classify_all_reviews()
        analysis: output from analyse_reviews() (has per_review with aspects)

    Returns dict with segment_insights and unattributed_summary.
    """
    from operator_intelligence.review_analysis import ASPECT_LABELS, ASPECT_KEYWORDS

    classifications = segment_data.get("classifications", [])

    # Build per-review aspect lookup from the analysis
    # The analysis per_review list is in the same order as the reviews were fed in
    analysis_per_review = (analysis or {}).get("per_review", [])

    # Match classifications to analysis by index (both iterate g_reviews then ta_reviews)
    # Attach aspects to each classified review
    for i, cls in enumerate(classifications):
        if i < len(analysis_per_review):
            cls["_aspects"] = analysis_per_review[i].get("aspects", [])
            cls["_sentiment"] = analysis_per_review[i].get("sentiment", "neutral")
        else:
            # Run simple keyword scan for aspects
            cls["_aspects"] = _quick_aspect_scan(cls.get("text", ""))
            cls["_sentiment"] = "positive" if (cls.get("rating") or 0) >= 4 else "mixed"

    # Build segment insights
    insights = {}
    watch_list = []

    for seg_key, seg_def in SEGMENTS.items():
        seg_reviews = [c for c in classifications if seg_key in c.get("segments", [])]
        if not seg_reviews:
            continue

        if len(seg_reviews) < 2:
            # Watch list — not enough for a pattern
            r = seg_reviews[0]
            quote = _pick_quote(r.get("text", ""))
            watch_list.append({
                "segment": seg_key,
                "label": seg_def["label"],
                "review_count": 1,
                "note": f"1 review suggests this segment may be present",
                "quote": quote,
            })
            continue

        # Count aspects across this segment's reviews
        praise_counts = {}  # aspect -> count
        criticism_counts = {}
        praise_quotes = {}
        criticism_quotes = {}

        for r in seg_reviews:
            aspects = r.get("_aspects", [])
            sentiment = r.get("_sentiment", "neutral")
            rating = r.get("rating")
            text = r.get("text", "")

            for asp in aspects:
                if rating and rating >= 4:
                    praise_counts[asp] = praise_counts.get(asp, 0) + 1
                    if asp not in praise_quotes:
                        praise_quotes[asp] = _pick_quote(text)
                elif rating and rating <= 2:
                    criticism_counts[asp] = criticism_counts.get(asp, 0) + 1
                    if asp not in criticism_quotes:
                        criticism_quotes[asp] = _pick_quote(text)

        top_praise = sorted(praise_counts.items(), key=lambda x: -x[1])[:3]
        top_criticism = sorted(criticism_counts.items(), key=lambda x: -x[1])[:3]

        insights[seg_key] = {
            "label": seg_def["label"],
            "review_count": len(seg_reviews),
            "top_praise": [
                {"aspect": ASPECT_LABELS.get(a, a), "count": c,
                 "example_quote": praise_quotes.get(a, "")}
                for a, c in top_praise
            ],
            "top_criticism": [
                {"aspect": ASPECT_LABELS.get(a, a), "count": c,
                 "example_quote": criticism_quotes.get(a, "")}
                for a, c in top_criticism
            ],
            "unique_needs": _UNIQUE_NEEDS.get(seg_key, []),
            "commercial_note": _COMMERCIAL_NOTES.get(seg_key, ""),
        }

    # Unattributed summary
    unattr_reviews = [c for c in classifications if not c.get("segments")]
    unattr_aspects = {}
    for r in unattr_reviews:
        for asp in r.get("_aspects", []):
            unattr_aspects[asp] = unattr_aspects.get(asp, 0) + 1
    unattr_top = sorted(unattr_aspects.items(), key=lambda x: -x[1])[:5]

    # Detect tensions between segments
    tensions = _detect_tensions(insights)

    return {
        "segment_insights": insights,
        "watch_list": watch_list,
        "unattributed_summary": {
            "count": len(unattr_reviews),
            "top_aspects": [
                {"aspect": ASPECT_LABELS.get(a, a), "count": c}
                for a, c in unattr_top
            ],
        },
        "tensions": tensions,
    }


def _quick_aspect_scan(text):
    """Quick aspect detection for reviews without full analysis."""
    from operator_intelligence.review_analysis import ASPECT_KEYWORDS
    text_lower = text.lower()
    found = []
    for asp, kws in ASPECT_KEYWORDS.items():
        for kw in kws.get("pos", []) + kws.get("neg", []):
            if kw in text_lower:
                found.append(asp)
                break
    return found


def _detect_tensions(insights):
    """Detect conflicting needs between segments."""
    tensions = []

    # Speed vs pace tension
    speed_segments = []
    pace_segments = []
    for seg_key, data in insights.items():
        needs = data.get("unique_needs", [])
        if any("speed" in n or "quick" in n or "timing" in n for n in needs):
            speed_segments.append(data["label"])
        if any("pace" in n or "slow" in n or "relaxed" in n for n in needs):
            pace_segments.append(data["label"])
    if speed_segments and pace_segments:
        tensions.append({
            "tension": "Speed vs Pace",
            "segments": speed_segments + pace_segments,
            "note": (f"{', '.join(speed_segments)} want fast, predictable service. "
                     f"{', '.join(pace_segments)} want a relaxed pace. "
                     f"These needs conflict — consider whether your service model "
                     f"can flex by time slot (pre-theatre = fast track, weekend = leisurely)."),
        })

    # Discovery vs loyalty tension
    discovery = [d["label"] for k, d in insights.items() if k in ("tourists",)]
    loyalty = [d["label"] for k, d in insights.items() if k in ("locals",)]
    if discovery and loyalty:
        tensions.append({
            "tension": "Discovery vs Loyalty",
            "segments": discovery + loyalty,
            "note": (f"{', '.join(discovery)} need online proof to choose you. "
                     f"{', '.join(loyalty)} need consistency to stay. "
                     f"Investing in digital presence serves discovery; "
                     f"investing in consistency serves retention. Both matter."),
        })

    return tensions
