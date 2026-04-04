"""
operator_intelligence/report_generator.py — Report Assembly + QA

Assembles monthly/quarterly reports from section builders,
validates against report_spec quality rules, and generates
QA companion artifacts.
"""

import csv
import json
import os
from datetime import datetime

from operator_intelligence.report_spec import (
    detect_report_mode, validate_report, generate_qa_artifact,
)
from operator_intelligence.builders import (
    build_executive_summary, build_scorecard,
    build_performance_diagnosis, build_commercial_diagnosis,
    build_review_intelligence, build_review_appendices,
    build_watch_list, build_what_not_to_do,
    build_recommendation_tracker, build_competitive_market_intelligence,
    build_data_coverage, build_monthly_movement, build_segment_intelligence,
    build_trust_detail, build_data_basis,
    build_management_priorities, build_category_validation,
    build_market_position,
    build_dimension_diagnosis, build_public_vs_reality,
    build_demand_capture_audit, build_monitoring_plan,
    build_evidence_appendix,
    build_known_for, build_protect_improve_ignore,
)

DIM_ORDER = ["experience", "visibility", "trust", "conversion", "prestige"]


# ---------------------------------------------------------------------------
# Monthly Report Assembly — proposition-led, business-language-first
# ---------------------------------------------------------------------------

