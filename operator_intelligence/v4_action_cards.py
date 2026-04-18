"""
operator_intelligence/v4_action_cards.py — V4-native action-card builder.

Replaces the V3.4 `implementation_framework.generate_action_cards` for
V4 reports. Reads the V4 recommendations payload (output of
`v4_recommendations.generate_v4_recommendations`) and produces
operator-facing action cards anchored on V4 evidence.

The V3.4 `generate_action_cards` switches on the legacy `dimension`
field (experience / visibility / trust / conversion / prestige) to
infer cost band, success measure, and next milestone. The V4 generator
emits these directly on each rec, so this builder is a thin formatter
rather than an inference engine.

Output card shape (matches what `v4_report_generator._render_implementation_framework`
expects):

    title              — rec.title
    targets_component  — rec.targets_component
    status             — rec.status
    status_label       — pretty status (Ongoing N months / Stale / etc.)
    target_date        — projected by cost-band window
    cost_band          — rec.cost_band normalised label
    expected_upside    — rec.expected_upside (V4-grounded)
    success_measure    — externally verifiable signal anchored on V4 fields
    next_milestone     — concrete one-sitting next step
    owner_guidance     — short who-does-this hint
    times_seen         — rec.times_seen
    evidence           — rec.evidence list

The B6 cleanup removed the legacy `dimension` passthrough — V4 recs
no longer carry that field.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

# Cost-band → projected delivery window (days from today)
_COST_WINDOWS = {
    "zero":   7,
    "low":    21,
    "medium": 60,
    "high":   90,
}

_COST_LABELS = {
    "zero":   "Zero (profile update)",
    "low":    "Low (< £200)",
    "medium": "Medium (£200 – £1,000)",
    "high":   "High (£1,000+)",
}


def _status_label(rec: dict) -> str:
    months = int(rec.get("times_seen", 1) or 1)
    status = rec.get("status", "new")
    if status in {"new"} or months <= 1:
        return "New"
    if months >= 12:
        return f"Chronic ({months} months)"
    if months >= 6:
        return f"Overdue ({months} months)"
    if months >= 3:
        return f"Stale ({months} months)"
    return f"Ongoing ({months} months)"


def _target_date(cost_band: str, today: Optional[datetime] = None) -> str:
    today = today or datetime.utcnow()
    days = _COST_WINDOWS.get(cost_band, 30)
    return (today + timedelta(days=days)).strftime("%d %B %Y")


def _success_measure(rec: dict) -> str:
    """Externally verifiable signal anchored on V4 fields."""
    title_lower = (rec.get("title") or "").lower()
    component = rec.get("targets_component", "")
    if "menu" in title_lower:
        return ("Menu URL present in Google Business Profile — verifiable "
                "via Places API on next enrichment run.")
    if "hour" in title_lower:
        return ("Opening hours complete for 7/7 days — verifiable via "
                "the `goh` field on next enrichment run.")
    if "phone" in title_lower or "booking" in title_lower or "reserv" in title_lower:
        return ("Phone, booking URL, or `reservable=True` observed on "
                "next Google Places enrichment.")
    if "website" in title_lower:
        return ("`websiteUri` observed on next Google Places enrichment "
                "(moves the website signal from inferred to observed).")
    if "fhrs" in title_lower or "hygiene" in title_lower or "inspection" in title_lower:
        return ("Updated `r` / `rd` on next FHRS sync — and any active "
                "STALE-* / P1 / P2 cap drops out.")
    if "companies house" in title_lower or "accounts" in title_lower:
        return ("Updated company status on next Companies House sync — "
                "CH-1 / CH-2 / CH-3 / CH-4 entries clear.")
    if "platform" in title_lower or "review" in title_lower:
        return ("New customer-platform listing or review-count growth "
                "observable on next Customer Validation refresh.")
    if "entity" in title_lower or "disambiguate" in title_lower:
        return ("`entity_match_status` upgraded from current state on "
                "next entity-resolution pass.")
    if "distinction" in title_lower or "michelin" in title_lower or "rosette" in title_lower:
        return ("Distinction modifier preserved on next editorial sync.")
    return f"Component refresh detectable on next {component} update."


def _next_milestone(rec: dict) -> str:
    """Concrete, one-sitting next step."""
    title_lower = (rec.get("title") or "").lower()
    if "menu" in title_lower:
        return ("Log into business.google.com → select venue → Info → "
                "Menu URL → paste link to your current menu page.")
    if "hour" in title_lower:
        return ("Log into business.google.com → select venue → Info → "
                "Hours → add hours for all 7 days, including any special "
                "hours.")
    if "phone" in title_lower or "booking" in title_lower:
        return ("Log into business.google.com → select venue → Info → "
                "add a public phone number or booking link.")
    if "website" in title_lower:
        return ("Log into business.google.com → select venue → Info → "
                "Website → paste the venue's website URL.")
    if "fhrs" in title_lower or "hygiene" in title_lower or "inspection" in title_lower:
        return ("Contact your Local Authority's environmental health "
                "team to schedule the next inspection. Prepare the "
                "venue against the FSA structural / management / "
                "food-handling categories beforehand.")
    if "accounts" in title_lower:
        return ("File the overdue accounts at "
                "find-and-update.company-information.service.gov.uk.")
    if "director" in title_lower:
        return ("Review the appointment calendar — confirm any filings "
                "in the trailing 12 months were strictly necessary.")
    if "entity" in title_lower or "disambiguate" in title_lower:
        return ("Confirm the venue's FHRSID and Google Place ID are "
                "the canonical pair (cross-check via "
                "ratings.food.gov.uk and Google Maps URL). Open a "
                "manual entry in `data/entity_aliases.json` if a "
                "permanent disambiguation is needed.")
    if "platform" in title_lower or "review" in title_lower:
        return ("Claim a TripAdvisor business listing if not present, "
                "or seed your second platform via a soft launch — do "
                "not solicit fake reviews.")
    if "temporary" in title_lower or "closed" in title_lower or "reopening" in title_lower:
        return ("Update the Google Business Profile description to "
                "include the closure window and expected reopening "
                "date.")
    return ("Take the smallest verifiable step toward the action above "
            "this calendar week.")


def _owner_guidance(rec: dict) -> str:
    component = rec.get("targets_component", "")
    if component == "Trust & Compliance":
        return ("Owner / general manager — compliance and Companies "
                "House actions need formal authority.")
    if component == "Customer Validation":
        return ("Owner or marketing lead — platform listings and "
                "review-volume strategy.")
    if component == "Commercial Readiness":
        return ("General manager or front-of-house lead — Google "
                "Business Profile updates take ~30 minutes.")
    if component == "Distinction":
        return ("Owner — editorial recognition currency is a long-game "
                "PR concern.")
    if component == "Entity / Identity":
        return ("Operations lead — entity resolution typically goes "
                "through DayDine support if the FHRSID needs "
                "disambiguating.")
    return "Owner."


def generate_v4_action_cards(recs: dict, month_str: str,
                                today: Optional[datetime] = None) -> list[dict]:
    """Produce action cards from a V4 recommendations payload.

    `recs` is the dict returned by
    `v4_recommendations.generate_v4_recommendations`. We surface
    actionable recs (fix / exploit / protect) only — watch and ignore
    items live in their own report sections.
    """
    actionable = [r for r in (recs.get("all_recs") or [])
                   if r.get("rec_type") in {"fix", "exploit", "protect"}]
    actionable.sort(key=lambda r: -int(r.get("priority_score", 0)))
    cards: list[dict] = []
    for r in actionable[:6]:
        cost_band = r.get("cost_band", "low")
        cards.append({
            "title": r.get("title"),
            "targets_component": r.get("targets_component"),
            "status": r.get("status", "new"),
            "status_label": _status_label(r),
            "target_date": _target_date(cost_band, today=today),
            "cost_band": cost_band,
            "cost_label": _COST_LABELS.get(cost_band, cost_band),
            "expected_upside": r.get("expected_upside", "—"),
            "success_measure": _success_measure(r),
            "next_milestone": _next_milestone(r),
            "owner_guidance": _owner_guidance(r),
            "times_seen": int(r.get("times_seen", 1) or 1),
            "evidence": list(r.get("evidence") or []),
        })
    return cards
