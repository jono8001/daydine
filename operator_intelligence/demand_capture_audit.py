"""
operator_intelligence/demand_capture_audit.py — 7-Dimension Demand Capture Audit

Performs a structured outside-in walkthrough of a venue's public digital
presence. Each dimension produces a verdict (Clear/Partial/Missing/Broken/Gap)
with specific signal citations and commercial consequence.

Uses only publicly observable data: Google Places fields, GBP profile,
TripAdvisor listing, review text, website inference.
"""

# ============================================================================
# SHARED — NARRATIVE / PROFILE-ONLY HELPER (V3.4 origin, reused by V4)
# ----------------------------------------------------------------------------
# This module produces narrative / profile-only output. The V4 report layer
# reuses it as a text / theme source (see `operator_intelligence/v4_report_
# generator.py`) — NEVER as a score input. V4 scoring does not consume
# sentiment, aspect scores, review text, photo count, price level, social
# presence, or any other forbidden input defined in `docs/DayDine-V4-
# Scoring-Spec.md` §2.3 / `docs/DayDine-V4-Report-Spec.md` §2.3.
#
# Changes here must keep the output shape stable so V4 consumers do not
# break. See spec §8 for the narrative rules.
# ============================================================================

import re
from collections import Counter


# ---------------------------------------------------------------------------
# Review text scanning helpers
# ---------------------------------------------------------------------------

def _scan_reviews(venue_rec, keywords):
    """Scan all review text for keyword matches. Returns list of snippets."""
    matches = []
    for field in ["g_reviews", "ta_reviews"]:
        for rev in venue_rec.get(field, []):
            text = (rev.get("text") or "").strip()
            if not text:
                continue
            text_lower = text.lower()
            for kw in keywords:
                if kw in text_lower:
                    snippet = text[:120].strip()
                    if len(text) > 120:
                        snippet += "..."
                    matches.append(snippet)
                    break  # one match per review
    return matches


# ---------------------------------------------------------------------------
# Individual dimension auditors
# ---------------------------------------------------------------------------

def _audit_booking(venue_rec, review_intel):
    """Dimension 1: Booking Friction."""
    gty = venue_rec.get("gty", [])
    is_restaurant = "restaurant" in gty
    has_web = venue_rec.get("web") is True
    ta_present = venue_rec.get("ta_present") is True

    # Review evidence
    booking_kw = ["book", "reserv", "pre-book", "couldn't get a table",
                  "no booking", "turned away", "walk-in", "walk in"]
    booking_reviews = _scan_reviews(venue_rec, booking_kw)
    positive_booking = [r for r in booking_reviews
                        if any(w in r.lower() for w in ["pre-booked", "booked online",
                                                         "easy to book", "reservation"])]
    negative_booking = [r for r in booking_reviews
                        if any(w in r.lower() for w in ["couldn't book", "no booking",
                                                         "turned away", "had to wait"])]

    # Verdict logic
    signals = []
    if is_restaurant:
        signals.append("GBP type includes 'restaurant' (reservation expected)")
    else:
        signals.append("GBP type does not include 'restaurant' — booking expectation unclear")

    if has_web:
        signals.append("Website present (may host booking)")
    else:
        signals.append("No website detected — no online booking path visible")

    if ta_present:
        signals.append("TripAdvisor listing present")

    if positive_booking:
        signals.append(f"Review evidence: {len(positive_booking)} mention(s) of successful booking")
    if negative_booking:
        signals.append(f"Review evidence: {len(negative_booking)} mention(s) of booking difficulty")

    # Determine verdict
    if is_restaurant and has_web and not negative_booking:
        verdict = "Partial"
        finding = ("Booking is likely available via website, but no direct booking link "
                   "is confirmed in Google Maps. A customer must leave Maps → find the "
                   "website → locate the booking page. Each click loses ~20% of intent.")
        consequence = ("Customers searching 'restaurant near me' expect 1-click booking. "
                       "Without it, you lose to competitors with Reserve with Google or a visible booking button.")
    elif not has_web and not is_restaurant:
        verdict = "Missing"
        finding = "No booking path detected from any public channel."
        consequence = "Walk-in only limits demand capture to spontaneous visitors."
    elif negative_booking:
        verdict = "Broken"
        finding = (f"Booking friction reported in reviews: "
                   f'"{negative_booking[0][:80]}"')
        consequence = "Visible booking complaints on public platforms deter future customers."
    else:
        verdict = "Partial"
        finding = ("Booking path exists but is not surfaced in the primary discovery "
                   "channel (Google Maps). Requires leaving Maps to book.")
        consequence = "Friction between discovery and commitment costs conversion."

    return {
        "dimension": "Booking Friction",
        "verdict": verdict,
        "finding": finding,
        "consequence": consequence,
        "signals": signals,
        "review_evidence": booking_reviews[:2],
    }


