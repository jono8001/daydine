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
    if gr is not None:
        gr = float(gr)
        if gr >= 4.5 and grc >= 100:
            lines.append(f"A {gr}/5 rating across {grc} reviews — genuine earned reputation driving discovery.")
        elif gr >= 4.0 and grc < 50:
            lines.append(f"{gr}/5 rating on only {grc} reviews — looks solid but volatile. Build volume.")
        elif gr < 4.0 and grc >= 100:
            lines.append(f"{gr}/5 across {grc} reviews is persistent. Google prioritises 4.0+; this suppresses discovery.")
        elif gr < 4.0:
            lines.append(f"Google {gr}/5 — below threshold where customers consider visiting.")
    trust, exp = scorecard.get("trust"), scorecard.get("experience")
    if trust and exp:
        gap = trust - exp
        if gap > 2: lines.append("Trust exceeds Experience — compliance strong, customer product needs attention.")
        elif gap < -2: lines.append("Experience exceeds Trust — customers enjoy it but compliance lags.")
    conv = scorecard.get("conversion")
    if conv and conv < 5:
        lines.append("Low Conversion — customers can't easily find hours, order, or confirm you're open.")
    ring1 = (benchmarks or {}).get("ring1_local") or (benchmarks or {}).get("ring2_catchment")
    if ring1 and ring1.get("dimensions", {}).get("overall"):
        pct = ring1["dimensions"]["overall"].get("percentile")
        if pct is not None:
            if pct >= 80:
                lines.append(f"P{pct} locally — top tier. Protect position, build prestige.")
            elif pct <= 30:
                lines.append(f"P{pct} locally — majority of competitors outperforming you.")
    if not lines:
        lines.append("Limited signals constrain diagnosis. Additional enrichment would unlock specifics.")
    for line in lines:
        w(line + "\n")
