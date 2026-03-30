#!/usr/bin/env python3
"""
rcs_scoring_stratford.py — Fetch Stratford establishments from Firebase,
run the full 7-stage RCS scoring pipeline, and output results.

Implements the Evidtrace RCS methodology:
  1. NORMALISE — raw signals to 0-10
  2. TEMPORAL DECAY — exponential decay with 300-day half-life
  3. PENALTY RULES — 16+ multiplier rules across 5 groups
  4. WEIGHTED AGGREGATION — SCP-weighted composite
  5. CONVERGENCE ADJUSTMENT — pairwise divergence
  6. CALIBRATION CORRECTION — ground-truth alignment
  7. TIER ASSIGNMENT — 5-tier classification

Usage:
    python rcs_scoring_stratford.py
    python rcs_scoring_stratford.py --la "Newham"          # London Stratford
    python rcs_scoring_stratford.py --la "Stratford-on-Avon"
    python rcs_scoring_stratford.py --from-cache            # use saved JSON

Requires:
    pip install requests
"""

import argparse
import csv
import json
import math
import os
import sys
from collections import Counter
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
FIREBASE_DB_URL = os.getenv(
    "FIREBASE_DATABASE_URL",
    "https://recursive-research-eu-default-rtdb.europe-west1.firebasedatabase.app",
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_CACHE = os.path.join(SCRIPT_DIR, "stratford_establishments.json")
CSV_INPUT = os.path.join(SCRIPT_DIR, "stratford_establishments.csv")
CSV_OUTPUT = os.path.join(SCRIPT_DIR, "stratford_rcs_scores.csv")

NOW = datetime.now(timezone.utc)

# ---------------------------------------------------------------------------
# Source Credibility Priors (SCP) — from methodology spec
# ---------------------------------------------------------------------------
SCP = {
    "fsa":         0.92,
    "google":      0.72,
    "tripadvisor": 0.68,
    "editorial":   0.90,
    "enforcement": 0.94,
}

# ---------------------------------------------------------------------------
# Category weights — from methodology spec
# ---------------------------------------------------------------------------
CATEGORY_WEIGHTS = {
    "fsa":          0.20,   # Food Hygiene (FSA)
    "google":       0.25,   # Primary Review (Google)
    "tripadvisor":  0.12,   # Secondary Review (TripAdvisor)
    "editorial":    0.18,   # Editorial Recognition
    "consistency":  0.15,   # Review Consistency
    "recency":      0.10,   # Recency Trend
}

# ---------------------------------------------------------------------------
# Temporal decay: T_weight(t) = e^(-lambda * t)
# lambda = 0.0023 → 300-day half-life
# ---------------------------------------------------------------------------
LAMBDA_DECAY = 0.0023
STALE_THRESHOLD_DAYS = 548   # ~18 months — flagged stale
EXCLUDE_THRESHOLD_DAYS = 730  # ~24 months — excluded

def temporal_weight(age_days):
    """Exponential decay with lambda=0.0023 (300-day half-life)."""
    if age_days <= 0:
        return 1.0
    if age_days > EXCLUDE_THRESHOLD_DAYS:
        return 0.0  # excluded
    return math.exp(-LAMBDA_DECAY * age_days)


def days_since(date_str):
    """Parse a date string and return days since that date."""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, (NOW - dt).days)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Stage 1: NORMALISE — raw signals to 0-10 scale
# ---------------------------------------------------------------------------

def normalise_fsa(record):
    """FSA hygiene rating 0-5 → 0-10. Returns (score, age_days) or None."""
    rv = record.get("rv") or record.get("r")
    if rv is None:
        return None
    try:
        rating = float(rv)
    except (ValueError, TypeError):
        return None
    score = (rating / 5.0) * 10.0
    age = days_since(record.get("rd"))
    return score, age if age is not None else 0


