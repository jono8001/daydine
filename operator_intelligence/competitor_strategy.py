"""
operator_intelligence/competitor_strategy.py — Competitor Strategy Reads

Selects the top 2–3 most strategically relevant peers and derives a
compact comparative read from external/public signals only.

Never claims knowledge of a competitor's internal operations.
"""

from operator_intelligence.report_spec import (
    CompetitorRead, COMPETITOR_READ_NOT_ASSESSABLE,
)

HEADLINE_DIMS = ["experience", "visibility", "trust", "conversion"]

# Dimension → commercial meaning when a peer leads
_DIM_COMMERCIAL_MEANING = {
    "experience": "guests rate their visit higher — this drives reviews, repeats, and word-of-mouth",
    "visibility": "they are easier to find online — this controls top-of-funnel discovery",
    "trust": "their compliance record is stronger — this creates a ceiling you hit and they don't",
    "conversion": "they convert interest into visits more effectively — their digital shopfront is more complete",
}

# Dimension → what the observable driver likely is
_DIM_SIGNAL_EXPLANATION = {
    "experience": lambda v, p: _explain_experience(v, p),
    "visibility": lambda v, p: _explain_visibility(v, p),
    "trust": lambda v, p: _explain_trust(v, p),
    "conversion": lambda v, p: _explain_conversion(v, p),
}


def _explain_experience(venue, peer):
    vgr = venue.get("google_rating")
    pgr = peer.get("google_rating")
    if pgr and vgr:
        if float(pgr) > float(vgr):
            return f"Google {pgr}/5 vs your {vgr}/5"
        elif float(pgr) == float(vgr):
            return f"same Google rating ({pgr}/5) but higher experience score — likely stronger FSA food hygiene sub-scores"
    return "higher composite experience score from rating + compliance signals"


def _explain_visibility(venue, peer):
    vrc = venue.get("google_reviews") or 0
    prc = peer.get("google_reviews") or 0
    if prc > vrc:
        return f"{prc} Google reviews vs your {vrc} — they have volume advantage"
    elif vrc > prc:
        return f"you have {vrc} reviews vs their {prc} — but they score higher on other visibility signals"
    return "comparable review volume but stronger profile completeness"


def _explain_trust(venue, peer):
    vfsa = venue.get("fsa_rating")
    pfsa = peer.get("fsa_rating")
    if pfsa and vfsa:
        if int(pfsa) > int(vfsa):
            return f"FSA {pfsa}/5 vs your {vfsa}/5"
        elif int(pfsa) == int(vfsa):
            return "same FSA rating but likely stronger sub-scores or more recent inspection"
    return "stronger compliance signals"


def _explain_conversion(venue, peer):
    # We don't have per-peer operational detail in the scorecard,
    # but we can note the gap exists
    return "more complete operational signals (hours, menu, delivery/takeaway, booking)"


# ---------------------------------------------------------------------------
# Peer selection
# ---------------------------------------------------------------------------

def _select_strategy_peers(venue_card, benchmarks, max_peers=3):
    """Select the top 2–3 most strategically relevant peers.

    Prefers peers that are:
    - Ahead of or close to the venue (within +0.5 above or -0.3 below)
    - From ring1 (local, 5mi) first, then ring2 if needed
    """
    v_overall = venue_card.get("overall") or 0
    selected = []

    for ring_key in ["ring1_local", "ring2_catchment"]:
        ring = benchmarks.get(ring_key, {})
        top_peers = ring.get("top_peers", [])

        for peer in top_peers:
            p_overall = peer.get("overall") or 0
            gap = p_overall - v_overall

            # Strategically relevant: ahead or close
            if -0.3 <= gap <= 0.5:
                # Skip if already selected (can appear in multiple rings)
                if any(s["name"] == peer["name"] for s in selected):
                    continue
                selected.append(peer)

            if len(selected) >= max_peers:
                break

        if len(selected) >= max_peers:
            break

    # If we found fewer than 2, relax criteria: take top peers that lead
    if len(selected) < 2:
        for ring_key in ["ring1_local", "ring2_catchment"]:
            ring = benchmarks.get(ring_key, {})
            for peer in ring.get("top_peers", []):
                if any(s["name"] == peer["name"] for s in selected):
                    continue
                selected.append(peer)
                if len(selected) >= max_peers:
                    break
            if len(selected) >= max_peers:
                break

    return selected[:max_peers]


# ---------------------------------------------------------------------------
# Strategic read generation
# ---------------------------------------------------------------------------

