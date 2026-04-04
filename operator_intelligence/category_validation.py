"""
operator_intelligence/category_validation.py — Multi-Signal Category Resolution

Triangulates venue category across multiple public signals rather than
relying solely on Google Place Types. Produces a resolved category with
confidence level, evidence summary, and alternatives considered.

Also provides peer set transparency: justification for each peer and
sensitivity analysis showing what changes if category changes.
"""

import re
from collections import Counter


# ---------------------------------------------------------------------------
# Category-indicative terms in review text
# ---------------------------------------------------------------------------

_REVIEW_CATEGORY_TERMS = {
    "restaurant": ["restaurant", "dining", "dine", "dined"],
    "pub": ["pub", "boozer", "local"],
    "wine_bar": ["wine bar", "wine list"],
    "cafe": ["café", "cafe", "coffee shop"],
    "bistro": ["bistro", "brasserie"],
    "gastropub": ["gastropub", "gastro pub", "gastro-pub"],
    "fine_dining": ["fine dining", "tasting menu", "michelin"],
    "bar": ["cocktail"],  # "bar" handled separately to avoid "wine bar" double-count
}

# Service model indicators
_SERVICE_INDICATORS = {
    "table_service": ["waiter", "waitress", "server", "served by", "our table",
                      "seated us", "brought us", "took our order"],
    "counter_service": ["ordered at the counter", "counter service", "self-service"],
    "reservation": ["booked", "reservation", "pre-booked", "pre booked",
                    "booking", "reserved"],
    "set_menu": ["set menu", "prix fixe", "tasting menu", "courses",
                 "pre-theatre", "pre theatre"],
    "named_staff": ["charlie", "jason", "our waitress", "our waiter"],
}


def _scan_review_language(venue_rec):
    """Count category-indicative terms and service indicators in reviews."""
    cat_counts = Counter()
    service_counts = Counter()

    for field in ["g_reviews", "ta_reviews"]:
        for rev in venue_rec.get(field, []):
            text = (rev.get("text") or "").lower()
            if not text:
                continue
            for cat, terms in _REVIEW_CATEGORY_TERMS.items():
                for term in terms:
                    if term in text:
                        cat_counts[cat] += 1
                        break  # one match per category per review
            # Handle "bar" separately: match standalone "bar" but not
            # "wine bar", "snack bar", "minibar" etc.
            if re.search(r'(?<!wine )(?<!snack )(?<!mini)\bbar\b', text):
                if "wine bar" not in text and "snack bar" not in text:
                    cat_counts["bar"] = cat_counts.get("bar", 0) + 1
            for indicator, terms in _SERVICE_INDICATORS.items():
                for term in terms:
                    if term in text:
                        service_counts[indicator] += 1
                        break

    return dict(cat_counts), dict(service_counts)


# ---------------------------------------------------------------------------
# Multi-signal resolution
# ---------------------------------------------------------------------------

