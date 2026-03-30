#!/usr/bin/env python3
"""
restaurant_confidence.py — Restaurant Confidence Score (RCS) Engine

Computes a composite 0-10 confidence score for UK restaurants by
combining multiple data sources with weighted aggregation, convergence
adjustment, temporal decay, and penalty rules.

Based on the methodology in UK-Restaurant-Tracker-Methodology-Spec.docx:
  RCS = C(n) * sum(w_i * S_i(t)) - P

Where:
  S_i(t) = source score with temporal decay
  w_i    = source weight (normalised to sum to 1.0 across available sources)
  C(n)   = convergence adjustment (confidence scales with number of sources)
  P      = penalty deductions (critical violations)

Usage:
    # Score a single establishment from Firebase
    python restaurant_confidence.py --id <firebase_key>

    # Score all establishments in a local authority
    python restaurant_confidence.py --la "Camden"

    # Dry run (compute but don't write)
    python restaurant_confidence.py --la "Camden" --dry-run

Requires:
    pip install requests python-dotenv
"""

import argparse
import math
import os
import sys
import time
from datetime import datetime, timezone
from urllib.parse import quote

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv()

FIREBASE_DB_URL = os.getenv(
    "FIREBASE_DATABASE_URL",
    "https://recursive-research-eu-default-rtdb.europe-west1.firebasedatabase.app",
)

# ---------------------------------------------------------------------------
# Source weights (base weights before normalisation)
# When a source is missing, remaining weights are renormalised.
# ---------------------------------------------------------------------------
SOURCE_WEIGHTS = {
    "fsa":         0.30,   # FSA hygiene rating (0-5 → normalised to 0-10)
    "google":      0.30,   # Google Places rating + review volume
    "tripadvisor": 0.20,   # TripAdvisor rating + review volume (Phase 3)
    "editorial":   0.10,   # Editorial mentions sentiment (Phase 3)
    "recency":     0.10,   # Recency / freshness bonus (Phase 3)
}

# ---------------------------------------------------------------------------
# Convergence adjustment C(n)
# With only 1 source the score is heavily discounted; with 4+ sources
# we approach full confidence.
#
#   C(n) = 1 - e^(-k * n)     where k controls the curve steepness
#
# n=1 → ~0.63, n=2 → ~0.86, n=3 → ~0.95, n=4 → ~0.98
# ---------------------------------------------------------------------------
CONVERGENCE_K = 1.0

def convergence(n):
    """Convergence factor C(n): 0→0, 1→0.63, 2→0.86, 3→0.95, 4+→~1.0."""
    if n <= 0:
        return 0.0
    return 1.0 - math.exp(-CONVERGENCE_K * n)


# ---------------------------------------------------------------------------
# Temporal decay
# Scores lose relevance over time. Half-life varies by source.
#
#   decay(age_days) = 2^(-age_days / half_life)
#
# ---------------------------------------------------------------------------
HALF_LIFE_DAYS = {
    "fsa":         730,    # FSA inspections ~2 year half-life
    "google":      365,    # Google ratings refreshed yearly
    "tripadvisor": 365,
    "editorial":   180,    # Editorial mentions decay faster
}

def temporal_decay(age_days, source):
    """Exponential decay factor based on age and source half-life."""
    half_life = HALF_LIFE_DAYS.get(source, 365)
    if age_days <= 0:
        return 1.0
    return 2.0 ** (-age_days / half_life)


# ---------------------------------------------------------------------------
# Source scorers — each returns (score_0_to_10, age_days) or None
# ---------------------------------------------------------------------------

def score_fsa(record):
    """
    FSA hygiene rating 0-5 → 0-10 scale.
    Score = (r / 5) * 10
    Age based on last inspection date (rd field).
    """
    r = record.get("r")
    if r is None:
        return None

    try:
        rating = float(r)
    except (ValueError, TypeError):
        return None

    score = (rating / 5.0) * 10.0

    # Age from last inspection
    rd = record.get("rd")
    age_days = 0
    if rd:
        try:
            inspection_date = datetime.fromisoformat(rd.replace("Z", "+00:00"))
            if inspection_date.tzinfo is None:
                inspection_date = inspection_date.replace(tzinfo=timezone.utc)
            age_days = max(0, (datetime.now(timezone.utc) - inspection_date).days)
        except (ValueError, TypeError):
            pass

    return score, age_days


def score_google(record):
    """
    Google Places rating 1.0-5.0 → 0-10 scale, adjusted by review volume.

    Base: (gr / 5) * 10
    Volume adjustment: log10(grc + 1) / log10(1001) — scales 0→0, 1000→1.0
    Final: base * (0.7 + 0.3 * volume_factor)

    This means a 4.5-star place with 500 reviews scores higher than
    a 4.5-star place with 3 reviews.
    """
    gr = record.get("gr")
    if gr is None:
        return None

    try:
        rating = float(gr)
    except (ValueError, TypeError):
        return None

    base = (rating / 5.0) * 10.0

    # Volume adjustment
    grc = record.get("grc", 0)
    try:
        review_count = max(0, int(grc))
    except (ValueError, TypeError):
        review_count = 0

    volume_factor = math.log10(review_count + 1) / math.log10(1001)
    volume_factor = min(1.0, volume_factor)

    score = base * (0.7 + 0.3 * volume_factor)

    # Google ratings are current — age = 0
    return score, 0


def score_tripadvisor(record):
    """Placeholder for TripAdvisor scoring (Phase 3)."""
    # Fields TBD: ta_rating, ta_review_count
    return None


def score_editorial(record):
    """Placeholder for editorial/press scoring (Phase 3)."""
    # Fields TBD: ed_sentiment, ed_count, ed_date
    return None


