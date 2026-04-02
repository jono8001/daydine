"""
Performance diagnosis + commercial diagnosis builders.

V2: 3-part diagnosis model (primary constraint, secondary drag, hidden risk)
plus false-comfort detection.
"""

from operator_intelligence.report_spec import assess_review_confidence

DIM_ORDER = ["experience", "visibility", "trust", "conversion", "prestige"]


# ---------------------------------------------------------------------------
# Performance Diagnosis
# ---------------------------------------------------------------------------

def build_performance(w, scorecard, deltas, benchmarks, review_intel):
    w("## Performance Diagnosis\n")
    dims = {d: scorecard.get(d) for d in DIM_ORDER if scorecard.get(d) is not None}
    if not dims:
        w("*Insufficient signal data for diagnosis.*\n")
        return

    ranked = sorted(dims.items(), key=lambda x: -x[1])
    strong = [(d, s) for d, s in ranked if s >= 7.5]
    weak = [(d, s) for d, s in ranked if s < 5.5]

    gr = scorecard.get("google_rating")
    grc = scorecard.get("google_reviews") or 0
    fsa = scorecard.get("fsa_rating")

    if strong:
        w("**Strengths:**\n")
        for d, s in strong:
            if d == "experience" and gr:
                w(f"- **Experience ({s:.1f})**: {gr}/5 Google rating across {grc} reviews — "
                  f"earned reputation backed by volume.")
            elif d == "trust" and fsa:
                w(f"- **Trust ({s:.1f})**: FSA {fsa}/5 with strong compliance sub-scores.")
            elif d == "visibility":
                w(f"- **Visibility ({s:.1f})**: {grc:,} reviews provide significant "
                  f"search discovery advantage.")
            elif d == "conversion":
                w(f"- **Conversion ({s:.1f})**: Operational readiness signals present — "
                  f"hours, menu, ordering options available.")
            elif d == "prestige":
                w(f"- **Prestige ({s:.1f})**: Editorial recognition differentiates "
                  f"from peers.")
            else:
                w(f"- **{d.title()} ({s:.1f})**: Above threshold.")
        w("")

    if weak:
        w("**Vulnerabilities:**\n")
        for d, s in weak:
            if d == "experience" and gr and float(gr) < 4.0:
                w(f"- **Experience ({s:.1f})**: {gr}/5 Google rating actively suppresses "
                  f"discovery. Most commercially urgent.")
            elif d == "trust" and fsa and int(fsa) < 5:
                w(f"- **Trust ({s:.1f})**: FSA {fsa}/5 is visible to customers. "
                  f"Re-inspection targeting 5 is highest-impact action.")
            elif d == "visibility":
                w(f"- **Visibility ({s:.1f})**: Only {grc} reviews — may be invisible "
                  f"in 'near me' searches.")
            elif d == "conversion":
                w(f"- **Conversion ({s:.1f})**: Missing hours, delivery, or menu online. "
                  f"Friction at purchase intent.")
            else:
                w(f"- **{d.title()} ({s:.1f})**: Below threshold.")
        w("")
    elif ranked:
        lowest = ranked[-1]
        w(f"**Development area:** {lowest[0].title()} ({lowest[1]:.1f}) — "
          f"lowest dimension, clearest area for incremental improvement.\n")

    # Competitive advantage / gap from peer data
    ring1 = (benchmarks or {}).get("ring1_local") or (benchmarks or {}).get("ring2_catchment")
    if ring1 and ring1.get("dimensions"):
        lead = lag = None
        for d in DIM_ORDER:
            dd = ring1["dimensions"].get(d)
            if dd and dd.get("peer_mean") is not None:
                g = dd["score"] - dd["peer_mean"]
                if lead is None or g > lead[1]:
                    lead = (d, g)
                if lag is None or g < lag[1]:
                    lag = (d, g)
        if lead and lead[1] > 0.5:
            w(f"**Biggest competitive advantage:** {lead[0].title()} "
              f"(+{lead[1]:.1f} vs peers). Protect this.\n")
        if lag and lag[1] < -0.5:
            w(f"**Biggest competitive gap:** {lag[0].title()} "
              f"({lag[1]:+.1f} vs peers). Peers are winning here.\n")


