#!/usr/bin/env python3
"""
commercial_readiness_coverage.py — Per-signal coverage for V4 Commercial Readiness.

Produces `stratford_commercial_readiness_coverage.json` reporting:
  - % with website (web)
  - % with menu online (from establishments or menus side file)
  - % with opening hours (goh non-empty)
  - % with phone
  - % with booking / reservation path (reservable, booking_url, reservation_url, tel)
  - resulting Commercial Readiness component distribution

Only reads existing files; does not touch Google/TA APIs.
"""
from __future__ import annotations

import json
import os
import statistics
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
EST = os.path.join(REPO, "stratford_establishments.json")
MENUS = os.path.join(REPO, "stratford_menus.json")
V4 = os.path.join(REPO, "stratford_rcs_v4_scores.json")
OUT = os.path.join(REPO, "stratford_commercial_readiness_coverage.json")


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _pct(num, denom):
    return round(100.0 * num / denom, 1) if denom else 0.0


def main() -> int:
    if not os.path.exists(EST):
        print(f"ERROR: {EST} not found", file=sys.stderr)
        return 1
    establishments = _load(EST)
    menus = _load(MENUS) if os.path.exists(MENUS) else {}
    v4 = _load(V4) if os.path.exists(V4) else {}

    n = len(establishments)

    # Per-signal counts
    has_web = sum(1 for r in establishments.values() if r.get("web"))
    has_menu = sum(
        1 for k, r in establishments.items()
        if (menus.get(k) or {}).get("has_menu_online")
        or r.get("has_menu_online")
    )
    has_goh = sum(1 for r in establishments.values() if r.get("goh"))
    has_phone = sum(
        1 for r in establishments.values()
        if r.get("phone") or r.get("tel")
    )
    has_reservable = sum(
        1 for r in establishments.values() if r.get("reservable")
    )
    has_booking_url = sum(
        1 for r in establishments.values()
        if r.get("booking_url") or r.get("reservation_url")
    )
    has_contact_path = sum(
        1 for r in establishments.values()
        if r.get("phone") or r.get("tel") or r.get("booking_url")
        or r.get("reservation_url") or r.get("reservable")
    )

    # Observed vs inferred website. Currently `web_url` only gets set when
    # observed from Google API.
    web_observed = sum(1 for r in establishments.values() if r.get("web_url"))
    web_inferred = has_web - web_observed

    # Business status (closure flag for V4 §7.4)
    has_business_status = sum(
        1 for r in establishments.values() if r.get("business_status")
    )

    # Commercial Readiness component distribution from V4 outputs
    cr_scores = []
    cr_unavailable = 0
    for rec in v4.values():
        c = (rec.get("components") or {}).get("commercial_readiness") or {}
        if c.get("available"):
            cr_scores.append(c.get("score"))
        else:
            cr_unavailable += 1

    cr_buckets = {"0.00": 0, "2.50": 0, "5.00": 0, "7.50": 0, "10.00": 0,
                  "other": 0}
    for s in cr_scores:
        key = f"{s:.2f}"
        if key in cr_buckets:
            cr_buckets[key] += 1
        else:
            cr_buckets["other"] += 1

    stats = {
        "n": len(cr_scores),
        "mean": round(statistics.mean(cr_scores), 3) if cr_scores else None,
        "median": round(statistics.median(cr_scores), 3) if cr_scores else None,
        "stdev": round(statistics.pstdev(cr_scores), 3) if len(cr_scores) > 1
        else 0,
        "min": round(min(cr_scores), 3) if cr_scores else None,
        "max": round(max(cr_scores), 3) if cr_scores else None,
    }

    # Before/after hardcoded from the previous calibration snapshot
    baseline = {
        "source": "pre-enrichment baseline snapshot",
        "web_pct": 1.0,
        "menu_pct": 75.2,
        "hours_pct": 81.9,
        "phone_pct": 0.0,
        "booking_contact_pct": 0.0,
        "cr_stats": {
            "mean": 5.000,
            "median": 5.000,
            "max": 7.500,
            "stdev": 1.050,
        },
        "note": ("CR was structurally capped near 5.0 because only menu + "
                 "hours landed for most venues; web/phone/reservable were "
                 "all at 0-1% coverage."),
    }

    report = {
        "generated_by": "commercial_readiness_coverage.py",
        "total_establishments": n,
        "signals": {
            "web_any": {"count": has_web, "pct": _pct(has_web, n),
                         "observed_from_google": web_observed,
                         "inferred_from_heuristic": web_inferred},
            "menu_online": {"count": has_menu, "pct": _pct(has_menu, n)},
            "opening_hours": {"count": has_goh, "pct": _pct(has_goh, n)},
            "phone": {"count": has_phone, "pct": _pct(has_phone, n)},
            "reservable": {"count": has_reservable,
                            "pct": _pct(has_reservable, n)},
            "booking_url": {"count": has_booking_url,
                             "pct": _pct(has_booking_url, n)},
            "any_contact_path": {"count": has_contact_path,
                                  "pct": _pct(has_contact_path, n)},
            "business_status": {"count": has_business_status,
                                 "pct": _pct(has_business_status, n)},
        },
        "commercial_readiness_distribution": {
            "buckets": cr_buckets,
            "stats": stats,
            "unavailable_count": cr_unavailable,
        },
        "baseline_before_enrichment": baseline,
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Wrote {OUT}")
    print(f"  n={n}  web={has_web} ({_pct(has_web, n)}%)  "
          f"menu={has_menu} ({_pct(has_menu, n)}%)  "
          f"hours={has_goh} ({_pct(has_goh, n)}%)")
    print(f"  phone={has_phone} ({_pct(has_phone, n)}%)  "
          f"reservable={has_reservable} ({_pct(has_reservable, n)}%)  "
          f"booking_url={has_booking_url} "
          f"({_pct(has_booking_url, n)}%)")
    print(f"  CR: n={stats['n']} mean={stats['mean']} "
          f"median={stats['median']} max={stats['max']} "
          f"stdev={stats['stdev']}")
    print(f"  CR buckets: {cr_buckets}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
