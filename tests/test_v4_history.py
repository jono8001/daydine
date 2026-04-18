#!/usr/bin/env python3
"""
tests/test_v4_history.py — V4 recommendation-history lifecycle tests.

Exercises `operator_intelligence.v4_recommendations_history` against
the `v4_recommendations.generate_v4_recommendations` entry point so
the lifecycle behaviour is verified end-to-end, not just at the
module boundary. Uses a temporary history root that is torn down
between test runs, and deterministic synthetic `ReportInputs`
fixtures so the assertions stay stable.

Covers:
  * first sighting — status new, times_seen 1
  * second month  — status ongoing, times_seen 2
  * third month   — status ongoing, times_seen 3 (label will read
                    "Stale (3 months)" in the action-card renderer)
  * idempotent same-month re-run — no times_seen advance
  * resolution path — rec that drops out of candidates this run
                    is marked resolved in history
  * reopened path — rec that drops out then reappears is
                    status "reopened"
  * identity across title+component — same title+component returns
                    the same rec_id
  * suppression modes — Profile-only-D / Closed calls do not
                    corrupt an existing history

Run with: python -m tests.test_v4_history
Exits non-zero on any failure; prints a per-test summary.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import traceback
from dataclasses import replace

from operator_intelligence.v4_adapter import (
    ComponentView, ReportInputs,
    MODE_RANKABLE_A, MODE_RANKABLE_B, MODE_DIRECTIONAL_C,
    MODE_PROFILE_ONLY_D, MODE_CLOSED,
)
from operator_intelligence.v4_recommendations import (
    generate_v4_recommendations,
)
from operator_intelligence.v4_recommendations_history import (
    load_history, rec_id,
)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

def _make_inputs(
    *,
    month: str = "2026-04",
    mode: str = MODE_RANKABLE_B,
    venue_record: dict | None = None,
    commercial_available: bool = True,
    booking_observed: bool = False,
) -> ReportInputs:
    """Minimal ReportInputs for a Rankable-B-ish venue that will
    reliably trigger a Commercial Readiness booking/contact-path fix
    (the anchor rec we track across runs)."""
    trust = ComponentView(score=8.0, available=True, signals_used=5)
    customer = ComponentView(
        score=7.5, available=True,
        platforms={"google": {"raw": 4.5, "count": 312,
                                "shrunk": 4.31, "weight": 1.0}},
    )
    commercial = ComponentView(
        score=7.0, available=commercial_available, signals_used=3,
    )

    record = dict(venue_record or {
        "id": "TESTFHR",
        "n": "Test Venue",
        "r": 5,
        "rd": "2026-01-01",
        "web": True,
        "goh": [f"{d}: 09:00-22:00" for d in
                ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]],
        "grc": 312, "gr": 4.5,
    })
    if booking_observed:
        record["phone"] = "01234 567890"

    return ReportInputs(
        fhrsid="TESTFHR",
        name="Test Venue", fsa_name="Test Venue",
        trading_names=[], alias_confidence=None,
        address="1 Test Lane", postcode="TS1 1AA", la="Test LA",
        month_str=month,
        rcs_v4_final=7.5, base_score=7.5, adjusted_score=7.5,
        confidence_class=("Rankable-A" if mode == MODE_RANKABLE_A
                           else "Rankable-B" if mode == MODE_RANKABLE_B
                           else "Directional-C" if mode == MODE_DIRECTIONAL_C
                           else "Profile-only-D" if mode == MODE_PROFILE_ONLY_D
                           else "Rankable-B"),
        rankable=(mode in {MODE_RANKABLE_A, MODE_RANKABLE_B}),
        league_table_eligible=(mode in {MODE_RANKABLE_A, MODE_RANKABLE_B}),
        entity_match_status="confirmed",
        entity_ambiguous=False,
        source_family_summary={
            "fsa": "present",
            "customer_platforms": ["google"],
            "commercial": "full" if commercial_available else "absent",
            "companies_house": "unmatched",
        },
        penalties_applied=[], caps_applied=[],
        decision_trace=[], engine_version="v4.0.0",
        computed_at="2026-04-17T00:00:00Z",
        trust=trust, customer=customer, commercial=commercial,
        distinction_value=0.0, distinction_sources=[],
        business_status=None, fsa_closed=False, closure_status=None,
        report_mode=mode,
        venue_record=record,
    )


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------

def _find_booking_rec(payload: dict) -> dict | None:
    """Locate the booking/contact-path fix rec (our canary action)."""
    for rec in payload.get("all_recs", []):
        if rec.get("rec_type") == "fix" and "booking" in \
                (rec.get("title") or "").lower():
            return rec
    return None


def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_first_sighting_marks_new():
    with tempfile.TemporaryDirectory() as root:
        inputs = _make_inputs(month="2026-04")
        payload = generate_v4_recommendations(inputs, history_root=root)
        rec = _find_booking_rec(payload)
        _assert(rec is not None, "booking rec must be present for thin CR")
        _assert(rec["status"] == "new",
                f"first sighting status: expected 'new', got {rec['status']!r}")
        _assert(rec["times_seen"] == 1,
                f"first sighting times_seen: expected 1, got {rec['times_seen']}")
        _assert(rec["first_seen"] == "2026-04",
                f"first_seen: expected 2026-04, got {rec['first_seen']!r}")
        _assert(rec["last_seen"] == "2026-04",
                f"last_seen: expected 2026-04, got {rec['last_seen']!r}")


def test_second_month_advances_to_ongoing():
    with tempfile.TemporaryDirectory() as root:
        # Month 1
        generate_v4_recommendations(
            _make_inputs(month="2026-04"), history_root=root,
        )
        # Month 2
        payload = generate_v4_recommendations(
            _make_inputs(month="2026-05"), history_root=root,
        )
        rec = _find_booking_rec(payload)
        _assert(rec["status"] == "ongoing",
                f"second month status: expected 'ongoing', got {rec['status']!r}")
        _assert(rec["times_seen"] == 2,
                f"second month times_seen: expected 2, got {rec['times_seen']}")
        _assert(rec["first_seen"] == "2026-04",
                "first_seen must be preserved across runs")
        _assert(rec["last_seen"] == "2026-05",
                "last_seen must update each run")


def test_third_month_still_ongoing():
    with tempfile.TemporaryDirectory() as root:
        for m in ("2026-04", "2026-05", "2026-06"):
            payload = generate_v4_recommendations(
                _make_inputs(month=m), history_root=root,
            )
        rec = _find_booking_rec(payload)
        _assert(rec["status"] == "ongoing",
                "status stays 'ongoing'; Stale / Overdue / Chronic "
                "labels are derived from times_seen in the action-card "
                "renderer, not in the status field itself")
        _assert(rec["times_seen"] == 3,
                f"third month times_seen: expected 3, got {rec['times_seen']}")


def test_idempotent_same_month_rerun():
    with tempfile.TemporaryDirectory() as root:
        inputs = _make_inputs(month="2026-04")
        generate_v4_recommendations(inputs, history_root=root)
        # Run again for the same month — identity should resolve to the
        # same entry and times_seen must NOT increment.
        payload2 = generate_v4_recommendations(inputs, history_root=root)
        rec = _find_booking_rec(payload2)
        _assert(rec["times_seen"] == 1,
                f"same-month rerun times_seen: expected 1, got {rec['times_seen']}")
        _assert(rec["status"] == "new",
                f"same-month rerun status: expected 'new' preserved, "
                f"got {rec['status']!r}")


def test_resolved_when_rec_drops_out():
    with tempfile.TemporaryDirectory() as root:
        # Month 1: booking fix triggers (no phone observed)
        generate_v4_recommendations(
            _make_inputs(month="2026-04", booking_observed=False),
            history_root=root,
        )
        history_before = load_history("TESTFHR", root=root)
        booking_id = next(
            rid for rid, e in history_before.items()
            if "booking" in (e.get("title") or "").lower()
        )
        _assert(history_before[booking_id]["status"] == "new",
                "booking rec should be new in month 1")

        # Month 2: phone now observed → booking rec drops out of
        # candidates entirely.
        generate_v4_recommendations(
            _make_inputs(month="2026-05", booking_observed=True),
            history_root=root,
        )
        history_after = load_history("TESTFHR", root=root)
        _assert(booking_id in history_after,
                "resolved entry must remain in history")
        _assert(history_after[booking_id]["status"] == "resolved",
                f"resolved status expected, got "
                f"{history_after[booking_id]['status']!r}")
        _assert(history_after[booking_id].get("resolved_at") == "2026-05",
                "resolved_at must carry the month the rec dropped out")


def test_reopened_path():
    with tempfile.TemporaryDirectory() as root:
        # Month 1: booking fix triggers
        generate_v4_recommendations(
            _make_inputs(month="2026-04", booking_observed=False),
            history_root=root,
        )
        # Month 2: phone observed → rec resolves
        generate_v4_recommendations(
            _make_inputs(month="2026-05", booking_observed=True),
            history_root=root,
        )
        # Month 3: phone unobserved again → rec reappears
        payload = generate_v4_recommendations(
            _make_inputs(month="2026-06", booking_observed=False),
            history_root=root,
        )
        rec = _find_booking_rec(payload)
        _assert(rec is not None, "booking rec should re-appear after regression")
        _assert(rec["status"] == "reopened",
                f"reopened status expected, got {rec['status']!r}")
        _assert(rec["first_seen"] == "2026-04",
                "first_seen must survive across resolve + reopen")
        _assert(rec["times_seen"] == 2,
                f"reopened times_seen: expected 2 (resolve doesn't "
                f"advance; reopen does), got {rec['times_seen']}")


def test_identity_stable_across_runs():
    v_id = "TESTFHR"
    rid_a = rec_id(v_id, "Commercial Readiness",
                     "Publish a reachable phone number or booking link")
    rid_b = rec_id(v_id, "Commercial Readiness",
                     "Publish a reachable phone number or booking link")
    _assert(rid_a == rid_b,
            f"rec_id must be deterministic; got {rid_a!r} vs {rid_b!r}")
    # Different component → different ID (identity deliberately
    # includes the component).
    rid_c = rec_id(v_id, "Trust & Compliance",
                     "Publish a reachable phone number or booking link")
    _assert(rid_a != rid_c,
            "rec_id must fork when targets_component changes")


def test_suppressed_mode_does_not_corrupt_history():
    with tempfile.TemporaryDirectory() as root:
        # Seed history with one active rec.
        generate_v4_recommendations(
            _make_inputs(month="2026-04"), history_root=root,
        )
        seeded = load_history("TESTFHR", root=root)
        _assert(seeded, "fixture must seed at least one history entry")
        booking_id = next(
            rid for rid, e in seeded.items()
            if "booking" in (e.get("title") or "").lower()
        )
        _assert(seeded[booking_id]["status"] == "new",
                "seed status should be 'new'")

        # Month 2 with Profile-only-D — recs are suppressed. History
        # must not flip the previously-active rec to 'resolved'; that
        # would corrupt the record on a transient suppression.
        generate_v4_recommendations(
            _make_inputs(month="2026-05", mode=MODE_PROFILE_ONLY_D,
                          commercial_available=False),
            history_root=root,
        )
        after = load_history("TESTFHR", root=root)
        _assert(after[booking_id]["status"] == "new",
                f"suppressed-mode run must not advance status; got "
                f"{after[booking_id]['status']!r}")
        _assert(after[booking_id]["last_seen"] == "2026-04",
                "last_seen must not advance during suppressed mode")


def test_ignore_recs_are_not_persisted():
    with tempfile.TemporaryDirectory() as root:
        payload = generate_v4_recommendations(
            _make_inputs(month="2026-04"), history_root=root,
        )
        history = load_history("TESTFHR", root=root)
        # The perennial 'don't chase reviews' ignore recs are in the
        # payload but must not be in persisted history.
        ignore_titles = {
            r.get("title") for r in payload["all_recs"]
            if r.get("rec_type") == "ignore"
        }
        _assert(ignore_titles, "fixture should produce at least one "
                                "ignore rec")
        stored_titles = {e.get("title") for e in history.values()}
        overlap = ignore_titles & stored_titles
        _assert(not overlap,
                f"ignore recs must not be persisted; overlap: {overlap}")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _collect_tests():
    return [(n, fn) for n, fn in globals().items()
            if n.startswith("test_") and callable(fn)]


def main() -> int:
    tests = _collect_tests()
    failures: list[tuple[str, str]] = []
    for name, fn in tests:
        try:
            fn()
            print(f"ok   {name}")
        except AssertionError as e:
            failures.append((name, str(e)))
            print(f"FAIL {name} — {e}")
        except Exception as e:
            failures.append((name, f"{type(e).__name__}: {e}"))
            print(f"ERR  {name} — {type(e).__name__}: {e}")
            traceback.print_exc()
    print()
    print(f"Ran {len(tests)} tests — {len(failures)} failures.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
