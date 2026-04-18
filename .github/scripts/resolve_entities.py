#!/usr/bin/env python3
"""
resolve_entities.py — Entity resolution for the Stratford trial.

Applies three layers of entity-identity cleanup to
`stratford_establishments.json`:

  1. Parse "Also Trading As" patterns out of the FSA `n` / `a` fields and
     attach `public_name` + `trading_names` so a consumer-facing name
     search can reach the right FHRSID.
  2. Apply a manual alias table (`data/entity_aliases.json`) for venues
     where automatic parsing is not enough or to record human review.
  3. Auto-detect duplicate Google Place IDs (one `gpid` shared by
     multiple FHRS records) and flag each such record
     `entity_ambiguous = true` (spec V4 §8.4).

Also attaches `entity_match` hints that V4's `assess_entity_match()`
consumes. Hint precedence:
   - `entity_match_override` on the alias entry wins.
   - Otherwise a manually-aliased record stays at `confirmed` (unless
     ambiguous, which trumps).
   - Records sharing a `gpid` get `entity_ambiguous = true`.

Writes `stratford_entity_resolution_report.json` summarising:
   - how many records have `public_name` / `trading_names`
   - ambiguous-gpid groups
   - which `known_unresolved` venues remain not-in-slice
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
EST = os.path.join(REPO, "stratford_establishments.json")
ALIASES = os.path.join(REPO, "data", "entity_aliases.json")
REPORT = os.path.join(REPO, "stratford_entity_resolution_report.json")


TRADE_AS_RE = re.compile(
    r"^(?P<public>.+?)\s+(?:also\s+trading\s+as|trading\s+as|t/a)\s+"
    r"(?P<legal>.+)$",
    re.IGNORECASE,
)


def _strip_legal_suffix(name: str) -> str:
    """Remove trailing ' Ltd' / ' Limited' / ' Plc' etc. for display."""
    return re.sub(r"\s+(ltd|limited|plc|llp|corp|incorporated|inc)\s*$",
                  "", name, flags=re.IGNORECASE).strip()


def _normalise_key(name: str) -> str:
    """Conservative name key for dedup/search."""
    n = (name or "").lower()
    n = re.sub(r"[^\w\s]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    for tail in (" ltd", " limited", " plc", " llp", " restaurant",
                 " pub", " cafe", " bistro", " bar", " restaurant and bar"):
        if n.endswith(tail):
            n = n[: -len(tail)].strip()
    if n.startswith("the "):
        n = n[4:]
    return n


def _parse_trade_as(name: str) -> tuple[str, list[str]] | None:
    """Pull public + legal names out of an 'Also Trading As' FSA name.

    Returns (public_name, trading_names) or None if the pattern doesn't match.
    """
    m = TRADE_AS_RE.match((name or "").strip())
    if not m:
        return None
    public = _strip_legal_suffix(m.group("public").strip())
    legal = m.group("legal").strip()
    trading = []
    if legal and legal.lower() != public.lower():
        trading.append(legal)
    return public, trading


def _apply_aliases(establishments: dict, aliases: dict) -> dict:
    """Apply manual alias entries to records. Returns stats dict."""
    applied = 0
    missing = []
    conflicts = []
    for entry in aliases.get("aliases", []):
        fid = str(entry.get("fhrsid") or "")
        if not fid or fid not in establishments:
            missing.append(fid)
            continue
        rec = establishments[fid]
        pub = entry.get("public_name")
        if pub:
            rec["public_name"] = pub
        # Merge trading_names, avoiding duplicates
        existing_tn = rec.get("trading_names") or []
        if not isinstance(existing_tn, list):
            existing_tn = []
        for tn in entry.get("trading_names", []) or []:
            if tn and tn not in existing_tn:
                existing_tn.append(tn)
        if entry.get("legal_name") and \
                entry["legal_name"] not in existing_tn:
            existing_tn.append(entry["legal_name"])
        if existing_tn:
            rec["trading_names"] = existing_tn
        rec["alias_source"] = entry.get("source", "manual")
        rec["alias_confidence"] = entry.get("confidence", "high")
        # entity_match override
        override = entry.get("entity_match_override")
        if override:
            rec["entity_match"] = override
        applied += 1
    return {"applied": applied, "missing_fhrsids": missing,
            "conflicts": conflicts}


def _auto_parse_trade_as(establishments: dict) -> int:
    """For records with 'Also Trading As' in name, derive public_name /
    trading_names if not already set."""
    count = 0
    for rec in establishments.values():
        if rec.get("public_name"):
            continue  # manual alias already set
        name = rec.get("n") or ""
        parsed = _parse_trade_as(name)
        if parsed is None:
            continue
        public, trading = parsed
        rec["public_name"] = public
        existing_tn = rec.get("trading_names") or []
        for tn in trading:
            if tn and tn not in existing_tn:
                existing_tn.append(tn)
        if existing_tn:
            rec["trading_names"] = existing_tn
        rec["alias_source"] = "auto_parse_trading_as"
        rec["alias_confidence"] = "medium"
        count += 1
    return count


def _flag_duplicate_gpids(establishments: dict, aliases: dict) -> dict:
    """Flag `entity_ambiguous = true` on any set of records sharing a gpid.
    Also compares against aliases['ambiguous_gpids'] for any human-reviewed
    groupings (which we respect even if no automatic duplicate is seen).

    When a manual alias entry carries a `disambiguation_type` /
    `reason_for_operator` / `primary_fhrsid` / `resolution_path`, the
    resolver propagates these onto each flagged record (as
    `disambiguation_type`, `disambiguation_reason`, etc.) so the V4
    report can surface a specific operator-facing explanation rather
    than a generic "ambiguous" label. When `primary_fhrsid` is set,
    the non-primary records in that group are additionally marked
    `fsa_closed = true` — the manual reviewer's assertion that the
    non-primary is the retired side of a rebrand / relocation. Default
    (no `primary_fhrsid`) keeps all records in the group ambiguous.
    """
    by_gpid: dict[str, list[str]] = {}
    for fid, rec in establishments.items():
        g = rec.get("gpid")
        if g:
            by_gpid.setdefault(g, []).append(str(fid))

    auto_groups = []
    auto_group_fhrsids: set[str] = set()
    for g, fids in by_gpid.items():
        if len(fids) > 1:
            auto_groups.append({"gpid": g, "fhrsids": fids})
            for fid in fids:
                establishments[fid]["entity_ambiguous"] = True
                auto_group_fhrsids.add(fid)

    # Respect manual ambiguity declarations + propagate disambiguation
    # context onto each flagged record.
    manual_flagged = 0
    retired_flagged = 0
    for entry in aliases.get("ambiguous_gpids", []) or []:
        fhrsids = [str(f) for f in (entry.get("fhrsids") or [])]
        primary = entry.get("primary_fhrsid")
        if primary:
            primary = str(primary)
        for fid in fhrsids:
            if fid not in establishments:
                continue
            rec = establishments[fid]
            if not rec.get("entity_ambiguous"):
                rec["entity_ambiguous"] = True
                manual_flagged += 1
            # Attach disambiguation context
            if entry.get("disambiguation_type"):
                rec["disambiguation_type"] = entry["disambiguation_type"]
            if entry.get("reason_for_operator"):
                rec["disambiguation_reason"] = entry["reason_for_operator"]
            if entry.get("resolution_path"):
                rec["disambiguation_resolution_path"] = \
                    entry["resolution_path"]
            if entry.get("site"):
                rec["disambiguation_site"] = entry["site"]
            # Primary / retired handling for rebrand_or_relocation
            if primary and fid != primary:
                rec["fsa_closed"] = True
                rec["disambiguation_primary_fhrsid"] = primary
                retired_flagged += 1
            elif primary and fid == primary:
                # Primary record — no longer ambiguous from our side.
                rec["entity_ambiguous"] = False
                rec["disambiguation_primary_fhrsid"] = primary

    # Attach disambiguation context onto the auto_groups too so the
    # resolver-report consumer (the V4 report generator) gets the
    # richer context without having to re-read the alias table.
    alias_by_gpid: dict[tuple[str, ...], dict] = {}
    for entry in aliases.get("ambiguous_gpids", []) or []:
        fhrsids_tuple = tuple(sorted(str(f) for f in entry.get("fhrsids", [])))
        alias_by_gpid[fhrsids_tuple] = entry
    for grp in auto_groups:
        key = tuple(sorted(grp.get("fhrsids", [])))
        alias_match = alias_by_gpid.get(key)
        if alias_match:
            # Copy names in alias-entry order (preserves the human-
            # curated ordering) and the disambiguation fields.
            grp["names"] = alias_match.get("names") or []
            for f in (
                "disambiguation_type", "reason_for_operator",
                "resolution_path", "site", "primary_fhrsid",
            ):
                if f in alias_match:
                    grp[f] = alias_match[f]

    return {
        "auto_groups": auto_groups,
        "manual_groups": aliases.get("ambiguous_gpids", []),
        "manual_only_flagged": manual_flagged,
        "retired_flagged": retired_flagged,
    }


def _summarise_match_classes(establishments: dict) -> dict:
    """Counts based on the same logic V4 uses in assess_entity_match()."""
    summary = {"confirmed": 0, "probable": 0, "ambiguous": 0, "none": 0}
    for rec in establishments.values():
        override = rec.get("entity_match")
        if isinstance(override, str) and override in summary:
            summary[override] += 1
            continue
        has_fhrs = rec.get("id") is not None
        has_gpid = bool(rec.get("gpid"))
        if rec.get("entity_ambiguous"):
            summary["ambiguous"] += 1
        elif has_fhrs and has_gpid:
            summary["confirmed"] += 1
        elif has_fhrs or has_gpid:
            summary["probable"] += 1
        else:
            summary["none"] += 1
    return summary


def main() -> int:
    if not os.path.exists(EST):
        print(f"ERROR: {EST} not found", file=sys.stderr)
        return 1
    if not os.path.exists(ALIASES):
        print(f"ERROR: {ALIASES} not found", file=sys.stderr)
        return 1

    with open(EST, encoding="utf-8") as f:
        establishments = json.load(f)
    with open(ALIASES, encoding="utf-8") as f:
        aliases = json.load(f)

    # 1. Manual alias table
    alias_stats = _apply_aliases(establishments, aliases)

    # 2. Auto-parse 'Also Trading As' patterns
    auto_parsed = _auto_parse_trade_as(establishments)

    # 3. Duplicate-gpid ambiguity
    ambig_stats = _flag_duplicate_gpids(establishments, aliases)

    # Save back
    with open(EST, "w", encoding="utf-8") as f:
        json.dump(establishments, f, indent=2, ensure_ascii=False)

    # Build a search index over public_name + legal name + trading_names
    # to demonstrate coverage of the named-miss list
    search_index = {}
    for fid, rec in establishments.items():
        names = [rec.get("n"), rec.get("public_name")]
        names.extend(rec.get("trading_names") or [])
        for n in names:
            if not n:
                continue
            k = _normalise_key(n)
            if k:
                search_index.setdefault(k, []).append(str(fid))

    def _resolve_query(q: str):
        k = _normalise_key(q)
        hits = list(dict.fromkeys(search_index.get(k, [])))
        if hits:
            return hits
        # fallback: substring over keys
        substring_hits = []
        for key, fids in search_index.items():
            if k in key or key in k:
                for h in fids:
                    if h not in substring_hits:
                        substring_hits.append(h)
        return substring_hits

    named_queries = [
        "The Dirty Duck", "The Black Swan", "The Rooftop Restaurant",
        "RSC Rooftop", "Church Street Townhouse", "The Townhouse",
        "No 9 Church Street", "No.9 Church Street", "Pick Thai",
        "Oscar's", "Vintner", "Lambs", "Loxleys", "Opposition",
        "New York Pizzas", "Super Nonna", "Hussains", "Bella Italia",
    ]
    named_resolution = {}
    for q in named_queries:
        hits = _resolve_query(q)
        named_resolution[q] = {
            "resolved_fhrsids": hits,
            "resolved": bool(hits),
            "public_names": [
                establishments[fid].get("public_name")
                or establishments[fid].get("n")
                for fid in hits
            ],
        }

    match_class_summary = _summarise_match_classes(establishments)

    report = {
        "generated_by": "resolve_entities.py",
        "total_establishments": len(establishments),
        "manual_aliases_applied": alias_stats["applied"],
        "manual_aliases_missing_fhrsids": alias_stats["missing_fhrsids"],
        "auto_parsed_trade_as": auto_parsed,
        "records_with_public_name": sum(
            1 for r in establishments.values() if r.get("public_name")),
        "records_with_trading_names": sum(
            1 for r in establishments.values() if r.get("trading_names")),
        "duplicate_gpid_groups": ambig_stats["auto_groups"],
        "manual_ambiguous_groups": ambig_stats["manual_groups"],
        "records_flagged_ambiguous": sum(
            1 for r in establishments.values() if r.get("entity_ambiguous")),
        "entity_match_class_counts": match_class_summary,
        "named_venue_resolution": named_resolution,
        "known_unresolved_not_in_slice": aliases.get("known_unresolved", []),
    }

    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Wrote {REPORT}")
    print(f"  manual aliases applied:   {alias_stats['applied']}")
    print(f"  auto-parsed trade-as:     {auto_parsed}")
    print(f"  records with public_name: "
          f"{report['records_with_public_name']}")
    print(f"  records with trading_names: "
          f"{report['records_with_trading_names']}")
    print(f"  duplicate gpid groups:    "
          f"{len(ambig_stats['auto_groups'])}")
    print(f"  ambiguous records:        "
          f"{report['records_flagged_ambiguous']}")
    print(f"  entity_match classes:     {match_class_summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
