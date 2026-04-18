#!/usr/bin/env python3
"""
restaurant_operator_intelligence.py — CLI entry point

Operator Intelligence System for restaurant benchmarking and monthly reporting.

Usage:
    # Monthly report for one venue
    python restaurant_operator_intelligence.py --mode monthly --month 2026-04 \
        --venue "Arrow Mill" --from-cache

    # Monthly report for all venues
    python restaurant_operator_intelligence.py --mode monthly --month 2026-04 \
        --from-cache

    # Quarterly report
    python restaurant_operator_intelligence.py --mode quarterly --quarter 2026-Q1 \
        --venue "Arrow Mill"

    # List available venues
    python restaurant_operator_intelligence.py --list-venues --from-cache
"""

# ============================================================================
# LEGACY (V3.4) — NOT PART OF THE ACTIVE V4 PATH
# ----------------------------------------------------------------------------
# This module is part of the DayDine V3.4 scoring / reporting layer. V4 is
# now the active model (`rcs_scoring_v4.py` + `operator_intelligence/v4_*.py`).
# This file is retained only for rollback, comparison against V4 output
# (via `compare_v3_v4.py`), and historical reference.
#
# Do NOT import this module from any V4 code path. The boundary check in
# `tests/test_v4_legacy_boundary.py` enforces this.
#
# See `docs/DayDine-Legacy-Quarantine-Note.md` for conditions under which
# this file becomes safe to delete.
# ============================================================================

import argparse
import json
import os
import sys

