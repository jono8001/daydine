"""
operator_intelligence/recommendations.py — Recommendation Memory System

Generates, persists, and tracks recommendations with stateful lifecycle:
  New → Ongoing → Escalated → Resolved/Completed/Dropped

Recommendations come from:
  - Structural gaps (missing signals, low dimension scores)
  - New changes (score drops, new penalties)
  - Persistent unresolved issues
  - Opportunities (peer outperformance potential)

Output format: top 3 priority actions, top 2 watch items, top 1 what-not-to-do.
"""

import hashlib
import json
import os
from datetime import datetime

STATUSES = ("new", "ongoing", "escalated", "resolved", "watchlist",
            "dropped", "completed")

HISTORY_DIR = "history/recommendations"

# ---------------------------------------------------------------------------
# Recommendation generation rules
# ---------------------------------------------------------------------------

def _generate_recs(venue, scorecard, benchmarks, deltas):
    """Generate candidate recommendations from current data.
    Returns list of rec dicts (unsorted, no status yet)."""
    recs = []
    name = venue.get("n", "Unknown")

    # --- Structural gaps ---

    # No Google photos
    gpc = venue.get("gpc")
    if gpc is not None and int(gpc) == 0:
        recs.append({
            "theme": "visibility",
            "dimension": "visibility",
            "title": "Add photos to Google Business Profile",
            "description": ("Your listing has zero photos. Venues with 10+ photos "
                            "get 35% more click-throughs on Google Maps."),
            "evidence": "gpc=0",
            "owner": "marketing",
            "priority_score": 8.5,
            "expected_upside": "+1.0 Visibility",
            "confidence": 0.9,
            "rec_type": "action",
        })

    # No opening hours
    goh = venue.get("goh")
    if not goh or (isinstance(goh, list) and len(goh) == 0):
        recs.append({
            "theme": "conversion",
            "dimension": "conversion",
            "title": "Publish opening hours on Google",
            "description": ("No opening hours listed. Customers filtering by "
                            "'open now' will never see you."),
            "evidence": "goh missing",
            "owner": "operations",
            "priority_score": 8.0,
            "expected_upside": "+1.5 Conversion",
            "confidence": 0.95,
            "rec_type": "action",
        })

    # No menu online
    if not venue.get("has_menu_online"):
        recs.append({
            "theme": "conversion",
            "dimension": "conversion",
            "title": "Get your menu online",
            "description": ("No online menu found. 77% of diners check "
                            "the menu before visiting."),
            "evidence": "has_menu_online=false",
            "owner": "marketing",
            "priority_score": 7.5,
            "expected_upside": "+2.0 Conversion",
            "confidence": 0.85,
            "rec_type": "action",
        })

    # Low Google rating
    gr = venue.get("gr")
    if gr is not None and float(gr) < 4.0:
        recs.append({
            "theme": "experience",
            "dimension": "experience",
            "title": "Address service quality signals",
            "description": (f"Google rating is {gr}/5. Focus on the specific "
                            "criticisms in recent reviews to lift this."),
            "evidence": f"gr={gr}",
            "owner": "operations",
            "priority_score": 9.0 if float(gr) < 3.5 else 7.0,
            "expected_upside": "+1.5 Experience",
            "confidence": 0.8,
            "rec_type": "action",
        })

    # Few reviews (< 20)
    grc = venue.get("grc")
    if grc is not None and int(grc) < 20:
        recs.append({
            "theme": "visibility",
            "dimension": "visibility",
            "title": "Build review volume",
            "description": (f"Only {grc} Google reviews. Encourage satisfied "
                            "customers to leave reviews — aim for 50+."),
            "evidence": f"grc={grc}",
            "owner": "front-of-house",
            "priority_score": 6.5,
            "expected_upside": "+1.0 Visibility",
            "confidence": 0.85,
            "rec_type": "action",
        })

    # Stale FSA inspection
    from rcs_scoring_stratford import days_since
    age = days_since(venue.get("rd"))
    if age is not None and age > 730:
        recs.append({
            "theme": "trust",
            "dimension": "trust",
            "title": "Request FSA re-inspection",
            "description": (f"Last inspected {age} days ago. A fresh 5-rating "
                            "would materially lift your Trust score."),
            "evidence": f"inspection_age={age}d",
            "owner": "compliance",
            "priority_score": 7.0,
            "expected_upside": "+1.0 Trust",
            "confidence": 0.7,
            "rec_type": "action",
        })

    # FSA rating < 5
    r = venue.get("r")
    if r is not None and int(r) < 5:
        recs.append({
            "theme": "trust",
            "dimension": "trust",
            "title": f"Improve FSA hygiene rating from {r} to 5",
            "description": ("A rating below 5 caps your Trust score. "
                            "Address the inspector's specific concerns."),
            "evidence": f"r={r}",
            "owner": "compliance",
            "priority_score": 8.5 if int(r) <= 3 else 6.0,
            "expected_upside": "+2.0 Trust",
            "confidence": 0.9,
            "rec_type": "action",
        })

    # No social presence
    if not venue.get("web") and not venue.get("fb") and not venue.get("ig"):
        recs.append({
            "theme": "visibility",
            "dimension": "visibility",
            "title": "Establish basic social media presence",
            "description": ("No website, Facebook, or Instagram detected. "
                            "Even a basic page improves discoverability."),
            "evidence": "web=false, fb=false, ig=false",
            "owner": "marketing",
            "priority_score": 5.5,
            "expected_upside": "+1.5 Visibility",
            "confidence": 0.8,
            "rec_type": "action",
        })

    # --- Score drop warnings (from deltas) ---
    if deltas:
        for dim, delta in deltas.items():
            if delta is not None and delta <= -0.5 and dim != "overall":
                recs.append({
                    "theme": dim,
                    "dimension": dim,
                    "title": f"{dim.title()} score dropped {delta:+.1f}",
                    "description": (f"Your {dim} score fell by {abs(delta):.1f} "
                                    "points this month. Investigate the cause."),
                    "evidence": f"delta={delta:+.2f}",
                    "owner": "management",
                    "priority_score": 8.0,
                    "expected_upside": "Prevent further decline",
                    "confidence": 0.75,
                    "rec_type": "watch",
                })

    # --- Peer opportunity ---
    if benchmarks:
        ring1 = benchmarks.get("ring1_local", {})
        overall = ring1.get("dimensions", {}).get("overall")
        if overall and overall.get("percentile") is not None:
            if overall["percentile"] < 50:
                recs.append({
                    "theme": "competitive",
                    "dimension": "overall",
                    "title": "Below local median — competitive risk",
                    "description": (f"Ranked #{overall['rank']} of {overall['of']} "
                                    f"locally (P{overall['percentile']}). "
                                    "Peers are outperforming you on aggregate."),
                    "evidence": f"local_percentile={overall['percentile']}",
                    "owner": "management",
                    "priority_score": 7.5,
                    "expected_upside": "Competitive positioning",
                    "confidence": 0.7,
                    "rec_type": "watch",
                })

    return recs


