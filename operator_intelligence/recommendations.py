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
            "title": "Identify and fix the recurring guest complaint",
            "description": (f"At {gr}/5 on Google, something specific is landing badly. "
                            "Read the 5 most recent negative reviews, identify the common "
                            "thread (food, service, wait, or environment), and fix it at "
                            "source. The rating won't move until the root cause does."),
            "evidence": f"gr={gr}",
            "owner": "operations",
            "priority_score": 9.0 if float(gr) < 3.5 else 7.0,
            "expected_upside": "Rating recovery → discovery recovery",
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
        years = round(age / 365, 1)
        recs.append({
            "theme": "trust",
            "dimension": "trust",
            "title": "Get ahead of the next inspection",
            "description": (f"Last inspected {years} years ago. A stale inspection "
                            "date signals to both customers and the algorithm that "
                            "compliance isn't actively managed. Request a voluntary "
                            "re-inspection once you're confident of a strong result."),
            "evidence": f"inspection_age={age}d",
            "owner": "compliance",
            "priority_score": 7.0,
            "expected_upside": "Fresh compliance proof, trust signal renewal",
            "confidence": 0.7,
            "rec_type": "action",
        })

    # FSA rating < 5
    r = venue.get("r")
    if r is not None and int(r) < 5:
        recs.append({
            "theme": "trust",
            "dimension": "trust",
            "title": f"Close the hygiene gap — {r} to 5",
            "description": (f"An FSA rating of {r} is visible on your Google listing "
                            "and the FSA website. Customers see it before they see your "
                            "menu. Address the inspector's specific findings — the report "
                            "will tell you exactly what to fix."),
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

        # Weakest dimension vs peers — watch items in operator language
        _DIM_WATCH_LANG = {
            "experience": ("Guest experience trailing local competitors",
                           "Peers are delivering a more consistent or higher-quality guest "
                           "experience. Identify what they do differently — is it menu depth, "
                           "service style, or ambience? — and decide whether to match or "
                           "differentiate."),
            "visibility": ("Online discoverability behind competitors",
                           "Competitors have stronger online presence. Customers searching "
                           "'near me' are finding them first. Review your Google profile "
                           "completeness and review generation strategy."),
            "trust": ("Compliance record trailing local standards",
                      "Most local peers carry stronger formal compliance signals. This "
                      "may not affect daily footfall yet but creates exposure if an "
                      "inspection goes poorly or a customer complaint escalates."),
            "conversion": ("Conversion readiness gap vs peers",
                           "Competitors make it easier for customers to act on interest — "
                           "clearer hours, visible menus, booking options. Customers who "
                           "can't convert on your venue convert elsewhere."),
            "prestige": ("No editorial edge vs peers",
                         "Some competitors carry editorial recognition that you lack. "
                         "This matters most at the premium end of the market."),
        }
        for dim in ["experience", "visibility", "trust", "conversion", "prestige"]:
            dim_data = ring1.get("dimensions", {}).get(dim)
            if dim_data and dim_data.get("percentile") is not None:
                if dim_data["percentile"] < 40:
                    title, desc = _DIM_WATCH_LANG.get(dim, (f"{dim.title()} gap", "Monitor."))
                    recs.append({
                        "theme": dim, "dimension": dim,
                        "title": title, "description": desc,
                        "evidence": f"{dim}: {dim_data['score']:.1f} vs peer avg {dim_data['peer_mean']:.1f}",
                        "owner": "management", "priority_score": 5.5,
                        "expected_upside": f"Closing {dim_data['peer_mean'] - dim_data['score']:.1f}-point gap to peer average",
                        "confidence": 0.65, "rec_type": "watch",
                    })

    # --- Opportunity recs for strong venues ---
    # These ensure even top performers get actionable intelligence

    # Review volume growth opportunity
    grc = venue.get("grc")
    if grc is not None and 20 <= int(grc) < 200:
        recs.append({
            "theme": "visibility", "dimension": "visibility",
            "title": "Accelerate review volume toward 200+",
            "description": (f"At {grc} reviews, your rating is credible but not dominant. "
                            "Venues with 200+ reviews rank higher in Google Maps. "
                            "Consider post-visit SMS/email review prompts."),
            "evidence": f"grc={grc}",
            "owner": "marketing", "priority_score": 5.0,
            "expected_upside": "+0.5 Visibility, improved Google Maps ranking",
            "confidence": 0.75, "rec_type": "action",
        })

    # GBP completeness opportunity
    gbp = venue.get("gbp_completeness")
    if gbp is not None and float(gbp) < 8.0:
        recs.append({
            "theme": "visibility", "dimension": "visibility",
            "title": "Complete your Google Business Profile",
            "description": (f"GBP completeness is {gbp}/10. Complete profiles get "
                            "70% more direction requests. Add photos, menu link, "
                            "booking link, and business description."),
            "evidence": f"gbp_completeness={gbp}",
            "owner": "marketing", "priority_score": 4.5,
            "expected_upside": "+0.5 Visibility",
            "confidence": 0.8, "rec_type": "action",
        })

    # Prestige opportunity for strong venues
    overall_score = scorecard.get("overall")
    if overall_score and overall_score >= 7.5:
        if not venue.get("has_michelin_mention") and not venue.get("has_aa_rating"):
            recs.append({
                "theme": "prestige", "dimension": "prestige",
                "title": "Pursue editorial recognition",
                "description": ("Your operational scores support a credible submission "
                                "to the AA Restaurant Guide or local food awards. "
                                "Editorial recognition would differentiate you from "
                                "peers and justify premium positioning."),
                "evidence": f"overall={overall_score}",
                "owner": "management", "priority_score": 3.5,
                "expected_upside": "+2.0 Prestige, brand differentiation",
                "confidence": 0.5, "rec_type": "action",
            })

    # Conversion optimisation for venues with high experience but low conversion
    exp = scorecard.get("experience")
    conv = scorecard.get("conversion")
    if exp and conv and exp >= 7.0 and conv < 6.0:
        recs.append({
            "theme": "conversion", "dimension": "conversion",
            "title": "Fix the digital shopfront — you're losing walk-ins",
            "description": ("You deliver a strong experience but your online presence "
                            "doesn't make it easy to act on. Check: can a new customer "
                            "confirm your hours, see your menu, and book or walk in — "
                            "all within 60 seconds on their phone? If not, that's your "
                            "fix list."),
            "evidence": f"experience={exp}, conversion={conv}",
            "owner": "operations", "priority_score": 6.0,
            "expected_upside": "Capture demand you're currently losing",
            "confidence": 0.8, "rec_type": "action",
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

    # --- Guarantee 3 actions, 2 watches, 1 what-not-to-do ---

    # If fewer than 3 actions, promote watches or add standing recs
    if len(actions) < 3 and len(watches) > 2:
        # Promote lowest-priority watches to actions
        while len(actions) < 3 and watches:
            promoted = watches.pop()
            promoted["rec_type"] = "action"
            actions.append(promoted)
        actions.sort(key=lambda x: -x["priority_score"])

    # Standing recommendations for strong venues that generate few issues
    _STANDING_ACTIONS = [
        {"theme": "visibility", "dimension": "visibility",
         "title": "Turn strong guest warmth into fresh public proof",
         "description": "Respond to every Google review within 48 hours — positive "
                        "and negative. For satisfied tables, a brief 'we'd love your "
                        "feedback on Google' at bill presentation converts private "
                        "goodwill into public evidence. This compounds monthly.",
         "evidence": "standing_best_practice", "owner": "front-of-house",
         "priority_score": 4.0, "expected_upside": "Review velocity → discovery ranking",
         "confidence": 0.8, "rec_type": "action", "status": "new"},
        {"theme": "trust", "dimension": "trust",
         "title": "Tighten compliance documentation before next inspection",
         "description": "Even with a clean record, walk the floor with an inspector's "
                        "eye. Check HACCP logs are current, allergen matrices are posted, "
                        "cleaning schedules are signed off. The next visit is unannounced — "
                        "preparation is the only lever you control.",
         "evidence": "standing_best_practice", "owner": "compliance",
         "priority_score": 3.5, "expected_upside": "Protect compliance record",
         "confidence": 0.85, "rec_type": "action", "status": "new"},
        {"theme": "experience", "dimension": "experience",
         "title": "Read the last 10 Google reviews — look for the quiet complaint",
         "description": "Strong venues develop blind spots. The complaints that matter "
                        "aren't the angry 1-star rants — they're the 3-star reviews that "
                        "say 'good but...' followed by a specific operational miss. "
                        "Those are the early warning signals.",
         "evidence": "standing_best_practice", "owner": "operations",
         "priority_score": 3.0, "expected_upside": "Early issue detection",
         "confidence": 0.7, "rec_type": "action", "status": "new"},
    ]
    standing_idx = 0
    while len(actions) < 3 and standing_idx < len(_STANDING_ACTIONS):
        actions.append(_STANDING_ACTIONS[standing_idx])
        standing_idx += 1

    # Guarantee 2 watches
    _STANDING_WATCHES = [
        {"theme": "competitive", "dimension": "overall",
         "title": "Monitor local competitor openings and closures",
         "description": "New entrants or closures in your category within 5 miles "
                        "can shift your competitive position. Stay aware of planning "
                        "applications and social media announcements.",
         "evidence": "standing_market_awareness", "owner": "management",
         "priority_score": 3.0, "expected_upside": "Market awareness",
         "confidence": 0.6, "rec_type": "watch", "status": "new"},
        {"theme": "visibility", "dimension": "visibility",
         "title": "Track Google rating trend month-over-month",
         "description": "A sustained 0.1-point drop over 3 months can indicate "
                        "systemic issues before they become obvious. Monitor monthly.",
         "evidence": "standing_monitoring", "owner": "management",
         "priority_score": 2.5, "expected_upside": "Early warning",
         "confidence": 0.7, "rec_type": "watch", "status": "new"},
    ]
    standing_w_idx = 0
    while len(watches) < 2 and standing_w_idx < len(_STANDING_WATCHES):
        watches.append(_STANDING_WATCHES[standing_w_idx])
        standing_w_idx += 1

    # What not to do: lowest-priority action beyond top 3, or standing fallback
    dont = None
    if len(actions) > 3:
        dont = actions[3]
        dont["_reason"] = ("Low impact relative to effort this month. Spending time here "
                           "diverts attention from the three actions above that will "
                           "move your scores more effectively.")
    else:
        dont = {"title": "Don't chase prestige before fixing fundamentals",
                "_reason": ("Avoid spending time on awards submissions, PR, or premium "
                            "positioning until Experience, Trust, and Visibility scores "
                            "are all above 7.0. The fundamentals compound into commercial "
                            "value; prestige without substance doesn't."),
                "dimension": "prestige", "status": "new"}

    return {
        "priority_actions": actions[:3],
        "watch_items": watches[:2],
        "what_not_to_do": dont,
        "all_recs": list(history.values()),
    }