from operator_intelligence.scorecard import (
    compute_all_scorecards, compute_scorecard, compute_score_deltas,
    save_snapshot, load_snapshot,
)
from operator_intelligence.peer_benchmarking import compute_peer_benchmarks
from operator_intelligence.recommendations import generate_recommendations
from operator_intelligence.review_delta import (
    extract_review_intelligence, compute_review_delta,
    save_review_snapshot, load_review_snapshot,
)
from operator_intelligence.review_analysis import analyse_reviews, analyse_volume_signals
from operator_intelligence.report_generator import (
    generate_monthly_report, generate_monthly_json, write_monthly_csv_row,
    generate_quarterly_report, generate_conditional_blocks,
    load_prior_month_json,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_CACHE = os.path.join(SCRIPT_DIR, "stratford_establishments.json")


def _prev_month(month_str):
    """Given 'YYYY-MM', return the previous month string."""
    year, month = int(month_str[:4]), int(month_str[5:7])
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def _find_venue(data, name):
    """Find a venue by name (case-insensitive partial match)."""
    name_lower = name.lower()
    for key, rec in data.items():
        if rec.get("n", "").lower() == name_lower:
            return key, rec
    # Partial match
    for key, rec in data.items():
        if name_lower in rec.get("n", "").lower():
            return key, rec
    return None, None


def run_monthly_venue(venue_key, venue_rec, data, all_cards, month_str):
    """Run full monthly intelligence pipeline for one venue."""
    venue_id = str(venue_rec.get("id") or venue_key)
    venue_name = venue_rec.get("n", "Unknown")
    card = all_cards.get(venue_id)

    if not card:
        print(f"  Skipping {venue_name} — not a ranked food venue")
        return None

    # Score deltas vs previous month
    prev_month = _prev_month(month_str)
    prev_snapshot = load_snapshot(prev_month)
    prev_card = prev_snapshot.get(venue_id) if prev_snapshot else None
    deltas = compute_score_deltas(card, prev_card)

    # Peer benchmarks
    benchmarks = compute_peer_benchmarks(card, all_cards)

    # Load external sentiment data if available
    sentiment_path = os.path.join(SCRIPT_DIR, "stratford_sentiment.json")
    sentiment_data = None
    if os.path.exists(sentiment_path):
        with open(sentiment_path, "r", encoding="utf-8") as f:
            sentiment_data = json.load(f)

    # Review intelligence (two-mode: narrative-rich or structured-signal)
    review_intel = extract_review_intelligence(venue_rec, sentiment_data)

    # Deep review analysis if text is available
    if review_intel.get("has_narrative"):
        reviews_raw = []
        for field in ["g_reviews", "ta_reviews"]:
            for rev in venue_rec.get(field, []):
                text = (rev.get("text") or "").strip()
                if text:
                    reviews_raw.append((text, rev.get("rating")))
        review_intel["analysis"] = analyse_reviews(reviews_raw)

    # Volume/momentum signals (always available from structured data)
    review_intel["volume_signals"] = analyse_volume_signals(
        venue_rec, venue_rec.get("gr"), venue_rec.get("grc"))

    prev_review = load_review_snapshot(venue_id, prev_month)
    rev_delta = compute_review_delta(review_intel, prev_review)
    save_review_snapshot(venue_id, review_intel, month_str)

    # Recommendations
    recs = generate_recommendations(venue_rec, card, benchmarks, deltas, month_str,
                                    review_intel=review_intel)

    # Conditional intelligence
    cond_blocks = generate_conditional_blocks(venue_rec, card, benchmarks)

    # Load prior month snapshot for temporal layer
    prior_snapshot = load_prior_month_json(venue_name, month_str)

    # Generate markdown report + QA artifact
    report_md, qa = generate_monthly_report(
        venue_name, month_str, card, deltas,
        benchmarks, review_intel, rev_delta,
        recs, cond_blocks, venue_rec=venue_rec,
        all_cards=all_cards, all_data=data,
        prior_snapshot=prior_snapshot,
    )

    # Generate JSON summary
    from operator_intelligence.demand_capture_audit import run_demand_capture_audit
    from operator_intelligence.segment_analysis import classify_all_reviews, generate_segment_insights
    from operator_intelligence.fsa_intelligence import generate_fsa_intelligence
    demand_audit = run_demand_capture_audit(venue_rec, card, benchmarks, review_intel)
    seg_data = classify_all_reviews(venue_rec)
    seg_insights = generate_segment_insights(seg_data, review_intel.get("analysis"))
    segment_intel = {"segment_data": seg_data, "insights": seg_insights}
    fsa_intel = generate_fsa_intelligence(venue_rec, card, benchmarks)
    summary_json = generate_monthly_json(
        venue_name, month_str, card, deltas, recs,
        benchmarks=benchmarks, venue_rec=venue_rec, review_intel=review_intel,
        demand_audit=demand_audit, segment_intel=segment_intel,
        fsa_intel=fsa_intel)

    # Write outputs
    os.makedirs("outputs/monthly", exist_ok=True)
    safe_name = venue_name.replace(" ", "_").replace("/", "-")

    md_path = f"outputs/monthly/{safe_name}_{month_str}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    json_path = f"outputs/monthly/{safe_name}_{month_str}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary_json, f, indent=2, ensure_ascii=False)

    qa_path = f"outputs/monthly/{safe_name}_{month_str}_qa.json"
    with open(qa_path, "w", encoding="utf-8") as f:
        json.dump(qa, f, indent=2, ensure_ascii=False)

    # Render the branded PDF version of the monthly report. Kept outside
    # generate_monthly_report() so PDF failures never break the upstream
    # markdown/JSON pipeline; re-runnable via
    #   python -m operator_intelligence.pdf.renderer outputs/monthly/
    pdf_path = f"outputs/monthly/pdf/{safe_name}_{month_str}.pdf"
    try:
        from operator_intelligence.pdf.renderer import render_pdf_report
        os.makedirs("outputs/monthly/pdf", exist_ok=True)
        render_pdf_report(json_path, pdf_path)
    except Exception as e:
        pdf_path = None
        print(f"  WARN: PDF render failed for {venue_name}: {e}")

    csv_path = f"outputs/monthly/scores_{month_str}.csv"
    write_monthly_csv_row(venue_name, month_str, card, csv_path)

    qa_status = "PASS" if qa["validation_passed"] else "FAIL"
    qa_warns = len(qa["validation_warnings"])
    print(f"  {venue_name}: overall={card['overall']:.1f} "
          f"| mode={qa['report_mode']} "
          f"| actions={len(recs['priority_actions'])} "
          f"| QA={qa_status}"
          f"{f' ({qa_warns} warnings)' if qa_warns else ''} "
          f"| report → {md_path}")

    return summary_json


def run_monthly(data, month_str, venue_filter=None):
    """Run monthly mode for one or all venues."""
    print(f"\n{'='*60}")
    print(f"  DayDine Operator Intelligence — Monthly {month_str}")
    print(f"{'='*60}\n")

    all_cards = compute_all_scorecards(data)
    print(f"Scored {len(all_cards)} venues across 5 dimensions\n")

    # Save snapshot for future delta comparison
    snap_path = save_snapshot(all_cards, month_str)
    print(f"Snapshot saved: {snap_path}\n")

    results = []

    if venue_filter:
        key, rec = _find_venue(data, venue_filter)
        if not rec:
            print(f"ERROR: Venue '{venue_filter}' not found")
            sys.exit(1)
        result = run_monthly_venue(key, rec, data, all_cards, month_str)
        if result:
            results.append(result)
    else:
        for key, rec in data.items():
            result = run_monthly_venue(key, rec, data, all_cards, month_str)
            if result:
                results.append(result)

    print(f"\nGenerated {len(results)} venue report(s)")
    return results