def normalise_google(record):
    """Google rating 1-5 → 0-10. Returns (score, age_days) or None."""
    gr = record.get("gr")
    if gr is None:
        return None
    try:
        rating = float(gr)
    except (ValueError, TypeError):
        return None
    score = (rating / 5.0) * 10.0

    # Volume adjustment: log10(count+1) / log10(1001)
    grc = record.get("grc", 0)
    try:
        count = max(0, int(grc))
    except (ValueError, TypeError):
        count = 0
    vol = min(1.0, math.log10(count + 1) / math.log10(1001))
    score = score * (0.7 + 0.3 * vol)

    return score, 0  # Google ratings are current


def normalise_tripadvisor(record):
    """TripAdvisor rating → 0-10. Placeholder for Phase 3."""
    ta = record.get("ta")
    if ta is None:
        return None
    try:
        rating = float(ta)
    except (ValueError, TypeError):
        return None
    return (rating / 5.0) * 10.0, 0


def normalise_editorial(record):
    """Editorial recognition → 0-10. Placeholder for Phase 3."""
    return None


# ---------------------------------------------------------------------------
# Stage 2: TEMPORAL DECAY — applied in weighted aggregation
# ---------------------------------------------------------------------------
# (temporal_weight function defined above)


# ---------------------------------------------------------------------------
# Stage 3: PENALTY RULES — 16+ rules across 5 groups
# Returns list of (rule_name, multiplier) tuples.
# ---------------------------------------------------------------------------

def compute_penalty_multipliers(record, source_scores):
    """
    Apply penalty rules. Returns list of (rule_name, multiplier).
    Multipliers < 1.0 are penalties, > 1.0 are boosts.
    """
    penalties = []

    rv = None
    try:
        rv = float(record.get("rv") or record.get("r") or -1)
    except (ValueError, TypeError):
        pass

    gr = record.get("gr")
    grc = record.get("grc", 0)
    try:
        grc = int(grc) if grc else 0
    except (ValueError, TypeError):
        grc = 0

    rd_age = days_since(record.get("rd"))

    # --- Review Integrity Group ---
    # Low review volume (< 10 Google reviews)
    if gr is not None and grc < 10:
        penalties.append(("low_review_volume", 0.90))

    # Owner response rate boost — not available yet, skip

    # --- Hygiene Group ---
    if rv is not None:
        # FSA rating decline: rating 0 or 1
        if rv <= 1:
            penalties.append(("fsa_critical", 0.80))
        # Enforcement action: rating 0
        if rv == 0:
            penalties.append(("enforcement_action", 0.60))
        # Score improvement post-action: rating improved — can't detect without history
        # Awaiting inspection: no rd or very old
        if rd_age is not None and rd_age > STALE_THRESHOLD_DAYS:
            penalties.append(("awaiting_inspection", 0.88))

    # --- Consistency Group ---
    fsa_score = source_scores.get("fsa")
    google_score = source_scores.get("google")
    if fsa_score is not None and google_score is not None:
        # Rating-hygiene divergence: big gap between FSA and Google normalised scores
        divergence = abs(fsa_score - google_score)
        if divergence > 4.0:
            penalties.append(("rating_hygiene_divergence", 0.85))
        elif divergence > 3.0:
            penalties.append(("platform_divergence", 0.88))

    # --- Temporal Group ---
    if rd_age is not None:
        if rd_age > 365:
            penalties.append(("declining_trend", 0.88))

    # New establishment < 6 months — can't detect without creation date

    # --- Anti-accumulation cap ---
    # 4 most severe at full weight, additional at 0.95x each
    if len(penalties) > 4:
        penalties.sort(key=lambda x: x[1])
        capped = penalties[:4]
        for name, mult in penalties[4:]:
            # Dampen additional penalties
            dampened = 1.0 - (1.0 - mult) * 0.95
            capped.append((name + "_dampened", dampened))
        penalties = capped

    return penalties


# ---------------------------------------------------------------------------
# Stage 4: WEIGHTED AGGREGATION
# RCS_base = sum(w_i * SCP_i * S_i) / sum(w_i * SCP_i)
# ---------------------------------------------------------------------------