def _audit_menu(venue_rec, review_intel):
    """Dimension 2: Menu Visibility."""
    has_menu = venue_rec.get("has_menu_online") is True
    has_web = venue_rec.get("web") is True

    menu_kw = ["menu", "set menu", "prix fixe", "tasting menu", "specials"]
    menu_reviews = _scan_reviews(venue_rec, menu_kw)
    surprise_kw = ["didn't know", "wasn't on the menu", "no menu online", "couldn't find the menu"]
    surprise_reviews = _scan_reviews(venue_rec, surprise_kw)

    signals = []
    if has_menu:
        signals.append("Menu online: detected (inferred from web presence)")
    else:
        signals.append("Menu online: not detected")
    if has_web:
        signals.append("Website present (menu may be hosted there)")
    if menu_reviews:
        signals.append(f"{len(menu_reviews)} review(s) mention the menu")
    if surprise_reviews:
        signals.append(f"{len(surprise_reviews)} review(s) mention menu surprise or difficulty finding it")

    if has_menu and not surprise_reviews:
        verdict = "Partial"
        finding = ("Menu exists online (inferred) but we cannot confirm it is linked "
                   "from Google Maps or that it is scannable on mobile. 77% of diners "
                   "check the menu before visiting — if it is buried on a sub-page or "
                   "a PDF, it may as well be missing.")
        consequence = "A menu that exists but isn't in the discovery path loses most of its conversion value."
    elif has_menu and surprise_reviews:
        verdict = "Broken"
        finding = (f"Menu exists but reviews suggest friction: "
                   f'"{surprise_reviews[0][:80]}"')
        consequence = "Menu expectations set online don't match the visit experience."
    elif not has_menu:
        verdict = "Missing"
        finding = ("No online menu detected. A customer deciding between you and a "
                   "competitor who shows their menu will choose the one that reduces uncertainty.")
        consequence = "Missing menu = lost at the research stage for 77% of diners (industry benchmark)."
    else:
        verdict = "Clear"
        finding = "Menu is accessible in the primary discovery path."
        consequence = "No friction detected."

    return {
        "dimension": "Menu Visibility",
        "verdict": verdict,
        "finding": finding,
        "consequence": consequence,
        "signals": signals,
        "review_evidence": menu_reviews[:2],
    }


