#!/usr/bin/env python3
"""
run_daydine.py — Orchestrator for the DayDine RCS scoring pipeline.

Coordinates all data collection tiers and runs the scoring engine.
Can be run locally or via GitHub Actions.

Usage:
    python run_daydine.py                    # Full pipeline
    python run_daydine.py --skip-fetch       # Use cached data
    python run_daydine.py --tiers 1,2        # Only run specific tiers
    python run_daydine.py --score-only       # Just re-score, no collection

Tier pipeline:
    1. Fetch establishments from Firebase RTDB
    2. Merge Google Places enrichment (Tier 2)
    3. Merge TripAdvisor data (Tier 3)
    4. Collect & merge menu data (Tier 5: Menu & Offering)
    5. Collect & merge editorial data (Tier 6: Reputation & Awards)
    6. Collect & merge enforcement data (FSA enforcement)
    7. Run V2 RCS scoring engine
    8. Output CSV + summary JSON
"""

import argparse
import importlib.util
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GH_SCRIPTS = os.path.join(SCRIPT_DIR, ".github", "scripts")


def run_script(name, path, required=False):
    """Run a Python script, return True if successful."""
    full_path = os.path.join(path, name)
    if not os.path.exists(full_path):
        if required:
            print(f"ERROR: {full_path} not found")
            sys.exit(1)
        print(f"  SKIP: {name} (not found)")
        return False

    print(f"\n{'='*60}")
    print(f"  Running: {name}")
    print(f"{'='*60}")
    result = subprocess.run(
        [sys.executable, full_path],
        cwd=SCRIPT_DIR,
    )
    if result.returncode != 0:
        print(f"  WARNING: {name} exited with code {result.returncode}")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(
        description="DayDine RCS Pipeline Orchestrator"
    )
    parser.add_argument("--skip-fetch", action="store_true",
                        help="Skip Firebase fetch, use cached data")
    parser.add_argument("--score-only", action="store_true",
                        help="Skip all collection, just re-score")
    parser.add_argument("--tiers", default="all",
                        help="Comma-separated tier numbers to run (e.g. 1,2,3)")
    args = parser.parse_args()

    tiers = set()
    if args.tiers != "all":
        tiers = {int(t.strip()) for t in args.tiers.split(",")}

    def should_run(tier_num):
        if args.score_only:
            return False
        if args.tiers == "all":
            return True
        return tier_num in tiers

    print("=" * 60)
    print("  DayDine RCS Pipeline Orchestrator")
    print("  35 signals | 7 tiers | 0-10 scale")
    print("=" * 60)

    # Step 1: Fetch from Firebase
    if not args.skip_fetch and not args.score_only:
        run_script("fetch_firebase_stratford.py", GH_SCRIPTS, required=True)
    else:
        print("\n  Using cached stratford_establishments.json")

    # Step 2: Google Places enrichment (Tier 2)
    if should_run(2):
        if os.path.exists(os.path.join(SCRIPT_DIR, "stratford_google_enrichment.json")):
            run_script("merge_enrichment.py", GH_SCRIPTS)
        else:
            print("\n  SKIP: Google enrichment (no data file, run enrich_and_score workflow)")

    # Step 3: TripAdvisor (Tier 3)
    if should_run(3):
        if os.path.exists(os.path.join(SCRIPT_DIR, "stratford_tripadvisor.json")):
            run_script("merge_tripadvisor.py", GH_SCRIPTS)
        else:
            print("\n  SKIP: TripAdvisor (no data file, run collect_tripadvisor workflow)")

    # Step 4: Menu data (Tier 5)
    if should_run(5):
        run_script("collect_menus.py", GH_SCRIPTS)
        run_script("merge_menus.py", GH_SCRIPTS)

    # Step 5: Editorial data (Tier 6)
    if should_run(6):
        run_script("collect_editorial.py", GH_SCRIPTS)
        run_script("merge_editorial.py", GH_SCRIPTS)

    # Step 6: Enforcement data (FSA)
    if should_run(1):
        if os.path.exists(os.path.join(GH_SCRIPTS, "collect_enforcement.py")):
            run_script("collect_enforcement.py", GH_SCRIPTS)
            run_script("merge_enforcement.py", GH_SCRIPTS)

    # Step 7: Run RCS scoring
    print(f"\n{'='*60}")
    print("  Running V2 RCS Scoring Engine")
    print(f"{'='*60}")
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, "rcs_scoring_stratford.py"),
         "--from-cache"],
        cwd=SCRIPT_DIR,
    )
    if result.returncode != 0:
        print("ERROR: Scoring pipeline failed")
        sys.exit(1)

    print(f"\n{'='*60}")
    print("  Pipeline complete!")
    print(f"{'='*60}")
    print(f"  Output: stratford_rcs_scores.csv")
    print(f"          stratford_rcs_summary.json")


if __name__ == "__main__":
    main()