def weighted_aggregation(source_scores, source_ages):
    """
    Compute weighted base score with SCP and temporal decay.
    Returns (rcs_base, available_sources dict).
    """
    numerator = 0.0
    denominator = 0.0
    available = {}

    for source, score in source_scores.items():
        if score is None:
            continue
        w = CATEGORY_WEIGHTS.get(source, 0)
        scp = SCP.get(source, 0.7)
        age = source_ages.get(source, 0)
        t_weight = temporal_weight(age)

        if t_weight == 0.0:
            continue  # excluded (>24 months)

        weighted = w * scp * score * t_weight
        numerator += weighted
        denominator += w * scp
        available[source] = {
            "raw_score": round(score, 2),
            "age_days": age,
            "t_weight": round(t_weight, 3),
            "decayed": round(score * t_weight, 2),
            "w": w,
            "scp": scp,
        }

    if denominator == 0:
        return 0.0, available

    return numerator / denominator, available


# ---------------------------------------------------------------------------
# Stage 5: CONVERGENCE ADJUSTMENT
# Pairwise divergence with source-pair credibility weighting.
# C_factor = 1.0 - alpha * D_weighted, alpha = 0.15
# ---------------------------------------------------------------------------
ALPHA_CONVERGENCE = 0.15

def convergence_adjustment(source_scores):
    """
    Compute convergence factor based on pairwise divergence.
    With fewer sources, confidence is lower.
    """
    available = {k: v for k, v in source_scores.items() if v is not None}
    n = len(available)

    if n <= 1:
        # Single source: heavy discount
        return 0.6 if n == 1 else 0.0, []

    # Pairwise divergence
    sources = list(available.keys())
    total_div = 0.0
    total_cred = 0.0
    flags = []

    for i in range(len(sources)):
        for j in range(i + 1, len(sources)):
            s1, s2 = sources[i], sources[j]
            diff = abs(available[s1] - available[s2])
            # Weight by average SCP of the pair
            pair_cred = (SCP.get(s1, 0.7) + SCP.get(s2, 0.7)) / 2.0
            total_div += diff * pair_cred
            total_cred += pair_cred

            # Divergence flags
            if diff > 4.0:
                if {"fsa", "google"} == {s1, s2} or {"fsa", "tripadvisor"} == {s1, s2}:
                    flags.append("HYGIENE-RATING SPLIT")
                elif {"google", "tripadvisor"} == {s1, s2}:
                    flags.append("REVIEW PLATFORM CONFLICT")

    d_weighted = total_div / total_cred if total_cred > 0 else 0
    c_factor = max(0.3, 1.0 - ALPHA_CONVERGENCE * (d_weighted / 10.0))

    return c_factor, flags


# ---------------------------------------------------------------------------
# Stage 6: CALIBRATION CORRECTION
# Ground-truth cases — placeholder, returns 1.0 (no adjustment yet)
# ---------------------------------------------------------------------------

def calibration_correction(rcs_raw):
    """
    Apply calibration correction based on ground-truth cases.
    Currently a passthrough — to be populated with known-excellent,
    known-problematic, and known-mid-range restaurants.
    """
    return rcs_raw


# ---------------------------------------------------------------------------
# Stage 7: TIER ASSIGNMENT
# ---------------------------------------------------------------------------

TIERS = [
    (8.5, "Exceptional"),
    (7.0, "Recommended"),
    (5.0, "Acceptable"),
    (3.0, "Caution"),
    (0.0, "Avoid"),
]

def assign_tier(rcs):
    """Assign tier based on RCS score."""
    for threshold, tier_name in TIERS:
        if rcs >= threshold:
            return tier_name
    return "Avoid"


def confidence_level(n_sources, c_factor):
    """Determine confidence level based on source count and convergence."""
    if n_sources >= 3 and c_factor >= 0.85:
        return "High"
    elif n_sources >= 2 and c_factor >= 0.7:
        return "Medium"
    else:
        return "Low"


# ---------------------------------------------------------------------------
# Full RCS Pipeline
# ---------------------------------------------------------------------------