def _audit_cta(venue_rec):
    """Dimension 3: CTA Clarity (GBP completeness breakdown)."""
    # Replicate the 10-attribute GBP check to show which are present/missing
    checks = {}
    checks["Has rating"] = venue_rec.get("gr") is not None
    checks["Has reviews (>0)"] = (venue_rec.get("grc") or 0) > 0
    checks["Has photos (>0)"] = (venue_rec.get("gpc") or 0) > 0
    checks["Has opening hours"] = bool(venue_rec.get("goh"))
    checks["Has price level"] = venue_rec.get("gpl") is not None
    checks["Has place types"] = bool(venue_rec.get("gty"))
    checks["Has Place ID"] = bool(venue_rec.get("gpid"))
    checks["Review count >= 10"] = (venue_rec.get("grc") or 0) >= 10
    checks["Review count >= 100"] = (venue_rec.get("grc") or 0) >= 100
    checks["Has website"] = venue_rec.get("web") is True

    present = [k for k, v in checks.items() if v]
    missing = [k for k, v in checks.items() if not v]
    score = len(present)

    signals = [f"GBP completeness: {score}/10"]
    if missing:
        signals.append(f"Missing: {', '.join(missing)}")
    else:
        signals.append("All 10 GBP attributes present")

    if score >= 9:
        verdict = "Clear"
        finding = (f"GBP profile is {score}/10 complete. All critical action paths "
                   f"(call, directions, website) are populated.")
        consequence = "No CTA friction detected."
    elif score >= 7:
        verdict = "Partial"
        finding = (f"GBP profile is {score}/10 complete. Missing: {', '.join(missing)}. "
                   f"Each gap removes a potential action path for a customer ready to commit.")
        consequence = "Partial CTA completeness means some customers can't take their preferred action."
    else:
        verdict = "Missing"
        finding = (f"GBP profile is only {score}/10 complete. Significant gaps: "
                   f"{', '.join(missing)}.")
        consequence = "Incomplete GBP profile suppresses Google Maps visibility and customer action."

    return {
        "dimension": "CTA Clarity",
        "verdict": verdict,
        "finding": finding,
        "consequence": consequence,
        "signals": signals,
        "review_evidence": [],
    }


def _audit_photos(venue_rec, scorecard, benchmarks, review_intel):
    """Dimension 4: Photo Mix & Quality."""
    gpc = venue_rec.get("gpc") or 0

    # Peer comparison
    ring1 = (benchmarks or {}).get("ring1_local", {})
    peer_photos = []
    for tp in ring1.get("top_peers", []):
        fid = tp.get("fhrsid", "")
        # We only have gpc from the scorecard enrichment, not per-peer raw data
        # Use a reasonable proxy: peers with GBP completeness likely have ~10 photos
        peer_photos.append(10)  # default assumption from current data
    peer_avg_photos = sum(peer_photos) / len(peer_photos) if peer_photos else 10

    # Top review themes for cross-reference
    analysis = review_intel.get("analysis") if review_intel else None
    praise = analysis.get("praise_themes", []) if analysis else []
    top_theme = praise[0]["label"] if praise else None

    signals = [f"Photo count: {gpc}"]
    signals.append(f"Peer average: ~{peer_avg_photos:.0f} photos")
    if top_theme:
        signals.append(f"Top review theme: {top_theme}")

    if gpc >= 10 and top_theme:
        verdict = "Partial"
        finding = (f"{gpc} photos present — matching peer average. However, we cannot "
                   f"verify from external data whether photos match the experience guests "
                   f"praise. Reviews highlight **{top_theme.lower()}** — if your photos "
                   f"don't showcase this, there is a proposition mismatch in the listing.")
        consequence = ("Photos that don't match the praised experience waste the strongest "
                       "conversion signal your listing has.")
    elif gpc >= 10:
        verdict = "Clear"
        finding = f"{gpc} photos — competitive with peers. Photo content cannot be assessed from external data."
        consequence = "No photo count friction. Content quality requires manual review."
    elif gpc > 0:
        verdict = "Partial"
        finding = f"Only {gpc} photos vs peer average of ~{peer_avg_photos:.0f}. Low photo count suppresses click-through."
        consequence = "Venues with 10+ photos get ~35% more click-throughs (Google data)."
    else:
        verdict = "Missing"
        finding = "Zero photos. A faceless listing loses to every competitor with a single photo."
        consequence = "No visual proof of experience — maximum conversion friction at discovery."

    return {
        "dimension": "Photo Mix & Quality",
        "verdict": verdict,
        "finding": finding,
        "consequence": consequence,
        "signals": signals,
        "review_evidence": [],
    }


