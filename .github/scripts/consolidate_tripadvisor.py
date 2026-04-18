#!/usr/bin/env python3
"""
consolidate_tripadvisor.py — Build `stratford_tripadvisor.json` from raw TA data.

Reads every per-venue raw TripAdvisor file under `data/raw/tripadvisor/` and
produces a single side-input file keyed by FHRSID with headline metadata
(`ta`, `trc`, `ta_url`, `ta_present`) plus match audit metadata.

Matching priority:
    1. `fhrsid` field explicitly set in the raw file.
    2. Normalised name + postcode exact match against
       `stratford_establishments.json`.
    3. Normalised name + coordinate distance ≤ 200 m.
    4. Dropped into `_unmatched` block with candidate hints.

Headline score inputs (spec V4 §4):
    ta  — rating, 0-5, float
    trc — review count, int

All other fields (reviews text, cuisines, ranking, recency) stay in the
side file and are NOT merged into `stratford_establishments.json` by
`merge_tripadvisor.py`. Spec V4 §9: review text never feeds the score.

Writes: `stratford_tripadvisor.json`
"""
from __future__ import annotations

import glob
import json
import math
import os
import re
import sys
from datetime import datetime, timezone

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
ESTABLISHMENTS = os.path.join(REPO, "stratford_establishments.json")
RAW_DIR = os.path.join(REPO, "data", "raw", "tripadvisor")
OUTPUT = os.path.join(REPO, "stratford_tripadvisor.json")

COORD_TOLERANCE_M = 200.0