def compute_rcs(record):
    """
    Run the full 7-stage RCS pipeline on a single establishment record.

    Returns dict:
        rcs, tier, confidence, sources, c_factor, penalties, flags, breakdown
    """
    # Stage 1: Normalise
    source_scores = {}
    source_ages = {}

    fsa_result = normalise_fsa(record)
    if fsa_result:
        source_scores["fsa"] = fsa_result[0]
        source_ages["fsa"] = fsa_result[1]

    google_result = normalise_google(record)
    if google_result:
        source_scores["google"] = google_result[0]
        source_ages["google"] = google_result[1]

    ta_result = normalise_tripadvisor(record)
    if ta_result:
        source_scores["tripadvisor"] = ta_result[0]
        source_ages["tripadvisor"] = ta_result[1]

    ed_result = normalise_editorial(record)
    if ed_result:
        source_scores["editorial"] = ed_result[0]
        source_ages["editorial"] = ed_result[1]

    n_sources = len(source_scores)
    if n_sources == 0:
        return {
            "rcs": 0.0, "tier": "Avoid", "confidence": "Low",
            "sources": 0, "c_factor": 0.0, "penalties": [],
            "flags": [], "breakdown": {},
        }

    # Stage 3: Penalty multipliers
    penalty_list = compute_penalty_multipliers(record, source_scores)

    # Stage 4: Weighted aggregation (includes Stage 2 temporal decay)
    rcs_base, breakdown = weighted_aggregation(source_scores, source_ages)

    # Stage 5: Convergence adjustment
    c_factor, div_flags = convergence_adjustment(source_scores)
    rcs_adjusted = rcs_base * c_factor

    # Apply penalty multipliers
    total_multiplier = 1.0
    for _, mult in penalty_list:
        total_multiplier *= mult
    rcs_penalised = rcs_adjusted * total_multiplier

    # Stage 6: Calibration
    rcs_final = calibration_correction(rcs_penalised)
    rcs_final = max(0.0, min(10.0, rcs_final))

    # Stage 7: Tier assignment
    tier = assign_tier(rcs_final)
    conf = confidence_level(n_sources, c_factor)

    return {
        "rcs": round(rcs_final, 2),
        "tier": tier,
        "confidence": conf,
        "sources": n_sources,
        "c_factor": round(c_factor, 3),
        "rcs_base": round(rcs_base, 2),
        "penalty_multiplier": round(total_multiplier, 3),
        "penalties": penalty_list,
        "flags": div_flags,
        "breakdown": breakdown,
    }


# ---------------------------------------------------------------------------
# Firebase REST helpers
# ---------------------------------------------------------------------------

def fb_read(path, params=None):
    """Read from Firebase RTDB via REST API."""
    url = f"{FIREBASE_DB_URL}/{path}.json"
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_establishments(la_name):
    """Fetch all establishments for a local authority from Firebase."""
    print(f"Fetching establishments for LA: {la_name}")
    data = fb_read("daydine/establishments", {
        "orderBy": '"la"',
        "equalTo": f'"{la_name}"',
    })
    if not data:
        print(f"No establishments found for LA '{la_name}'")
        return {}
    print(f"Found {len(data)} establishments")
    return data


# ---------------------------------------------------------------------------
# CSV / JSON I/O
# ---------------------------------------------------------------------------