def resolve_category(venue_rec, review_intel=None):
    """Resolve venue category from multiple signals.

    Returns dict with:
      primary: str — resolved category name
      confidence: str — "high" / "medium" / "low"
      evidence: list of {source, signal, weight} dicts
      alternatives: list of {category, reason_rejected} dicts
      google_raw: list of Google types
      review_language: dict of category term counts
      service_model: dict of service indicator counts
    """
    name = (venue_rec.get("n") or "").strip()
    gty = venue_rec.get("gty", [])
    gpl = venue_rec.get("gpl")
    ta_cuisines = venue_rec.get("ta_cuisines")

    # Gather evidence
    evidence = []
    signals = {}

    # 1. Google Place Types
    primary_types = [t for t in gty if t not in
                     ("food", "point_of_interest", "establishment")]
    if primary_types:
        evidence.append({
            "source": "Google Place Types",
            "signal": ", ".join(primary_types),
            "weight": "Primary",
        })
        signals["google"] = set(primary_types)

    # 2. TripAdvisor cuisine/type
    if ta_cuisines:
        evidence.append({
            "source": "TripAdvisor Cuisines",
            "signal": ", ".join(ta_cuisines) if isinstance(ta_cuisines, list) else str(ta_cuisines),
            "weight": "Corroborating",
        })

    # 3. Review language analysis
    cat_counts, service_counts = _scan_review_language(venue_rec)
    if cat_counts:
        top_terms = sorted(cat_counts.items(), key=lambda x: -x[1])
        term_strs = [f'"{t}" ({c}x)' for t, c in top_terms]
        evidence.append({
            "source": "Review Language",
            "signal": ", ".join(term_strs),
            "weight": "Strong" if sum(cat_counts.values()) >= 5 else "Supportive",
        })

    # 4. Service model from reviews
    if service_counts:
        indicators = [f"{k.replace('_', ' ')} ({v}x)" for k, v in service_counts.items()]
        evidence.append({
            "source": "Service Model",
            "signal": ", ".join(indicators),
            "weight": "Supportive",
        })

    # 5. Price level
    if gpl is not None:
        price_map = {1: "Budget", 2: "Casual dining", 3: "Mid-range dining", 4: "Fine dining"}
        evidence.append({
            "source": "Price Level",
            "signal": f"{'£' * int(gpl)} ({gpl}/4) — {price_map.get(gpl, 'Unknown')}",
            "weight": "Supportive",
        })

    # 6. Name analysis
    name_lower = name.lower()
    name_cat = None
    for cat, terms in _REVIEW_CATEGORY_TERMS.items():
        for term in terms:
            if term in name_lower:
                name_cat = cat
                break
        if name_cat:
            break
    if name_cat:
        evidence.append({
            "source": "Name",
            "signal": f'"{name}" contains "{name_cat.replace("_", " ")}"',
            "weight": "Supportive",
        })

    # --- Resolution logic ---
    google_cats = set()
    for t in primary_types:
        if "restaurant" in t:
            google_cats.add("restaurant")
        elif t in ("pub", "gastropub", "brewpub", "beer_garden"):
            google_cats.add("pub")
        elif t in ("bar", "wine_bar", "cocktail_bar", "lounge_bar"):
            google_cats.add("bar")
        elif t in ("cafe", "coffee_shop"):
            google_cats.add("cafe")

    _cat_counter = Counter(cat_counts)
    review_dominant = _cat_counter.most_common(1)[0][0] if _cat_counter else None
    review_dominant_count = _cat_counter.most_common(1)[0][1] if _cat_counter else 0

    has_table_service = service_counts.get("table_service", 0) >= 2
    has_reservations = service_counts.get("reservation", 0) >= 2
    has_set_menu = service_counts.get("set_menu", 0) >= 1
    restaurant_service = has_table_service or has_reservations or has_set_menu

    # Decision tree
    alternatives = []

    # Case: Google says bar/wine_bar but reviews + service say restaurant
    if ("bar" in google_cats or "wine_bar" in set(primary_types)) and \
       "restaurant" in google_cats and \
       review_dominant == "restaurant" and review_dominant_count >= 3 and \
       restaurant_service:
        primary = "Wine-led Dining / Restaurant-Bar"
        confidence = "medium"
        alternatives.append({
            "category": "Pub / Bar",
            "reason": "Google types include 'bar'/'wine_bar', but review language "
                      f"overwhelmingly says 'restaurant' ({review_dominant_count}x) and "
                      "service model is restaurant-grade (table service, reservations).",
        })
        if gpl and gpl >= 3:
            alternatives.append({
                "category": "Fine Dining",
                "reason": f"Price level {gpl}/4 could suggest fine dining, but review "
                          "language doesn't use fine dining vocabulary.",
            })

    # Case: clearly a pub
    elif "pub" in google_cats and review_dominant in ("pub", None):
        primary = "Pub / Bar"
        confidence = "high" if review_dominant == "pub" else "medium"

    # Case: clearly a restaurant
    elif "restaurant" in google_cats and "bar" not in google_cats and "pub" not in google_cats:
        primary = "Restaurant (General)"
        confidence = "high" if review_dominant == "restaurant" else "medium"

    # Case: bar without restaurant signal
    elif ("bar" in google_cats or "wine_bar" in set(primary_types)) and \
         "restaurant" not in google_cats:
        if restaurant_service and review_dominant == "restaurant":
            primary = "Wine-led Dining / Restaurant-Bar"
            confidence = "low"
            alternatives.append({
                "category": "Pub / Bar",
                "reason": "Google doesn't list 'restaurant' type, but review language "
                          "and service model suggest dining venue.",
            })
        else:
            primary = "Pub / Bar"
            confidence = "medium"

    # Case: cafe
    elif "cafe" in google_cats:
        primary = "Cafe / Coffee Shop"
        confidence = "high" if review_dominant in ("cafe", None) else "medium"

    # Fallback: use Google's primary type
    elif primary_types:
        # Try to map the first meaningful type
        first = primary_types[0].replace("_", " ").title()
        primary = f"{first}"
        confidence = "low"
    else:
        primary = "Uncategorised"
        confidence = "low"

    return {
        "primary": primary,
        "confidence": confidence,
        "evidence": evidence,
        "alternatives": alternatives,
        "google_raw": primary_types,
        "review_language": cat_counts,
        "service_model": service_counts,
    }


