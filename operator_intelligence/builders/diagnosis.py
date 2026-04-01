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
    w("## Commercial Diagnosis\n")
    lines = []
    gr = scorecard.get("google_rating")
    grc = scorecard.get("google_reviews") or 0
    fsa = scorecard.get("fsa_rating")
    overall = scorecard.get("overall")
    trust = scorecard.get("trust")
    exp = scorecard.get("experience")
    vis = scorecard.get("visibility")
    conv = scorecard.get("conversion")
    prest = scorecard.get("prestige")

    # --- Rating × volume matrix ---
    if gr is not None:
        gr = float(gr)
        if gr >= 4.5 and grc >= 500:
            lines.append(f"A {gr}/5 Google rating across {grc:,} reviews is a commanding position. "
                         "This volume means the rating is statistically stable — individual reviews "
                         "won't move it. The commercial value is in Google Maps ranking, where "
                         "high-rating + high-volume venues dominate local search results.")
        elif gr >= 4.5 and grc >= 100:
            lines.append(f"Your {gr}/5 rating across {grc} reviews represents genuine earned "
                         "reputation. This drives discovery through Google Maps and 'near me' "
                         "searches. The priority is maintaining this rating while building "
                         "volume toward 500+ for maximum algorithmic benefit.")
        elif gr >= 4.0 and grc < 50:
            lines.append(f"A {gr}/5 rating on {grc} reviews looks solid on the surface, but "
                         "at this volume the rating is fragile. Three consecutive 1-star reviews "
                         "would drop your average by ~0.2 points. Building review volume is "
                         "a protective measure as much as a growth strategy.")
        elif gr >= 4.0:
            lines.append(f"Your {gr}/5 rating across {grc} reviews is adequate but not distinctive. "
                         "In a competitive local market, this positions you as acceptable rather "
                         "than compelling. The gap to 4.5 — where Google's algorithm provides "
                         "meaningful ranking uplift — is achievable with operational focus.")
        elif gr < 4.0 and grc >= 100:
            lines.append(f"A {gr}/5 rating across {grc} reviews is a persistent negative signal. "
                         "Google suppresses sub-4.0 venues in local search results, and customers "
                         "filtering by rating will exclude you. This volume means the low rating "
                         "reflects a real, sustained pattern — not bad luck with a few reviewers.")
        elif gr < 4.0:
            lines.append(f"Google rating of {gr}/5 is below the threshold where most customers "
                         "will consider visiting. This is the single most commercially urgent "
                         "metric. Every week at this rating represents lost discovery.")

    # --- Trust vs Experience alignment ---
    if trust is not None and exp is not None:
        gap = trust - exp
        if gap > 2.0:
            lines.append("Your compliance scores significantly exceed your customer experience "
                         "scores. This is an unusual pattern — it means the kitchen and back-of-house "
                         "are strong, but something in the front-of-house delivery, menu, or "
                         "service is not landing with customers. This is typically a management "
                         "and training issue, not a compliance one.")
        elif gap < -2.0:
            lines.append("Customer experience outpaces compliance — guests enjoy the venue but "
                         "your regulatory scores are lagging. This creates a risk: a poor re-inspection "
                         "result would be visible on the FSA website and could undermine the "
                         "positive perception you've built. Address compliance before it surfaces publicly.")
        elif trust is not None and trust >= 8.0 and exp is not None and exp >= 8.0:
            lines.append("Trust and Experience are aligned at a high level. This is the strongest "
                         "commercial position — what customers experience is backed by genuine "
                         "operational rigour. Focus on sustaining this alignment.")

    # --- Conversion friction as commercial cost ---
    if conv is not None and conv < 5.0 and exp is not None and exp >= 7.0:
        lines.append(f"There is a significant gap between your experience quality ({exp:.1f}) "
                     f"and your conversion readiness ({conv:.1f}). Commercially, this means "
                     "you're generating demand you can't capture. Customers who discover you "
                     "via Google or word-of-mouth then hit friction — missing hours, no online "
                     "menu, unclear booking options. Each friction point is a measurable loss "
                     "of potential covers.")
    elif conv is not None and conv < 5.0:
        lines.append("Low conversion readiness suggests customers may struggle to find your "
                     "hours, menu, or ordering options online. In a market where competitors "
                     "have complete Google profiles, this is a competitive disadvantage.")

    # --- Peer position commercial implication ---
    ring1 = (benchmarks or {}).get("ring1_local") or (benchmarks or {}).get("ring2_catchment")
    if ring1 and ring1.get("dimensions", {}).get("overall"):
        pct = ring1["dimensions"]["overall"].get("percentile")
        peer_count = ring1.get("peer_count", 0)
        if pct is not None:
            if pct >= 80:
                lines.append(f"At P{pct} among {peer_count} local peers, you hold a strong "
                             "market position. The commercial question is not how to fix problems "
                             "but how to capture the upside of your position — premium pricing, "
                             "event hosting, private dining, or catering extensions.")
            elif 50 <= pct < 80:
                lines.append(f"At P{pct} locally, you're above average but not dominant. "
                             "Customers have better-rated alternatives nearby. The commercial "
                             "risk is being 'fine but forgettable' — adequate enough to survive "
                             "but not distinctive enough to generate strong word-of-mouth.")
            elif pct < 50:
                lines.append(f"At P{pct} locally, the majority of direct competitors are "
                             "outperforming you. Customers searching for your category in this "
                             "area will likely find and choose alternatives first. This has "
                             "direct revenue implications.")

    # --- Prestige vs fundamentals ---
    if prest is not None and prest < 2.0 and overall is not None and overall >= 7.5:
        lines.append("Your fundamentals are strong but you have zero prestige markers. "
                     "This caps your ability to command premium pricing or attract media "
                     "attention. A credible awards submission (AA, local food guides) would "
                     "be a low-cost, high-signal move at your current quality level.")

    if not lines:
        lines.append("Limited signal data constrains diagnostic depth. Additional "
                     "data enrichment would unlock more specific commercial insights.")

    for line in lines:
        w(line + "\n")