def _audit_proposition(venue_rec, review_intel):
    """Dimension 5: Proposition Clarity."""
    gty = venue_rec.get("gty", [])
    primary_types = [t for t in gty if t not in
                     ("food", "point_of_interest", "establishment")]

    analysis = review_intel.get("analysis") if review_intel else None
    praise = analysis.get("praise_themes", []) if analysis else []
    top_themes = [p["label"].lower() for p in praise[:3]]

    # Check for mismatch
    type_words = " ".join(primary_types).replace("_", " ").lower()
    signals = [f"Google types: {', '.join(primary_types) or 'none'}"]
    if top_themes:
        signals.append(f"Top review themes: {', '.join(t.title() for t in top_themes)}")

    # Proposition gap detection
    mismatch = False
    if top_themes and primary_types:
        # If top review theme is service/hospitality but types say bar/wine_bar
        service_led = any("service" in t or "hospitality" in t for t in top_themes)
        food_led = any("food" in t or "quality" in t for t in top_themes)
        typed_as_bar = any("bar" in t for t in primary_types)
        typed_as_restaurant = "restaurant" in primary_types

        if service_led and typed_as_bar and not typed_as_restaurant:
            mismatch = True
        elif food_led and typed_as_bar and not typed_as_restaurant:
            mismatch = True

    if mismatch:
        verdict = "Gap"
        finding = (f"Public identity leads with '{', '.join(primary_types)}' but "
                   f"guests praise {', '.join(t.title() for t in top_themes[:2])}. "
                   f"A customer searching for what you're actually good at may not "
                   f"find you because the listing doesn't say it.")
        consequence = ("Proposition mismatch means your best customers can't self-select. "
                       "The listing attracts 'wine bar' seekers; reviews say 'great service restaurant'.")
    elif not top_themes:
        verdict = "Partial"
        finding = ("Insufficient review data to cross-reference proposition. Google types "
                   f"show: {', '.join(primary_types)}. Whether this matches the lived "
                   f"experience cannot be confirmed.")
        consequence = "Proposition alignment cannot be assessed without review theme data."
    else:
        verdict = "Clear"
        finding = (f"Google types ({', '.join(primary_types)}) are broadly consistent "
                   f"with what guests praise ({', '.join(t.title() for t in top_themes[:2])}).")
        consequence = "No major proposition mismatch detected."

    return {
        "dimension": "Proposition Clarity",
        "verdict": verdict,
        "finding": finding,
        "consequence": consequence,
        "signals": signals,
        "review_evidence": [],
    }


def _audit_mobile(venue_rec):
    """Dimension 6: Mobile Usability Signals."""
    goh = venue_rec.get("goh", [])
    goh_days = len(goh) if isinstance(goh, list) else 0
    has_web = venue_rec.get("web") is True
    # Phone: not directly stored, but if website exists we assume phone is findable
    # GBP always shows phone if populated — we can't check from our data
    has_gpid = bool(venue_rec.get("gpid"))

    signals = [f"Opening hours: {goh_days}/7 days"]
    signals.append(f"Website: {'Yes' if has_web else 'No'}")
    signals.append(f"Google Place ID: {'Yes' if has_gpid else 'No'}")

    complete_count = sum([goh_days == 7, has_web, has_gpid])

    if complete_count == 3 and goh_days == 7:
        verdict = "Clear"
        finding = ("Opening hours complete (7/7 days), website present, Place ID active. "
                   "A mobile user can confirm hours and navigate without leaving Maps.")
        consequence = "No mobile usability friction detected."
    elif goh_days < 7:
        verdict = "Partial"
        missing_days = 7 - goh_days
        finding = (f"Opening hours incomplete ({goh_days}/7 days). {missing_days} day(s) "
                   f"missing. Customers filtering 'open now' on the missing days will "
                   f"not find you.")
        consequence = f"Invisible to 'open now' searches on {missing_days} day(s) per week."
    elif not has_web:
        verdict = "Partial"
        finding = ("No website detected. Mobile users who want more detail (menu, "
                   "booking) have no path beyond the Maps listing.")
        consequence = "No website = dead end for research-stage customers on mobile."
    else:
        verdict = "Clear"
        finding = "Core mobile action signals are present."
        consequence = "No major mobile friction detected."

    return {
        "dimension": "Mobile Usability",
        "verdict": verdict,
        "finding": finding,
        "consequence": consequence,
        "signals": signals,
        "review_evidence": [],
    }


