"""Guest Segment Intelligence section builder."""

# ============================================================================
# LEGACY (V3.4) — NOT PART OF THE ACTIVE V4 PATH
# ----------------------------------------------------------------------------
# This module is part of the DayDine V3.4 scoring / reporting layer. V4 is
# now the active model (`rcs_scoring_v4.py` + `operator_intelligence/v4_*.py`).
# This file is retained only for rollback, comparison against V4 output
# (via `compare_v3_v4.py`), and historical reference.
#
# Do NOT import this module from any V4 code path. The boundary check in
# `tests/test_v4_legacy_boundary.py` enforces this.
#
# See `docs/DayDine-Legacy-Quarantine-Note.md` for conditions under which
# this file becomes safe to delete.
# ============================================================================

from operator_intelligence.segment_analysis import SEGMENTS
from operator_intelligence.review_analysis import ASPECT_LABELS


def build_segment_intelligence(w, venue_rec, review_intel):
    """Render 'Who's Telling You What — Guest Segment Intelligence' section."""
    from operator_intelligence.segment_analysis import (
        classify_all_reviews, generate_segment_insights,
    )

    seg_data = classify_all_reviews(venue_rec)
    analysis = (review_intel or {}).get("analysis")
    intel = generate_segment_insights(seg_data, analysis)

    total = seg_data["total_reviews"]
    unattr = seg_data["unattributed_count"]
    attributed = total - unattr
    attr_pct = round(attributed / max(1, total) * 100)

    w("## Who's Telling You What — Guest Segment Intelligence\n")
    w("*Different guests experience your venue differently. "
      "Here's what each group is telling you.*\n")
    w(f"**Data basis:** {attributed} of {total} reviews ({attr_pct}%) "
      f"contained enough context to identify the guest type. "
      f"Segments below require ≥2 reviews to surface a pattern.\n")

    # Segment blocks (only those with ≥2 reviews)
    insights = intel.get("segment_insights", {})
    for seg_key in ["theatre_goers", "couples", "tourists", "locals", "business", "family"]:
        data = insights.get(seg_key)
        if not data:
            continue

        w(f"### {data['label']} ({data['review_count']} reviews)\n")

        # What they value
        if data["top_praise"]:
            praise_parts = []
            for p in data["top_praise"][:3]:
                part = f"{p['aspect']} ({p['count']}x)"
                if p.get("example_quote"):
                    short = p["example_quote"][:60]
                    part += f' — *"{short}"*'
                praise_parts.append(part)
            w(f"**What they value:** {'; '.join(praise_parts)}\n")
        else:
            w("**What they value:** Positive across the board — no single standout aspect.\n")

        # Where you lose them
        if data["top_criticism"]:
            crit_parts = []
            for c in data["top_criticism"][:3]:
                part = f"{c['aspect']} ({c['count']}x)"
                if c.get("example_quote"):
                    short = c["example_quote"][:60]
                    part += f' — *"{short}"*'
                crit_parts.append(part)
            w(f"**Where you lose them:** {'; '.join(crit_parts)}\n")
        else:
            w("**Where you lose them:** No recurring complaints from this segment.\n")

        # Commercial read
        if data.get("commercial_note"):
            w(f"**Commercial read:** {data['commercial_note']}\n")

    # Tensions
    tensions = intel.get("tensions", [])
    if tensions:
        w("### Segment Tensions\n")
        w("*These segments have conflicting needs. Managing the tension "
          "is more valuable than ignoring it.*\n")
        for t in tensions:
            w(f"**{t['tension']}:** {t['note']}\n")

    # Watch list
    watch = intel.get("watch_list", [])
    if watch:
        w("### Watch List (single-review signals — not yet patterns)\n")
        for item in watch:
            w(f"- 1 review suggests **{item['label']}** may be present"
              f' — *"{item["quote"][:60]}"*')
        w("")

    # Unattributed
    unattr_data = intel.get("unattributed_summary", {})
    if unattr_data.get("count", 0) > 0:
        w(f"### Unattributed Reviews ({unattr_data['count']})\n")
        aspects = unattr_data.get("top_aspects", [])
        if aspects:
            asp_str = ", ".join(f"{a['aspect']} ({a['count']}x)" for a in aspects[:5])
            w(f"Top themes across unattributed reviews: {asp_str}.\n")
        w("*As review volume grows, more segments will become readable.*\n")
