"""Review & reputation intelligence section builder — business intelligence focus."""

from operator_intelligence.report_spec import MODE_NARRATIVE, assess_review_confidence
from operator_intelligence.review_analysis import ASPECT_LABELS


# ---------------------------------------------------------------------------
# Evidence-language helpers
# ---------------------------------------------------------------------------

def _strength_read(score, mentions):
    """Convert a numeric aspect score + mention count into an evidence-weighted
    plain-language read. Avoids false precision from small samples."""
    if mentions <= 2:
        if score >= 7:
            return "positive signal, limited evidence"
        elif score >= 4:
            return "mixed, limited evidence"
        else:
            return "emerging concern, limited evidence"
    if score >= 8.5:
        return "consistent praise"
    if score >= 7:
        return "strong positive signal"
    if score >= 5:
        return "mixed"
    if score >= 3:
        return "emerging concern"
    return "significant concern"


def _confidence_language(rc):
    """Return (adjective, hedge) appropriate to the confidence tier."""
    mapping = {
        "anecdotal": ("limited", "Early impressions suggest"),
        "indicative": ("early", "The available evidence points toward"),
        "directional": ("moderate", "Review evidence supports"),
        "established": ("strong", "There is clear evidence that"),
    }
    return mapping.get(rc.tier, ("insufficient", "There is not enough data to assess"))


def _pick_best_quote(quotes, max_len=120):
    """Return the single most illustrative quote, or None."""
    if not quotes:
        return None
    # Prefer shorter, punchier quotes that still have substance
    candidates = [q for q in quotes if 30 <= len(q) <= max_len]
    if candidates:
        return candidates[0]
    return quotes[0][:max_len] + "..." if quotes else None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build(w, mode, review_intel, review_delta):
    w("## Review & Reputation Intelligence\n")
    if mode != MODE_NARRATIVE:
        _structured(w, review_intel)
    else:
        _narrative(w, review_intel, review_delta)


# ---------------------------------------------------------------------------
# Structured mode (no review text available)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Narrative mode (full review text available)
# ---------------------------------------------------------------------------

