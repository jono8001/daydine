"""Review & reputation intelligence section builder — business intelligence focus."""

from datetime import datetime, timedelta
from operator_intelligence.report_spec import MODE_NARRATIVE, assess_review_confidence
from operator_intelligence.review_analysis import ASPECT_LABELS


def _valid_recent_window(ri, month_str):
    """Compute a valid recent-movement window, filtering out future dates.

    Returns dict with keys: available, count, sources, cutoff, note
    or {available: False, note: reason}.
    """
    if not ri.get("has_dated_reviews"):
        return {"available": False,
                "note": "No dated reviews available — recent movement cannot be isolated."}

    date_range = ri.get("date_range") or {}
    latest = date_range.get("latest", "")

    # Determine report ceiling: end of the report month
    try:
        report_ceiling = datetime.strptime(month_str, "%Y-%m")
        # End of that month (approx)
        if report_ceiling.month == 12:
            report_ceiling = report_ceiling.replace(year=report_ceiling.year + 1, month=1)
        else:
            report_ceiling = report_ceiling.replace(month=report_ceiling.month + 1)
        ceiling_str = report_ceiling.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        ceiling_str = None

    # Filter: reject dates after report month
    analysis = ri.get("analysis") or {}
    per_review = analysis.get("per_review", [])
    dated_valid = []
    future_count = 0
    for rev in per_review:
        d = (rev.get("date") or "")[:10]
        if not d:
            continue
        if ceiling_str and d >= ceiling_str:
            future_count += 1
            continue
        dated_valid.append(rev)

    if not dated_valid:
        note = "All dated reviews fall outside the report period"
        if future_count > 0:
            note += f" ({future_count} have dates after {month_str})"
        note += " — recent movement cannot be assessed."
        return {"available": False, "note": note}

    # Compute 30-day window from latest valid date
    valid_dates = sorted(r["date"][:10] for r in dated_valid)
    latest_valid = valid_dates[-1]
    try:
        latest_dt = datetime.strptime(latest_valid, "%Y-%m-%d")
        cutoff_dt = latest_dt - timedelta(days=30)
        cutoff_str = cutoff_dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return {"available": False,
                "note": "Could not parse review dates for recent-movement analysis."}

    recent = [r for r in dated_valid if r["date"][:10] >= cutoff_str]
    if not recent:
        return {"available": False,
                "note": f"No dated reviews in the 30 days before {latest_valid}."}

    sources = list(set(r.get("source") or "unknown" for r in recent))
    return {
        "available": True,
        "count": len(recent),
        "total_valid": len(dated_valid),
        "sources": sources,
        "cutoff": cutoff_str,
        "latest": latest_valid,
        "future_excluded": future_count,
    }


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