def save_json(data, path):
    """Save establishments dict to JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(data)} records to {path}")


def load_json(path):
    """Load establishments dict from JSON."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_establishments_csv(data, path):
    """Save raw establishment records to CSV."""
    if not data:
        return
    # Collect all fields across records
    fields = ["_key", "n", "a1", "a2", "a3", "a4", "pc", "la", "bt",
              "rv", "r", "rd", "lat", "lng", "fhrsid", "gr", "grc", "gpl"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for key, record in data.items():
            row = {"_key": key}
            row.update(record)
            writer.writerow(row)
    print(f"Saved {len(data)} records to {path}")


def save_scores_csv(scored_rows, path):
    """Save scored results to CSV."""
    fields = ["name", "postcode", "la", "business_type", "fsa_rating",
              "fsa_date", "google_rating", "google_reviews",
              "rcs", "tier", "confidence", "sources", "c_factor",
              "rcs_base", "penalty_multiplier", "flags"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(scored_rows)
    print(f"Wrote {len(scored_rows)} scored records to {path}")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(data):
    """Score all establishments and return sorted results."""
    scored = []
    for key, record in data.items():
        result = compute_rcs(record)
        scored.append({
            "name": record.get("n", "Unknown"),
            "postcode": record.get("pc", ""),
            "la": record.get("la", ""),
            "business_type": record.get("bt", ""),
            "fsa_rating": record.get("rv") or record.get("r", ""),
            "fsa_date": record.get("rd", ""),
            "google_rating": record.get("gr", ""),
            "google_reviews": record.get("grc", ""),
            "rcs": result["rcs"],
            "tier": result["tier"],
            "confidence": result["confidence"],
            "sources": result["sources"],
            "c_factor": result["c_factor"],
            "rcs_base": result["rcs_base"],
            "penalty_multiplier": result["penalty_multiplier"],
            "flags": "; ".join(result["flags"]) if result["flags"] else "",
        })
    return scored


def print_results(scored):
    """Print top 10, bottom 10, and tier summary."""
    sorted_rows = sorted(scored, key=lambda x: x["rcs"], reverse=True)

    # Top 10
    print()
    print("=" * 75)
    print("  TOP 10 RESTAURANTS BY RCS SCORE")
    print("=" * 75)
    print(f"  {'#':<4} {'Name':<35} {'Postcode':<10} {'RCS':>5}  {'Tier':<14}")
    print("  " + "-" * 71)
    for i, row in enumerate(sorted_rows[:10], 1):
        print(f"  {i:<4} {row['name'][:34]:<35} {row['postcode']:<10} "
              f"{row['rcs']:>5.2f}  {row['tier']:<14}")

    # Bottom 10
    print()
    print("=" * 75)
    print("  BOTTOM 10 RESTAURANTS BY RCS SCORE")
    print("=" * 75)
    print(f"  {'#':<4} {'Name':<35} {'Postcode':<10} {'RCS':>5}  {'Tier':<14}")
    print("  " + "-" * 71)
    bottom = sorted_rows[-10:][::-1]
    for i, row in enumerate(bottom, 1):
        print(f"  {i:<4} {row['name'][:34]:<35} {row['postcode']:<10} "
              f"{row['rcs']:>5.2f}  {row['tier']:<14}")

    # Tier summary
    tier_counts = Counter(row["tier"] for row in scored)
    tier_order = ["Exceptional", "Recommended", "Acceptable", "Caution", "Avoid"]
    total = len(scored)

    print()
    print("=" * 45)
    print("  TIER SUMMARY")
    print("=" * 45)
    print(f"  {'Tier':<16} {'Count':>7} {'%':>8}")
    print("  " + "-" * 41)
    for tier in tier_order:
        count = tier_counts.get(tier, 0)
        pct = (count / total * 100) if total else 0
        print(f"  {tier:<16} {count:>7} {pct:>7.1f}%")
    print("  " + "-" * 41)
    print(f"  {'TOTAL':<16} {total:>7}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Stratford establishments and run RCS scoring pipeline"
    )
    parser.add_argument(
        "--la", default="Stratford-on-Avon",
        help="Local authority name (default: Stratford-on-Avon). "
             "Use 'Newham' for Stratford, London."
    )
    parser.add_argument(
        "--from-cache", action="store_true",
        help="Load from stratford_establishments.json instead of fetching"
    )
    args = parser.parse_args()

    # Step 1: Get data
    if args.from_cache:
        if not os.path.exists(JSON_CACHE):
            print(f"ERROR: Cache file not found: {JSON_CACHE}")
            print("Run without --from-cache first to fetch from Firebase.")
            sys.exit(1)
        print(f"Loading from cache: {JSON_CACHE}")
        data = load_json(JSON_CACHE)
    else:
        data = fetch_establishments(args.la)
        if not data:
            sys.exit(1)
        # Save raw data
        save_json(data, JSON_CACHE)
        save_establishments_csv(data, CSV_INPUT)

    # Step 2: Run RCS pipeline
    print(f"\nRunning 7-stage RCS pipeline on {len(data)} establishments...")
    scored = run_pipeline(data)

    # Step 3: Save scored CSV
    save_scores_csv(scored, CSV_OUTPUT)

    # Step 4: Print results
    print_results(scored)


if __name__ == "__main__":
    main()