# ---------------------------------------------------------------------------
# Commercial Diagnosis — 3-part model
# ---------------------------------------------------------------------------

def build_commercial(w, scorecard, deltas, benchmarks, review_intel):
    """Proposition-led commercial diagnosis with 3-part constraint model
    and false-comfort detection."""
    w("## Commercial Diagnosis\n")

    gr = scorecard.get("google_rating")
    grc = scorecard.get("google_reviews") or 0
    fsa = scorecard.get("fsa_rating")
    overall = scorecard.get("overall")
    trust = scorecard.get("trust")
    exp = scorecard.get("experience")
    vis = scorecard.get("visibility")
    conv = scorecard.get("conversion")
    prest = scorecard.get("prestige")
    cat = scorecard.get("category", "venue")

    analysis = review_intel.get("analysis") if review_intel else None
    praise = analysis.get("praise_themes", []) if analysis else []
    criticism = analysis.get("criticism_themes", []) if analysis else []
    top_theme = praise[0]["label"].lower() if praise else None
    top_criticism = criticism[0]["label"].lower() if criticism else None

    ring1 = (benchmarks or {}).get("ring1_local") or (benchmarks or {}).get("ring2_catchment")
    pct = None
    peer_avg = None
    if ring1 and ring1.get("dimensions", {}).get("overall"):
        pct = ring1["dimensions"]["overall"].get("percentile")
        peer_avg = ring1["dimensions"]["overall"].get("peer_mean")

    from rcs_scoring_stratford import days_since
    inspection_age = days_since(scorecard.get("_rd") or "")

    # -----------------------------------------------------------------------
    # 1. Primary Constraint
    # -----------------------------------------------------------------------
    w("### Primary Constraint\n")

    if gr and float(gr) < 4.0:
        w(f"**Discovery suppression.** A {gr}/5 Google rating actively prevents "
          f"customers from finding you. Google deprioritises sub-4.0 venues, "
          f"and most customers filter by 4+ stars. Until this lifts, "
          f"all other investment underperforms because fewer people see it.\n")
    elif conv and conv < 5.5 and exp and exp >= 7.5:
        w("**Demand leakage.** The venue generates strong guest outcomes but "
          "loses customers at the point of conversion — when they try to check "
          "hours, see the menu, or book. This is the 'great product, poor "
          "shopfront' pattern. The fix is operational and digital, not culinary.\n")
    elif exp and exp < 7.0:
        w("**Experience gap.** Guest experience is the binding constraint. "
          "Stronger visibility or conversion simply accelerates exposure to "
          "a product that isn't landing consistently. Fix the guest outcome "
          "before investing in anything else.\n")
    elif trust and trust < 7.0 and exp and exp >= 7.5:
        w("**Trust deficit.** Guests enjoy the venue but formal trust signals "
          "(compliance record, inspection recency) lag behind. This creates "
          "a hidden ceiling — one poor inspection makes a private gap public.\n")
    elif pct and pct >= 80 and prest and prest < 3.0:
        w("**Under-recognition.** The venue operates at a level that justifies "
          "premium positioning but carries none of the formal recognition to "
          "support premium pricing or press attention. The constraint is "
          "credentialing, not quality.\n")
    else:
        w("**No single binding constraint.** The venue is operationally "
          "balanced. The commercial focus should be on marginal gains and "
          "protecting the strongest dimensions rather than crisis management.\n")

    # -----------------------------------------------------------------------
    # 2. Secondary Drag
    # -----------------------------------------------------------------------
    w("### Secondary Drag\n")

    secondary_found = False

    # Check for a second-order issue distinct from the primary
    if exp and exp >= 7.0 and trust and trust < 7.5 and not (trust < 7.0 and exp >= 7.5):
        w("Compliance scores are adequate but not strong. While not the "
          "primary issue, a stale or borderline trust record creates "
          "cumulative drag on the overall score and limits upward movement.\n")
        secondary_found = True
    elif vis and vis < 7.0 and exp and exp >= 7.0:
        w(f"Online visibility ({vis:.1f}) hasn't kept pace with guest "
          f"experience quality ({exp:.1f}). Good venues that aren't easily "
          f"found online are subsidising competitors with better digital "
          f"presence. This is fixable within 60 days.\n")
        secondary_found = True
    elif conv and conv < 6.0 and not (conv < 5.5 and exp and exp >= 7.5):
        w("Conversion friction exists — missing hours, menu, or booking "
          "options — but it's secondary to other issues. Fix the primary "
          "constraint first, then address the digital shopfront.\n")
        secondary_found = True

    # Review-informed secondary drag
    if not secondary_found and criticism:
        crit_label = criticism[0]["label"]
        crit_mentions = criticism[0].get("mentions", 0)
        if crit_mentions >= 2:
            w(f"Review criticism centres on {crit_label.lower()} "
              f"({crit_mentions} mentions). While not the primary constraint, "
              f"this is the specific operational area guests flag most often. "
              f"Addressing it would improve both rating trajectory and "
              f"repeat-visit likelihood.\n")
            secondary_found = True

    if not secondary_found:
        w("No clear secondary drag identified. Focus resources on the "
          "primary constraint.\n")

    # -----------------------------------------------------------------------
    # 3. Hidden Risk / Emerging Threat
    # -----------------------------------------------------------------------
    w("### Hidden Risk\n")

    risk_found = False

    # Inspection age as hidden risk
    if inspection_age and inspection_age > 540:
        months = round(inspection_age / 30)
        w(f"Last FSA inspection was {months} months ago. The longer the gap, "
          f"the more weight falls on the next unannounced visit. If anything "
          f"has drifted operationally, the next inspection will make it "
          f"visible — and permanent in the public record.\n")
        risk_found = True
    # Accessibility / reputation risk from reviews
    elif analysis and analysis.get("risk_flags"):
        flags = analysis["risk_flags"]
        w(f"Review risk phrases detected: {', '.join(flags[:3])}. "
          f"These may represent isolated incidents, but if they escalate "
          f"on social media or local press, the reputational impact is "
          f"disproportionate to the operational issue.\n")
        risk_found = True
    # Rating at inflection point
    elif gr and 3.9 <= float(gr) <= 4.1:
        w(f"Google rating sits at {gr}/5 — the threshold where Google's "
          f"algorithm shifts search priority. A few bad reviews could push "
          f"you below 4.0, which would materially reduce discovery. "
          f"Conversely, a small improvement would lift you into a stronger "
          f"ranking band.\n")
        risk_found = True
    # Thin evidence base
    elif analysis and analysis.get("reviews_analyzed", 0) <= 5:
        n = analysis["reviews_analyzed"]
        w(f"This assessment rests on only {n} review texts. The scores "
          f"look reasonable but could shift materially with more data. "
          f"Don't over-invest based on the current picture — collect "
          f"TripAdvisor data and more review text before making "
          f"strategic commitments.\n")
        risk_found = True

    if not risk_found:
        w("No hidden risks identified from current data. Continue "
          "monitoring for emerging signals.\n")

    # -----------------------------------------------------------------------
    # 4. What May Be Misleading (False Comfort)
    # -----------------------------------------------------------------------
    w("### What May Be Misleading\n")

    comfort_items = []

    # Strong rating, weak position
    if gr and float(gr) >= 4.5 and pct is not None and pct < 55:
        comfort_items.append(
            f"**The {gr}/5 rating feels dominant but isn't.** In this market, "
            f"peer venues achieve similar ratings. Your percentile position "
            f"(P{pct}) shows the rating is table stakes, not a differentiator.")

    # Strong experience, stale trust
    if exp and exp >= 8.0 and trust and trust < 7.5:
        comfort_items.append(
            "**Guest experience scores well but trust hasn't kept pace.** "
            "The gap between what guests experience and what the formal "
            "record shows creates exposure. One inspection or public "
            "complaint could make the gap visible.")

    # High visibility, low conversion
    if vis and vis >= 8.0 and conv and conv < 5.5:
        comfort_items.append(
            "**Easy to find, hard to act on.** Discovery without "
            "conversion is vanity traffic — it feels good in analytics "
            "but doesn't put customers in seats.")

    # Good overall on thin evidence
    rc = assess_review_confidence(review_intel)
    if rc.tier == "anecdotal" and overall and overall >= 7.0:
        comfort_items.append(
            f"**The overall score ({overall:.1f}) rests on thin evidence.** "
            f"Only {rc.review_text_count} review texts inform this assessment. "
            f"More data could shift the picture significantly — treat the "
            f"score as provisional.")

    # All positive reviews (could be selection bias)
    if analysis:
        sent = analysis.get("sentiment_distribution", {})
        neg = sent.get("negative", 0)
        total = sum(sent.values()) if sent else 0
        if total >= 5 and neg == 0:
            comfort_items.append(
                "**All analysed reviews are positive.** This may reflect "
                "genuine quality or Google's algorithm surfacing popular "
                "reviews. Check recent 1-2 star reviews directly on Google "
                "Maps to validate.")

    if comfort_items:
        for item in comfort_items:
            w(f"- {item}")
        w("")
    else:
        w("No significant false-comfort signals detected. The data picture "
          "appears consistent.\n")

    # -----------------------------------------------------------------------
    # 5. Positioning
    # -----------------------------------------------------------------------
    w("### Positioning\n")
    if pct is not None:
        if pct >= 80:
            if top_theme:
                w(f"Category leader in the local market, with {top_theme} "
                  f"as the emerging differentiator. This position supports "
                  f"premium pricing and extension opportunities. The risk is "
                  f"complacency — leadership must be actively maintained.\n")
            else:
                w("Strong market position — leads the local peer set. "
                  "The commercial opportunity is premium pricing and "
                  "proposition extensions rather than competing on "
                  "fundamentals.\n")
        elif pct >= 50:
            w("Above the local median but without a distinctive market "
              "position. This is the 'good but not destination' zone — "
              "adequate for steady trade but not generating the word-of-mouth "
              "or destination appeal that drives growth.\n")
        else:
            w("Below the local median. Customers have higher-rated "
              "alternatives nearby. Without a distinctive proposition or "
              "significant improvement, the venue competes primarily on "
              "convenience and price.\n")

    # -----------------------------------------------------------------------
    # 6. Revenue Left on the Table
    # -----------------------------------------------------------------------
    w("### Revenue Left on the Table\n")
    money = []

    if conv and conv < 6.0 and exp and exp >= 7.0:
        money.append(
            "**Incomplete digital shopfront.** Interested customers who "
            "can't confirm hours, see a menu, or book online will choose "
            "a competitor who makes it easier.")

    if grc < 200 and gr and float(gr) >= 4.0:
        money.append(
            f"**Unrealised review authority.** At {grc} reviews, you lack "
            f"the volume to dominate local search. 500+ reviews at similar "
            f"ratings rank measurably higher in Google Maps.")

    if prest and prest < 2.0 and overall and overall >= 7.5:
        money.append(
            "**No formal credentialing.** Quality supports premium pricing "
            "but without editorial recognition, the venue cannot justify "
            "the price point its experience would support.")

    if top_theme and exp and exp >= 8.0:
        rc = assess_review_confidence(review_intel)
        if rc.can_claim_proposition:
            money.append(
                f"**Proposition not explicitly marketed.** Guests praise "
                f"{top_theme}, but this isn't visibly communicated online. "
                f"Making it the headline would sharpen expectations and "
                f"attract the right customers.")
        else:
            money.append(
                f"**Potential proposition signal.** Early review data "
                f"({rc.qualifier}) suggests {top_theme} resonates. If "
                f"confirmed, this could become a marketable differentiator.")

    # Review-driven leakage
    if top_criticism and analysis:
        crit_mentions = criticism[0].get("mentions", 0)
        if crit_mentions >= 3:
            money.append(
                f"**Operational leakage via {top_criticism}.** Recurring "
                f"complaints ({crit_mentions} mentions) about {top_criticism} "
                f"suggest a specific operational gap that affects both "
                f"immediate revenue (table turns, repeat visits) and "
                f"long-term rating trajectory.")

    if money:
        for item in money[:4]:
            w(f"- {item}")
        w("")
    else:
        w("No significant revenue leakage identified from available "
          "signals. Additional data would enable deeper analysis.\n")
