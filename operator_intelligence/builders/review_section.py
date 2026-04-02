"""Review & reputation intelligence section builder — uses deep analysis engine."""

from operator_intelligence.report_spec import MODE_NARRATIVE, assess_review_confidence
from operator_intelligence.review_analysis import ASPECT_LABELS


def build(w, mode, review_intel, review_delta):
    w("## Review & Reputation Intelligence\n")
    if mode != MODE_NARRATIVE:
        _structured(w, review_intel)
    else:
        _narrative(w, review_intel, review_delta)


def _structured(w, ri):
    """Signal-led analysis — no review text available."""
    w("**Source coverage:** No individual review text collected. "
      "Analysis below uses aggregated rating and volume signals.\n")

    vol = ri.get("volume_signals") if ri else None
    if vol:
        w(f"### Rating & Volume Position\n")
        w(f"- **Volume:** {vol.get('volume_note', 'Unknown')}")
        w(f"- **Rating position:** {vol.get('rating_note', 'Unknown')}")
        w("")

    grc = ri.get("review_count_google") if ri else None
    if grc is not None and not vol:
        if grc >= 500:
            w(f"- **Review volume ({grc:,}):** Statistically robust. Rating stable.")
        elif grc >= 100:
            w(f"- **Review volume ({grc}):** Adequate base for rating stability.")
        elif grc >= 20:
            w(f"- **Review volume ({grc}):** Moderate. Rating is volatile.")
        else:
            w(f"- **Review volume ({grc}):** Low. Rating is fragile.")

    trc = ri.get("review_count_ta") if ri else None
    if trc and trc > 0:
        w(f"- **TripAdvisor:** {trc} reviews — cross-platform credibility.")
    else:
        w("- **TripAdvisor:** No presence detected.")

    w("\n*Run Google Places review text enrichment to unlock full narrative analysis.*\n")


