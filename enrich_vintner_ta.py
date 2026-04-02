#!/usr/bin/env python3
"""
enrich_vintner_ta.py — Ingest raw TripAdvisor reviews into Vintner's
establishment record and regenerate the monthly report.

Usage:
    python enrich_vintner_ta.py
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ESTABLISHMENTS_PATH = os.path.join(SCRIPT_DIR, "stratford_establishments.json")
TA_RAW_PATH = os.path.join(SCRIPT_DIR, "vintner_ta_raw.json")
VINTNER_ID = "503480"


def main():
    # Load raw TA data
    with open(TA_RAW_PATH, "r", encoding="utf-8") as f:
        ta_raw = json.load(f)

    print(f"Loaded {len(ta_raw)} TripAdvisor reviews from {TA_RAW_PATH}")

    # Compute aggregate TA stats
    ratings = [r["rating"] for r in ta_raw if r.get("rating") is not None]
    ta_avg = round(sum(ratings) / len(ratings), 1) if ratings else None
    ta_count = len(ratings)

    print(f"TripAdvisor aggregate: {ta_avg}/5 from {ta_count} reviews")

    # Convert to ta_reviews format expected by the system
    ta_reviews = []
    for r in ta_raw:
        ta_reviews.append({
            "text": r.get("text", ""),
            "rating": r.get("rating"),
            "title": r.get("title", ""),
            "date": r.get("publishedDate", ""),
            "username": r.get("username", ""),
            "source": "tripadvisor",
        })

    # Load establishments
    with open(ESTABLISHMENTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    if VINTNER_ID not in data:
        print(f"ERROR: Vintner (ID {VINTNER_ID}) not found in establishments")
        sys.exit(1)

    venue = data[VINTNER_ID]
    print(f"\nBefore enrichment:")
    print(f"  Name: {venue.get('n')}")
    print(f"  Google: {venue.get('gr')}/5 ({venue.get('grc')} reviews)")
    print(f"  TA rating: {venue.get('ta', 'None')}")
    print(f"  TA reviews: {venue.get('trc', 'None')}")
    print(f"  ta_reviews field: {'present' if venue.get('ta_reviews') else 'absent'}")
    print(f"  ta_present: {venue.get('ta_present', 'not set')}")

    # Enrich
    venue["ta"] = ta_avg
    venue["trc"] = ta_count
    venue["ta_present"] = True
    venue["ta_reviews"] = ta_reviews

    print(f"\nAfter enrichment:")
    print(f"  TA rating: {venue['ta']}/5")
    print(f"  TA review count: {venue['trc']}")
    print(f"  ta_reviews: {len(venue['ta_reviews'])} reviews with text")
    print(f"  ta_present: {venue['ta_present']}")

    # Save back
    data[VINTNER_ID] = venue
    with open(ESTABLISHMENTS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nSaved enriched data to {ESTABLISHMENTS_PATH}")

    # Now regenerate the monthly report
    print(f"\n{'='*60}")
    print(f"  Regenerating Vintner Wine Bar monthly report...")
    print(f"{'='*60}\n")

    from operator_intelligence.scorecard import (
        compute_all_scorecards, compute_score_deltas,
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
        generate_conditional_blocks,
    )

    month_str = "2026-04"
    venue_name = venue["n"]
    venue_id = str(venue.get("id") or VINTNER_ID)

    # Compute all scorecards (needed for peer benchmarks)
    all_cards = compute_all_scorecards(data)
    card = all_cards.get(venue_id)

    if not card:
        print("ERROR: Vintner not found in scorecards")
        sys.exit(1)

    print(f"Scorecard computed: overall={card['overall']}")

    # Save updated snapshot
    snap_path = save_snapshot(all_cards, month_str)
    print(f"Snapshot saved: {snap_path}")

    # Score deltas (compare to previous — none in this case but try)
    prev_month = "2026-03"
    prev_snapshot = load_snapshot(prev_month)
    prev_card = prev_snapshot.get(venue_id) if prev_snapshot else None
    deltas = compute_score_deltas(card, prev_card)

    # Peer benchmarks
    benchmarks = compute_peer_benchmarks(card, all_cards)

    # Load external sentiment data
    sentiment_path = os.path.join(SCRIPT_DIR, "stratford_sentiment.json")
    sentiment_data = None
    if os.path.exists(sentiment_path):
        with open(sentiment_path, "r", encoding="utf-8") as f:
            sentiment_data = json.load(f)

    # Review intelligence
    review_intel = extract_review_intelligence(venue, sentiment_data)

    # Deep review analysis with TA text
    if review_intel.get("has_narrative"):
        reviews_raw = []
        for field in ["g_reviews", "ta_reviews"]:
            for rev in venue.get(field, []):
                text = (rev.get("text") or "").strip()
                if text:
                    reviews_raw.append((text, rev.get("rating")))
        review_intel["analysis"] = analyse_reviews(reviews_raw)
        print(f"Deep analysis: {review_intel['analysis']['reviews_analyzed']} reviews analysed "
              f"(Google + TripAdvisor)")

    # Volume/momentum signals
    review_intel["volume_signals"] = analyse_volume_signals(
        venue, venue.get("gr"), venue.get("grc"))

    prev_review = load_review_snapshot(venue_id, prev_month)
    rev_delta = compute_review_delta(review_intel, prev_review)
    save_review_snapshot(venue_id, review_intel, month_str)

    # Recommendations
    recs = generate_recommendations(venue, card, benchmarks, deltas, month_str,
                                    review_intel=review_intel)

    # Conditional blocks
    cond_blocks = generate_conditional_blocks(venue, card, benchmarks)

    # Generate report
    report_md, qa = generate_monthly_report(
        venue_name, month_str, card, deltas,
        benchmarks, review_intel, rev_delta,
        recs, cond_blocks, venue_rec=venue,
    )

    # Generate JSON
    summary_json = generate_monthly_json(venue_name, month_str, card, deltas, recs)

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

    qa_status = "PASS" if qa["validation_passed"] else "FAIL"
    qa_warns = len(qa["validation_warnings"])
    print(f"\n  {venue_name}: overall={card['overall']:.1f} "
          f"| mode={qa['report_mode']} "
          f"| actions={len(recs['priority_actions'])} "
          f"| QA={qa_status}"
          f"{f' ({qa_warns} warnings)' if qa_warns else ''}")
    print(f"  Report → {md_path}")
    print(f"  JSON   → {json_path}")
    print(f"  QA     → {qa_path}")

    # Print scorecard for comparison
    print(f"\n{'='*60}")
    print(f"  SCORECARD COMPARISON")
    print(f"{'='*60}")
    print(f"\n  {'Dimension':<15} {'Score':>8}")
    print(f"  {'-'*25}")
    for dim in ["experience", "visibility", "trust", "conversion", "prestige", "overall"]:
        val = card.get(dim)
        print(f"  {dim:<15} {val:>8.2f}" if val is not None else f"  {dim:<15}     None")


if __name__ == "__main__":
    main()
