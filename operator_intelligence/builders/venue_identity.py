"""
Venue identity and strategic framing builders.

These sections shift the report from score-description to proposition diagnosis.
They synthesise guest narrative, peer position, and structured signals into
commercially meaningful management language.
"""

from operator_intelligence.review_analysis import ASPECT_LABELS
from operator_intelligence.report_spec import assess_review_confidence, CONFIDENCE_LANGUAGE

DIM_ORDER = ["experience", "visibility", "trust", "conversion", "prestige"]


# ---------------------------------------------------------------------------
# Category → proposition language mappings
# ---------------------------------------------------------------------------

_CATEGORY_PROPOSITIONS = {
    "Pub / Bar": "pub dining",
    "Restaurant (General)": "restaurant",
    "Cafe / Coffee Shop": "cafe",
    "Indian Restaurant": "Indian dining",
    "Italian Restaurant": "Italian dining",
    "Chinese Restaurant": "Chinese dining",
    "Hotel / Accommodation": "hotel dining",
    "Fast Food / Quick Service": "quick-service food",
    "French Restaurant": "French dining",
    "British Restaurant": "British dining",
    "Takeaway": "takeaway",
    "Bakery / Desserts": "bakery",
}


def _proposition_word(category):
    return _CATEGORY_PROPOSITIONS.get(category, category.lower())


# ---------------------------------------------------------------------------
# What This Venue Is Becoming Known For
# ---------------------------------------------------------------------------

def build_known_for(w, venue_name, scorecard, benchmarks, review_intel):
    """Synthesise the venue's emerging market identity from all available signals."""
    w("## What This Venue Is Becoming Known For\n")

    cat = scorecard.get("category", "Unknown")
    prop = _proposition_word(cat)
    gr = scorecard.get("google_rating")
    grc = scorecard.get("google_reviews") or 0
    exp = scorecard.get("experience")
    trust = scorecard.get("trust")
    vis = scorecard.get("visibility")
    conv = scorecard.get("conversion")

    # Determine the venue's strongest guest-facing signal
    analysis = review_intel.get("analysis") if review_intel else None
    praise = analysis.get("praise_themes", []) if analysis else []
    top_theme = praise[0] if praise else None
    second_theme = praise[1] if len(praise) > 1 else None

    # Build the identity paragraph
    lines = []

    # Opening — what the venue is in market terms
    if gr and float(gr) >= 4.5 and grc >= 500:
        lines.append(f"{venue_name} is a well-established {prop} venue with a strong "
                     f"public reputation — {gr}/5 across {grc:,} Google reviews. "
                     f"That volume means the reputation is earned, not manufactured.")
    elif gr and float(gr) >= 4.0 and grc >= 100:
        lines.append(f"{venue_name} operates as a credible {prop} venue with "
                     f"a {gr}/5 Google rating across {grc} reviews — solid but "
                     f"not yet commanding.")
    elif gr and float(gr) >= 4.0:
        lines.append(f"{venue_name} is a {prop} venue with an adequate public "
                     f"reputation ({gr}/5, {grc} reviews) that has room to build "
                     f"stronger proof.")
    else:
        lines.append(f"{venue_name} operates in the {prop} category with a public "
                     f"rating of {gr}/5 that is currently limiting discovery.")

    # Aggregate context — TripAdvisor if available
    ta = review_intel.get("ta_rating") if review_intel else None
    trc = review_intel.get("review_count_ta") or 0
    if ta and trc:
        lines.append(f"TripAdvisor shows {ta}/5 across {trc} reviews"
                     + (f" — slightly lower than Google, possibly reflecting a more tourist-weighted sample."
                        if gr and float(ta) < float(gr) - 0.1 else "."))

    # What guests value — from deep analysis of recent reviews
    rc = assess_review_confidence(review_intel)
    lang = CONFIDENCE_LANGUAGE.get(rc.tier, CONFIDENCE_LANGUAGE["none"])
    deep_count = rc.review_text_count if rc else 0
    if deep_count > 0:
        lines.append(f"**From deep analysis of {deep_count} recent reviews:**")

    if top_theme and second_theme and rc.can_claim_proposition:
        lines.append(f"Guest feedback {rc.qualifier} centres on "
                     f"**{top_theme['label'].lower()}** ({top_theme['mentions']} mentions) "
                     f"and **{second_theme['label'].lower()}** ({second_theme['mentions']} "
                     f"mentions). {lang['strong']}these as defining elements "
                     f"of the proposition as guests perceive it.")
    elif top_theme and second_theme:
        # Anecdotal tier — can observe themes but not claim proposition
        hedge = lang["hedge"].format(n=rc.review_text_count, s=rc.source_count)
        lines.append(f"{hedge}**{top_theme['label'].lower()}** "
                     f"({top_theme['mentions']} mentions) and "
                     f"**{second_theme['label'].lower()}** ({second_theme['mentions']} "
                     f"mentions) are the most frequent themes. Whether these represent "
                     f"settled guest perception or sampling artefact cannot be determined "
                     f"from this evidence base alone.")
    elif top_theme:
        hedge = lang["hedge"].format(n=rc.review_text_count, s=rc.source_count)
        lines.append(f"{hedge}**{top_theme['label'].lower()}** "
                     f"({top_theme['mentions']} mentions) {lang['theme_verb']}.")
    elif exp and exp >= 8.0:
        lines.append("No individual review text is available for narrative analysis. "
                     "The aggregate experience score (based on rating and compliance) "
                     "is directionally positive but cannot confirm what specifically "
                     "guests value.")

    # Peer context — what the position means for identity
    ring1 = (benchmarks or {}).get("ring1_local") or (benchmarks or {}).get("ring2_catchment")
    if ring1 and ring1.get("dimensions", {}).get("overall"):
        pct = ring1["dimensions"]["overall"].get("percentile")
        peer_count = ring1.get("peer_count", 0)
        if pct is not None and pct >= 80:
            lines.append(f"Within the local {prop} market ({peer_count} peers), "
                         f"this venue leads the field. The identity is that of a "
                         f"category leader — the venue others are compared against.")
        elif pct is not None and pct >= 50:
            lines.append(f"In the local market, the venue sits above the median but "
                         f"hasn't established itself as the clear category leader. "
                         f"The identity is 'reliably good' rather than 'destination'.")
        elif pct is not None:
            lines.append(f"The venue currently sits below the local median. "
                         f"Guests have demonstrably higher-rated alternatives nearby, "
                         f"which constrains the venue's ability to define its own "
                         f"market identity.")

    # Public proof vs lived experience tension
    if trust and exp:
        if trust >= 8.0 and exp >= 8.0:
            lines.append("The public proof (ratings, compliance) aligns with what "
                         "guests actually experience. This consistency is commercially "
                         "valuable — it means expectations set online are met in person.")
        elif exp >= 8.0 and trust < 7.0:
            lines.append("There is a gap between lived experience (strong) and formal "
                         "trust signals (lagging). Guests enjoy the venue but the "
                         "compliance record doesn't yet match — this creates an "
                         "under-recognition risk.")
        elif trust >= 8.0 and exp < 7.0:
            lines.append("Compliance is strong but the guest experience doesn't match "
                         "the operational rigour. The venue is well-run behind the scenes "
                         "but something in the front-of-house delivery isn't landing.")

    # Underexploited angle
    if conv and conv < 5.5 and exp and exp >= 7.5:
        lines.append("The venue appears to be underexploiting its experience quality "
                     "commercially — strong guest outcomes are not fully converted into "
                     "accessibility, discoverability, or convenience. Demand is being "
                     "generated but not fully captured.")

    for line in lines:
        w(line + "\n")


