"""
operator_intelligence/v4_recommendations_history.py — V4 recommendation
history persistence.

Closes the main remaining pilot-readiness warning tracked in
`docs/DayDine-V4-Pilot-Readiness.md` §4: before this module the V4
recs generator emitted `status = "new"` and `times_seen = 1` on every
run, which made pilot reports look as if every priority were newly
created each month. With persistence, recommendations that persist
across runs carry a stable identity, incrementing `times_seen` and
advancing through `new → ongoing → resolved` (with the reopened
case covered as well). The existing action-card `_status_label`
helper already derives `New / Ongoing (N months) / Stale / Overdue /
Chronic` labels from `times_seen` alone, so adding history
immediately unlocks the full lifecycle visible in the Implementation
Framework table.

Design decisions recorded for future engineers:

  * Storage: per-venue JSON files at
    `history/v4_recommendations/<fhrsid>.json`. One file per venue
    keeps diffs readable and avoids lock contention when reports are
    generated in parallel.

  * Identity: `md5(fhrsid + ":" + targets_component + ":" + title)`
    truncated to 12 hex chars. Including `targets_component` in the
    ID means that renaming a rec's component forks the identity —
    deliberate, because a rec moving to a different component is
    semantically a different action. Title stability is relied on
    (the V4 recs generator emits stable titles for the same
    evidence; dynamic text like platform names is in the evidence
    anchor, not the title).

  * Only persistable rec types: `fix`, `exploit`, `protect`, `watch`.
    `ignore`-type recs (the V4 perennials teaching "don't chase
    reviews for score") are advisory, not actionable, and would
    otherwise climb to "Chronic" in history. They are skipped.

  * Suppression-mode safety: when the report mode is
    `profile_only_d` or `closed`, the V4 generator emits no
    recommendations. Calling `apply_history` with an empty candidate
    list from a suppressed mode must not mark every existing entry
    as "resolved" — that would corrupt the history on a transient
    D / Closed reading. Suppressed-mode calls are short-circuited:
    history is loaded-and-saved unchanged (touching mtime but not
    content).

  * Idempotent same-month reruns: if `last_seen == month_str` on an
    existing entry, we do not increment `times_seen`. Running the
    generator twice for the same month yields byte-identical
    history. This is also what lets the sample runner be reproducible
    when it opts out of history via `disable_history=True`.

Public surface:

    HISTORY_ROOT             default storage root
    load_history(...)        read one venue's history file
    save_history(...)        write one venue's history file
    rec_id(...)              deterministic ID function
    apply_history(...)       the core merge: decorates candidates and
                              returns the updated history dict
    generate_and_persist(... )  convenience wrapper that does
                              load → apply → save in one call
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Iterable, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HISTORY_ROOT = "history/v4_recommendations"

# Report modes in which history should advance. Other modes either
# suppress the report entirely (profile_only_d, closed) or are handled
# via the `apply_history` short-circuit.
_ACTIVE_MODES = {
    "rankable_a",
    "rankable_b",
    "directional_c",
    "temp_closed",
}

# Rec types that get persisted. `ignore` items are advisory perennials
# and would rapidly climb to "Chronic" in history; excluded.
_PERSISTABLE_TYPES = {"fix", "exploit", "protect", "watch"}

# Status ladder — minimal, delegating "Stale / Overdue / Chronic" to
# the action-card label builder which reads times_seen directly.
_STATUS_NEW = "new"
_STATUS_ONGOING = "ongoing"
_STATUS_REOPENED = "reopened"
_STATUS_RESOLVED = "resolved"

# Fields we copy onto the history entry. Kept deliberately compact —
# full evidence / rationale lives on the current rec; the history file
# only needs enough to identify and lifecycle-track the rec.
_HISTORY_SNAPSHOT_FIELDS = (
    "rec_id",
    "venue_id",
    "targets_component",
    "title",
    "rec_type",
    "first_seen",
    "last_seen",
    "times_seen",
    "status",
)


# ---------------------------------------------------------------------------
# Path / IO
# ---------------------------------------------------------------------------

def _history_path(venue_id: str, root: Optional[str]) -> str:
    root = root or HISTORY_ROOT
    return os.path.join(root, f"{venue_id}.json")


def load_history(venue_id: str, root: Optional[str] = None) -> dict:
    path = _history_path(venue_id, root)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_history(venue_id: str, history: dict,
                 root: Optional[str] = None) -> None:
    root_dir = root or HISTORY_ROOT
    os.makedirs(root_dir, exist_ok=True)
    path = _history_path(venue_id, root_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False, sort_keys=True)


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

def rec_id(venue_id: str, targets_component: str, title: str) -> str:
    """Deterministic 12-char rec identifier.

    Identity is stable across runs so long as the venue, component,
    and title are stable. The V4 recs engine produces deterministic
    titles for the same underlying evidence; dynamic text (e.g.
    platform names) lives on the evidence anchors, not the title.
    """
    raw = f"{venue_id}:{targets_component}:{title}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

def _snapshot(rec: dict) -> dict:
    return {k: rec.get(k) for k in _HISTORY_SNAPSHOT_FIELDS}


def apply_history(candidates: list[dict], history: dict, *,
                  venue_id: str, month_str: str,
                  report_mode: str) -> dict:
    """Decorate candidates with lifecycle fields and return updated
    history.

    Mutates each candidate in place (`rec_id`, `venue_id`,
    `first_seen`, `last_seen`, `times_seen`, `status`) for candidates
    whose `rec_type` is persistable.

    Returns a new history dict (shallow copy) so callers can decide
    whether to write it back. The returned dict includes:

      - entries for persistable candidates in this run (updated or new)
      - entries from the prior history that were not seen this run,
        marked `status = "resolved"` with `resolved_at = month_str` —
        but only when `report_mode` is in `_ACTIVE_MODES`. Suppressed
        modes (profile_only_d / closed) return the history unchanged.

    Idempotent for same-month reruns: if an entry's `last_seen` already
    equals `month_str`, `times_seen` is not incremented again.
    """
    if report_mode not in _ACTIVE_MODES:
        # Suppressed-mode call — preserve history verbatim. This is
        # what prevents a transient Profile-only-D / Closed reading
        # from silently marking every previously-active rec resolved.
        return dict(history)

    updated = dict(history)
    seen_ids: set[str] = set()

    for rec in candidates:
        if rec.get("rec_type") not in _PERSISTABLE_TYPES:
            continue

        component = rec.get("targets_component") or "(unspecified)"
        title = rec.get("title") or ""
        rid = rec_id(venue_id, component, title)
        rec["rec_id"] = rid
        rec["venue_id"] = venue_id
        seen_ids.add(rid)

        prev = updated.get(rid)
        if prev:
            first_seen = prev.get("first_seen") or month_str
            prev_last = prev.get("last_seen")
            prev_status = prev.get("status") or _STATUS_NEW
            prev_times_seen = int(prev.get("times_seen") or 0)

            if prev_last == month_str:
                # Idempotent re-run within the same month — no
                # lifecycle advance.
                times_seen = prev_times_seen or 1
                status = prev_status
            else:
                times_seen = prev_times_seen + 1
                if prev_status == _STATUS_NEW:
                    status = _STATUS_ONGOING
                elif prev_status in {_STATUS_RESOLVED}:
                    status = _STATUS_REOPENED
                else:
                    # ongoing / reopened → stays ongoing; the
                    # action-card _status_label derives Stale /
                    # Overdue / Chronic from times_seen alone.
                    status = _STATUS_ONGOING

            rec["first_seen"] = first_seen
            rec["last_seen"] = month_str
            rec["times_seen"] = times_seen
            rec["status"] = status
        else:
            rec["first_seen"] = month_str
            rec["last_seen"] = month_str
            rec["times_seen"] = 1
            rec["status"] = _STATUS_NEW

        updated[rid] = _snapshot(rec)

    # Mark previously-active entries not seen this run as resolved.
    # Only fires for active modes (already guarded above).
    for rid, entry in list(updated.items()):
        if rid in seen_ids:
            continue
        prev_status = entry.get("status")
        if prev_status in {_STATUS_NEW, _STATUS_ONGOING, _STATUS_REOPENED}:
            entry["status"] = _STATUS_RESOLVED
            entry["resolved_at"] = month_str

    return updated


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def generate_and_persist(candidates: list[dict], *,
                         venue_id: str,
                         month_str: str,
                         report_mode: str,
                         history_root: Optional[str] = None,
                         disable_persistence: bool = False) -> dict:
    """Load → apply_history → save in one call. Returns the updated
    history dict (same content that was persisted). When
    `disable_persistence=True`, neither reads nor writes the store —
    useful for tests and reproducible sample generation.
    """
    if disable_persistence:
        return apply_history(
            candidates, {}, venue_id=venue_id,
            month_str=month_str, report_mode=report_mode,
        )

    history = load_history(venue_id, root=history_root)
    updated = apply_history(
        candidates, history, venue_id=venue_id,
        month_str=month_str, report_mode=report_mode,
    )
    save_history(venue_id, updated, root=history_root)
    return updated
