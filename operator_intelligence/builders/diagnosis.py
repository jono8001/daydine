"""Performance diagnosis + commercial diagnosis builders."""

DIM_ORDER = ["experience", "visibility", "trust", "conversion", "prestige"]

_STRENGTH = {
    "experience": lambda s: (f"Google rating of {s.get('google_rating')}/5 — earned reputation, not artefact."
                              if s.get('google_rating') else "High FSA compliance scores."),
    "trust": lambda s: f"FSA rating {s.get('fsa_rating')}/5 with strong sub-scores. Recent inspection adds freshness.",
    "visibility": lambda s: f"{s.get('google_reviews', 0)} Google reviews — significant search discovery advantage.",
    "conversion": lambda s: "Operational readiness — hours, ordering options available.",
    "prestige": lambda s: "Editorial recognition differentiates from peers.",
}

_WEAKNESS = {
    "experience": lambda s: (f"Google {s.get('google_rating')}/5 signals dissatisfaction. Most commercially urgent."
                              if s.get('google_rating') and float(s['google_rating']) < 4 else
                              "Gaps in food quality or service delivery."),
    "trust": lambda s: (f"FSA {s.get('fsa_rating')}/5 caps this. Re-inspection targeting 5 is highest-impact action."
                         if s.get('fsa_rating') and int(s['fsa_rating']) < 5 else
                         "Inspection age or sub-scores dragging this down."),
    "visibility": lambda s: f"Only {s.get('google_reviews', 0)} reviews — may be invisible in 'near me' searches.",
    "conversion": lambda s: "Missing hours, delivery, or menu online. Friction at purchase intent.",
    "prestige": lambda s: "No editorial recognition. Limits premium positioning potential.",
}


def build_performance(w, scorecard, deltas, benchmarks, review_intel):
    w("## Performance Diagnosis\n")
    dims = {d: scorecard.get(d) for d in DIM_ORDER if scorecard.get(d) is not None}
    if not dims:
        w("*Insufficient signal data for diagnosis.*\n")
        return

    ranked = sorted(dims.items(), key=lambda x: -x[1])
    strong = [(d, s) for d, s in ranked if s >= 7.5]
    weak = [(d, s) for d, s in ranked if s < 5.5]

    if strong:
        w("**Strengths:**\n")
        for d, s in strong:
            w(f"- **{d.title()} ({s:.1f})**: {_STRENGTH.get(d, lambda _: 'Strong.')(scorecard)}")
        w("")
    if weak:
        w("**Vulnerabilities:**\n")
        for d, s in weak:
            w(f"- **{d.title()} ({s:.1f})**: {_WEAKNESS.get(d, lambda _: 'Below threshold.')(scorecard)}")
        w("")
    if not weak:
        lowest = ranked[-1]
        w(f"**Development area:** {lowest[0].title()} ({lowest[1]:.1f}) — "
          f"lowest dimension, clearest area for incremental improvement.\n")

    ring1 = (benchmarks or {}).get("ring1_local") or (benchmarks or {}).get("ring2_catchment")
    if ring1 and ring1.get("dimensions"):
        lead = lag = None
        for d in DIM_ORDER:
            dd = ring1["dimensions"].get(d)
            if dd and dd.get("peer_mean") is not None:
                g = dd["score"] - dd["peer_mean"]
                if lead is None or g > lead[1]: lead = (d, g)
                if lag is None or g < lag[1]: lag = (d, g)
        if lead and lead[1] > 0.5:
            w(f"**Biggest competitive advantage:** {lead[0].title()} (+{lead[1]:.1f} vs peers). Protect this.\n")
        if lag and lag[1] < -0.5:
            w(f"**Biggest competitive gap:** {lag[0].title()} ({lag[1]:+.1f} vs peers). Peers are winning here.\n")


