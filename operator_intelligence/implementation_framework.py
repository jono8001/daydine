"""
operator_intelligence/implementation_framework.py — Action Card Generation

Transforms flat recommendations into structured implementation cards with:
  - target dates
  - success measures (externally verifiable)
  - next milestones (specific, one-sitting actions)
  - owner guidance
  - cost bands
  - barrier diagnosis (for recs aged 3+ months)
"""

from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Cost band → target date window
# ---------------------------------------------------------------------------

_COST_WINDOWS = {
    "zero":   7,
    "low":    7,
    "medium": 30,
    "high":   90,
}

_COST_LABELS = {
    "zero":   "Zero cost (profile update)",
    "low":    "Low (< £200)",
    "medium": "Medium (£200–£1,000)",
    "high":   "High (£1,000+)",
}


def _infer_cost_band(rec):
    """Infer cost band from rec type, dimension, and title."""
    dim = rec.get("dimension", "")
    title_lower = rec.get("title", "").lower()
    rec_type = rec.get("rec_type", "")

    # Digital profile fixes are zero/low cost
    if dim == "conversion":
        if any(w in title_lower for w in ["shopfront", "hours", "menu", "delivery",
                                           "booking", "gbp", "google"]):
            return "zero"
        return "low"
    if dim == "visibility":
        if "photo" in title_lower:
            return "low"
        if "review" in title_lower:
            return "low"
        return "low"
    if dim == "trust":
        return "medium"  # re-inspection prep
    if dim == "experience":
        if rec_type == "exploit":
            return "low"  # messaging change
        return "medium"  # operational fix
    if dim == "prestige":
        return "high"
    return "medium"


# ---------------------------------------------------------------------------
# Success measures — externally verifiable
# ---------------------------------------------------------------------------

def _success_measure(rec):
    """Map rec to an externally verifiable success signal."""
    dim = rec.get("dimension", "")
    title_lower = rec.get("title", "").lower()

    if "menu" in title_lower:
        return "Menu URL present in GBP profile (verifiable via Google Places API)"
    if "hour" in title_lower:
        return "Opening hours complete for 7/7 days (verifiable via goh field)"
    if "photo" in title_lower:
        return "Photo count ≥ 10 and ≥ peer average (verifiable via gpc field)"
    if "shopfront" in title_lower or "digital" in title_lower:
        return "GBP completeness ≥ 9/10 with menu and hours complete (verifiable via API)"
    if "delivery" in title_lower or "takeaway" in title_lower:
        return "Delivery/takeaway types present in Google listing (verifiable via gty field)"
    if "booking" in title_lower or "reserv" in title_lower:
        return "Booking link present in GBP profile (verifiable via Google Places attributes)"
    if "food quality" in title_lower or "complaint" in title_lower:
        return "No food quality complaints in next 10 reviews (verifiable via sentiment analysis)"
    if "rating" in title_lower and "protect" in title_lower:
        return "Google rating maintained or improved vs current baseline (verifiable via gr field)"
    if dim == "trust":
        return "FSA rating maintained or improved on next inspection (verifiable via FSA API)"
    if dim == "visibility":
        return "Google review count increased by 10+ (verifiable via grc field)"
    if dim == "experience" and "service" in title_lower:
        return "Service-related praise maintained in next review sample (verifiable via sentiment)"
    if "competi" in title_lower or "position" in title_lower:
        return "Overall score percentile improved vs local peers (verifiable via next scoring run)"
    return "Signal improvement detectable in next month's data collection"


# ---------------------------------------------------------------------------
# Next milestone — specific, one-sitting action
# ---------------------------------------------------------------------------

def _next_milestone(rec):
    """Generate a specific next-step action, not a vague instruction."""
    dim = rec.get("dimension", "")
    title_lower = rec.get("title", "").lower()

    if "menu" in title_lower:
        return ("Log into business.google.com → select venue → Info → Menu URL → "
                "paste link to your current menu page on your website")
    if "hour" in title_lower:
        return ("Log into business.google.com → select venue → Info → Hours → "
                "add hours for all 7 days including any special hours")
    if "photo" in title_lower:
        return ("Take 5 new photos showing the dining room, a signature dish, "
                "the exterior, and the team. Upload via Google Maps app on your phone")
    if "shopfront" in title_lower or "digital" in title_lower:
        return ("Open your Google Maps listing on your phone. Check: (1) hours for all 7 days, "
                "(2) menu link works, (3) phone number dials correctly, (4) website loads. "
                "Fix any gaps via business.google.com")
    if "delivery" in title_lower or "takeaway" in title_lower:
        return ("Log into business.google.com → select venue → Info → Service options → "
                "enable delivery/takeaway if you offer them")
    if "booking" in title_lower:
        return ("Log into business.google.com → select venue → Info → Booking links → "
                "add your reservation URL or enable Reserve with Google")
    if "food quality" in title_lower or "complaint" in title_lower:
        return ("Pull up the 3 most recent negative reviews. Identify the common theme. "
                "Brief the head chef and FOH manager together on the pattern this week")
    if dim == "trust":
        return ("Review the last FSA inspection report. Address each specific point. "
                "When ready, request a re-inspection via your local authority")
    if "rating" in title_lower and "protect" in title_lower:
        return ("Respond to the 3 most recent Google reviews (positive and negative) "
                "this week. Set a weekly review-response routine")
    if "service" in title_lower and "hospitality" in title_lower:
        return ("Update your GBP description and website homepage to lead with what "
                "guests actually praise: service quality and hospitality")
    if "competi" in title_lower or "position" in title_lower:
        return ("Review the 3 competitor profiles listed in this report. Note what "
                "they do on Google that you don't. Pick one gap to close this week")
    return "Identify the single most actionable sub-task and assign it to a named person with a deadline"


