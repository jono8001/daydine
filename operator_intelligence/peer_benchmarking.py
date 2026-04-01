"""
operator_intelligence/peer_benchmarking.py — 3-Ring Peer Benchmarking

Ring 1: Local direct peers — same category within 5 miles
Ring 2: Extended catchment — same category within 15 miles
Ring 3: UK peer cohort — all venues in same category (full dataset)

For each ring, computes rank and percentile on every dimension
plus overall score. Stratford is a small market so rings may overlap;
that's fine — the point is widening the comparison lens.
"""

import math
from operator_intelligence.scorecard import DIMENSION_WEIGHTS

# ---------------------------------------------------------------------------
# Distance calculation (Haversine)
# ---------------------------------------------------------------------------

def _haversine_miles(lat1, lon1, lat2, lon2):
    """Great-circle distance in miles between two lat/lon points."""
    R = 3959  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Ring definitions
# ---------------------------------------------------------------------------

RING_DEFS = {
    "ring1_local":    {"radius_miles": 5,  "label": "Local Peers (5mi)"},
    "ring2_catchment": {"radius_miles": 15, "label": "Catchment (15mi)"},
    "ring3_uk_cohort": {"radius_miles": None, "label": "UK Category Cohort"},
}


def _build_peer_set(venue, all_cards, radius_miles, match_category=True):
    """Find peers within radius and optionally same category.
    Returns list of scorecards (excluding the venue itself)."""
    v_lat = venue.get("lat")
    v_lon = venue.get("lon")
    v_cat = venue.get("category")
    v_id = str(venue.get("fhrsid"))

    peers = []
    for fid, card in all_cards.items():
        if str(fid) == v_id:
            continue
        if match_category and card.get("category") != v_cat:
            continue

        # Distance filter
        if radius_miles is not None:
            p_lat = card.get("lat")
            p_lon = card.get("lon")
            if p_lat is None or p_lon is None or v_lat is None or v_lon is None:
                continue
            dist = _haversine_miles(v_lat, v_lon, p_lat, p_lon)
            if dist > radius_miles:
                continue

        peers.append(card)
    return peers


def _rank_in_peers(venue_score, peer_scores):
    """Rank (1-based) and percentile of venue_score among peers.
    Percentile = % of peers scored at or below this venue."""
    if not peer_scores:
        return None, None
    all_scores = sorted(peer_scores + [venue_score], reverse=True)
    rank = all_scores.index(venue_score) + 1
    at_or_below = sum(1 for s in peer_scores if s <= venue_score)
    percentile = round(at_or_below / len(peer_scores) * 100, 1)
    return rank, percentile


def _benchmarks_for_dimension(venue, peers, dim):
    """Compute rank, percentile, peer mean, peer top for one dimension."""
    v_score = venue.get(dim)
    if v_score is None:
        return None

    peer_scores = [p[dim] for p in peers if p.get(dim) is not None]
    if not peer_scores:
        return None

    rank, pct = _rank_in_peers(v_score, peer_scores)
    return {
        "score": v_score,
        "rank": rank,
        "of": len(peer_scores) + 1,
        "percentile": pct,
        "peer_mean": round(sum(peer_scores) / len(peer_scores), 2),
        "peer_top": round(max(peer_scores), 2),
        "peer_bottom": round(min(peer_scores), 2),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_peer_benchmarks(venue_card, all_cards):
    """Compute 3-ring peer benchmarks for a single venue.

    Returns dict:
    {
        "ring1_local": {
            "label": "Local Peers (5mi)",
            "peer_count": N,
            "dimensions": {
                "experience": {score, rank, of, percentile, peer_mean, ...},
                ...
            }
        },
        ...
    }
    """
    results = {}
    dims = list(DIMENSION_WEIGHTS.keys()) + ["overall"]

    for ring_key, ring_def in RING_DEFS.items():
        peers = _build_peer_set(
            venue_card, all_cards,
            radius_miles=ring_def["radius_miles"],
            match_category=True,
        )

        ring_result = {
            "label": ring_def["label"],
            "peer_count": len(peers),
            "dimensions": {},
        }

        for dim in dims:
            bench = _benchmarks_for_dimension(venue_card, peers, dim)
            if bench:
                ring_result["dimensions"][dim] = bench

        # Top peers list (up to 5, sorted by overall)
        sorted_peers = sorted(
            [p for p in peers if p.get("overall") is not None],
            key=lambda x: -x["overall"]
        )
        ring_result["top_peers"] = [
            {"name": p["name"], "overall": p["overall"],
             "category": p["category"]}
            for p in sorted_peers[:5]
        ]

        results[ring_key] = ring_result

    return results


def format_peer_summary(benchmarks):
    """One-line summary string per ring for report use."""
    lines = []
    for ring_key in ["ring1_local", "ring2_catchment", "ring3_uk_cohort"]:
        ring = benchmarks.get(ring_key)
        if not ring or ring["peer_count"] == 0:
            continue
        overall = ring["dimensions"].get("overall")
        if overall:
            lines.append(
                f"{ring['label']}: #{overall['rank']} of {overall['of']} "
                f"(P{overall['percentile']}) — "
                f"peer avg {overall['peer_mean']}, top {overall['peer_top']}"
            )
    return lines
