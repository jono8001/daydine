"""Data Basis section — what this report is built on."""

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


def build_data_basis(w, venue_rec, review_intel):
    """Render the Data Basis section — compact evidence overview."""
    from operator_intelligence.evidence_base import compute_evidence_base

    eb = compute_evidence_base(venue_rec)
    t1 = eb["evidence_tiers"]["tier_1_deep_analysis"]
    t2 = eb["evidence_tiers"]["tier_2_aggregate_signals"]
    t3 = eb["evidence_tiers"]["tier_3_structural_signals"]
    divergence = eb.get("platform_divergence")

    w("## Data Basis\n")
    w("This report draws on three layers of evidence:\n")

    w("| Layer | What | Count | Confidence |")
    w("|---|---|---|---|")
    w(f"| Deep analysis | Text reviewed, themes extracted, segments identified "
      f"| {t1['total']} reviews ({t1['google_count']} Google, "
      f"{t1['tripadvisor_count']} TripAdvisor) | {t1['confidence']} |")
    w(f"| Aggregate signals | Rating and volume from all platforms "
      f"| {t2['google_total_reviews']:,} Google ({t2['google_rating']}★), "
      f"{t2['tripadvisor_total_reviews']} TripAdvisor "
      f"({t2['tripadvisor_rating']}★) | {t2['confidence']} |")
    w(f"| Structural data | FSA record, Google Business Profile, web presence "
      f"| {t3['source_count']} sources | {t3['confidence']} |")
    w("")

    w(f"**What this means:** The narrative insights (themes, complaints, praise, "
      f"segment reads) are based on {t1['total']} deeply-analysed recent reviews "
      f"— a detailed sample, not a census. The aggregate {t2['google_rating']} "
      f"rating across {t2['google_total_reviews']:,} Google reviews is the "
      f"reputation bedrock and is factored into scoring separately.\n")

    if divergence:
        w(f"**Platform note:** Google ({divergence['google_rating']}) and "
          f"TripAdvisor ({divergence['tripadvisor_rating']}) ratings diverge by "
          f"{abs(divergence['difference']):.1f} points. "
          f"{divergence['hypothesis']}\n")

    # Confidence warnings for thin data
    total_deep = t1["total"]
    source_count = sum(1 for s in [t1["google_count"], t1["tripadvisor_count"]] if s > 0)

    if total_deep < 50:
        tier = "Indicative" if total_deep < 25 else "Directional"
        w(f"⚠️ **Data Confidence: {tier}.** This report is based on {total_deep} "
          f"reviews from {source_count} source(s), which is below our recommended "
          f"minimum of 50. Findings should be treated as indicative rather than conclusive.\n")

    if source_count <= 1:
        source_name = "Google" if t1["google_count"] > 0 else "TripAdvisor" if t1["tripadvisor_count"] > 0 else "unknown"
        w(f"ℹ️ Reviews are from a single source ({source_name}). "
          f"Cross-platform validation is not possible.\n")
