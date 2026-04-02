"""
operator_intelligence/recommendations.py — Recommendation Memory System

Generates, persists, and tracks recommendations with stateful lifecycle:
  New → Ongoing → Escalated → Resolved/Completed/Dropped

Recommendation types (V2):
  FIX      — urgent operational fix, something is broken or hurting
  EXPLOIT  — capitalise on an untapped strength or hidden advantage
  PROTECT  — defend an existing asset before it erodes
  WATCH    — monitor an emerging signal, not yet actionable
  IGNORE   — explicitly deprioritise something that looks tempting

Recommendations come from:
  - Structural gaps (missing signals, low dimension scores)
  - Review intelligence (praise themes, criticism themes, risk flags)
  - Peer context (gap analysis, false-comfort detection)
  - Score changes (drops, persistent issues)
  - Proposition alignment (what guests value vs what the venue promotes)

Output format: top 3 priority actions, top 2 watch items, top 1 what-not-to-do.
"""

import hashlib
import json
import os

STATUSES = ("new", "ongoing", "escalated", "resolved", "watchlist",
            "dropped", "completed")

REC_TYPES = ("fix", "exploit", "protect", "watch", "ignore")

HISTORY_DIR = "history/recommendations"


# ---------------------------------------------------------------------------
# Priority scoring — computed, not hardcoded
# ---------------------------------------------------------------------------

def _compute_priority(business_impact, evidence_strength, peer_gap=0,
                      persistence=0):
    """Compute priority score from constituent factors.
    Each factor is 0-3 except peer_gap and persistence (0-2).
    Returns float 0-10."""
    raw = (business_impact * 2.0
           + evidence_strength * 1.5
           + peer_gap * 1.0
           + persistence * 0.5)
    return round(min(10.0, raw), 1)


# ---------------------------------------------------------------------------
# Recommendation generation rules
# ---------------------------------------------------------------------------

