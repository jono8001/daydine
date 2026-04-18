"""
operator_intelligence/v4_peer_benchmarks.py — Lightweight V4-aware peer
benchmarks.

The existing V3.4 `peer_benchmarking` module is useful but requires the
full V3.4 scorecard pipeline. For V4 report samples we need a smaller,
self-contained helper that:

  * scopes the peer pool to Rankable-A ∪ Rankable-B only (spec §5.8
    and samples-assessment §6.1 point 1);
  * computes three rings — local (same LA), catchment (haversine ≤
    15 mi), and UK cohort (same Google place-type slug where
    available, else whole pool);
  * ranks on `rcs_v4_final`;
  * returns a dict in the shape the report generator expects
    (ring1_local / ring2_catchment / ring3_uk_cohort, each with
    `dimensions.overall = {rank, of, peer_mean, peer_top}` plus
    `peer_count`).

Does not wire through V3.4 scorecard computation; does not compute
per-dimension peer stats (only the overall ring). That is sufficient
for the Market Position table and the Executive Summary peer line. If
deeper peer analysis is needed later, the existing V3.4 module can be
fronted by a class-filter once it is refactored.
"""
from __future__ import annotations

import math
from statistics import mean
from typing import Optional


RANKABLE_CLASSES = {"Rankable-A", "Rankable-B"}


def _haversine_m(a_lat, a_lon, b_lat, b_lon) -> float:
    if None in (a_lat, a_lon, b_lat, b_lon):
        return float("inf")
    R = 6_371_000.0
    p1 = math.radians(float(a_lat))
    p2 = math.radians(float(b_lat))
    dp = math.radians(float(b_lat) - float(a_lat))
    dl = math.radians(float(b_lon) - float(a_lon))
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def _rankable_pool(v4_scores: dict, establishments: dict) -> list[dict]:
    """Return a list of rankable peers keyed by fhrsid, with score and
    location attached."""
    peers: list[dict] = []
    for fid, payload in v4_scores.items():
        if payload.get("confidence_class") not in RANKABLE_CLASSES:
            continue
        if not payload.get("rankable"):
            continue
        final = payload.get("rcs_v4_final")
        if final is None:
            continue
        rec = establishments.get(fid) or {}
        peers.append({
            "fhrsid": str(fid),
            "name": payload.get("name") or rec.get("n"),
            "final": float(final),
            "la": rec.get("la"),
            "lat": rec.get("lat"),
            "lon": rec.get("lon"),
        })
    return peers


def _rank_in(pool: list[dict], venue_fid: str) -> tuple[
        Optional[int], int, Optional[float], Optional[float]]:
    """Return (rank, of, peer_mean, peer_top) for a venue inside a pool."""
    if not pool:
        return None, 0, None, None
    sorted_pool = sorted(pool, key=lambda r: -r["final"])
    total = len(sorted_pool)
    venue_rank = next((i + 1 for i, r in enumerate(sorted_pool)
                        if r["fhrsid"] == str(venue_fid)), None)
    others = [r["final"] for r in sorted_pool
               if r["fhrsid"] != str(venue_fid)]
    peer_mean_ = round(mean(others), 3) if others else None
    peer_top = round(sorted_pool[0]["final"], 3) if sorted_pool else None
    return venue_rank, total, peer_mean_, peer_top


def compute_v4_peer_benchmarks(venue_fid: str,
                                 venue_record: dict,
                                 v4_scores: dict,
                                 establishments: dict,
                                 catchment_miles: float = 15.0
                                 ) -> dict:
    """Return benchmarks dict matching the generator's expected shape.

    Only Rankable-A / Rankable-B venues are counted. The requesting
    venue is included in the pool for ranking purposes but excluded
    from peer_mean / peer_top.
    """
    pool = _rankable_pool(v4_scores, establishments)
    venue_in_pool = any(r["fhrsid"] == str(venue_fid) for r in pool)
    if not venue_in_pool:
        # Requesting venue is not Rankable; return empty structure so
        # the report renders the "why not ranked" explainer.
        return {
            "ring1_local": {"peer_count": 0, "dimensions": {"overall": {}}},
            "ring2_catchment": {"peer_count": 0, "dimensions": {"overall": {}}},
            "ring3_uk_cohort": {"peer_count": 0, "dimensions": {"overall": {}}},
        }

    # --- Ring 1: same LA ---------------------------------------------------
    la = venue_record.get("la")
    ring1 = [r for r in pool if (r.get("la") == la) or r["fhrsid"] == str(venue_fid)]
    r1_rank, r1_of, r1_mean, r1_top = _rank_in(ring1, venue_fid)

    # --- Ring 2: haversine catchment ---------------------------------------
    catchment_m = catchment_miles * 1609.34
    v_lat = venue_record.get("lat")
    v_lon = venue_record.get("lon")
    ring2 = []
    for r in pool:
        d = _haversine_m(v_lat, v_lon, r.get("lat"), r.get("lon"))
        if d <= catchment_m or r["fhrsid"] == str(venue_fid):
            ring2.append(r)
    r2_rank, r2_of, r2_mean, r2_top = _rank_in(ring2, venue_fid)

    # --- Ring 3: whole rankable pool (UK cohort placeholder) ---------------
    r3_rank, r3_of, r3_mean, r3_top = _rank_in(pool, venue_fid)

    def _ring(peer_count, rank, of_, mean_, top):
        return {
            "peer_count": peer_count,
            "dimensions": {
                "overall": {
                    "rank": rank,
                    "of": of_,
                    "peer_mean": mean_,
                    "peer_top": top,
                }
            },
        }

    return {
        "ring1_local": _ring(len(ring1) - 1, r1_rank, r1_of, r1_mean, r1_top),
        "ring2_catchment": _ring(len(ring2) - 1, r2_rank, r2_of, r2_mean, r2_top),
        "ring3_uk_cohort": _ring(len(pool) - 1, r3_rank, r3_of, r3_mean, r3_top),
    }