def _narrative(w, ri, rd):
    """Full review intelligence from actual review text."""
    analysis = ri.get("analysis")
    vol = ri.get("volume_signals")

    if not analysis:
        w("*Review text collected but analysis unavailable.*\n")
        return

    n = analysis.get("reviews_analyzed", 0)
    rc = assess_review_confidence(ri)
    w(f"**Based on {n} customer reviews with full text analysis.**")
    w(f"**Evidence tier: {rc.tier.title()}** — {rc.qualifier}.\n")

    # --- Rating & Volume Context ---
    if vol:
        w("### Rating & Volume Context\n")
        w(f"- {vol.get('volume_note', '')}")
        w(f"- {vol.get('rating_note', '')}")

        # Sample vs aggregate comparison
        sample_avg = analysis.get("average_sample_rating")
        agg_rating = vol.get("aggregate_rating")
        if sample_avg is not None and agg_rating is not None:
            diff = sample_avg - agg_rating
            if abs(diff) < 0.2:
                w(f"- **Sample vs aggregate:** The {n} analysed reviews average "
                  f"{sample_avg:.1f}★, consistent with the overall {agg_rating}/5. "
                  f"No divergence detected.")
            elif diff > 0:
                w(f"- **Sample vs aggregate:** Analysed reviews average {sample_avg:.1f}★ "
                  f"vs overall {agg_rating}/5. Recent/prominent reviews skew higher than "
                  f"the lifetime average — may indicate improvement or selection bias "
                  f"in Google's 'most relevant' algorithm.")
            else:
                w(f"- **Sample vs aggregate:** Analysed reviews average {sample_avg:.1f}★ "
                  f"vs overall {agg_rating}/5. Prominent reviews are below the lifetime "
                  f"average — this warrants attention.")
        w("")

    # --- Sentiment Distribution ---
    sent_dist = analysis.get("sentiment_distribution", {})
    if sent_dist:
        total = sum(sent_dist.values())
        pos = sent_dist.get("positive", 0)
        neg = sent_dist.get("negative", 0)
        mixed = sent_dist.get("mixed", 0)
        w(f"### Sentiment Distribution\n")
        w(f"Of {total} reviews analysed: **{pos} positive**, "
          f"**{neg} negative**, **{mixed} mixed**.\n")
        if neg == 0 and total >= 3:
            w("All sampled reviews are positive. This is encouraging but note that "
              "Google's 'most relevant' algorithm tends to surface popular reviews. "
              "Negative signals may exist deeper in the review corpus.\n")

    # --- Aspect Sentiment Table ---
    aspects = analysis.get("aspect_scores", {})
    if aspects:
        w("### Sentiment by Topic\n")
        w("| Topic | Score | Positive | Negative | Total | Read |")
        w("|-------|------:|---------:|---------:|------:|------|")
        for asp, data in sorted(aspects.items(), key=lambda x: -x[1].get("mentions", 0)):
            label = ASPECT_LABELS.get(asp, asp.replace("_", " ").title())
            score = data.get("score", 0)
            read = "Strength" if score >= 8 else "Positive" if score >= 6 else "Mixed" if score >= 4 else "Concern"
            w(f"| {label} | {score:.1f}/10 | {data.get('positive', 0)} | "
              f"{data.get('negative', 0)} | {data.get('mentions', 0)} | {read} |")
        w("")

    # --- Praise Themes with Quotes ---
    praise = analysis.get("praise_themes", [])
    if praise:
        w("### What Customers Praise\n")
        for theme in praise:
            w(f"**{theme['label']}** ({theme['mentions']} positive mentions)")
            for q in theme.get("quotes", [])[:2]:
                w(f'> *"{q}"*')
            if not theme.get("quotes"):
                w(f"*Keywords detected but no single sentence captures this theme cleanly.*")
            w("")

    # --- Criticism Themes with Quotes ---
    criticism = analysis.get("criticism_themes", [])
    if criticism:
        w("### What Needs Attention\n")
        for theme in criticism:
            w(f"**{theme['label']}** ({theme['mentions']} negative mentions)")
            for q in theme.get("quotes", [])[:2]:
                w(f'> *"{q}"*')
            w("")
    elif praise:
        w("### Criticism Assessment\n")
        w(f"No negative themes detected across {n} analysed reviews. "
          "While positive, note that Google surfaces its 'most relevant' reviews "
          "first, which skew positive for well-rated venues. "
          "To validate, check the most recent 1-2 star reviews directly "
          "on Google Maps — these may reveal issues not captured here.\n")

    # --- Risk Flags ---
    risks = analysis.get("risk_flags", [])
    if risks:
        w("### Risk Flags\n")
        w(f"**{len(risks)} risk phrase(s) detected:** {', '.join(risks)}\n")
        w("These phrases in customer reviews represent reputational risk. "
          "Investigate the specific incidents referenced and ensure they "
          "have been operationally resolved.\n")

    # --- Rating Trajectory ---
    trajectory = analysis.get("trajectory")
    if trajectory:
        w("### Rating Trajectory\n")
        if trajectory == "improving":
            w("Recent reviews trend higher than earlier ones in the sample. "
              "This may indicate recent operational improvements landing with customers.\n")
        elif trajectory == "declining":
            w("**Recent reviews trend lower than earlier ones.** This is an "
              "early warning signal. Investigate what changed operationally "
              "in the last 1-2 months.\n")
        else:
            w("Rating across the sample is stable — no significant upward or "
              "downward trajectory detected.\n")

    # --- Per-Review Breakdown ---
    per_review = analysis.get("per_review", [])
    if per_review:
        w("### Review-by-Review Summary\n")
        w("| # | Rating | Sentiment | Topics | Snippet |")
        w("|--:|-------:|-----------|--------|---------|")
        for i, rev in enumerate(per_review, 1):
            topics = ", ".join(ASPECT_LABELS.get(a, a) for a in rev.get("aspects", [])[:3])
            snippet = rev.get("snippet", "")[:80]
            w(f"| {i} | {rev.get('rating', '—')}★ | {rev.get('sentiment', '—')} | "
              f"{topics or '—'} | {snippet}{'...' if len(rev.get('snippet', '')) > 80 else ''} |")
        w("")

    # --- Delta vs Prior Month ---
    if rd and rd.get("has_delta"):
        w("### Narrative Shifts vs Prior Month\n")
        for kind, label_text in [("new_aspects", "Emerging topics"),
                                  ("fading_aspects", "Fading topics")]:
            items = rd.get(kind, [])
            if items:
                labels = [ASPECT_LABELS.get(a, a) for a in items]
                w(f"**{label_text}:** {', '.join(labels)}\n")

    # --- Data Limitation Note ---
    review_count = ri.get('volume_signals', {}).get('review_count', 0)
    ta_count = ri.get("review_count_ta") or 0
    w("### Analysis Limitations\n")
    if ta_count > 0:
        w(f"**Evidence tier: {rc.tier.title()}.** This analysis is based on {n} reviews "
          f"from Google ({n - ta_count}) and TripAdvisor ({ta_count}). "
          f"Google reviews are limited to 5 per venue via the API; TripAdvisor reviews "
          f"were collected via Apify scraper. "
          "Claims above are calibrated to this evidence level — themes are observed "
          "across two independent platforms, strengthening confidence.\n")
    else:
        w(f"**Evidence tier: {rc.tier.title()}.** This analysis is based on {n} reviews "
          f"surfaced by Google's 'most relevant' algorithm out of {review_count:,} total. "
          "The Google Places API limits retrieval to 5 reviews per venue with no pagination "
          "or sort control. This sample is likely skewed toward popular positive reviews "
          "and may not represent the full sentiment distribution. "
          "Claims above are calibrated to this evidence level — themes are observed, "
          "not confirmed as settled reputation patterns.\n")