def _generate_recs(venue, scorecard, benchmarks, deltas, review_intel=None):
    """Generate candidate recommendations from all available signals.
    Returns list of rec dicts (unsorted, no status yet)."""
    recs = []

    gr = venue.get("gr")
    grc = venue.get("grc")
    r = venue.get("r")
    exp = scorecard.get("experience")
    vis = scorecard.get("visibility")
    trust = scorecard.get("trust")
    conv = scorecard.get("conversion")
    prest = scorecard.get("prestige")
    overall = scorecard.get("overall")

    # Extract review analysis data
    analysis = None
    praise = []
    criticism = []
    risks = []
    if review_intel:
        analysis = review_intel.get("analysis")
        if analysis:
            praise = analysis.get("praise_themes", [])
            criticism = analysis.get("criticism_themes", [])
            risks = analysis.get("risk_flags", [])

    # --- 1. STRUCTURAL FIX RECS ---

    # No Google photos
    gpc = venue.get("gpc")
    if gpc is not None and int(gpc) == 0:
        recs.append(_rec(
            "fix", "visibility",
            "Your Google listing is invisible — add photos now",
            "Zero photos on your listing. Venues with 10+ photos get 35% more "
            "click-throughs. This is the single fastest visibility fix available.",
            "gpc=0", "marketing",
            _compute_priority(2, 3),
            "+1.0 Visibility, immediate discovery improvement", 0.9,
            "A faceless listing loses to every competitor with a single photo."
        ))

    # No opening hours
    goh = venue.get("goh")
    if not goh or (isinstance(goh, list) and len(goh) == 0):
        recs.append(_rec(
            "fix", "conversion",
            "Publish opening hours — you're invisible to 'open now' searches",
            "No opening hours listed. Every customer filtering by 'open now' on "
            "Google Maps will never see you. This takes 2 minutes to fix.",
            "goh missing", "operations",
            _compute_priority(2, 3),
            "Appear in 'open now' searches immediately", 0.95,
            "This is a zero-effort, high-impact fix."
        ))

    # No menu online
    if not venue.get("has_menu_online"):
        recs.append(_rec(
            "fix", "conversion",
            "Get your menu online — 77% of diners check before visiting",
            "No online menu found. Most diners check the menu before committing. "
            "Without one, you lose the customer at the decision point.",
            "has_menu_online=false", "marketing",
            _compute_priority(2, 2),
            "Reduce decision-stage drop-off", 0.85,
            "Every day without a menu is a percentage of potential customers lost."
        ))

    # Low Google rating
    if gr is not None and float(gr) < 4.0:
        recs.append(_rec(
            "fix", "experience",
            "Identify and fix the recurring guest complaint",
            f"At {gr}/5 on Google, something specific is landing badly. "
            "Read the 5 most recent negative reviews, identify the common "
            "thread, and fix it at source. The rating won't move until the "
            "root cause does.",
            f"gr={gr}", "operations",
            _compute_priority(3, 2),
            "Rating recovery → discovery recovery", 0.8,
            "Below 4.0, Google actively suppresses your venue in search results."
        ))

    # Few reviews
    if grc is not None and int(grc) < 20:
        recs.append(_rec(
            "fix", "visibility",
            "Build review volume — you lack statistical credibility",
            f"Only {grc} Google reviews. A single bad review moves your "
            "average visibly. Encourage satisfied customers to leave reviews.",
            f"grc={grc}", "front-of-house",
            _compute_priority(2, 2),
            "Rating stability + discovery ranking", 0.85,
        ))

    # Stale FSA inspection
    from rcs_scoring_stratford import days_since
    age = days_since(venue.get("rd"))
    if age is not None and age > 730:
        years = round(age / 365, 1)
        recs.append(_rec(
            "fix", "trust",
            "Renew formal trust proof before it becomes a visible drag",
            f"Last inspected {years} years ago. A stale inspection date erodes "
            "trust scoring and signals to customers that compliance isn't "
            "actively managed. Request a voluntary re-inspection once you're "
            "confident of a strong result.",
            f"inspection_age={age}d", "compliance",
            _compute_priority(2, 2, persistence=1),
            "Fresh compliance proof, trust signal renewal", 0.7,
            "Stale trust is a hidden ceiling on your overall position."
        ))

    # FSA rating < 5
    if r is not None and int(r) < 5:
        recs.append(_rec(
            "fix", "trust",
            f"Close the hygiene gap — {r} to 5",
            f"An FSA rating of {r} is visible on your Google listing and the "
            "FSA website. Customers see it before they see your menu. Address "
            "the inspector's specific findings.",
            f"r={r}", "compliance",
            _compute_priority(3 if int(r) <= 3 else 2, 3),
            "Remove the trust ceiling on your overall score", 0.9,
        ))

    # No social presence at all
    if not venue.get("web") and not venue.get("fb") and not venue.get("ig"):
        recs.append(_rec(
            "fix", "visibility",
            "Establish basic web presence — you don't exist online beyond Google",
            "No website, Facebook, or Instagram detected. Even a basic page "
            "improves discoverability and gives customers a reason to trust you "
            "before visiting.",
            "web=false, fb=false, ig=false", "marketing",
            _compute_priority(1, 2),
            "Basic discoverability beyond Google Maps", 0.8,
        ))

    # High experience, low conversion — demand leakage
    if exp and conv and exp >= 7.0 and conv < 6.0:
        recs.append(_rec(
            "fix", "conversion",
            "Fix the digital shopfront — you're losing walk-ins",
            "You deliver a strong experience but your online presence doesn't "
            "make it easy to act on. Can a new customer confirm your hours, "
            "see your menu, and book — all within 60 seconds on their phone? "
            "If not, that's your fix list.",
            f"experience={exp}, conversion={conv}", "operations",
            _compute_priority(2, 2),
            "Capture demand you're currently losing", 0.8,
            "Interest without conversion is vanity traffic."
        ))

    # --- 2. REVIEW-DRIVEN RECS ---

    if criticism:
        for crit in criticism[:2]:
            label = crit.get("label", "Unknown")
            mentions = crit.get("mentions", 0)
            quotes = crit.get("quotes", [])
            best_quote = quotes[0][:100] if quotes else None

            if mentions >= 3:
                severity = "recurring"
                impact = 2
                evidence = 2
            elif mentions >= 2:
                severity = "repeated"
                impact = 2
                evidence = 1
            else:
                severity = "isolated"
                impact = 1
                evidence = 1

            desc = (f"{label} draws {severity} criticism across reviews "
                    f"({mentions} negative mentions).")
            if best_quote:
                desc += f' One guest wrote: "{best_quote}..."'
            desc += (" Investigate whether this reflects a systemic issue "
                     "or isolated incidents.")

            # Specific management implications by aspect
            if "access" in label.lower() or "booking" in label.lower():
                desc += (" Accessibility complaints carry legal and reputational "
                         "risk under the Equality Act — treat as urgent.")
                impact = 3

            recs.append(_rec(
                "fix", "experience",
                f"Address {severity} {label.lower()} complaints from guests",
                desc,
                f"review_criticism: {label}={mentions} negative",
                "operations",
                _compute_priority(impact, evidence),
                f"Reduce {label.lower()} complaints, protect rating", 0.7,
                f"Guests are telling you what's wrong. Listen."
            ))

    # Exploit untapped praise themes
    if praise:
        top_praise = praise[0]
        label = top_praise.get("label", "")
        mentions = top_praise.get("mentions", 0)
        if mentions >= 3 and exp and exp >= 7.0:
            recs.append(_rec(
                "exploit", "experience",
                f"Lean into {label.lower()} — it's what guests are buying",
                f"Guests consistently praise {label.lower()} ({mentions} positive "
                f"mentions). This appears to be what the venue actually sells, "
                f"whether or not it's what you think you sell. Make it the "
                f"headline of your online presence.",
                f"review_praise: {label}={mentions}",
                "management",
                _compute_priority(2, 2),
                "Sharpen proposition → attract the right guests", 0.7,
                "Your guests are telling you your proposition. Use it."
            ))

    # Risk flags from reviews
    if risks:
        recs.append(_rec(
            "fix", "experience",
            "Investigate review risk flags — reputational exposure",
            f"Risk phrases detected in reviews: {', '.join(risks[:3])}. "
            "These may indicate incidents that could escalate publicly. "
            "Verify they've been operationally resolved.",
            f"risk_flags={risks}",
            "management",
            _compute_priority(3, 1),
            "Prevent reputational damage", 0.6,
        ))

    # --- 3. FALSE COMFORT / WATCH RECS ---

    ring1 = (benchmarks or {}).get("ring1_local", {})
    ring1_overall = ring1.get("dimensions", {}).get("overall", {})
    pct = ring1_overall.get("percentile")

    # Strong Google rating but below-median position
    if gr and float(gr) >= 4.5 and pct is not None and pct < 50:
        recs.append(_rec(
            "watch", "overall",
            "Strong rating masks weak competitive position",
            f"Your {gr}/5 Google rating feels dominant but you sit below "
            f"the local median (P{pct}). Peer venues achieve similar or better "
            f"ratings — in this market, 4.5 is table stakes, not a "
            f"differentiator. Don't mistake the number for an advantage.",
            f"gr={gr}, local_percentile={pct}",
            "management",
            _compute_priority(2, 2),
            "Realistic competitive awareness", 0.7,
            "The rating looks good in isolation but not in context."
        ))

    # Strong experience but weak/stale trust
    if exp and exp >= 8.0 and trust and trust < 7.0:
        recs.append(_rec(
            "watch", "trust",
            "Guest experience outpaces formal trust record",
            "Guests enjoy the venue but the compliance record hasn't kept up. "
            "One poor inspection would make a private gap public. The fix is "
            "proactive compliance work, not more marketing.",
            f"experience={exp}, trust={trust}",
            "compliance",
            _compute_priority(2, 2),
            "Close the gap before it becomes visible", 0.75,
        ))

    # High visibility but weak conversion
    if vis and vis >= 8.0 and conv and conv < 5.5:
        recs.append(_rec(
            "watch", "conversion",
            "High discovery, low conversion — vanity traffic risk",
            "You're easy to find but hard to act on. Customers discover you "
            "then can't confirm hours, see a menu, or book. That interest "
            "converts to a competitor who makes it easier.",
            f"visibility={vis}, conversion={conv}",
            "operations",
            _compute_priority(2, 2),
            "Convert discovery into actual visits", 0.8,
        ))

    # Good score based on thin evidence
    rc = _assess_confidence(review_intel)
    if rc == "anecdotal" and overall and overall >= 7.0:
        recs.append(_rec(
            "watch", "overall",
            "Solid score rests on thin evidence — more data could shift it",
            "The overall score looks good but it's based on very limited "
            "review text. Collect TripAdvisor data and more Google reviews "
            "to confirm whether the position is real or artefact.",
            f"overall={overall}, evidence_tier=anecdotal",
            "management",
            _compute_priority(1, 1),
            "Validate the score before acting on it", 0.5,
        ))

    # Below-median competitive position (general watch)
    if pct is not None and pct < 50:
        peer_count = ring1_overall.get("of", 0)
        rank = ring1_overall.get("rank", "?")
        recs.append(_rec(
            "watch", "overall",
            f"Ranked #{rank} of {peer_count} locally — peers are ahead",
            f"At percentile {pct}, customers in this area have higher-rated "
            f"alternatives. This isn't a crisis but it means you're competing "
            f"on convenience rather than reputation.",
            f"local_percentile={pct}",
            "management",
            _compute_priority(1, 2),
            "Competitive awareness", 0.7,
        ))

    # Weakest dimension vs peers — specific watch items
    for dim in ["experience", "trust", "conversion"]:
        dim_data = ring1.get("dimensions", {}).get(dim, {})
        score = dim_data.get("score")
        peer_mean = dim_data.get("peer_mean")
        if score and peer_mean and score - peer_mean < -1.0:
            gap = peer_mean - score
            titles = {
                "experience": "Guest experience trailing — investigate what peers do differently",
                "trust": "Compliance record weakest in peer set — creates inspection exposure",
                "conversion": "Harder to book/find than competitors — friction losing customers",
            }
            recs.append(_rec(
                "watch", dim,
                titles.get(dim, f"{dim.title()} gap vs peers"),
                f"You trail peers by {gap:.1f} points on {dim}. This isn't a "
                f"label problem — it means customers are getting a measurably "
                f"better experience on this dimension from your competitors.",
                f"{dim}: {score:.1f} vs peer avg {peer_mean:.1f}",
                "management",
                _compute_priority(1, 2, peer_gap=1),
                f"Close the {gap:.1f}-point gap", 0.65,
            ))

    # --- 4. EXPLOIT / PROTECT RECS ---

    # Review volume growth opportunity
    if grc is not None and 20 <= int(grc) < 200:
        recs.append(_rec(
            "exploit", "visibility",
            "Accelerate review volume — you're credible but not dominant",
            f"At {grc} reviews, your rating is stable but not commanding. "
            "Venues with 200+ reviews rank higher in Maps. A post-visit "
            "review prompt would compound monthly.",
            f"grc={grc}", "front-of-house",
            _compute_priority(1, 2),
            "Improved Google Maps ranking", 0.75,
        ))

    # GBP completeness opportunity
    gbp = venue.get("gbp_completeness")
    if gbp is not None and float(gbp) < 8.0:
        recs.append(_rec(
            "exploit", "visibility",
            "Complete your Google Business Profile — 70% more direction requests",
            f"GBP completeness is {gbp}/10. Add photos, menu link, booking link, "
            "and business description to unlock the full discovery benefit.",
            f"gbp_completeness={gbp}", "marketing",
            _compute_priority(1, 2),
            "+0.5 Visibility", 0.8,
        ))

    # Prestige opportunity for strong venues
    if overall and overall >= 7.5:
        if not venue.get("has_michelin_mention") and not venue.get("has_aa_rating"):
            recs.append(_rec(
                "exploit", "prestige",
                "Your quality supports a credible awards submission",
                "Operational scores justify a submission to AA or local food "
                "awards. Editorial recognition would differentiate you from "
                "peers and support premium pricing.",
                f"overall={overall}", "management",
                _compute_priority(1, 1),
                "Brand differentiation", 0.5,
            ))

    # Protect strong Google rating
    if gr and float(gr) >= 4.5 and grc and int(grc) >= 200:
        recs.append(_rec(
            "protect", "visibility",
            f"Protect the {gr}/5 rating — it took years to build",
            f"With {grc} reviews at {gr}/5, your discovery advantage is "
            f"substantial. Protect it by responding to every review within "
            f"48 hours and prompting satisfied tables for feedback.",
            f"gr={gr}, grc={grc}", "front-of-house",
            _compute_priority(2, 2),
            "Sustain discovery advantage", 0.85,
        ))

    return recs