def _normalise_name(name: str) -> str:
    if not name:
        return ""
    n = name.lower()
    n = re.sub(r"[^\w\s]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    # strip common noise tokens
    for token in (" ltd", " limited", " plc", " restaurant", " pub",
                  " cafe", " coffee shop", " bistro", " bar"):
        if n.endswith(token):
            n = n[: -len(token)]
    return n.strip()


def _haversine_m(a_lat, a_lon, b_lat, b_lon) -> float:
    if None in (a_lat, a_lon, b_lat, b_lon):
        return float("inf")
    R = 6_371_000.0
    p1 = math.radians(a_lat)
    p2 = math.radians(b_lat)
    dp = math.radians(b_lat - a_lat)
    dl = math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def _load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _field(d, *names, default=None):
    """Return the first non-empty value of the named fields."""
    for n in names:
        v = d.get(n)
        if v not in (None, "", []):
            return v
    return default


def _extract_headline(raw: dict) -> dict | None:
    """Pull the fields V4 cares about out of any of the known raw shapes."""
    # Accept both legacy (`tripadvisor_*`) and apify (`ta`, `trc`) field names.
    rating = _field(raw, "tripadvisor_rating", "ta", "rating", "averageRating")
    count = _field(raw, "tripadvisor_review_count", "trc",
                   "numberOfReviews", "reviewCount", "reviewsCount")
    url = _field(raw, "tripadvisor_url", "ta_url", "url", "webUrl")
    ranking = _field(raw, "tripadvisor_ranking", "ta_ranking",
                     "ranking", "rankingPosition")
    cuisines = _field(raw, "tripadvisor_cuisines", "ta_cuisines",
                      "cuisines", "cuisine")

    try:
        ta = round(float(rating), 1) if rating is not None else None
    except (TypeError, ValueError):
        ta = None
    try:
        trc = int(count) if count is not None else None
    except (TypeError, ValueError):
        trc = None

    if ta is None and trc is None and not url:
        return None

    out = {}
    if ta is not None:
        out["ta"] = ta
    if trc is not None:
        out["trc"] = trc
    if url:
        out["ta_url"] = url
    if ranking:
        out["ta_ranking"] = str(ranking)
    if cuisines:
        if isinstance(cuisines, list):
            out["ta_cuisines"] = [c.get("name", c) if isinstance(c, dict)
                                   else str(c) for c in cuisines]
        elif isinstance(cuisines, str):
            out["ta_cuisines"] = [c.strip() for c in cuisines.split(",")]
    out["ta_present"] = True
    return out


def _match_fhrsid(raw: dict, establishments: dict) -> tuple[str | None, dict]:
    """Return (fhrsid, match_audit_dict).

    Attempts in order:
      1. raw['fhrsid'] if it exists in the canonical set.
      2. name + postcode exact.
      3. name (normalised) + coord distance.
    """
    audit: dict = {}

    # 1. Explicit FHRSID on the record
    raw_fid = raw.get("fhrsid")
    if raw_fid is not None:
        skey = str(raw_fid)
        if skey in establishments:
            audit["method"] = "fhrsid_field"
            audit["confidence"] = "high"
            return skey, audit

    name = raw.get("name") or raw.get("tripadvisor_name") or ""
    norm = _normalise_name(name)
    postcode = (raw.get("postcode") or raw.get("pc") or "").replace(" ", "").upper()
    lat = raw.get("lat") or raw.get("latitude")
    lon = raw.get("lon") or raw.get("longitude")

    if not norm:
        audit["method"] = "no_name"
        audit["confidence"] = "none"
        return None, audit

    # 2. Name + postcode exact
    if postcode:
        for fid, rec in establishments.items():
            r_pc = (rec.get("pc") or "").replace(" ", "").upper()
            if r_pc and r_pc == postcode and _normalise_name(rec.get("n", "")) == norm:
                audit["method"] = "name_postcode"
                audit["confidence"] = "high"
                return str(fid), audit

    # 3. Name + coord
    best_fid = None
    best_dist = COORD_TOLERANCE_M
    if lat is not None and lon is not None:
        for fid, rec in establishments.items():
            if _normalise_name(rec.get("n", "")) != norm:
                continue
            d = _haversine_m(float(lat), float(lon),
                             rec.get("lat"), rec.get("lon"))
            if d <= best_dist:
                best_dist = d
                best_fid = str(fid)
    if best_fid is not None:
        audit["method"] = "name_coord"
        audit["distance_m"] = round(best_dist, 1)
        audit["confidence"] = "medium"
        return best_fid, audit

    # 4. Name-only exact (last resort; may be ambiguous)
    hits = [str(fid) for fid, rec in establishments.items()
            if _normalise_name(rec.get("n", "")) == norm]
    if len(hits) == 1:
        audit["method"] = "name_exact"
        audit["confidence"] = "medium"
        return hits[0], audit
    if len(hits) > 1:
        audit["method"] = "name_ambiguous"
        audit["confidence"] = "low"
        audit["candidates"] = hits[:5]
        return None, audit

    audit["method"] = "no_match"
    audit["confidence"] = "none"
    audit["name_norm"] = norm
    return None, audit


def _collect_raw_files() -> list[tuple[str, dict]]:
    pairs: list[tuple[str, dict]] = []
    if not os.path.isdir(RAW_DIR):
        return pairs
    for path in sorted(glob.glob(os.path.join(RAW_DIR, "*.json"))):
        try:
            d = _load_json(path)
        except Exception as e:
            print(f"WARN: could not read {path}: {e}", file=sys.stderr)
            continue
        if isinstance(d, list):
            # Older collectors saved a list of reviews with no metadata.
            # Skip — we need per-venue metadata, not review lists.
            continue
        if not isinstance(d, dict):
            continue
        pairs.append((path, d))
    return pairs


def main() -> int:
    if not os.path.exists(ESTABLISHMENTS):
        print(f"ERROR: {ESTABLISHMENTS} not found", file=sys.stderr)
        return 1
    establishments = _load_json(ESTABLISHMENTS)

    raw_pairs = _collect_raw_files()
    consolidated: dict[str, dict] = {}
    unmatched: list[dict] = []

    for path, raw in raw_pairs:
        headline = _extract_headline(raw)
        if headline is None:
            continue
        fhrsid, audit = _match_fhrsid(raw, establishments)
        audit["source_file"] = os.path.relpath(path, REPO)
        audit["collected_at"] = raw.get("collected_at")
        audit["collection_method"] = raw.get("collection_method") or "unknown"

        if fhrsid is None:
            unmatched.append({
                "name": raw.get("name"),
                "match": audit,
                "headline": headline,
            })
            continue

        # If we already have an entry, keep the newer collection
        prev = consolidated.get(fhrsid)
        if prev is not None:
            prev_date = prev.get("match", {}).get("collected_at") or ""
            if str(audit.get("collected_at") or "") < prev_date:
                continue

        entry = dict(headline)
        entry["match"] = audit
        consolidated[fhrsid] = entry

    out = {
        "_meta": {
            "generated_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
            "source_dir": os.path.relpath(RAW_DIR, REPO),
            "raw_files_found": len(raw_pairs),
            "matched": len(consolidated),
            "unmatched": len(unmatched),
            "total_establishments": len(establishments),
        },
        "_unmatched": unmatched,
    }
    # flatten matched entries at the top level (keyed by fhrsid as string)
    for k, v in consolidated.items():
        out[k] = v

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"Wrote {OUTPUT}")
    print(f"  raw files found:   {len(raw_pairs)}")
    print(f"  matched to fhrsid: {len(consolidated)}")
    print(f"  unmatched:         {len(unmatched)}")
    print(f"  total venues:      {len(establishments)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