def generate_monthly_report(venue_name, month_str, scorecard, deltas,
                            benchmarks, review_intel, review_delta,
                            recs, conditional_blocks=None, venue_rec=None,
                            all_cards=None, all_data=None,
                            prior_snapshot=None):
    """Assemble full monthly report from builders. Returns (report_text, qa_dict).

    Report structure: leads with leaks/actions/risk, then covers 4 commercial
    lenses (Demand Capture, Proposition & Guest Signal, Trust & Public Risk,
    Competitive Market Intelligence), then supporting score detail, then tracking.
    """
    mode = detect_report_mode(review_intel)
    venue_rec = venue_rec or {}
    L = []
    w = L.append

    # Run demand capture audit early so it's available for delta computation
    from operator_intelligence.demand_capture_audit import run_demand_capture_audit
    _demand_audit = run_demand_capture_audit(venue_rec, scorecard, benchmarks, review_intel)

    # Compute snapshot deltas if prior month exists
    ring1 = (benchmarks or {}).get("ring1_local", {})
    ring1_ov = ring1.get("dimensions", {}).get("overall", {})
    _cur_snap = {
        "scorecard": {k: scorecard.get(k) for k in DIM_ORDER + ["overall"]},
        "signals": {
            "google_review_count": scorecard.get("google_reviews"),
            "google_rating": scorecard.get("google_rating"),
        },
        "peer_position": {
            "local_rank": ring1_ov.get("rank"),
            "local_of": ring1_ov.get("of"),
        },
        "demand_capture": {
            d["dimension"]: d["verdict"]
            for d in _demand_audit.get("dimensions", [])
        },
    }
    snapshot_deltas = compute_snapshot_deltas(_cur_snap, prior_snapshot)

    # --- Lead: leaks / actions / risk / what not to do ---
    # 1. Executive Summary (actions-led, score secondary)
    build_executive_summary(w, venue_name, month_str, mode, scorecard,
                            deltas, benchmarks, review_intel, recs)
    # 1a. Data Basis
    build_data_basis(w, venue_rec, review_intel)
    # 1b. Monthly Movement Summary
    build_monthly_movement(w, scorecard, benchmarks, venue_rec,
                           prior_snapshot, snapshot_deltas, month_str)
    # 2. What This Venue Is Becoming Known For
    build_known_for(w, venue_name, scorecard, benchmarks, review_intel)
    # 2b. Guest Segment Intelligence
    build_segment_intelligence(w, venue_rec, review_intel)
    # 3. Management Priorities
    build_management_priorities(w, scorecard, deltas, benchmarks, recs, venue_rec=venue_rec)
    # 4. Protect / Improve / Ignore
    build_protect_improve_ignore(w, scorecard, deltas, benchmarks, review_intel, recs)

    # --- Lens 1: Demand Capture ---
    # 5. Demand Capture Audit
    build_demand_capture_audit(w, scorecard, venue_rec, benchmarks=benchmarks,
                              review_intel=review_intel, prior_snapshot=prior_snapshot)

    # --- Lens 2: Proposition & Guest Signal ---
    # 6. Commercial Diagnosis (bottleneck, positioning, revenue leakage)
    build_commercial_diagnosis(w, scorecard, deltas, benchmarks, review_intel)
    # 7. Review & Reputation Intelligence
    build_review_intelligence(w, mode, review_intel, review_delta, month_str=month_str)

    # --- Lens 3: Trust & Public Risk ---
    # 8. Public Proof vs Operational Reality
    build_public_vs_reality(w, scorecard)

    # --- Lens 4: Competitive Market Intelligence (mandatory) ---
    # 9. Category & Peer Validation
    build_category_validation(w, scorecard, benchmarks, venue_rec or {},
                              all_cards=all_cards, all_data=all_data,
                              review_intel=review_intel)
    # 10. Competitive Market Intelligence
    build_competitive_market_intelligence(w, scorecard, benchmarks, conditional_blocks,
                                         prior_snapshot=prior_snapshot)
    # 10. Market Position (detailed 3-ring peer analysis)
    build_market_position(w, scorecard, benchmarks, venue_rec=venue_rec)

    # --- Score detail (supporting, not driving) ---
    # 11. Dimension Scorecard (compact table, prestige demoted)
    build_scorecard(w, scorecard, deltas, benchmarks)
    # 12. Dimension-by-Dimension Diagnosis
    build_dimension_diagnosis(w, scorecard, deltas, benchmarks, venue_rec=venue_rec)
    # 12b. Trust — Behind the Headline
    build_trust_detail(w, venue_rec, scorecard, benchmarks)

    # --- Tracking and monitoring ---
    # 13. Watch List
    build_watch_list(w, recs)
    # 14. What Not to Do
    build_what_not_to_do(w, recs)
    # 15. Implementation Framework (replaces Recommendation Tracker)
    build_recommendation_tracker(w, recs, month_str=month_str)
    # 16. Next-Month Monitoring Plan (external leading indicators)
    build_monitoring_plan(w, scorecard, recs)
    # 17. Data Coverage & Confidence
    build_data_coverage(w, scorecard, review_intel)
    # 18. Evidence Appendix
    build_evidence_appendix(w, scorecard, venue_rec)
    # 19. Review-by-Review Summary + Full Review Text Appendix
    build_review_appendices(w, review_intel)

    # 20. How Scores Work appendix
    _render_score_appendix(w)

    w("")
    w(f"*Report generated by DayDine v3.3 — {month_str}*")

    report_text = "\n".join(L)

    # Validate
    validation = validate_report(report_text, mode, recs, review_intel, scorecard)

    # QA artifact
    qa = generate_qa_artifact(venue_name, month_str, mode, report_text,
                              validation, review_intel, recs, scorecard)

    return report_text, qa


def _render_score_appendix(w):
    """Compact appendix explaining how scores work."""
    w("## Appendix: How Scores Work\n")
    w("The overall score is a weighted composite of four headline dimensions "
      "plus a tracked prestige signal:\n")
    w("| Dimension | Weight | What It Measures |")
    w("|---|---|---|")
    w("| Experience | ~30% | Food quality, service, ambience — from ratings, reviews, and FSA food hygiene |")
    w("| Trust | ~25% | FSA compliance record, inspection recency, management confidence |")
    w("| Visibility | ~20% | Online discoverability — review volume, photos, profile completeness |")
    w("| Conversion | ~15% | Operational readiness — hours, menu, reservations, delivery/takeaway |")
    w("| Prestige | ~10% | Awards, editorial recognition (tracked, not a headline lever) |")
    w("")
    w("**How scores move:** Scores change when underlying data changes "
      "(new reviews, new inspection, profile updates). The biggest levers "
      "are Experience (~30%) and Trust (~25%). Some factors decay over time "
      "(e.g., inspection recency) even without new data. Peer averages shift "
      "as competitors improve or decline.\n")
    w("**What scores don't capture:** Internal operational data, financial "
      "performance, staff quality beyond what's visible in reviews. "
      "This is an outside-in view only.\n")
    w("*Methodology: DayDine Premium v3.3. Full methodology available on request.*\n")