def _rec(rec_type, dimension, title, description, evidence, owner,
         priority_score, expected_upside, confidence,
         management_implication=None):
    """Build a recommendation dict with consistent structure."""
    d = {
        "rec_type": rec_type,
        "theme": dimension,
        "dimension": dimension,
        "title": title,
        "description": description,
        "evidence": evidence,
        "owner": owner,
        "priority_score": priority_score,
        "expected_upside": expected_upside,
        "confidence": confidence,
    }
    if management_implication:
        d["management_implication"] = management_implication
    return d


def _assess_confidence(review_intel):
    """Quick confidence tier check without importing report_spec."""
    if not review_intel:
        return "none"
    analysis = review_intel.get("analysis")
    if not analysis:
        return "none"
    n = analysis.get("reviews_analyzed", 0)
    if n <= 5:
        return "anecdotal"
    if n <= 15:
        return "indicative"
    if n <= 30:
        return "directional"
    return "established"


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


def generate_recommendations(venue, scorecard, benchmarks, deltas, month_str,
                             review_intel=None):
    """Generate recommendations, merge with history, return prioritised output.

    Returns dict with:
      priority_actions: top 3 (mix of fix/exploit/protect)
      watch_items: top 2
      what_not_to_do: top 1 (ignore type)
      all_recs: full list with status
    """
    venue_id = str(venue.get("id") or venue.get("fhrsid", "unknown"))
    now = month_str

    candidates = _generate_recs(venue, scorecard, benchmarks, deltas,
                                review_intel=review_intel)
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

    # Sort by priority — separate actionable types from watches
    active = [r for r in candidates if r["status"] not in ("resolved", "dropped", "completed")]
    actionable = sorted(
        [r for r in active if r.get("rec_type") in ("fix", "exploit", "protect", "action")],
        key=lambda x: -x["priority_score"])
    watches = sorted(
        [r for r in active if r.get("rec_type") == "watch"],
        key=lambda x: -x["priority_score"])

    # --- Guarantee 3 actions, 2 watches, 1 ignore ---

    # If fewer than 3 actionable, promote top watches
    if len(actionable) < 3 and len(watches) > 2:
        while len(actionable) < 3 and watches:
            promoted = watches.pop(0)
            promoted["rec_type"] = "fix"
            actionable.append(promoted)
        actionable.sort(key=lambda x: -x["priority_score"])

    # Standing recommendations — only when genuinely no better recs exist
    _STANDING = [
        _rec("protect", "visibility",
             "Turn strong guest warmth into fresh public proof",
             "Respond to every Google review within 48 hours. For satisfied "
             "tables, a brief prompt at bill presentation converts private "
             "goodwill into public evidence. This compounds monthly.",
             "standing_best_practice", "front-of-house",
             _compute_priority(1, 1), "Review velocity → discovery ranking", 0.8),
        _rec("protect", "trust",
             "Tighten compliance documentation before next inspection",
             "Walk the floor with an inspector's eye. Check HACCP logs, "
             "allergen matrices, cleaning schedules. The next visit is "
             "unannounced — preparation is the only lever you control.",
             "standing_best_practice", "compliance",
             _compute_priority(1, 1), "Protect compliance record", 0.85),
        _rec("exploit", "experience",
             "Mine the quiet complaints in your 3-star reviews",
             "Strong venues develop blind spots. The complaints that matter "
             "aren't the angry 1-star rants — they're the 3-star 'good but...' "
             "reviews with specific operational misses. Those are early warnings.",
             "standing_best_practice", "operations",
             _compute_priority(1, 1), "Early issue detection", 0.7),
    ]
    idx = 0
    while len(actionable) < 3 and idx < len(_STANDING):
        actionable.append({**_STANDING[idx], "status": "new"})
        idx += 1

    # Guarantee 2 watches
    _STANDING_WATCHES = [
        _rec("watch", "overall",
             "Monitor local competitor openings and closures",
             "New entrants or closures within 5 miles can shift your position. "
             "Stay aware of planning applications and social media.",
             "standing_market_awareness", "management",
             _compute_priority(0, 1), "Market awareness", 0.6),
        _rec("watch", "visibility",
             "Track Google rating trend month-over-month",
             "A sustained 0.1-point drop over 3 months indicates systemic "
             "issues before they become obvious.",
             "standing_monitoring", "management",
             _compute_priority(0, 1), "Early warning", 0.7),
    ]
    w_idx = 0
    while len(watches) < 2 and w_idx < len(_STANDING_WATCHES):
        watches.append({**_STANDING_WATCHES[w_idx], "status": "new"})
        w_idx += 1

    # What not to do — lowest-priority excess action, or standing ignore
    dont = None
    if len(actionable) > 3:
        dont = actionable[3]
        dont["rec_type"] = "ignore"
        dont["_reason"] = ("Low impact relative to effort this month. "
                           "Focus on the three priorities above.")
    else:
        exp_val = scorecard.get("experience") or 0
        trust_val = scorecard.get("trust") or 0
        vis_val = scorecard.get("visibility") or 0
        if exp_val >= 7.0 and trust_val >= 7.0 and vis_val >= 7.0:
            dont = {"title": "Don't diversify channels before deepening the core",
                    "rec_type": "ignore",
                    "_reason": ("Your fundamentals are sound. Resist the temptation "
                                "to spread into delivery platforms, catering, or "
                                "events unless they genuinely fit your proposition. "
                                "Depth beats breadth at this stage."),
                    "dimension": "conversion", "status": "new"}
        else:
            dont = {"title": "Don't chase prestige before fixing fundamentals",
                    "rec_type": "ignore",
                    "_reason": ("Awards don't fix a weak proposition — they amplify "
                                "a strong one. Get Experience, Trust, and Visibility "
                                "above 7.0 first."),
                    "dimension": "prestige", "status": "new"}

    return {
        "priority_actions": actionable[:3],
        "watch_items": watches[:2],
        "what_not_to_do": dont,
        "all_recs": list(history.values()),
    }