SOURCE_SCORERS = {
    "fsa":         score_fsa,
    "google":      score_google,
    "tripadvisor": score_tripadvisor,
    "editorial":   score_editorial,
}


# ---------------------------------------------------------------------------
# Penalty rules
# Critical violations that deduct from the final score.
# ---------------------------------------------------------------------------

def compute_penalties(record):
    """
    Deduct points for critical issues.
    Returns a non-negative penalty value.
    """
    penalty = 0.0

    # FSA rating 0 or 1 = critical hygiene concern → penalty
    r = record.get("r")
    if r is not None:
        try:
            rating = int(r)
            if rating == 0:
                penalty += 2.0   # Urgent improvement
            elif rating == 1:
                penalty += 1.0   # Major improvement necessary
        except (ValueError, TypeError):
            pass

    return penalty


# ---------------------------------------------------------------------------
# RCS computation
# ---------------------------------------------------------------------------

def compute_rcs(record):
    """
    Compute Restaurant Confidence Score for a single establishment.

    Returns dict with:
      rcs:      float 0.0-10.0 (final score)
      sources:  int (number of sources used)
      breakdown: dict of per-source details
    """
    breakdown = {}
    available_weights = {}

    for source, scorer in SOURCE_SCORERS.items():
        result = scorer(record)
        if result is None:
            continue

        raw_score, age_days = result
        decay = temporal_decay(age_days, source)
        decayed_score = raw_score * decay

        breakdown[source] = {
            "raw": round(raw_score, 2),
            "age_days": age_days,
            "decay": round(decay, 3),
            "decayed": round(decayed_score, 2),
        }
        available_weights[source] = SOURCE_WEIGHTS[source]

    n_sources = len(breakdown)
    if n_sources == 0:
        return {"rcs": 0.0, "sources": 0, "breakdown": {}}

    # Renormalise weights to sum to 1.0 across available sources
    total_weight = sum(available_weights.values())
    normalised = {s: w / total_weight for s, w in available_weights.items()}

    # Weighted sum
    weighted_sum = sum(
        normalised[s] * breakdown[s]["decayed"] for s in breakdown
    )

    # Convergence adjustment
    conv = convergence(n_sources)

    # Penalties
    penalty = compute_penalties(record)

    # Final RCS
    rcs = max(0.0, min(10.0, conv * weighted_sum - penalty))

    return {
        "rcs": round(rcs, 1),
        "sources": n_sources,
        "convergence": round(conv, 3),
        "penalty": round(penalty, 1),
        "breakdown": breakdown,
    }


# ---------------------------------------------------------------------------
# Firebase REST helpers
# ---------------------------------------------------------------------------

def fb_read(path, params=None):
    url = f"{FIREBASE_DB_URL}/{path}.json"
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fb_update(path, data):
    url = f"{FIREBASE_DB_URL}/{path}.json"
    resp = requests.patch(url, json=data, timeout=15)
    resp.raise_for_status()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Compute Restaurant Confidence Scores (RCS 0-10)"
    )
    parser.add_argument("--la", help="Local authority to score")
    parser.add_argument("--id", help="Single Firebase establishment key to score")
    parser.add_argument("--dry-run", action="store_true", help="Compute but don't write to Firebase")
    parser.add_argument("--limit", type=int, default=0, help="Max records to process (0=all)")
    args = parser.parse_args()

    if not args.la and not args.id:
        print("ERROR: Provide --la or --id")
        sys.exit(1)

    if args.id:
        print(f"Scoring single establishment: {args.id}")
        record = fb_read(f"daydine/establishments/{args.id}")
        if not record:
            print("Not found.")
            sys.exit(1)

        result = compute_rcs(record)
        print(f"\n  Name:    {record.get('n', '—')}")
        print(f"  RCS:     {result['rcs']} / 10.0")
        print(f"  Sources: {result['sources']}")
        print(f"  Conv:    {result.get('convergence', '—')}")
        print(f"  Penalty: {result.get('penalty', 0)}")
        for src, detail in result["breakdown"].items():
            print(f"  {src:15s}  raw={detail['raw']:5.1f}  decay={detail['decay']:.3f}  "
                  f"decayed={detail['decayed']:5.1f}  age={detail['age_days']}d")

        if not args.dry_run:
            fb_update(f"daydine/establishments/{args.id}", {"rcs": result["rcs"]})
            print(f"\n  Written rcs={result['rcs']} to Firebase")
        return

    # Score by LA
    print(f"Fetching establishments for LA: {args.la}")
    data = fb_read("daydine/establishments", {
        "orderBy": '"la"',
        "equalTo": f'"{args.la}"',
    })

    if not data:
        print(f"No establishments found for LA '{args.la}'")
        sys.exit(0)

    entries = list(data.items())
    print(f"Found {len(entries)} establishments")

    if args.limit > 0:
        entries = entries[:args.limit]

    scored = 0
    for i, (key, record) in enumerate(entries, 1):
        result = compute_rcs(record)
        name = record.get("n", "—")

        if result["sources"] == 0:
            if i <= 10 or i == len(entries):
                print(f"  [{i}/{len(entries)}] {name}: no data sources, skipping")
            continue

        if args.dry_run:
            print(f"  [{i}/{len(entries)}] {name}: RCS={result['rcs']} "
                  f"(sources={result['sources']}, conv={result.get('convergence','—')})")
        else:
            fb_update(f"daydine/establishments/{key}", {"rcs": result["rcs"]})
            print(f"  [{i}/{len(entries)}] {name}: RCS={result['rcs']} → written")

        scored += 1

    print(f"\nDone. Scored: {scored}/{len(entries)}")


if __name__ == "__main__":
    main()