def run_quarterly(data, quarter_str, venue_filter=None):
    """Run quarterly mode — aggregates 3 monthly snapshots."""
    print(f"\n{'='*60}")
    print(f"  DayDine Operator Intelligence — Quarterly {quarter_str}")
    print(f"{'='*60}\n")

    # Parse quarter into months
    year, q = quarter_str.split("-Q")
    q = int(q)
    months = {
        1: [f"{year}-01", f"{year}-02", f"{year}-03"],
        2: [f"{year}-04", f"{year}-05", f"{year}-06"],
        3: [f"{year}-07", f"{year}-08", f"{year}-09"],
        4: [f"{year}-10", f"{year}-11", f"{year}-12"],
    }[q]

    # Load monthly snapshots
    monthly_snaps = {}
    for m in months:
        snap = load_snapshot(m)
        if snap:
            monthly_snaps[m] = snap
            print(f"  Loaded snapshot: {m} ({len(snap)} venues)")

    if not monthly_snaps:
        print("ERROR: No monthly snapshots found for this quarter.")
        print("  Run monthly reports first.")
        sys.exit(1)

    os.makedirs("outputs/quarterly", exist_ok=True)

    if venue_filter:
        venues = []
        key, rec = _find_venue(data, venue_filter)
        if rec:
            venues.append((str(rec.get("id") or key), rec.get("n", "Unknown")))
    else:
        all_cards = compute_all_scorecards(data)
        venues = [(vid, c["name"]) for vid, c in all_cards.items()]

    for venue_id, venue_name in venues:
        # Gather monthly cards for this venue
        venue_months = {}
        for m, snap in monthly_snaps.items():
            if venue_id in snap:
                venue_months[m] = snap[venue_id]

        if not venue_months:
            continue

        # Load recommendation history
        rec_path = f"history/recommendations/{venue_id}.json"
        recs_hist = []
        if os.path.exists(rec_path):
            with open(rec_path) as f:
                recs_hist = list(json.load(f).values())

        report = generate_quarterly_report(venue_name, quarter_str,
                                           venue_months, recs_hist)

        safe_name = venue_name.replace(" ", "_").replace("/", "-")
        out_path = f"outputs/quarterly/{safe_name}_{quarter_str}.md"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"  {venue_name} → {out_path}")

    print(f"\nQuarterly reports generated")


def list_venues(data):
    """Print all venue names for reference."""
    from rcs_scoring_stratford import is_food_establishment
    venues = []
    for key, rec in data.items():
        food_ok, _ = is_food_establishment(rec)
        if food_ok:
            venues.append((rec.get("n", "Unknown"), rec.get("pc", ""),
                          rec.get("gr"), rec.get("r")))
    venues.sort(key=lambda x: x[0])
    print(f"\n{len(venues)} food venues available:\n")
    print(f"  {'Name':<40} {'PC':<10} {'Google':>6} {'FSA':>4}")
    print(f"  {'-'*65}")
    for name, pc, gr, r in venues:
        gr_str = f"{gr}" if gr else "—"
        r_str = f"{r}" if r else "—"
        print(f"  {name[:39]:<40} {pc:<10} {gr_str:>6} {r_str:>4}")


def main():
    parser = argparse.ArgumentParser(
        description="DayDine Operator Intelligence System")
    parser.add_argument("--mode", choices=["monthly", "quarterly"],
                        default="monthly")
    parser.add_argument("--month", default=None,
                        help="Month in YYYY-MM format (default: current)")
    parser.add_argument("--quarter", default=None,
                        help="Quarter in YYYY-QN format (e.g. 2026-Q1)")
    parser.add_argument("--venue", default=None,
                        help="Venue name (partial match ok)")
    parser.add_argument("--from-cache", action="store_true",
                        help="Load from stratford_establishments.json")
    parser.add_argument("--list-venues", action="store_true",
                        help="List all available venues")
    args = parser.parse_args()

    # Load data
    if not os.path.exists(JSON_CACHE):
        print(f"ERROR: {JSON_CACHE} not found. Use --from-cache with data file present.")
        sys.exit(1)

    with open(JSON_CACHE, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"Loaded {len(data)} establishments from cache")

    if args.list_venues:
        list_venues(data)
        return

    if args.mode == "monthly":
        month = args.month
        if not month:
            from datetime import datetime, timezone
            month = datetime.now(timezone.utc).strftime("%Y-%m")
        run_monthly(data, month, args.venue)

    elif args.mode == "quarterly":
        if not args.quarter:
            print("ERROR: --quarter required for quarterly mode (e.g. 2026-Q1)")
            sys.exit(1)
        run_quarterly(data, args.quarter, args.venue)


if __name__ == "__main__":
    main()