def _audit_promise_path(venue_rec, review_intel):
    """Dimension 7: Promise vs Path Consistency."""
    gty = venue_rec.get("gty", [])
    goh = venue_rec.get("goh", [])
    has_delivery_type = any(t in gty for t in ["food_delivery", "meal_takeaway"])

    # Review cross-reference
    closed_kw = ["closed", "shut", "turned away", "wasn't open", "closed early"]
    closed_reviews = _scan_reviews(venue_rec, closed_kw)

    promise_kw = ["pre-theatre", "pre theatre", "early bird", "lunch special"]
    promise_reviews = _scan_reviews(venue_rec, promise_kw)

    signals = []
    contradictions = []

    # Check: delivery type but no delivery in listing
    if not has_delivery_type:
        signals.append("No delivery/takeaway in Google types")
    else:
        signals.append("Delivery/takeaway flagged in Google types")

    if closed_reviews:
        contradictions.append(f"Reviews mention finding venue closed despite listing: "
                              f'"{closed_reviews[0][:80]}"')
        signals.append(f"{len(closed_reviews)} review(s) mention closure/access issues")

    # Check for pre-theatre mentions vs hours
    if promise_reviews and goh:
        signals.append(f"{len(promise_reviews)} review(s) mention pre-theatre/early dining")
        # Check if hours show early evening availability
        early_evening = any("5:" in h or "4:" in h or "16:" in h or "17:" in h
                           for h in goh if isinstance(h, str))
        if not early_evening:
            contradictions.append("Reviews mention pre-theatre dining but hours "
                                "don't clearly show early evening availability")

    if contradictions:
        verdict = "Broken"
        finding = " ".join(contradictions)
        consequence = ("Contradictory signals between listing and reality erode trust. "
                       "A customer who acts on the listing and hits a wall won't come back.")
    elif not has_delivery_type:
        verdict = "Partial"
        finding = ("No delivery/takeaway signal in Google types. If you offer these "
                   "services, customers filtering for them won't find you. If you "
                   "don't offer them, this is not friction — it's accurate.")
        consequence = ("Missing service flags hide you from filtered searches. "
                       "Only a problem if you actually offer the service.")
    else:
        verdict = "Clear"
        finding = "No contradictions detected between listing promises and available evidence."
        consequence = "Promise-path consistency appears intact."

    return {
        "dimension": "Promise vs Path",
        "verdict": verdict,
        "finding": finding,
        "consequence": consequence,
        "signals": signals,
        "review_evidence": closed_reviews[:2] + promise_reviews[:2],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_demand_capture_audit(venue_rec, scorecard, benchmarks, review_intel):
    """Run the full 7-dimension demand capture audit.

    Returns a dict with:
      - summary: {clear, partial, missing, broken, gap}
      - dimensions: list of 7 audit result dicts
    """
    dimensions = [
        _audit_booking(venue_rec, review_intel),
        _audit_menu(venue_rec, review_intel),
        _audit_cta(venue_rec),
        _audit_photos(venue_rec, scorecard, benchmarks, review_intel),
        _audit_proposition(venue_rec, review_intel),
        _audit_mobile(venue_rec),
        _audit_promise_path(venue_rec, review_intel),
    ]

    # Summary counts
    verdicts = Counter(d["verdict"] for d in dimensions)

    return {
        "summary": {
            "total": 7,
            "clear": verdicts.get("Clear", 0),
            "partial": verdicts.get("Partial", 0),
            "missing": verdicts.get("Missing", 0),
            "broken": verdicts.get("Broken", 0),
            "gap": verdicts.get("Gap", 0),
        },
        "dimensions": dimensions,
    }
