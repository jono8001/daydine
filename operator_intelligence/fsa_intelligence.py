"""
operator_intelligence/fsa_intelligence.py — FSA Trust Decomposition & Intelligence

Decomposes the trust score into constituent parts with plain-English
interpretation. Provides staleness classification, reinspection logic,
and commercial consequence framing.

Tone: operator intelligence, not customer-facing warning. A 5/5 venue
doesn't have a crisis — it has a maintenance gap.
"""

import math
from rcs_scoring_stratford import (
    safe_float, days_since, temporal_decay, TEMPORAL_LAMBDA,
)


# ---------------------------------------------------------------------------
# Trust subcomponent weights (must match scorecard.py score_trust)
# ---------------------------------------------------------------------------

_TRUST_WEIGHTS = {
    "headline_rating": 0.40,
    "inspection_recency": 0.25,
    "structural_compliance": 0.15,
    "management_confidence": 0.20,
}

# Staleness tiers
_STALENESS_TIERS = [
    (365,  "fresh",   "Full confidence. No action needed."),
    (548,  "ageing",  "Score starting to decay. Note it but don't escalate."),
    (730,  "stale",   "Meaningful score drag. Consider proactive action."),
    (9999, "overdue", "Maximum decay applied. Reinspection strongly recommended."),
]


def _staleness_tier(age_days):
    """Classify inspection staleness."""
    if age_days is None:
        return "unknown", "No inspection date available."
    for threshold, tier, desc in _STALENESS_TIERS:
        if age_days <= threshold:
            return tier, desc
    return "overdue", "Maximum decay applied."


# ---------------------------------------------------------------------------
# Step 1: Subcomponent decomposition
# ---------------------------------------------------------------------------

def decompose_trust(venue_rec, scorecard, benchmarks=None):
    """Decompose trust score into weighted subcomponents.

    Returns dict with subcomponents, biggest_drag, headline_gap, peer_comparison.
    """
    r = safe_float(venue_rec.get("r"))
    rd = venue_rec.get("rd")
    ss = safe_float(venue_rec.get("ss"))
    sm = safe_float(venue_rec.get("sm"))
    age = days_since(rd)
    trust_score = scorecard.get("trust")

    components = []

    # 1. Headline rating
    if r is not None:
        score = r * 2.0
        components.append({
            "component": "headline_rating",
            "label": "FSA Headline Rating",
            "raw_value": f"{int(r)}/5",
            "score_contribution": round(score, 2),
            "weight": _TRUST_WEIGHTS["headline_rating"],
            "weighted_impact": round(score * _TRUST_WEIGHTS["headline_rating"], 2),
            "drag_on_trust": round((score - 10.0) * _TRUST_WEIGHTS["headline_rating"], 2),
            "interpretation": (
                f"{'Top mark — no action needed' if r >= 5 else f'Below maximum ({int(r)}/5). Visible to customers.'}"
            ),
            "actionable": r < 5,
        })

    # 2. Inspection recency
    if age is not None:
        decay = temporal_decay(age)
        score = round(decay * 10.0, 2)
        age_months = round(age / 30)
        tier, tier_desc = _staleness_tier(age)
        components.append({
            "component": "inspection_recency",
            "label": "Inspection Recency",
            "raw_value": rd[:10] if rd else "Unknown",
            "age_days": age,
            "age_months": age_months,
            "staleness_tier": tier,
            "score_contribution": score,
            "weight": _TRUST_WEIGHTS["inspection_recency"],
            "weighted_impact": round(score * _TRUST_WEIGHTS["inspection_recency"], 2),
            "drag_on_trust": round((score - 10.0) * _TRUST_WEIGHTS["inspection_recency"], 2),
            "interpretation": (
                f"Last inspected {rd[:10] if rd else '?'} ({age_months} months ago). "
                f"{tier_desc} "
                f"{'The system discounts older inspections because they carry less certainty.' if tier in ('stale', 'overdue') else ''}"
            ),
            "actionable": tier in ("stale", "overdue"),
        })

    # 3. Structural compliance
    if ss is not None:
        components.append({
            "component": "structural_compliance",
            "label": "Structural Compliance",
            "raw_value": f"{ss}/10",
            "score_contribution": ss,
            "weight": _TRUST_WEIGHTS["structural_compliance"],
            "weighted_impact": round(ss * _TRUST_WEIGHTS["structural_compliance"], 2),
            "drag_on_trust": round((ss - 10.0) * _TRUST_WEIGHTS["structural_compliance"], 2),
            "interpretation": (
                f"{'Strong — premises, facilities, equipment all adequate.' if ss >= 8 else 'Room for improvement in premises/facilities.' if ss >= 6 else 'Significant structural concerns.'}"
            ),
            "actionable": ss < 8,
        })

    # 4. Management confidence
    if sm is not None:
        components.append({
            "component": "management_confidence",
            "label": "Confidence in Management",
            "raw_value": f"{sm}/10",
            "score_contribution": sm,
            "weight": _TRUST_WEIGHTS["management_confidence"],
            "weighted_impact": round(sm * _TRUST_WEIGHTS["management_confidence"], 2),
            "drag_on_trust": round((sm - 10.0) * _TRUST_WEIGHTS["management_confidence"], 2),
            "interpretation": (
                f"{'Strong management systems and training record.' if sm >= 8 else 'Adequate but with room to strengthen systems/training.' if sm >= 6 else 'Management confidence is a concern.'}"
            ),
            "actionable": sm < 8,
        })

    # Biggest drag
    biggest_drag = min(components, key=lambda c: c["drag_on_trust"]) if components else None

    # Headline gap
    headline_gap = None
    if r is not None and trust_score is not None:
        customer_sees = f"{int(r)}/5"
        system_scores = f"{trust_score:.1f}/10"
        if r >= 5 and trust_score < 9.0:
            gap_explanation = (
                f"Customers see {customer_sees} — the top mark. But the system scores "
                f"trust at {system_scores} because it also weighs inspection freshness, "
                f"structural compliance, and management confidence. The gap is mostly "
                f"driven by {biggest_drag['label'].lower() if biggest_drag else 'subcomponent scores'}."
            )
        elif r < 5:
            gap_explanation = (
                f"Customers see {customer_sees} — below top mark. This is visible and "
                f"actively affects customer decisions."
            )
        else:
            gap_explanation = f"Headline and trust score are well-aligned."
        headline_gap = {
            "customer_sees": customer_sees,
            "system_scores": system_scores,
            "gap_explanation": gap_explanation,
        }

    # Peer comparison
    peer_comparison = _compare_trust_to_peers(venue_rec, scorecard, benchmarks)

    return {
        "subcomponents": components,
        "biggest_drag": biggest_drag,
        "headline_gap": headline_gap,
        "peer_comparison": peer_comparison,
        "trust_score": trust_score,
    }