# ---------------------------------------------------------------------------
# Peer set transparency
# ---------------------------------------------------------------------------

def generate_peer_justifications(venue_card, venue_rec, top_peers, all_data):
    """Generate a brief justification for each peer in the local set."""
    from operator_intelligence.peer_benchmarking import _haversine_miles

    justifications = []
    v_lat = venue_card.get("lat")
    v_lon = venue_card.get("lon")
    v_gpl = venue_rec.get("gpl")

    for peer in top_peers:
        fid = peer.get("fhrsid", "")
        p_rec = all_data.get(fid, {}) if all_data else {}
        p_lat = p_rec.get("lat") or peer.get("lat")
        p_lon = p_rec.get("lon") or peer.get("lon")

        dist = None
        if v_lat and v_lon and p_lat and p_lon:
            dist = round(_haversine_miles(v_lat, v_lon, p_lat, p_lon), 1)

        p_gpl = p_rec.get("gpl")
        p_gty = p_rec.get("gty", [])
        p_name = peer.get("name", "Unknown")
        p_overall = peer.get("overall", 0)

        # Determine comparability
        notes = []
        is_hotel = any("hotel" in t or "lodging" in t for t in p_gty)
        is_takeaway = any("takeaway" in t or "delivery" in t for t in p_gty)
        same_price = p_gpl == v_gpl if p_gpl and v_gpl else None

        if is_hotel:
            notes.append("Hotel restaurant — different occasion type, may not compete for walk-in trade")
        elif is_takeaway:
            notes.append("Takeaway-focused — different service model")
        else:
            cat_desc = "pub dining" if any(t in p_gty for t in ["pub", "bar"]) else "dining"
            notes.append(f"{cat_desc.title()} with {'similar' if same_price else 'comparable'} price band")

        if dist is not None:
            notes.append(f"{dist} miles away")

        validity = "valid local competitor"
        if is_hotel:
            validity = "marginal comparator"
        elif is_takeaway:
            validity = "weak comparator"

        justifications.append({
            "name": p_name,
            "overall": p_overall,
            "distance": dist,
            "notes": "; ".join(notes),
            "validity": validity,
        })

    return justifications


def run_sensitivity_analysis(venue_card, all_cards, current_category, alternative_category):
    """What changes if venue is reclassified?

    Returns dict with alternative peer set stats and position delta.
    """
    from operator_intelligence.peer_benchmarking import _haversine_miles

    v_lat = venue_card.get("lat")
    v_lon = venue_card.get("lon")
    v_overall = venue_card.get("overall") or 0

    # Current peer set
    current_peers = [
        c for fid, c in all_cards.items()
        if str(fid) != str(venue_card.get("fhrsid"))
        and c.get("category") == current_category
        and c.get("lat") and v_lat
        and _haversine_miles(v_lat, v_lon, c["lat"], c["lon"]) <= 5
    ]

    # Alternative peer set
    alt_peers = [
        c for fid, c in all_cards.items()
        if str(fid) != str(venue_card.get("fhrsid"))
        and c.get("category") == alternative_category
        and c.get("lat") and v_lat
        and _haversine_miles(v_lat, v_lon, c["lat"], c["lon"]) <= 5
    ]

    def _position(peers):
        if not peers:
            return {"count": 0, "rank": None, "peer_avg": None, "peer_top": None}
        scores = sorted([p["overall"] for p in peers if p.get("overall")], reverse=True)
        all_s = sorted(scores + [v_overall], reverse=True)
        rank = all_s.index(v_overall) + 1
        return {
            "count": len(peers),
            "rank": rank,
            "of": len(peers) + 1,
            "peer_avg": round(sum(scores) / len(scores), 1) if scores else None,
            "peer_top": round(max(scores), 1) if scores else None,
            "peer_names": [p["name"] for p in sorted(peers, key=lambda x: -x.get("overall", 0))[:5]],
        }

    current_pos = _position(current_peers)
    alt_pos = _position(alt_peers)

    return {
        "current_category": current_category,
        "current_position": current_pos,
        "alternative_category": alternative_category,
        "alternative_position": alt_pos,
    }
