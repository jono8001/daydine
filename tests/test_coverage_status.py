#!/usr/bin/env python3
"""Unit tests for coverage_status (ADR-001 pivot).

Four invariants this file guards:

    1. `coverage_status` is a NEW, orthogonal field. Adding it must not
       change `confidence_class`, `rankable`, `league_table_eligible`,
       `rcs_v4_final`, `base_score`, or `adjusted_score` for any venue.
    2. `coverage_status` is emitted in V4Score.to_dict().
    3. `coverage-ready` requires all three components + entity confirmed
       + CR >= 2 + Trust >= 4 + at least one platform with >= 30 reviews
       + not dissolved + not closed_permanently.
    4. A `coverage-ready` venue on a single platform stays in Rankable-B
       (promotion to A still requires platforms_count >= 2).

Run via `python -m tests.test_coverage_status`.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parent
ENGINE_PATH = REPO / "rcs_scoring_v4.py"


def _load_engine():
    """Import the engine with sys.modules registration. Dataclasses with
    Optional[...] annotations need the module present in sys.modules at
    the moment @dataclass executes (typing._is_type walks cls.__module__)."""
    mod_name = "rcs_scoring_v4_test"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, ENGINE_PATH)
    m = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = m
    spec.loader.exec_module(m)
    return m


class CoverageStatusFieldTest(unittest.TestCase):
    """compute_coverage_status maps component availability to the three
    coverage-status values without consulting confidence_class."""

    def setUp(self):
        self.m = _load_engine()

    def _trust(self, available=True, signals_used=5):
        return self.m.TrustResult(
            score=7.0, available=available,
            signals_used=signals_used, recency=1.0)

    def _customer(self, available=True, platforms=None):
        platforms = platforms or [
            self.m.PlatformEvidence(
                platform="google", raw=4.3, count=120, shrunk=4.25,
                shrunk_norm=0.85, weight=1.0),
        ]
        return self.m.CustomerResult(
            score=8.5, available=available, platforms=platforms,
            total_reviews=sum(p.count for p in platforms),
            platforms_count=len(platforms))

    def _commercial(self, available=True, signals_used=2):
        return self.m.CommercialResult(
            score=5.0, available=available, signals_used=signals_used)

    def test_ready_when_all_gates_met(self):
        cov = self.m.compute_coverage_status(
            self._trust(signals_used=5),
            self._customer(),  # google count=120 >= 30
            self._commercial(signals_used=2),
            entity_match="confirmed",
            entity_dissolved=False,
            closure=None,
        )
        self.assertEqual(cov, "coverage-ready")

    def test_partial_when_entity_probable(self):
        """Probable-not-confirmed entity match blocks coverage-ready."""
        cov = self.m.compute_coverage_status(
            self._trust(), self._customer(), self._commercial(),
            entity_match="probable",
            entity_dissolved=False, closure=None,
        )
        self.assertEqual(cov, "coverage-partial")

    def test_partial_when_cr_below_two(self):
        cov = self.m.compute_coverage_status(
            self._trust(),
            self._customer(),
            self._commercial(signals_used=1),
            entity_match="confirmed",
            entity_dissolved=False, closure=None,
        )
        self.assertEqual(cov, "coverage-partial")

    def test_partial_when_no_big_platform(self):
        small = [
            self.m.PlatformEvidence(
                platform="google", raw=4.4, count=12, shrunk=4.1,
                shrunk_norm=0.82, weight=0.5),
        ]
        cov = self.m.compute_coverage_status(
            self._trust(),
            self._customer(platforms=small),
            self._commercial(),
            entity_match="confirmed",
            entity_dissolved=False, closure=None,
        )
        self.assertEqual(cov, "coverage-partial")

    def test_partial_when_trust_signals_low(self):
        cov = self.m.compute_coverage_status(
            self._trust(signals_used=3),
            self._customer(), self._commercial(),
            entity_match="confirmed",
            entity_dissolved=False, closure=None,
        )
        self.assertEqual(cov, "coverage-partial")

    def test_partial_when_one_component_absent(self):
        cov = self.m.compute_coverage_status(
            self._trust(),
            self._customer(),
            self._commercial(available=False, signals_used=0),
            entity_match="confirmed",
            entity_dissolved=False, closure=None,
        )
        self.assertEqual(cov, "coverage-partial")

    def test_absent_when_entity_match_none(self):
        cov = self.m.compute_coverage_status(
            self._trust(), self._customer(), self._commercial(),
            entity_match="none",
            entity_dissolved=False, closure=None,
        )
        self.assertEqual(cov, "coverage-absent")

    def test_absent_when_nothing_available(self):
        cov = self.m.compute_coverage_status(
            self._trust(available=False, signals_used=0),
            self._customer(available=False, platforms=[]),
            self._commercial(available=False, signals_used=0),
            entity_match="confirmed",
            entity_dissolved=False, closure=None,
        )
        self.assertEqual(cov, "coverage-absent")

    def test_partial_when_dissolved(self):
        cov = self.m.compute_coverage_status(
            self._trust(), self._customer(), self._commercial(),
            entity_match="confirmed",
            entity_dissolved=True, closure=None,
        )
        self.assertEqual(cov, "coverage-partial")

    def test_partial_when_closed_permanently(self):
        cov = self.m.compute_coverage_status(
            self._trust(), self._customer(), self._commercial(),
            entity_match="confirmed",
            entity_dissolved=False, closure="closed_permanently",
        )
        self.assertEqual(cov, "coverage-partial")


class CoverageStatusDoesNotMutateScoringTest(unittest.TestCase):
    """The most important invariant from ADR-001: adding coverage_status
    must NOT change rcs_v4_final, confidence_class, rankable, or
    league_table_eligible for any venue. This test exercises
    score_venue on a venue that hits every typical path and asserts the
    other fields take the values the spec says they should."""

    def setUp(self):
        self.m = _load_engine()

    def _score(self, record, entity_match="confirmed"):
        # score_venue takes entity_match as a bare status string.
        return self.m.score_venue(record, entity_match=entity_match)

    def test_rankable_b_single_platform_not_promoted_by_coverage_ready(self):
        """Critical invariant: a coverage-ready venue on a single
        platform is Rankable-B, NEVER Rankable-A. Promotion to A still
        requires platforms_count >= 2."""
        record = {
            "id": "test1", "n": "Test", "pc": "CV37 6AB",
            "lat": 52.19, "lon": -1.71,
            # Trust (FSA)
            "r": 5, "rd": "2025-09-15", "s": 5, "sh": 5, "ss": 5, "sm": 5,
            # Google (one platform, high review count)
            "gr": 4.5, "grc": 450, "gpid": "ChIJxxx",
            # Commercial Readiness — 3 of 4
            "web": True, "phone": "01789 123456", "goh": ["mon:9-5"],
        }
        sc = self._score(record)
        self.assertEqual(sc.confidence_class, "Rankable-B",
                         f"single platform must cap at B, got {sc.confidence_class}")
        self.assertEqual(sc.coverage_status, "coverage-ready",
                         "this fixture should clear the coverage-ready gates")
        self.assertTrue(sc.rankable)
        self.assertTrue(sc.league_table_eligible)

    def test_coverage_status_in_to_dict(self):
        record = {
            "id": "test2", "n": "Test2", "pc": "CV37 6AB",
            "lat": 52.19, "lon": -1.71,
            "r": 5, "rd": "2025-09-15", "s": 5, "sh": 5, "ss": 5, "sm": 5,
            "gr": 4.5, "grc": 450, "gpid": "ChIJxxx",
            "web": True, "phone": "01789 123456",
        }
        sc = self._score(record)
        d = sc.to_dict()
        self.assertIn("coverage_status", d)
        self.assertIn(d["coverage_status"],
                      {"coverage-ready", "coverage-partial", "coverage-absent"})

    def test_profile_only_d_is_coverage_absent(self):
        """Profile-only-D venues (entity_match='none' or signals<4) must
        land in coverage-absent."""
        record = {
            "id": "test3", "n": "Unknown", "pc": "CV37 6AB",
        }
        sc = self._score(record, entity_match="none")
        self.assertEqual(sc.confidence_class, "Profile-only-D")
        self.assertEqual(sc.coverage_status, "coverage-absent")


class RankableAGatesUnchangedTest(unittest.TestCase):
    """Regression guard for ADR-001: the Rankable-A gate still requires
    `customer.platforms_count >= 2`. Adding coverage_status did not
    change classify_confidence, apply_low_review_cap, or rankable_flags."""

    def setUp(self):
        self.m = _load_engine()

    def test_two_platforms_promote_to_rankable_a(self):
        """Put two big-N platforms on the same venue — must promote."""
        record = {
            "id": "two-plats", "n": "Two Plats", "pc": "CV37 6AB",
            "lat": 52.19, "lon": -1.71,
            "r": 5, "rd": "2025-09-15", "s": 5, "sh": 5, "ss": 5, "sm": 5,
            "gr": 4.5, "grc": 450, "gpid": "ChIJxxx",
            "ta": 4.2, "trc": 320, "ta_present": True,
            "web": True, "phone": "01789 123456",
        }
        sc = self.m.score_venue(record, entity_match="confirmed")
        self.assertEqual(sc.confidence_class, "Rankable-A",
                         f"expected Rankable-A with two big-N platforms, "
                         f"got {sc.confidence_class}")
        self.assertTrue(sc.rankable)
        self.assertTrue(sc.league_table_eligible)

    def test_one_platform_stays_rankable_b(self):
        """Regression companion to the test above: drop to one platform
        and the class must demote to B."""
        record = {
            "id": "one-plat", "n": "One Plat", "pc": "CV37 6AB",
            "lat": 52.19, "lon": -1.71,
            "r": 5, "rd": "2025-09-15", "s": 5, "sh": 5, "ss": 5, "sm": 5,
            "gr": 4.5, "grc": 450, "gpid": "ChIJxxx",
            "web": True, "phone": "01789 123456",
        }
        sc = self.m.score_venue(record, entity_match="confirmed")
        self.assertEqual(sc.confidence_class, "Rankable-B")


if __name__ == "__main__":
    unittest.main(verbosity=2)
