"""Review & reputation intelligence section builder — two modes."""

from operator_intelligence.review_delta import ASPECT_LABELS
from operator_intelligence.report_spec import MODE_NARRATIVE


def build(w, mode, review_intel, review_delta):
    w("## Review & Reputation Intelligence\n")
    if mode != MODE_NARRATIVE:
        _structured(w, review_intel)
    else:
        _narrative(w, review_intel, review_delta)


def _structured(w, ri):
    """Signal-led analysis — honest about no text."""
    w("**Source coverage:** No individual review text collected. "
      "Analysis below uses aggregated rating and volume signals.\n")
    grc = ri.get("review_count_google") if ri else None
    if grc is not None:
        if grc >= 500:
            w(f"- **Review volume ({grc}):** Strong social proof. Rating stable.")
        elif grc >= 100:
            w(f"- **Review volume ({grc}):** Adequate. Continue building authority.")
        elif grc >= 20:
            w(f"- **Review volume ({grc}):** Moderate. A few negatives shift your average.")
        else:
            w(f"- **Review volume ({grc}):** Low. Rating is fragile.")
    trc = ri.get("review_count_ta") if ri else None
    if trc and trc > 0:
        w(f"- **TripAdvisor:** {trc} reviews — cross-platform credibility.")
    else:
        w("- **TripAdvisor:** No presence. Missed discovery channel.")
    ext = ri.get("aspects") if ri else None
    if ext and isinstance(ext, dict):
        aspects = ext.get("aspects", ext)
        if isinstance(aspects, dict) and aspects:
            w("\n**Pre-computed aspect sentiment:**\n")
            for asp, data in aspects.items():
                if isinstance(data, dict):
                    sc = data.get("score", data.get("sentiment"))
                    pos = data.get("positive_mentions", data.get("positive", 0))
                    neg = data.get("negative_mentions", data.get("negative", 0))
                    w(f"- **{asp.replace('_', ' ').title()}:** {sc}/10 ({pos}+, {neg}-)")
    w("\n*Run Google Places review text enrichment to unlock narrative analysis.*\n")


def _narrative(w, ri, rd):
    """Full sentiment with quotes — only with real review text."""
    n = ri.get("reviews_analyzed", 0)
    w(f"**Based on {n} customer reviews with full text analysis.**\n")
    aspects = ri.get("aspect_scores", {})
    if aspects:
        w("### Sentiment by Topic\n")
        w("| Topic | Score | + | - | Read |")
        w("|-------|------:|--:|--:|------|")
        for asp, d in sorted(aspects.items(), key=lambda x: -x[1].get("sentiment", 0)):
            s = d.get("sentiment", 0)
            lbl = ASPECT_LABELS.get(asp, asp.replace("_", " ").title())
            read = "Strength" if s >= 8 else "Positive" if s >= 6 else "Mixed" if s >= 4 else "Concern"
            w(f"| {lbl} | {s:.1f}/10 | {d.get('positive', 0)} | {d.get('negative', 0)} | {read} |")
        w("")
    for key, title in [("praise_themes", "What Customers Praise"),
                       ("criticism_themes", "What Needs Attention")]:
        themes = ri.get(key, [])
        if themes:
            w(f"### {title}\n")
            for t in themes:
                w(f"**{t['label']}** ({t['mentions']} mentions)")
                for q in t.get("quotes", []):
                    w(f'> *"{q}"*')
                w("")
    pos_q = ri.get("strongest_positive_quotes", [])
    neg_q = ri.get("strongest_constructive_quotes", [])
    if pos_q or neg_q:
        w("### Key Quotes\n")
        if pos_q:
            w("**Strongest positive:**")
            for q in pos_q[:2]:
                w(f'> *"{q}"*')
            w("")
        if neg_q:
            w("**Strongest constructive:**")
            for q in neg_q[:2]:
                w(f'> *"{q}"*')
            w("")
    if rd and rd.get("has_delta"):
        w("### Narrative Shifts vs Prior Month\n")
        for kind, label in [("new_aspects", "Emerging"), ("fading_aspects", "Fading")]:
            items = rd.get(kind, [])
            if items:
                labels = [ASPECT_LABELS.get(a, a) for a in items]
                w(f"**{label}:** {', '.join(labels)}\n")