# ---------------------------------------------------------------------------
# JSON / CSV
# ---------------------------------------------------------------------------

def generate_monthly_json(venue_name, month_str, scorecard, deltas, recs,
                          benchmarks=None, venue_rec=None, review_intel=None,
                          demand_audit=None, segment_intel=None, fsa_intel=None):
    """Generate comprehensive monthly snapshot for month-over-month tracking."""
    from operator_intelligence.implementation_framework import generate_action_cards

    cards = generate_action_cards(recs, month_str)
    venue_rec = venue_rec or {}

    # Peer position from ring1
    ring1 = (benchmarks or {}).get("ring1_local", {})
    ring1_ov = ring1.get("dimensions", {}).get("overall", {})
    ring2 = (benchmarks or {}).get("ring2_catchment", {})
    ring2_ov = ring2.get("dimensions", {}).get("overall", {})

    # Review summary
    analysis = (review_intel or {}).get("analysis") or {}
    aspect_scores = analysis.get("aspect_scores", {})
    review_summary = {}
    for asp, data in aspect_scores.items():
        review_summary[asp] = {
            "positive": data.get("positive", 0),
            "negative": data.get("negative", 0),
        }

    return {
        "venue": venue_name,
        "month": month_str,
        "report_date": datetime.utcnow().strftime("%Y-%m-%d"),
        # Dimension scores
        "scorecard": {k: scorecard.get(k) for k in DIM_ORDER + ["overall"]},
        "deltas": deltas,
        # Raw signals
        "signals": {
            "google_rating": scorecard.get("google_rating"),
            "google_review_count": scorecard.get("google_reviews"),
            "google_photo_count": venue_rec.get("gpc"),
            "ta_rating": venue_rec.get("ta"),
            "ta_review_count": venue_rec.get("trc"),
            "fsa_rating": scorecard.get("fsa_rating"),
            "last_inspection_date": venue_rec.get("rd"),
            "price_level": venue_rec.get("gpl"),
            "gbp_completeness": venue_rec.get("gbp_completeness"),
        },
        # Competitive position
        "peer_position": {
            "local_rank": ring1_ov.get("rank"),
            "local_of": ring1_ov.get("of"),
            "local_peer_avg": ring1_ov.get("peer_mean"),
            "local_peer_top": ring1_ov.get("peer_top"),
            "local_peer_count": ring1.get("peer_count"),
            "catchment_rank": ring2_ov.get("rank"),
            "catchment_of": ring2_ov.get("of"),
        },
        # Demand capture verdicts
        "demand_capture": {
            d["dimension"]: d["verdict"]
            for d in (demand_audit or {}).get("dimensions", [])
        } if demand_audit else {},
        # Review sentiment summary
        "review_sentiment": review_summary,
        "reviews_analyzed": analysis.get("reviews_analyzed", 0),
        # Actions
        "priority_actions": [
            {"title": a["title"], "status": a["status"],
             "priority": a["priority_score"], "dimension": a["dimension"]}
            for a in recs.get("priority_actions", [])
        ],
        "watch_items": [
            {"title": wa["title"], "status": wa["status"]}
            for wa in recs.get("watch_items", [])
        ],
        "active_recommendations": sum(
            1 for r in recs.get("all_recs", [])
            if r.get("status") not in ("resolved", "dropped", "completed")),
        "implementation_framework": [
            {
                "title": c["title"],
                "dimension": c["dimension"],
                "status_label": c["status_label"],
                "target_date": c["target_date"],
                "cost_band": c["cost_band"],
                "expected_upside": c["expected_upside"],
                "success_measure": c["success_measure"],
                "next_milestone": c["next_milestone"],
                "owner_guidance": c["owner_guidance"],
                "times_seen": c["times_seen"],
                "barrier_category": c["barrier"][0] if c["barrier"] else None,
                "evidence": c["evidence"],
            }
            for c in cards
        ],
        "segment_intelligence": _build_segment_json(segment_intel),
        "fsa_intelligence": fsa_intel,
        "evidence_base": _build_evidence_base_json(venue_rec),
    }