# ---------------------------------------------------------------------------
# Owner guidance
# ---------------------------------------------------------------------------

def _owner_guidance(rec):
    """Add context to the role-level owner."""
    dim = rec.get("dimension", "")
    owner = rec.get("owner", "operations")
    title_lower = rec.get("title", "").lower()

    if any(w in title_lower for w in ["gbp", "google", "shopfront", "digital",
                                       "menu", "hour", "photo", "delivery", "booking"]):
        return f"{owner} — whoever holds Google Business Profile admin access"
    if "food quality" in title_lower or "complaint" in title_lower:
        return f"{owner} — head chef + FOH manager to review together"
    if "rating" in title_lower or "review" in title_lower:
        return f"{owner} — whoever currently responds to online reviews"
    if "service" in title_lower:
        return f"{owner} — FOH lead or general manager"
    if dim == "trust":
        return f"{owner} — compliance/food safety lead"
    return owner


# ---------------------------------------------------------------------------
# Barrier diagnosis
# ---------------------------------------------------------------------------

_BARRIER_CATEGORIES = {
    "access": ("Access barrier",
               "This likely requires system access (e.g. Google Business Profile admin) "
               "that may have been lost or never set up. If the original account holder "
               "has left, Google's ownership recovery process takes 7–14 days."),
    "awareness": ("Awareness barrier",
                  "This recommendation may not have reached the person who can act on it. "
                  "If this report goes to the owner but the system is managed by someone "
                  "else (or a marketing agency), the fix needs forwarding."),
    "prioritisation": ("Prioritisation barrier",
                       "The most common reason a low-cost fix goes undone this long is that "
                       "it was never assigned to a specific person with a specific deadline."),
    "capability": ("Capability barrier",
                   "This may require structured processes, training, or operational changes "
                   "that don't currently exist. It's not a quick fix — it's a project."),
    "disagreement": ("Disagreement barrier",
                     "If this recommendation doesn't apply to your situation, tell us. "
                     "Persistent irrelevant recommendations erode trust in the report. "
                     "We'd rather remove it than repeat it."),
}


def _diagnose_barrier(rec):
    """Diagnose the most likely barrier for a stale recommendation.
    Returns (category_key, label, explanation) or None if too new."""
    months = rec.get("times_seen", 1)
    if months < 3:
        return None

    cost = _infer_cost_band(rec)
    dim = rec.get("dimension", "")
    title_lower = rec.get("title", "").lower()

    # Disagreement: 12+ months on anything
    if months >= 12:
        cat = "disagreement"
        label, base = _BARRIER_CATEGORIES[cat]
        duration_note = (f"This has been flagged for {months} months. "
                         f"At this duration, the issue is no longer the fix — "
                         f"it's why the fix hasn't happened.")
        return cat, label, f"{duration_note} {base}"

    # Low-cost digital fix: likely access or prioritisation
    if cost in ("zero", "low") and dim == "conversion":
        if months >= 6:
            cat = "prioritisation"
        else:
            cat = "access"
        label, base = _BARRIER_CATEGORIES[cat]
        return cat, label, base

    # Visibility fixes: usually awareness
    if dim == "visibility":
        cat = "awareness"
        label, base = _BARRIER_CATEGORIES[cat]
        return cat, label, base

    # Experience/quality fixes: usually capability
    if dim == "experience":
        cat = "capability"
        label, base = _BARRIER_CATEGORIES[cat]
        return cat, label, base

    # Trust: access + capability
    if dim == "trust":
        cat = "capability"
        label, base = _BARRIER_CATEGORIES[cat]
        return cat, label, base

    # Default: prioritisation
    cat = "prioritisation"
    label, base = _BARRIER_CATEGORIES[cat]
    return cat, label, base


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_action_cards(recs, month_str, scorecard=None, venue_rec=None):
    """Generate structured action cards for all active recommendations.

    Returns list of action card dicts, sorted by priority.
    """
    all_recs = recs.get("all_recs", [])
    active = [r for r in all_recs
              if r.get("status") not in ("resolved", "dropped", "completed")]
    active.sort(key=lambda x: -x.get("priority_score", 0))

    # Parse report date for target date calculation
    try:
        report_date = datetime.strptime(month_str, "%Y-%m")
        # Use 1st of the month as base
    except (ValueError, TypeError):
        report_date = datetime.utcnow()

    cards = []
    for rec in active:
        cost_band = _infer_cost_band(rec)
        window_days = _COST_WINDOWS.get(cost_band, 30)
        target_date = report_date + timedelta(days=window_days)

        months = rec.get("times_seen", 1)
        barrier = _diagnose_barrier(rec)

        # Determine status label
        if months >= 12:
            status_label = f"Chronic ({months} months)"
        elif months >= 6:
            status_label = f"Overdue ({months} months)"
        elif months >= 3:
            status_label = f"Stale ({months} months)"
        elif months >= 2:
            status_label = f"Ongoing ({months} months)"
        else:
            status_label = "New"

        card = {
            "title": rec["title"],
            "rec_type": rec.get("rec_type", "fix"),
            "dimension": rec.get("dimension", "—"),
            "status_label": status_label,
            "priority_score": rec.get("priority_score", 0),
            "target_date": target_date.strftime("%d %B %Y"),
            "cost_band": cost_band,
            "cost_label": _COST_LABELS.get(cost_band, cost_band),
            "expected_upside": rec.get("expected_upside", "—"),
            "success_measure": _success_measure(rec),
            "next_milestone": _next_milestone(rec),
            "owner_guidance": _owner_guidance(rec),
            "times_seen": months,
            "barrier": barrier,  # (category, label, explanation) or None
            "evidence": rec.get("evidence", ""),
        }
        cards.append(card)

    return cards