# ---------------------------------------------------------------------------
# Protect / Improve / Ignore
# ---------------------------------------------------------------------------

def build_protect_improve_ignore(w, scorecard, deltas, benchmarks, review_intel, recs):
    """Decisive strategic framing — what to defend, what to fix, what to skip."""
    w("## Protect / Improve / Ignore\n")

    dims = {d: scorecard.get(d) for d in DIM_ORDER if scorecard.get(d) is not None}
    gr = scorecard.get("google_rating")
    grc = scorecard.get("google_reviews") or 0
    fsa = scorecard.get("fsa_rating")
    analysis = review_intel.get("analysis") if review_intel else None
    praise = analysis.get("praise_themes", []) if analysis else []
    top_theme = praise[0]["label"].lower() if praise else None

    ring1 = (benchmarks or {}).get("ring1_local") or (benchmarks or {}).get("ring2_catchment") or {}
    ring1_dims = ring1.get("dimensions", {})

    # --- PROTECT ---
    w("### Protect\n")
    protect_items = []

    rc = assess_review_confidence(review_intel)

    # Protect the strongest dimension that leads peers
    for dim in DIM_ORDER:
        score = dims.get(dim)
        peer = ring1_dims.get(dim, {})
        if score and score >= 8.0 and peer.get("peer_mean") and score - peer["peer_mean"] >= 0.5:
            if dim == "experience" and top_theme:
                if rc.can_claim_proposition:
                    protect_items.append(
                        f"**The {top_theme} reputation.** This is what guests "
                        f"consistently value. It's earned through consistency, not "
                        f"marketing, and it erodes the moment standards slip.")
                else:
                    protect_items.append(
                        f"**Guest experience quality.** Early review signals "
                        f"({rc.qualifier}) point to {top_theme} as a strength. "
                        f"Protect operational consistency while the evidence base builds.")
            elif dim == "trust":
                protect_items.append(
                    f"**Compliance record.** FSA {fsa}/5 with strong sub-scores is a "
                    f"genuine operational asset. Protect it by maintaining documentation "
                    f"rigour ahead of the next unannounced inspection.")
            elif dim == "visibility":
                protect_items.append(
                    f"**Search visibility.** {grc:,} Google reviews at {gr}/5 gives you "
                    f"a discovery advantage that took years to build. Protect it by "
                    f"continuing to respond to reviews and keeping your profile current.")
            elif dim == "experience":
                protect_items.append(
                    f"**Guest experience quality.** Your experience score leads peers. "
                    f"This is perishable — it depends on every service, not the average.")

    if not protect_items:
        # Fallback for venues without clear leads
        if gr and float(gr) >= 4.0:
            protect_items.append(f"**Your {gr}/5 Google rating.** This is your primary "
                                 f"commercial asset. Protect it through consistent delivery.")
        elif fsa and int(fsa) >= 4:
            protect_items.append(f"**Your FSA compliance record.** This is the foundation "
                                 f"everything else is built on.")

    for item in protect_items[:2]:
        w(f"- {item}")
    w("")

    # --- IMPROVE ---
    w("### Improve\n")
    improve_items = []

    # Find the dimension with the biggest commercial impact if improved
    exp = dims.get("experience")
    conv = dims.get("conversion")
    vis = dims.get("visibility")

    if conv and conv < 6.0 and exp and exp >= 7.0:
        improve_items.append(
            "**Demand capture.** You're generating interest that isn't being fully "
            "converted. Check that hours, menu, and booking/ordering options are "
            "complete and prominent on Google. Each missing element is lost footfall.")

    if vis and vis < 7.0:
        improve_items.append(
            f"**Review momentum.** At {grc} reviews, building toward the next "
            f"milestone (100, 250, 500) directly improves Google Maps ranking. "
            f"A systematic post-visit review prompt is the highest-ROI marketing action.")

    if exp and exp < 7.0:
        improve_items.append(
            "**Guest experience consistency.** The experience score suggests "
            "variability in what guests receive. Identify the specific operational "
            "gap — is it food, service, or ambience? — and fix it at the source.")

    # Peer-gap improvement
    for dim in DIM_ORDER:
        peer = ring1_dims.get(dim, {})
        score = dims.get(dim)
        if score and peer.get("peer_mean") and score - peer["peer_mean"] < -1.0:
            if dim == "trust" and fsa and int(fsa) < 5:
                improve_items.append(
                    f"**FSA rating.** At {fsa}/5 vs peer average, this is your "
                    f"widest competitive gap. Request a re-inspection once the "
                    f"specific inspector concerns have been addressed.")
                break

    if not improve_items:
        improve_items.append(
            "**Prestige positioning.** Your fundamentals are strong enough to "
            "support a credible awards submission. This is the clearest growth "
            "lever for a venue already operating well.")

    for item in improve_items[:2]:
        w(f"- {item}")
    w("")

    # --- IGNORE ---
    w("### Ignore\n")
    ignore_items = []

    prest = dims.get("prestige", 0)
    overall = scorecard.get("overall", 0)
    if prest < 3.0 and overall < 7.5:
        ignore_items.append(
            "**Awards and editorial pursuit.** Your fundamentals need strengthening "
            "before prestige investment makes sense. Awards don't fix a weak proposition; "
            "they amplify a strong one.")
    elif prest < 3.0:
        ignore_items.append(
            "**Prestige score anxiety.** Low prestige is normal — most excellent "
            "operators have zero editorial recognition. It does not affect footfall, "
            "discovery, or day-to-day revenue. Pursue it when the time is right, "
            "but don't let it distract from operational priorities.")

    if conv and conv < 5.0 and not (exp and exp >= 7.0):
        ignore_items.append(
            "**Delivery and takeaway channels** unless they genuinely fit your "
            "proposition. Not every venue needs to be on every platform. Focus "
            "on the channels that match your market position.")

    if not ignore_items:
        ignore_items.append(
            "**Competitor mimicry.** Your competitive position is earned through "
            "your own strengths, not by copying what peers do. Avoid reactive "
            "changes driven by what competitors are promoting this month.")

    for item in ignore_items[:2]:
        w(f"- {item}")
    w("")