def _build_evidence_base_json(venue_rec):
    """Compute and return evidence base for JSON storage."""
    if not venue_rec:
        return None
    from operator_intelligence.evidence_base import compute_evidence_base
    return compute_evidence_base(venue_rec)


def _build_segment_json(segment_intel):
    """Format segment intelligence for JSON storage."""
    if not segment_intel:
        return None
    seg_data = segment_intel.get("segment_data", {})
    insights_data = segment_intel.get("insights", {})
    return {
        "segment_distribution": seg_data.get("segment_distribution", {}),
        "unattributed_count": seg_data.get("unattributed_count", 0),
        "total_reviews": seg_data.get("total_reviews", 0),
        "segment_insights": {
            k: {
                "label": v["label"],
                "review_count": v["review_count"],
                "top_praise": v["top_praise"],
                "top_criticism": v["top_criticism"],
                "commercial_note": v["commercial_note"],
            }
            for k, v in insights_data.get("segment_insights", {}).items()
        },
        "tensions": insights_data.get("tensions", []),
        "data_quality": {
            "attributed_pct": round(
                (1 - seg_data.get("unattributed_count", 0) /
                 max(1, seg_data.get("total_reviews", 1))) * 100, 1),
            "note": ("Honest segment attribution from keyword evidence. "
                     "Reviews without clear guest-type signals are unattributed."),
        },
    }


