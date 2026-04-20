"""Build assets/rankings/stratford-on-avon.json from the V4 scoring output.

Reads:
  stratford_rcs_v4_scores.json   (RCS V4 per-venue output)
  stratford_establishments.json  (Firebase RTDB snapshot with postcode + category)

Writes:
  assets/rankings/stratford-on-avon.json  (all rankable venues, ranked desc)
  assets/rankings/index.json              (update total_venues for Stratford)

This replaces the manually-curated top-10 JSON with the full V4 rankable set
so the /rankings page can surface every scored venue we have for the market.
"""
from __future__ import annotations
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
V4 = REPO / "stratford_rcs_v4_scores.json"
EST = REPO / "stratford_establishments.json"
OUT = REPO / "assets" / "rankings" / "stratford-on-avon.json"
IDX = REPO / "assets" / "rankings" / "index.json"

# Band thresholds — RCS V4, matching CLAUDE.md
BANDS = [
    (8.0, "Excellent", "excellent"),
    (6.5, "Good", "good"),
    (5.0, "Generally Satisfactory", "satisfactory"),
    (3.5, "Improvement Necessary", "improvement"),
    (2.0, "Major Improvement", "major"),
    (0.0, "Urgent Improvement", "urgent"),
]


def band_for(score: float) -> tuple[str, str]:
    for floor, name, cls in BANDS:
        if score >= floor:
            return name, cls
    return BANDS[-1][1], BANDS[-1][2]


# In the Stratford snapshot every FSA type code is "1" (Restaurant/Cafe/Canteen),
# so we derive category from Google types (`gty`) — more specific.
GTY_TO_CAT = [
    # (token substring, display category) — checked in order; first match wins
    ("pub", "Pub / Bar"),
    ("bar", "Pub / Bar"),
    ("beer_garden", "Pub / Bar"),
    ("cafe", "Cafe / Coffee Shop"),
    ("coffee_shop", "Cafe / Coffee Shop"),
    ("tea_house", "Cafe / Coffee Shop"),
    ("bakery", "Bakery"),
    ("hotel", "Hotel / Accommodation"),
    ("lodging", "Hotel / Accommodation"),
    ("inn", "Hotel / Accommodation"),
    ("meal_takeaway", "Takeaway / Delivery"),
    ("meal_delivery", "Takeaway / Delivery"),
    ("fast_food", "Takeaway / Delivery"),
    ("restaurant", "Restaurant (General)"),
    ("food", "Restaurant (General)"),
]


def categorise(est_row: dict | None) -> str:
    if not est_row:
        return "Restaurant (General)"
    gty = est_row.get("gty") or []
    joined = " ".join(str(t) for t in gty).lower()
    for tok, cat in GTY_TO_CAT:
        if tok in joined:
            return cat
    return "Restaurant (General)"


def convergence_for(entry: dict) -> str:
    """Infer convergence from V4 customer_validation platforms."""
    cv = entry.get("components", {}).get("customer_validation", {})
    plats = cv.get("platforms") or {}
    ratings = []
    for name, p in plats.items():
        if isinstance(p, dict) and p.get("raw") is not None:
            ratings.append(float(p["raw"]))
    if len(ratings) < 2:
        return "neutral"
    # Normalise each rating to 0-1 scale assuming 5-point platforms (Google/TA/OT all 1-5).
    norm = [r / 5.0 for r in ratings]
    span = max(norm) - min(norm)
    if span <= 0.10:
        return "converged"
    if span <= 0.20:
        return "neutral"
    if span <= 0.30:
        return "mild"
    return "diverged"


def build() -> None:
    v4 = json.loads(V4.read_text())
    est = json.loads(EST.read_text())

    rankable = [
        v for v in v4.values()
        if v.get("league_table_eligible") and v.get("rcs_v4_final") is not None
    ]
    rankable.sort(key=lambda v: v["rcs_v4_final"], reverse=True)

    # Tiebreaker loop — rank field, guarantee unique ranks.
    venues = []
    for i, v in enumerate(rankable, start=1):
        fhrsid = v.get("fhrsid")
        e = est.get(str(fhrsid), {}) if isinstance(est, dict) else {}
        score = round(float(v["rcs_v4_final"]), 3)
        band_name, band_cls = band_for(score)
        venues.append({
            "rank": i,
            "name": v.get("name") or e.get("n") or "Unknown",
            "postcode": e.get("pc", ""),
            "category": categorise(e),
            "rcs_final": score,
            "rcs_band": band_name,
            "band_class": band_cls,
            "convergence": convergence_for(v),
            "movement": "same",       # no historical run to diff against yet
            "movement_delta": 0,
            "confidence_class": v.get("confidence_class", ""),
        })

    total_venues = len(venues)
    top_n = min(10, total_venues)
    others_count = max(0, total_venues - top_n)
    top_score = venues[0]["rcs_final"] if venues else None

    # Preserve last_updated from existing file if present, else use the V4 audit timestamp
    last_updated = None
    if OUT.exists():
        existing = json.loads(OUT.read_text())
        last_updated = existing.get("last_updated")
    if not last_updated:
        # Pull the most recent audit.computed_at from V4
        stamps = [v.get("audit", {}).get("computed_at") for v in v4.values() if v.get("audit")]
        stamps = [s for s in stamps if s]
        if stamps:
            last_updated = max(stamps)[:10]

    payload = {
        "la_name": "Stratford-on-Avon",
        "display_name": "Stratford-upon-Avon",
        "slug": "stratford-on-avon",
        "total_venues": total_venues,
        "top_n": top_n,
        "others_count": others_count,
        "last_updated": last_updated or "2026-04-12",
        "venues": venues,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {OUT.relative_to(REPO)}: {total_venues} venues, top={top_score}")

    # Update index.json
    idx = json.loads(IDX.read_text())
    for entry in idx.get("available", []):
        if entry.get("slug") == "stratford-on-avon":
            entry["total_venues"] = total_venues
            if top_score is not None:
                entry["top_score"] = top_score
    if last_updated:
        idx["last_updated"] = last_updated
    IDX.write_text(json.dumps(idx, indent=2) + "\n")
    print(f"wrote {IDX.relative_to(REPO)}: total_venues={total_venues}")


if __name__ == "__main__":
    build()