def _compare_trust_to_peers(venue_rec, scorecard, benchmarks):
    """Compare trust subcomponents to local peers."""
    ring1 = (benchmarks or {}).get("ring1_local", {})
    trust_dim = ring1.get("dimensions", {}).get("trust", {})
    peer_avg = trust_dim.get("peer_mean")
    peer_top = trust_dim.get("peer_top")
    trust_score = scorecard.get("trust")

    if not peer_avg or not trust_score:
        return None

    return {
        "venue_trust": trust_score,
        "peer_avg": peer_avg,
        "peer_top": peer_top,
        "gap_to_avg": round(trust_score - peer_avg, 2),
        "gap_to_leader": round(trust_score - peer_top, 2),
    }


# ---------------------------------------------------------------------------
# Step 2: Staleness & reinspection assessment
# ---------------------------------------------------------------------------

def assess_reinspection(venue_rec, scorecard, benchmarks=None):
    """Assess whether voluntary reinspection is worth pursuing."""
    r = safe_float(venue_rec.get("r"))
    rd = venue_rec.get("rd")
    age = days_since(rd)
    trust_score = scorecard.get("trust")

    if age is None or r is None:
        return {"reinspection_recommended": False, "reasoning": "Insufficient data."}

    tier, tier_desc = _staleness_tier(age)
    age_months = round(age / 30)

    # Estimate score recovery: what trust would be with a fresh inspection
    fresh_recency_score = 10.0  # decay(0) = 1.0 → score = 10
    current_recency_score = temporal_decay(age) * 10.0
    recency_recovery = (fresh_recency_score - current_recency_score) * _TRUST_WEIGHTS["inspection_recency"]
    # Normalize by total weight
    total_w = sum(_TRUST_WEIGHTS.values())
    trust_recovery = round(recency_recovery / total_w, 2)

    # Overall score impact (trust dimension weight in overall scoring)
    from operator_intelligence.scorecard import DIMENSION_WEIGHTS
    trust_overall_weight = DIMENSION_WEIGHTS.get("trust", 0.20)
    overall_recovery = round(trust_recovery * trust_overall_weight, 2)

    # Peer context
    peer_comp = _compare_trust_to_peers(venue_rec, scorecard, benchmarks)
    peers_beaten = 0
    if peer_comp and trust_score and trust_recovery:
        new_trust = trust_score + trust_recovery
        ring1 = (benchmarks or {}).get("ring1_local", {})
        for tp in ring1.get("top_peers", []):
            pt = tp.get("trust")
            if pt and trust_score < pt <= new_trust:
                peers_beaten += 1

    recommended = tier in ("stale", "overdue")
    urgency = "high" if tier == "overdue" else "medium" if tier == "stale" else "low"

    reasoning = (
        f"Your inspection is {age_months} months old ({tier} tier). "
        f"The recency decay is costing you ~{trust_recovery:.1f} points on trust. "
    )
    if recommended:
        reasoning += (
            f"A fresh {int(r)}/5 result would recover this immediately"
            + (f" and put you ahead of {peers_beaten} local peers on trust." if peers_beaten else ".")
        )

    return {
        "reinspection_recommended": recommended,
        "urgency": urgency,
        "staleness_tier": tier,
        "age_months": age_months,
        "reasoning": reasoning,
        "score_recovery_estimate": trust_recovery,
        "overall_score_impact": overall_recovery,
        "estimated_trust_after": round((trust_score or 0) + trust_recovery, 2),
        "peers_overtaken": peers_beaten,
        "cost_context": "Voluntary reinspection is free via local authority request. Typical wait: 4–8 weeks.",
        "risk_note": (
            f"Only request reinspection if confident of maintaining {int(r)}/5. "
            f"A drop to {int(r)-1} would be worse than the staleness drag."
            if r >= 4 else
            f"A reinspection targeting {int(r)+1}/5 would materially improve your score and customer visibility."
        ),
        "trust_building_actions": [
            {"action": "Display 5/5 sticker prominently (entrance + digital)", "effort": "zero", "impact": "visibility"},
            {"action": "Add FSA rating to Google Business Profile", "effort": "zero", "impact": "digital trust signal"},
            {"action": "Mention compliance in review responses where relevant", "effort": "low", "impact": "signals confidence"},
        ] if r >= 5 else [
            {"action": "Address specific inspection points before requesting re-inspection", "effort": "medium", "impact": "rating improvement"},
        ],
    }