def load_prior_month_json(venue_name, month_str, output_dir="outputs/monthly"):
    """Load the previous month's JSON snapshot for delta computation.
    Returns the parsed dict or None if no prior month exists."""
    # Compute prior month
    try:
        dt = datetime.strptime(month_str, "%Y-%m")
        if dt.month == 1:
            prior = dt.replace(year=dt.year - 1, month=12)
        else:
            prior = dt.replace(month=dt.month - 1)
        prior_str = prior.strftime("%Y-%m")
    except (ValueError, TypeError):
        return None

    safe_name = venue_name.replace(" ", "_").replace("/", "-")
    path = os.path.join(output_dir, f"{safe_name}_{prior_str}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def compute_snapshot_deltas(current, prior):
    """Compute deltas between two monthly snapshots.
    Returns a dict of field-level changes, or None if prior is missing."""
    if not prior:
        return None

    deltas = {}

    # Dimension deltas
    cur_sc = current.get("scorecard", {})
    pri_sc = prior.get("scorecard", {})
    for dim in DIM_ORDER + ["overall"]:
        c = cur_sc.get(dim)
        p = pri_sc.get(dim)
        if c is not None and p is not None:
            deltas[f"score_{dim}"] = round(c - p, 2)

    # Signal deltas
    cur_sig = current.get("signals", {})
    pri_sig = prior.get("signals", {})
    for key in ["google_rating", "google_review_count", "google_photo_count",
                "ta_rating", "ta_review_count", "gbp_completeness"]:
        c = cur_sig.get(key)
        p = pri_sig.get(key)
        if c is not None and p is not None:
            try:
                deltas[f"signal_{key}"] = round(float(c) - float(p), 2)
            except (ValueError, TypeError):
                pass

    # Peer position delta
    cur_pp = current.get("peer_position", {})
    pri_pp = prior.get("peer_position", {})
    if cur_pp.get("local_rank") and pri_pp.get("local_rank"):
        deltas["local_rank_change"] = pri_pp["local_rank"] - cur_pp["local_rank"]  # positive = improved

    # Demand capture delta
    cur_dc = current.get("demand_capture", {})
    pri_dc = prior.get("demand_capture", {})
    dc_improved = []
    dc_worsened = []
    for dim_name in cur_dc:
        cur_v = cur_dc.get(dim_name)
        pri_v = pri_dc.get(dim_name)
        if cur_v and pri_v and cur_v != pri_v:
            verdict_order = {"Clear": 0, "Partial": 1, "Missing": 2, "Broken": 3, "Gap": 2}
            if verdict_order.get(cur_v, 9) < verdict_order.get(pri_v, 9):
                dc_improved.append(f"{dim_name}: {pri_v} → {cur_v}")
            else:
                dc_worsened.append(f"{dim_name}: {pri_v} → {cur_v}")
    deltas["demand_capture_improved"] = dc_improved
    deltas["demand_capture_worsened"] = dc_worsened

    return deltas


def write_monthly_csv_row(venue_name, month_str, scorecard, csv_path):
    fields = ["month", "venue"] + DIM_ORDER + ["overall"]
    row = {"month": month_str, "venue": venue_name}
    for dim in DIM_ORDER + ["overall"]:
        row[dim] = scorecard.get(dim)
    write_header = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


# ---------------------------------------------------------------------------
# Quarterly
# ---------------------------------------------------------------------------

def generate_quarterly_report(venue_name, quarter_str, monthly_cards, recs_history):
    L = []
    w = L.append
    w(f"# Quarterly Strategic Review — {venue_name}")
    w(f"*{quarter_str} | DayDine Premium*\n---\n")
    months = sorted(monthly_cards.keys())
    if not months:
        w("*No monthly data available.*")
        return "\n".join(L)
    w("## Dimension Trends\n")
    w("| Dimension | " + " | ".join(months) + " | Trend |")
    w("|-----------|" + "|".join(["------:" for _ in months]) + "|-------|")
    for dim in DIM_ORDER + ["overall"]:
        vals = [monthly_cards[m].get(dim) for m in months]
        strs = [f"{v:.1f}" if v is not None else "—" for v in vals]
        avail = [v for v in vals if v is not None]
        trend = "—"
        if len(avail) >= 2:
            d = avail[-1] - avail[0]
            trend = "▲" if d > 0.3 else "▼" if d < -0.3 else "→"
        w(f"| {dim.title()} | " + " | ".join(strs) + f" | {trend} |")
    w("")
    if recs_history:
        w("## Recommendation Outcomes\n")
        res = sum(1 for r in recs_history if r.get("status") in ("resolved", "completed"))
        act = sum(1 for r in recs_history if r.get("status") in ("new", "ongoing", "escalated"))
        w(f"- **{res}** resolved/completed, **{act}** still active")
    w(f"\n*DayDine Operator Intelligence v2.0*")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Conditional blocks
# ---------------------------------------------------------------------------

def generate_conditional_blocks(venue, scorecard, benchmarks):
    blocks = []
    ring1 = benchmarks.get("ring1_local", {}) if benchmarks else {}
    if ring1.get("peer_count", 0) >= 10:
        blocks.append({"title": "Competitive Density Alert",
            "content": f"{ring1['peer_count']} direct competitors within 5mi. Differentiation critical."})
    fsa = scorecard.get("fsa_rating")
    if fsa is not None and int(fsa) <= 3:
        blocks.append({"title": "Compliance Risk",
            "content": f"FSA {fsa} caps Trust score and may suppress Google visibility."})
    vis = scorecard.get("visibility")
    if vis is not None and vis < 4.0:
        blocks.append({"title": "Visibility Gap",
            "content": "Online visibility significantly below average. Prioritise GBP and reviews."})
    return blocks
