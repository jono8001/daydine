"""Data Basis section — what this report is built on."""


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