# ---------------------------------------------------------------------------
# Step 3: Commercial consequence of trust gap
# ---------------------------------------------------------------------------

def compute_trust_commercial(venue_rec, scorecard, benchmarks, reinspection):
    """Estimate commercial impact of trust gap."""
    r = safe_float(venue_rec.get("r"))
    trust = scorecard.get("trust")
    peer_comp = _compare_trust_to_peers(venue_rec, scorecard, benchmarks)

    if not peer_comp or not trust:
        return None

    gap_to_leader = abs(peer_comp["gap_to_leader"])
    gap_to_avg = peer_comp["gap_to_avg"]

    # For 5/5 venues: trust gap is competitive, not revenue-critical
    if r and r >= 5:
        scenario = (
            "If a customer is choosing between you and a competitor with a "
            "fresher inspection record, the competitor's recency is a tiebreaker "
            "— especially for risk-averse bookers (families, corporate groups, "
            "tourists checking hygiene ratings)."
        )
        value_range = "£0–£500/month"
        basis = (
            "Trust gap unlikely to drive direct revenue loss at 5/5 headline, "
            "but creates competitive vulnerability. Value is defensive — "
            "preventing loss if headline drops or competitor highlights "
            "their fresher record."
        )
    else:
        scenario = (
            f"An FSA rating of {int(r)}/5 is visible to customers and actively "
            f"suppresses trust. This is a direct revenue factor."
        )
        value_range = "£500–£3,000/month"
        basis = "Sub-5 ratings are visible on FSA website and Google, affecting booking decisions."

    recovery = reinspection.get("score_recovery_estimate", 0)
    trust_after = reinspection.get("estimated_trust_after", trust)
    overall = scorecard.get("overall", 0)
    overall_after = round(overall + reinspection.get("overall_score_impact", 0), 2)

    return {
        "trust_gap_to_peer_leader": round(gap_to_leader, 1),
        "trust_gap_to_peer_avg": round(abs(gap_to_avg), 1),
        "commercial_exposure": {
            "scenario": scenario,
            "segments_most_affected": ["families", "corporate_groups", "tourists"],
            "value_at_stake": value_range,
            "basis": basis,
        },
        "upside_if_fixed": {
            "action": "Request voluntary reinspection",
            "trust_score_after": trust_after,
            "overall_score_after": overall_after,
            "competitive_shift": f"Would overtake {reinspection.get('peers_overtaken', 0)} peers on trust",
            "cost": "Free (local authority request)",
            "time_to_effect": "4–8 weeks",
            "risk": reinspection.get("risk_note", ""),
        },
    }


# ---------------------------------------------------------------------------
# Public API: full FSA intelligence package
# ---------------------------------------------------------------------------

def generate_fsa_intelligence(venue_rec, scorecard, benchmarks=None):
    """Generate the complete FSA intelligence package."""
    decomposition = decompose_trust(venue_rec, scorecard, benchmarks)
    reinspection = assess_reinspection(venue_rec, scorecard, benchmarks)
    commercial = compute_trust_commercial(venue_rec, scorecard, benchmarks, reinspection)

    return {
        "decomposition": decomposition,
        "reinspection": reinspection,
        "commercial": commercial,
    }