def _narrative(w, ri, rd):
    """Full business intelligence from review text."""
    analysis = ri.get("analysis")
    vol = ri.get("volume_signals")

    if not analysis:
        w("*Review text collected but analysis unavailable.*\n")
        return

    n = analysis.get("reviews_analyzed", 0)
    rc = assess_review_confidence(ri)
    adj, _ = _confidence_language(rc)

    # Gather core data structures
    aspects = analysis.get("aspect_scores", {})
    praise = analysis.get("praise_themes", [])
    criticism = analysis.get("criticism_themes", [])
    risks = analysis.get("risk_flags", [])
    trajectory = analysis.get("trajectory")
    sent_dist = analysis.get("sentiment_distribution", {})

    # Sort aspects by mention volume
    sorted_aspects = sorted(aspects.items(), key=lambda x: -x[1].get("mentions", 0))
    top_aspects = sorted_aspects[:3] if sorted_aspects else []
    weak_aspects = [
        (k, v) for k, v in sorted_aspects if v.get("score", 10) < 5 and v.get("mentions", 0) >= 2
    ]

    # -----------------------------------------------------------------------
    # 1. What Guests Value Most
    # -----------------------------------------------------------------------
    w("### What Guests Value Most\n")

    if not praise and not top_aspects:
        w("Insufficient review data to identify guest value drivers.\n")
    else:
        _, hedge = _confidence_language(rc)
        paragraphs = []

        for asp_key, asp_data in top_aspects:
            label = ASPECT_LABELS.get(asp_key, asp_key.replace("_", " ").title())
            score = asp_data.get("score", 0)
            mentions = asp_data.get("mentions", 0)
            read = _strength_read(score, mentions)

            # Find matching praise theme for richer context
            matching_praise = next((p for p in praise if p.get("label", "").lower() in label.lower()
                                    or label.lower() in p.get("label", "").lower()), None)
            quote = None
            if matching_praise:
                quote = _pick_best_quote(matching_praise.get("quotes", []))

            if score >= 7:
                if asp_key == "service":
                    interpretation = (
                        f"{label} is a dominant theme ({read}). "
                        "Guests describe attentive, personal care — naming individual "
                        "staff in several cases. This suggests the venue's competitive "
                        "advantage is human rather than purely operational: it depends "
                        "on who is working, not just what systems are in place."
                    )
                elif asp_key == "food_quality":
                    interpretation = (
                        f"{label} draws {read} across reviews. "
                        "Guests highlight specific dishes and ingredients rather than "
                        "generic praise, which indicates the kitchen is delivering "
                        "memorable experiences, not just adequate meals."
                    )
                elif asp_key == "ambience":
                    interpretation = (
                        f"{label} registers as {read}. "
                        "The physical environment is contributing positively to the "
                        "guest experience and may be a factor in repeat visits and "
                        "social media visibility."
                    )
                elif asp_key == "value":
                    interpretation = (
                        f"{label} shows {read}. "
                        "Guests feel the price-to-quality ratio works in their favour, "
                        "which strengthens repeat visit likelihood and word-of-mouth."
                    )
                else:
                    interpretation = (
                        f"{label} shows {read} across available reviews."
                    )
            elif score >= 5:
                interpretation = (
                    f"{label} appears frequently but with mixed sentiment ({read}). "
                    "This is neither a clear strength nor a liability — it may "
                    "reflect inconsistency rather than a settled position."
                )
            else:
                # Low-scoring top aspect — mentioned a lot but poorly received
                interpretation = (
                    f"{label} is frequently mentioned but registers as {read}. "
                    "High mention volume combined with low sentiment suggests this "
                    "is an area guests care about but feel let down by."
                )

            if quote and rc.can_claim_themes:
                interpretation += f' As one reviewer put it: *"{quote}"*'
            paragraphs.append(interpretation)

        w(" ".join(paragraphs) + "\n")

    # -----------------------------------------------------------------------
    # 2. What This Means for the Proposition
    # -----------------------------------------------------------------------
    if rc.can_claim_proposition:
        w("### What This Means for the Proposition\n")

        # Determine the dominant signals
        top_labels = [ASPECT_LABELS.get(k, k) for k, v in top_aspects if v.get("score", 0) >= 6]
        weak_labels = [ASPECT_LABELS.get(k, k) for k, v in weak_aspects]

        if top_labels:
            drivers = " and ".join(top_labels[:2])
            w(f"The review evidence suggests this venue's real proposition is built on "
              f"**{drivers}**. ")

            if "Service & Hospitality" in top_labels and "Food Quality" in top_labels:
                w("When both service and food quality dominate guest feedback, the "
                  "venue is selling an experience, not just a meal. Pricing power, "
                  "loyalty, and resilience to competition are typically stronger for "
                  "experience-led venues.")
            elif "Value for Money" in top_labels:
                w("Value prominence in reviews indicates the venue competes partly on "
                  "price perception. This can drive volume but may limit pricing "
                  "flexibility. Management should monitor whether value praise masks "
                  "lower expectations rather than genuine quality recognition.")
            elif "Food Quality" in top_labels and "Service & Hospitality" not in top_labels:
                w("Food-led without strong service signals suggests the kitchen "
                  "carries the reputation. This creates concentration risk — guest "
                  "satisfaction is tied to culinary consistency, and any chef turnover "
                  "could impact the proposition quickly.")
            else:
                w("These strengths define what guests choose this venue for, "
                  "and should be protected in any operational changes.")

            if weak_labels:
                w(f" However, weakness in {' and '.join(weak_labels)} may be "
                  f"undermining the overall guest experience and limiting "
                  f"the venue's ability to convert first-time visitors into regulars.")
        else:
            w("The review evidence does not yet point to a clear proposition. "
              "No single theme dominates positively, which may indicate the venue "
              "has not yet established a distinctive identity in guests' minds.")

        w("")

    # -----------------------------------------------------------------------
    # 3. What Management May Be Missing
    # -----------------------------------------------------------------------
    has_criticism = bool(criticism)
    has_weak = bool(weak_aspects)
    has_mixed_signals = bool(sent_dist.get("mixed", 0))

    if has_criticism or has_weak or has_mixed_signals:
        w("### What Management May Be Missing\n")

        if not has_criticism and not has_weak:
            # Only mixed signals, no outright criticism
            mixed_count = sent_dist.get("mixed", 0)
            w(f"{mixed_count} reviews contain mixed sentiment — praise in some areas "
              f"paired with reservations in others. These are not outright complaints "
              f"but they signal inconsistency that, left unaddressed, erodes "
              f"the overall reputation over time.\n")
        else:
            for theme in criticism:
                label = theme.get("label", "Unknown")
                mentions = theme.get("mentions", 0)
                quotes = theme.get("quotes", [])
                quote = _pick_best_quote(quotes)

                if mentions <= 2 and rc.tier == "anecdotal":
                    severity = "isolated mention"
                elif mentions <= 3:
                    severity = "recurring note"
                else:
                    severity = "persistent theme"

                w(f"**{label}** ({severity}, {mentions} mention{'s' if mentions != 1 else ''}).")
                if quote:
                    w(f'> *"{quote}"*')

                # Interpret the operational meaning
                label_lower = label.lower()
                if any(term in label_lower for term in ["wait", "slow", "speed", "time"]):
                    w("Long waits are among the most common triggers for negative "
                      "online reviews and disproportionately affect overall ratings. "
                      "Even guests who enjoy the food will penalise the experience "
                      "for timing failures.")
                elif any(term in label_lower for term in ["access", "disab", "wheelchair", "step"]):
                    w("Accessibility complaints carry legal and reputational weight "
                      "beyond their frequency. A single detailed accessibility "
                      "complaint on a public platform can deter an entire segment "
                      "of potential guests and may indicate Equality Act exposure.")
                elif any(term in label_lower for term in ["cold", "temperature", "stale", "dry"]):
                    w("Food temperature and freshness complaints point to kitchen "
                      "timing or holding procedures. These are operational fixes "
                      "that can be addressed without changing the menu or concept.")
                elif any(term in label_lower for term in ["price", "expensive", "cost", "value"]):
                    w("Price complaints may indicate a gap between perceived and "
                      "delivered value. This is worth monitoring alongside the "
                      "venue's positioning — are expectations being set correctly?")
                elif any(term in label_lower for term in ["noise", "loud", "cramped", "space"]):
                    w("Environmental complaints (noise, space) are difficult to "
                      "fix structurally but important to acknowledge. Consider "
                      "whether booking management or layout tweaks could mitigate.")
                else:
                    w("This warrants investigation to determine whether it reflects "
                      "a systemic issue or isolated incidents.")
                w("")

    elif not criticism and praise and n >= 3:
        w("### What Management May Be Missing\n")
        w("No negative themes were detected in the analysed reviews. While "
          "encouraging, note that review platforms surface popular reviews first, "
          "which skew positive for well-rated venues. To validate, check the "
          "most recent 1-2 star reviews directly on the relevant platforms — "
          "these may reveal issues not captured in this sample.\n")

    # -----------------------------------------------------------------------
    # 4. Reputation Risk Assessment
    # -----------------------------------------------------------------------
    has_risks = bool(risks)
    has_declining = trajectory == "declining"
    neg_count = sent_dist.get("negative", 0)
    total_reviews = sum(sent_dist.values()) if sent_dist else n

    if has_risks or has_declining or (neg_count > 0 and total_reviews > 0 and neg_count / total_reviews > 0.3):
        w("### Reputation Risk Assessment\n")

        if has_risks:
            # Categorise risk phrases by severity
            severe_risks = [r for r in risks if any(term in r.lower() for term in
                           ["poisoning", "sick", "ill", "cockroach", "rat", "raw chicken",
                            "health hazard", "undercooked"])]
            reputational_risks = [r for r in risks if r not in severe_risks]

            if severe_risks:
                w(f"**Health and safety language detected:** {', '.join(severe_risks)}. "
                  "These phrases in public reviews represent serious reputational "
                  "and potentially legal exposure. Regardless of whether the specific "
                  "claims are valid, their presence on public platforms influences "
                  "prospective guests and may attract regulatory attention. "
                  "Immediate investigation and, if warranted, a management response "
                  "on the platform is advisable.")
                w("")

            if reputational_risks:
                w(f"**Reputational warning phrases detected:** {', '.join(reputational_risks)}. "
                  "While less severe than health concerns, these phrases signal "
                  "strongly negative guest experiences that damage word-of-mouth "
                  "and suppress return visits.")
                w("")

        if has_declining:
            w("**Trajectory warning:** Recent reviews trend lower than earlier ones "
              "in the sample. A declining trajectory, if sustained, will erode the "
              "aggregate rating over time. This is an early warning — the operational "
              "cause should be identified before it becomes visible in headline "
              "ratings.")
            w("")
        elif trajectory == "improving":
            w("**Positive trajectory:** Recent reviews trend higher than earlier ones, "
              "suggesting operational improvements are landing with guests. "
              "Continued monitoring will confirm whether this is a sustained shift.")
            w("")

        if neg_count > 0 and total_reviews > 0:
            neg_pct = neg_count / total_reviews
            if neg_pct > 0.3:
                w(f"**Negative review concentration:** {neg_count} of {total_reviews} "
                  f"analysed reviews ({neg_pct:.0%}) are negative. This is above "
                  f"the threshold where aggregate ratings typically begin declining "
                  f"and suggests an active, not historical, problem.")
                w("")

    elif trajectory == "improving":
        # No risk, but worth noting positive trajectory
        w("### Reputation Trajectory\n")
        w("Recent reviews trend higher than earlier ones, suggesting operational "
          "improvements are being recognised by guests. No significant reputation "
          "risks were identified in this sample.\n")

    # -----------------------------------------------------------------------
    # 5. Evidence Quality
    # -----------------------------------------------------------------------
    w("### Evidence Quality\n")

    review_count = ri.get('volume_signals', {}).get('review_count', 0)
    ta_count = ri.get("review_count_ta") or 0
    source_desc_parts = []
    if n - ta_count > 0:
        source_desc_parts.append(f"{n - ta_count} from Google")
    if ta_count > 0:
        source_desc_parts.append(f"{ta_count} from TripAdvisor")
    source_desc = " and ".join(source_desc_parts) if source_desc_parts else f"{n} reviews"

    w(f"**Confidence: {rc.tier.title()}** ({source_desc}).")

    if rc.tier == "anecdotal":
        w(f" This analysis draws on a very small sample. Themes are observed "
          f"impressions, not confirmed patterns. Management should treat these "
          f"findings as hypotheses to investigate, not conclusions to act on.")
    elif rc.tier == "indicative":
        w(f" The sample provides early directional signals. Themes that appear "
          f"across multiple reviews carry more weight, but any single finding "
          f"could shift with additional data.")
    elif rc.tier == "directional":
        if rc.source_count >= 2:
            w(f" Cross-platform evidence strengthens confidence. Themes corroborated "
              f"across Google and TripAdvisor are more reliable than single-source "
              f"findings.")
        else:
            w(f" Moderate sample from a single platform. Findings are directionally "
              f"sound but would benefit from cross-platform validation.")
    else:  # established
        w(f" Large, multi-source sample provides high confidence. Major themes "
          f"identified here are likely representative of the broader guest experience.")

    if review_count > 0 and not ta_count:
        w(f" Note: Google's API surfaces only its 'most relevant' reviews "
          f"(max 5 per venue) from {review_count:,} total — this sample likely "
          f"skews toward popular positive reviews.")

    w("")

    # -----------------------------------------------------------------------
    # 6. Delta vs Prior Month (if available)
    # -----------------------------------------------------------------------
    if rd and rd.get("has_delta"):
        w("### Narrative Shifts vs Prior Period\n")
        for kind, label_text in [("new_aspects", "Emerging topics"),
                                  ("fading_aspects", "Fading topics")]:
            items = rd.get(kind, [])
            if items:
                labels = [ASPECT_LABELS.get(a, a) for a in items]
                w(f"**{label_text}:** {', '.join(labels)}\n")

    # -----------------------------------------------------------------------
    # Appendix: Detailed Review Data (only for 15+ reviews)
    # -----------------------------------------------------------------------
    if n >= 15:
        _appendix_tables(w, analysis, aspects, sorted_aspects)
    elif aspects and n >= 5:
        # For moderate samples, include a compact summary table only
        _compact_aspect_summary(w, sorted_aspects)