def _validated_trajectory(per_review, month_str, orig_trajectory, orig_method):
    """Recompute trajectory using only reviews with dates within the report period.

    If the analysis used date_sorted but included future-dated reviews,
    recompute from valid-only dates, or fall back to positional.
    """
    try:
        ceil = datetime.strptime(month_str, "%Y-%m")
        if ceil.month == 12:
            ceil = ceil.replace(year=ceil.year + 1, month=1)
        else:
            ceil = ceil.replace(month=ceil.month + 1)
        ceiling_str = ceil.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return orig_trajectory, orig_method

    valid_dated = [(r, r["date"][:10]) for r in per_review
                   if r.get("date") and r["date"][:10] < ceiling_str]
    total_dated = sum(1 for r in per_review if r.get("date"))
    future_count = total_dated - len(valid_dated)

    if future_count == 0:
        # No future dates — the original date_sorted trajectory is clean
        return orig_trajectory, orig_method

    # Future dates present — recompute from valid dates only
    if len(valid_dated) >= 4:
        sorted_valid = sorted(valid_dated, key=lambda x: x[1])
        mid = len(sorted_valid) // 2
        older = [r["rating"] for r, _ in sorted_valid[:mid] if r.get("rating")]
        newer = [r["rating"] for r, _ in sorted_valid[mid:] if r.get("rating")]
        if older and newer:
            diff = (sum(newer) / len(newer)) - (sum(older) / len(older))
            traj = "improving" if diff > 0.3 else "declining" if diff < -0.3 else "stable"
            return traj, "date_sorted"

    # Not enough valid dated reviews — fall back to positional
    all_ratings = [r["rating"] for r in per_review if r.get("rating")]
    if len(all_ratings) >= 4:
        first = all_ratings[:len(all_ratings) // 2]
        second = all_ratings[len(all_ratings) // 2:]
        diff = (sum(second) / len(second)) - (sum(first) / len(first))
        traj = "improving" if diff > 0.3 else "declining" if diff < -0.3 else "stable"
        return traj, "positional"

    return None, None


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

def build(w, mode, review_intel, review_delta, month_str=None, risk_result=None):
    w("## Review & Reputation Intelligence\n")

    # Cross-reference: if risk alerts exist that relate to review themes, note them
    if risk_result and not risk_result.get("clean", True):
        for alert in risk_result.get("alerts", []):
            if alert["severity"] == "red":
                w(f"> ⚠️ **Note:** A {alert['label']} pattern has been flagged in the "
                  f"Operational & Risk Alerts section above ({alert['review_count']} "
                  f"review(s)). The theme analysis below should be read alongside "
                  f"that alert.\n")

    if mode != MODE_NARRATIVE:
        _structured(w, review_intel)
    else:
        _narrative(w, review_intel, review_delta, month_str=month_str)


def build_review_appendices(w, review_intel):
    """Render review evidence appendices (summary table + full text).

    Called separately at the end of the report, after Data Coverage
    and Evidence Appendix, so the main narrative is not interrupted.
    """
    if not review_intel or not review_intel.get("has_narrative"):
        return
    analysis = review_intel.get("analysis")
    if not analysis:
        return

    n = analysis.get("reviews_analyzed", 0)
    aspects = analysis.get("aspect_scores", {})
    sorted_aspects = sorted(aspects.items(), key=lambda x: -x[1].get("mentions", 0))

    if n >= 15:
        _appendix_tables(w, analysis, aspects, sorted_aspects)
    elif aspects and n >= 5:
        _compact_aspect_summary(w, sorted_aspects)

    per_review = analysis.get("per_review", [])
    if per_review and any(r.get("full_text") for r in per_review):
        _full_text_appendix(w, per_review)


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

def _narrative(w, ri, rd, month_str=None):
    """Full business intelligence from review text."""
    analysis = ri.get("analysis")
    vol = ri.get("volume_signals")

    if not analysis:
        w("*Review text collected but analysis unavailable.*\n")
        return

    n = analysis.get("reviews_analyzed", 0)
    rc = assess_review_confidence(ri)
    adj, _ = _confidence_language(rc)

    # --- Sample scope statement (temporal honesty) ---
    ta_count = ri.get("review_count_ta") or 0
    google_text = n - ta_count
    date_range = ri.get("date_range")
    scope_parts = []
    if google_text > 0:
        scope_parts.append(f"{google_text} Google (undated)")
    if ta_count > 0:
        if date_range and month_str:
            # Show valid-only date range (exclude future-dated reviews)
            try:
                _ceil = datetime.strptime(month_str, "%Y-%m")
                if _ceil.month == 12:
                    _ceil = _ceil.replace(year=_ceil.year + 1, month=1)
                else:
                    _ceil = _ceil.replace(month=_ceil.month + 1)
                _ceil_str = _ceil.strftime("%Y-%m-%d")
                valid_dates = sorted(
                    r["date"][:10] for r in analysis.get("per_review", [])
                    if r.get("date") and r.get("source") == "tripadvisor"
                    and r["date"][:10] < _ceil_str
                )
                if valid_dates:
                    scope_parts.append(f"{ta_count} TripAdvisor ({valid_dates[0]} to {valid_dates[-1]})")
                else:
                    scope_parts.append(f"{ta_count} TripAdvisor (no valid dates within report period)")
            except (ValueError, TypeError):
                scope_parts.append(f"{ta_count} TripAdvisor ({date_range['earliest']} to {date_range['latest']})")
        elif date_range:
            scope_parts.append(f"{ta_count} TripAdvisor ({date_range['earliest']} to {date_range['latest']})")
        else:
            scope_parts.append(f"{ta_count} TripAdvisor")
    scope_str = " + ".join(scope_parts) if scope_parts else f"{n} reviews"
    w(f"*Reputation baseline: {n} reviews analysed ({scope_str}). "
      f"This is the full available sample, not limited to the current month.*\n")

    # Gather core data structures
    aspects = analysis.get("aspect_scores", {})
    praise = analysis.get("praise_themes", [])
    criticism = analysis.get("criticism_themes", [])
    risks = analysis.get("risk_flags", [])
    trajectory = analysis.get("trajectory")
    trajectory_method = analysis.get("trajectory_method")
    sent_dist = analysis.get("sentiment_distribution", {})

    # --- Validate trajectory against report-period date sanity ---
    # If the analysis claims date_sorted trajectory but the dated reviews
    # include dates outside the report period, recompute from valid dates
    # or downgrade to positional.
    if trajectory_method == "date_sorted" and month_str:
        trajectory, trajectory_method = _validated_trajectory(
            analysis.get("per_review", []), month_str, trajectory, trajectory_method)

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

        for p in paragraphs:
            w(p + "\n")

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

        _traj_caveat = (" (based on review dates)" if trajectory_method == "date_sorted"
                        else " (based on sample order — not date-confirmed)")
        if has_declining:
            w(f"**Trajectory warning:** Later reviews trend lower than earlier ones"
              f"{_traj_caveat}. A declining trajectory, if sustained, will erode the "
              "aggregate rating over time. This is an early warning — the operational "
              "cause should be identified before it becomes visible in headline "
              "ratings.")
            w("")
        elif trajectory == "improving":
            w(f"**Positive trajectory:** Later reviews trend higher than earlier ones"
              f"{_traj_caveat}, "
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
        _traj_note = ("by date" if trajectory_method == "date_sorted"
                      else "by sample order — not date-confirmed")
        w("### Reputation Trajectory\n")
        w(f"Later reviews trend higher than earlier ones ({_traj_note}), suggesting "
          "operational improvements are being recognised by guests. No significant "
          "reputation risks were identified in this sample.\n")

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
    # 6. Recent Movement (date-filtered layer)
    # -----------------------------------------------------------------------
    w("### Recent Movement\n")
    recent = _valid_recent_window(ri, month_str)

    if not recent["available"]:
        w(f"*{recent['note']}*\n")
        w("The analysis above reflects the full reputation baseline. "
          "A dated recent-movement layer will become available when "
          "reviews with reliable dates fall within the report period.\n")
    else:
        rc_count = recent["count"]
        rc_total = recent["total_valid"]
        rc_sources = ", ".join(s.title() for s in recent["sources"])
        rc_cutoff = recent["cutoff"]
        rc_latest = recent["latest"]
        future_note = ""
        if recent.get("future_excluded", 0) > 0:
            future_note = (f" ({recent['future_excluded']} review(s) with dates "
                           f"after the report period were excluded.)")

        w(f"**{rc_count} of {rc_total} dated reviews** fall within the 30-day "
          f"window ({rc_cutoff} to {rc_latest}), from {rc_sources}.{future_note}\n")

        # Check if Google is baseline-only
        if "google" not in recent["sources"]:
            google_text = n - (ri.get("review_count_ta") or 0)
            if google_text > 0:
                w(f"*Google reviews ({google_text}) contribute to the reputation "
                  f"baseline only — Google does not provide reliable review dates.*\n")

        # Quick sentiment summary of recent reviews
        recent_per_review = [r for r in analysis.get("per_review", [])
                             if r.get("date") and r["date"][:10] >= rc_cutoff
                             and (not month_str or r["date"][:10] < recent.get("_ceiling", "9999"))]
        # Filter out future dates using same ceiling logic
        try:
            from datetime import datetime as _dt
            _ceil = _dt.strptime(month_str, "%Y-%m")
            if _ceil.month == 12:
                _ceil = _ceil.replace(year=_ceil.year + 1, month=1)
            else:
                _ceil = _ceil.replace(month=_ceil.month + 1)
            _ceil_str = _ceil.strftime("%Y-%m-%d")
            recent_per_review = [r for r in recent_per_review if r["date"][:10] < _ceil_str]
        except (ValueError, TypeError):
            pass

        if recent_per_review:
            recent_ratings = [r["rating"] for r in recent_per_review if r.get("rating")]
            if recent_ratings:
                avg = sum(recent_ratings) / len(recent_ratings)
                w(f"Recent window average rating: **{avg:.1f}/5** "
                  f"({len(recent_ratings)} rated review{'s' if len(recent_ratings) != 1 else ''}).\n")

            # Check for new/intensifying themes in recent window
            from collections import Counter
            recent_aspects = Counter()
            for r in recent_per_review:
                for asp in r.get("aspects", []):
                    recent_aspects[asp] += 1
            if recent_aspects:
                top_recent = recent_aspects.most_common(3)
                labels = [f"{ASPECT_LABELS.get(a, a)} ({c})" for a, c in top_recent]
                w(f"Most mentioned in recent window: {', '.join(labels)}.\n")
        else:
            w("No reviews with valid dates fell within the recent window "
              "after filtering.\n")

    # -----------------------------------------------------------------------
    # 7. Delta vs Prior Month (if available)
    # -----------------------------------------------------------------------
    if rd and rd.get("has_delta"):
        w("### Narrative Shifts vs Prior Period\n")
        for kind, label_text in [("new_aspects", "Emerging topics"),
                                  ("fading_aspects", "Fading topics")]:
            items = rd.get(kind, [])
            if items:
                labels = [ASPECT_LABELS.get(a, a) for a in items]
                w(f"**{label_text}:** {', '.join(labels)}\n")

    # Review appendix tables are rendered separately at report end
    # via build_review_appendices()


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
        w("| # | Source | Date | Rating | Sentiment | Topics | Snippet |")
        w("|--:|--------|------|-------:|-----------|--------|---------|")
        for i, rev in enumerate(per_review, 1):
            topics = ", ".join(ASPECT_LABELS.get(a, a) for a in rev.get("aspects", [])[:3])
            snippet = rev.get("snippet", "")[:60]
            source = (rev.get("source") or "—").title()
            date_str = (rev.get("date") or "")[:10] or "Undated"
            w(f"| {i} | {source} | {date_str} | {rev.get('rating', '—')}\u2605 | {rev.get('sentiment', '—')} | "
              f"{topics or '—'} | {snippet}{'...' if len(rev.get('snippet', '')) > 60 else ''} |")
        w("")


def _full_text_appendix(w, per_review):
    """Full untruncated review text for transparency."""
    w("---\n")
    w("### Full Review Text Appendix\n")
    w("*Complete text of each analysed review. Provided for transparency "
      "and audit — the summary table above is the primary reference.*\n")

    for i, rev in enumerate(per_review, 1):
        source = (rev.get("source") or "Unknown").title()
        date_str = (rev.get("date") or "")[:10] or "Undated"
        rating = rev.get("rating", "—")
        sentiment = rev.get("sentiment", "—")
        topics = ", ".join(ASPECT_LABELS.get(a, a) for a in rev.get("aspects", [])[:3])
        full_text = rev.get("full_text", rev.get("snippet", ""))

        w(f"**Review {i}** | {source} | {date_str} | {rating}\u2605 | {sentiment}"
          + (f" | {topics}" if topics else ""))
        w(f"> {full_text}\n")