def build_commercial(w, scorecard, deltas, benchmarks, review_intel):
    """Proposition-led commercial diagnosis. Diagnoses bottleneck, positioning,
    and where money is being left on the table."""
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
    top_theme = praise[0]["label"].lower() if praise else None

    ring1 = (benchmarks or {}).get("ring1_local") or (benchmarks or {}).get("ring2_catchment")
    pct = None
    if ring1 and ring1.get("dimensions", {}).get("overall"):
        pct = ring1["dimensions"]["overall"].get("percentile")

    # --- 1. Diagnose the main bottleneck ---
    w("### Main Bottleneck\n")
    if gr and float(gr) < 4.0:
        w(f"**Discovery suppression.** A {gr}/5 Google rating actively prevents "
          f"customers from finding you. Google's local search algorithm deprioritises "
          f"sub-4.0 venues, and most customers filter by 4+ stars. Until this lifts, "
          f"all other investment — marketing, menu changes, refurbishment — will "
          f"underperform because fewer people see it.\n")
    elif conv and conv < 5.5 and exp and exp >= 7.5:
        w("**Demand leakage.** The venue generates strong guest outcomes but loses "
          "potential customers at the point of conversion — when they try to check "
          "hours, see the menu, or book. This is the classic 'great product, poor "
          "shopfront' pattern. The fix is operational and digital, not culinary.\n")
    elif exp and exp < 7.0:
        w("**Experience gap.** The guest experience is the binding constraint. "
          "Until this improves, stronger visibility or better conversion simply "
          "accelerates exposure to a product that isn't landing consistently.\n")
    elif trust and trust < 7.0 and exp and exp >= 7.5:
        w("**Trust deficit.** Guests enjoy the venue but formal trust signals "
          "(compliance record, inspection recency) lag behind. This creates "
          "a hidden risk — one poor inspection could make a private gap public.\n")
    elif pct and pct >= 80 and prest and prest < 3.0:
        w("**Under-recognition.** The venue operates at a level that justifies "
          "premium positioning but carries none of the formal recognition that "
          "would support premium pricing, press attention, or talent recruitment. "
          "The bottleneck is not quality — it's credentialing.\n")
    else:
        w("**No single binding constraint identified.** The venue is operationally "
          "balanced. The commercial focus should be on marginal gains across "
          "the proposition rather than fixing a single bottleneck.\n")

    # --- 2. Positioning assessment ---
    w("### Positioning\n")
    if pct is not None:
        if pct >= 80:
            if top_theme:
                w(f"The venue is positioned as the local category leader, primarily "
                  f"known for {top_theme}. Commercially, this position supports "
                  f"premium pricing, event hosting, and extension opportunities "
                  f"(private dining, catering, seasonal events). The risk is "
                  f"complacency — leadership must be actively maintained.\n")
            else:
                w("Strong market position — the venue leads its local peer set. "
                  "The commercial opportunity is to leverage this into premium "
                  "pricing and proposition extensions rather than continuing "
                  "to compete on fundamentals.\n")
        elif pct >= 50:
            w("The venue sits above the local median but hasn't established a "
              "distinctive market position. Commercially, this is the 'good but "
              "forgettable' zone — adequate for steady trade but not generating "
              "the word-of-mouth or destination appeal that drives growth.\n")
        else:
            w("Below the local median. Customers in this area have demonstrably "
              "better-rated alternatives available. The commercial implication is "
              "direct: without a distinctive proposition or significant improvement, "
              "the venue competes primarily on convenience and price.\n")

    # --- 3. Where money is being left on the table ---
    w("### Revenue Left on the Table\n")
    money_items = []
    if conv and conv < 6.0 and exp and exp >= 7.0:
        money_items.append(
            "**Incomplete digital shopfront.** Interested customers who can't "
            "confirm hours, see a menu, or book online will choose a competitor "
            "who makes it easier. This is measurable lost footfall.")
    if grc < 200 and gr and float(gr) >= 4.0:
        money_items.append(
            f"**Unrealised review authority.** At {grc} reviews, you lack the "
            f"volume to dominate local search. Venues with 500+ reviews at "
            f"similar ratings rank higher in Google Maps — that translates "
            f"directly to walk-in and 'near me' discovery.")
    if prest and prest < 2.0 and overall and overall >= 7.5:
        money_items.append(
            "**No formal credentialing.** Quality supports premium pricing but "
            "without editorial recognition (AA, Michelin Plate, local awards), "
            "the venue cannot justify the price point that its experience "
            "quality would support.")
    if exp and exp >= 8.0 and top_theme:
        money_items.append(
            f"**Proposition not explicitly marketed.** Guests consistently praise "
            f"{top_theme}, but this isn't visibly communicated in the venue's "
            f"online presence. Making this the headline proposition in Google "
            f"Business Profile, social media, and website would sharpen "
            f"customer expectations and attract the right guests.")

    if money_items:
        for item in money_items[:3]:
            w(f"- {item}")
        w("")
    else:
        w("No significant revenue leakage identified from available signals. "
          "Additional data (TripAdvisor cross-reference, booking platform "
          "integration) would enable deeper commercial analysis.\n")