def _rec_id(venue_id, title):
    """Deterministic ID so the same recommendation is recognised across months."""
    raw = f"{venue_id}:{title}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Persistence and lifecycle
# ---------------------------------------------------------------------------

def _load_history(venue_id):
    """Load recommendation history for a venue."""
    os.makedirs(HISTORY_DIR, exist_ok=True)
    path = os.path.join(HISTORY_DIR, f"{venue_id}.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_history(venue_id, history):
    os.makedirs(HISTORY_DIR, exist_ok=True)
    path = os.path.join(HISTORY_DIR, f"{venue_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def generate_recommendations(venue, scorecard, benchmarks, deltas, month_str):
    """Generate recommendations, merge with history, return prioritised output.

    Returns dict with:
      priority_actions: top 3
      watch_items: top 2
      what_not_to_do: top 1
      all_recs: full list with status
    """
    venue_id = str(venue.get("id") or venue.get("fhrsid", "unknown"))
    now = month_str

    candidates = _generate_recs(venue, scorecard, benchmarks, deltas)
    history = _load_history(venue_id)

    # Merge candidates with history
    for rec in candidates:
        rid = _rec_id(venue_id, rec["title"])
        rec["rec_id"] = rid
        rec["venue_id"] = venue_id

        if rid in history:
            prev = history[rid]
            rec["status"] = prev.get("status", "ongoing")
            rec["first_seen"] = prev["first_seen"]
            rec["times_seen"] = prev.get("times_seen", 1) + 1
            # Escalate if seen 3+ times and still unresolved
            if rec["times_seen"] >= 3 and rec["status"] in ("new", "ongoing"):
                rec["status"] = "escalated"
            elif rec["status"] == "new":
                rec["status"] = "ongoing"
        else:
            rec["status"] = "new"
            rec["first_seen"] = now
            rec["times_seen"] = 1

        rec["last_seen"] = now
        history[rid] = rec

    # Mark old recs not seen this month as potentially resolved
    for rid, old_rec in history.items():
        if old_rec.get("last_seen") != now and old_rec.get("status") in ("new", "ongoing", "escalated"):
            old_rec["status"] = "resolved"

    _save_history(venue_id, history)

    # Sort by priority
    active = [r for r in candidates if r["status"] not in ("resolved", "dropped", "completed")]
    actions = sorted([r for r in active if r.get("rec_type") == "action"],
                     key=lambda x: -x["priority_score"])
    watches = sorted([r for r in active if r.get("rec_type") == "watch"],
                     key=lambda x: -x["priority_score"])

    # What not to do: lowest-priority action that might be tempting
    dont = None
    if len(actions) > 3:
        dont = actions[-1]
        dont["_reason"] = "Low impact relative to effort — deprioritise this month."

    return {
        "priority_actions": actions[:3],
        "watch_items": watches[:2],
        "what_not_to_do": dont,
        "all_recs": list(history.values()),
    }