def _generate_one_read(venue_card, peer, venue_rec, all_data):
    """Generate a CompetitorRead for one peer from external signals."""
    peer_name = peer.get("name", "Unknown")
    v_overall = venue_card.get("overall") or 0
    p_overall = peer.get("overall") or 0

    # Count available signals for confidence assessment
    signal_count = sum(1 for d in HEADLINE_DIMS if peer.get(d) is not None)
    has_google = peer.get("google_rating") is not None
    has_fsa = peer.get("fsa_rating") is not None

    if signal_count < 2:
        return CompetitorRead(
            peer_name=peer_name,
            what_they_win_on=COMPETITOR_READ_NOT_ASSESSABLE,
            why_it_matters="—",
            what_to_copy="—",
            what_to_defend="—",
            confidence="limited",
            basis=f"Only {signal_count} dimension scores available for this peer.",
        )

    # Find where peer leads and where venue leads
    peer_leads = []  # (dim, gap, explanation)
    venue_leads = []

    for dim in HEADLINE_DIMS:
        v_score = venue_card.get(dim)
        p_score = peer.get(dim)
        if v_score is None or p_score is None:
            continue
        gap = p_score - v_score
        explain_fn = _DIM_SIGNAL_EXPLANATION.get(dim)
        explanation = explain_fn(venue_card, peer) if explain_fn else ""

        if gap >= 0.5:
            peer_leads.append((dim, gap, explanation))
        elif gap <= -0.5:
            venue_leads.append((dim, abs(gap), explanation))

    # Build the strategic read
    # What they win on
    if peer_leads:
        peer_leads.sort(key=lambda x: -x[1])
        wins = []
        for dim, gap, expl in peer_leads[:2]:
            wins.append(f"{dim.title()} (+{gap:.1f}): {expl}")
        what_they_win_on = "; ".join(wins)
    else:
        what_they_win_on = f"No significant dimension lead — scores within 0.5 of yours across the board"

    # Why it matters
    if peer_leads:
        top_dim = peer_leads[0][0]
        why = _DIM_COMMERCIAL_MEANING.get(top_dim, "this affects competitive position")
        what_matters = f"Their {top_dim} lead means {why}."
    else:
        what_matters = "You are closely matched — small improvements on either side shift the balance."

    # What to copy
    if peer_leads:
        top_dim, top_gap, top_expl = peer_leads[0]
        if top_dim == "trust" and has_fsa:
            pfsa = peer.get("fsa_rating")
            vfsa = venue_card.get("fsa_rating")
            if pfsa and vfsa and int(pfsa) > int(vfsa):
                copy = f"Target FSA re-inspection to match their {pfsa}/5 rating."
            else:
                copy = "Review inspection documentation and sub-score gaps."
        elif top_dim == "visibility":
            prc = peer.get("google_reviews") or 0
            vrc = venue_card.get("google_reviews") or 0
            if prc > vrc:
                copy = f"Systematic review generation — they have {prc} reviews to your {vrc}."
            else:
                copy = "Improve profile completeness (photos, GBP attributes)."
        elif top_dim == "conversion":
            copy = "Audit your Google profile vs theirs: check hours, menu, booking, delivery signals."
        elif top_dim == "experience":
            pgr = peer.get("google_rating")
            copy = f"Investigate what drives their {pgr}/5 — read their recent positive reviews for clues."
        else:
            copy = f"Investigate their {top_dim} advantage — observable signals suggest a lead."
    else:
        copy = "No clear action to copy — maintain current standards."

    # What to defend
    if venue_leads:
        venue_leads.sort(key=lambda x: -x[1])
        top_def = venue_leads[0]
        dim, gap, expl = top_def
        vrc = venue_card.get("google_reviews") or 0
        prc = peer.get("google_reviews") or 0
        if dim == "visibility" and vrc > prc:
            defend = f"Your {vrc}-review volume advantage — this took years to build and is your discovery moat."
        elif dim == "experience":
            defend = f"Your experience lead (+{gap:.1f}) — this drives repeat visits and is hard to replicate quickly."
        else:
            defend = f"Your {dim.title()} advantage (+{gap:.1f}) — protect it through consistency."
    else:
        defend = "No clear defensive advantage identified — you are closely matched across dimensions."

    # Confidence
    if signal_count >= 4 and has_google and has_fsa:
        confidence = "signal-backed"
    elif signal_count >= 3:
        confidence = "partial"
    else:
        confidence = "limited"

    # Basis
    basis_parts = []
    if has_google:
        basis_parts.append("Google rating/reviews")
    if has_fsa:
        basis_parts.append("FSA record")
    basis_parts.append(f"{signal_count} dimension scores")
    basis = f"Based on {', '.join(basis_parts)}"

    return CompetitorRead(
        peer_name=peer_name,
        what_they_win_on=what_they_win_on,
        why_it_matters=what_matters,
        what_to_copy=copy,
        what_to_defend=defend,
        confidence=confidence,
        basis=basis,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_competitor_reads(venue_card, venue_rec, benchmarks, all_data=None):
    """Generate strategic reads for the top 2–3 most relevant peers.

    Returns a list of CompetitorRead instances.
    """
    peers = _select_strategy_peers(venue_card, benchmarks)
    if not peers:
        return []

    reads = []
    for peer in peers:
        read = _generate_one_read(venue_card, peer, venue_rec, all_data)
        reads.append(read)

    return reads