# ---------------------------------------------------------------------------
# Appendix helpers
# ---------------------------------------------------------------------------

def _compact_aspect_summary(w, sorted_aspects):
    """Compact aspect summary for moderate sample sizes (5-14 reviews)."""
    w("### Topic Summary\n")
    w("| Topic | Signal | Mentions |")
    w("|-------|--------|--------:|")
    for asp, data in sorted_aspects:
        label = ASPECT_LABELS.get(asp, asp.replace("_", " ").title())
        score = data.get("score", 0)
        mentions = data.get("mentions", 0)
        read = _strength_read(score, mentions)
        w(f"| {label} | {read} | {mentions} |")
    w("")


def _appendix_tables(w, analysis, aspects, sorted_aspects):
    """Full detailed tables for large review samples (15+)."""
    w("---\n")
    w("### Detailed Review Data\n")
    w("*The tables below provide the underlying data for the analysis above.*\n")

    if sorted_aspects:
        w("#### Sentiment by Topic\n")
        w("| Topic | Signal | Positive | Negative | Mentions |")
        w("|-------|--------|--------:|---------:|---------:|")
        for asp, data in sorted_aspects:
            label = ASPECT_LABELS.get(asp, asp.replace("_", " ").title())
            score = data.get("score", 0)
            mentions = data.get("mentions", 0)
            read = _strength_read(score, mentions)
            w(f"| {label} | {read} | {data.get('positive', 0)} | "
              f"{data.get('negative', 0)} | {mentions} |")
        w("")

    per_review = analysis.get("per_review", [])
    if per_review:
        w("#### Review-by-Review Summary\n")
        w("| # | Rating | Sentiment | Topics | Snippet |")
        w("|--:|-------:|-----------|--------|---------|")
        for i, rev in enumerate(per_review, 1):
            topics = ", ".join(ASPECT_LABELS.get(a, a) for a in rev.get("aspects", [])[:3])
            snippet = rev.get("snippet", "")[:80]
            w(f"| {i} | {rev.get('rating', '—')}\u2605 | {rev.get('sentiment', '—')} | "
              f"{topics or '—'} | {snippet}{'...' if len(rev.get('snippet', '')) > 80 else ''} |")
        w("")
