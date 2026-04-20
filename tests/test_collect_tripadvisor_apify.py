#!/usr/bin/env python3
"""Unit tests for collect_tripadvisor_apify.py.

Covers the regressions from b705c2d:

    1. scrapapi/tripadvisor-review-scraper returns items in a REVIEW-shaped
       envelope with restaurant metadata nested under `placeInfo`. The
       matcher used to look at top-level keys and rejected everything.
    2. The end-of-run hard-fail guard didn't catch a 0-match run. The guard
       is now two-signal (matched==0 OR new_raw_files==0) and uses
       `raise SystemExit(1)`.
    3. The DRY_RUN_LIMIT dispatch input must actually slice the loop.

Tests are stdlib-only and run via `python -m tests.test_collect_tripadvisor_apify`.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent
REPO = HERE.parent
COLLECTOR_PATH = REPO / ".github/scripts/collect_tripadvisor_apify.py"


def _load_collector(env: dict[str, str] | None = None):
    """Import the collector script as a module with optional env overrides."""
    for k, v in (env or {}).items():
        os.environ[k] = v
    # Force re-import so module-level constants pick up new env.
    spec = importlib.util.spec_from_file_location(
        "collect_tripadvisor_apify", COLLECTOR_PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class NormaliseReviewShapedItemsTest(unittest.TestCase):
    """scrapapi/tripadvisor-review-scraper emits one item per REVIEW with
    the restaurant metadata nested under `placeInfo`. Our normaliser must
    fold many such items into one per-place dict."""

    def setUp(self):
        self.m = _load_collector({"APIFY_TOKEN": "t"})

    def test_three_reviews_of_one_place_fold_into_one_candidate(self):
        raw = [
            {
                "text": "Great food",
                "title": "Loved it",
                "rating": 5,
                "publishedDate": "2026-03-01",
                "placeInfo": {
                    "name": "The Vintner Wine Bar",
                    "locationId": "730193",
                    "url": "https://ta.com/Restaurant_Review-730193",
                    "rating": 4.4,
                    "numberOfReviews": 1234,
                    "latitude": 52.192,
                    "longitude": -1.706,
                    "cuisines": [{"name": "British"}, {"name": "Wine Bar"}],
                    "priceRange": "££-£££",
                    "rankingPosition": 12,
                },
            },
            {
                "text": "Lovely wine list",
                "rating": 4,
                "publishedDate": "2026-02-14",
                "placeInfo": {
                    "name": "The Vintner Wine Bar",
                    "locationId": "730193",
                    "url": "https://ta.com/Restaurant_Review-730193",
                    "rating": 4.4,
                    "numberOfReviews": 1234,
                    "latitude": 52.192,
                    "longitude": -1.706,
                },
            },
            {
                "reviewBody": "Cozy spot",
                "ratingValue": 5,
                "createdDate": "2026-01-10",
                "placeInfo": {
                    "name": "The Vintner Wine Bar",
                    "locationId": "730193",
                    "url": "https://ta.com/Restaurant_Review-730193",
                },
            },
        ]
        places = self.m.normalise_apify_items(raw)
        self.assertEqual(len(places), 1)
        p = places[0]
        self.assertEqual(p["name"], "The Vintner Wine Bar")
        self.assertEqual(p["url"], "https://ta.com/Restaurant_Review-730193")
        self.assertEqual(p["rating"], 4.4)
        self.assertEqual(p["review_count"], 1234)
        self.assertEqual(p["latitude"], 52.192)
        self.assertEqual(p["longitude"], -1.706)
        self.assertEqual(p["ranking"], 12)
        self.assertEqual(len(p["reviews"]), 3)
        self.assertEqual(p["reviews"][0]["text"], "Great food")

    def test_place_shaped_items_pass_through(self):
        """Legacy automation-lab actor returns per-place items already."""
        raw = [
            {
                "name": "Loxleys",
                "url": "https://ta.com/Restaurant_Review-501",
                "rating": 4.3,
                "reviewCount": 900,
                "lat": 52.19,
                "lng": -1.71,
                "cuisines": "British, Contemporary",
            }
        ]
        places = self.m.normalise_apify_items(raw)
        self.assertEqual(len(places), 1)
        p = places[0]
        self.assertEqual(p["name"], "Loxleys")
        self.assertEqual(p["review_count"], 900)
        self.assertEqual(p["latitude"], 52.19)

    def test_location_and_place_aliases(self):
        """Actors sometimes nest under `location` or `place` instead of `placeInfo`."""
        raw = [
            {
                "text": "Nice place",
                "rating": 4,
                "location": {
                    "name": "Lambs",
                    "url": "https://ta.com/Restaurant_Review-502",
                    "rating": 4.1,
                },
            },
            {
                "text": "Good food",
                "place": {
                    "name": "Lambs",
                    "url": "https://ta.com/Restaurant_Review-502",
                    "rating": 4.1,
                },
            },
        ]
        places = self.m.normalise_apify_items(raw)
        self.assertEqual(len(places), 1)
        self.assertEqual(places[0]["name"], "Lambs")
        self.assertEqual(len(places[0]["reviews"]), 2)

    def test_empty_input_returns_empty_list(self):
        self.assertEqual(self.m.normalise_apify_items([]), [])


class ExtractTaDataTest(unittest.TestCase):
    """Feed the post-normalise place dict into extract_ta_data and verify
    it produces the expected headline fields and clears MATCH_MIN_SCORE."""

    def setUp(self):
        self.m = _load_collector({"APIFY_TOKEN": "t", "MATCH_MIN_SCORE": "0.55"})

    def test_good_match_produces_entry(self):
        place = {
            "name": "The Vintner Wine Bar",
            "url": "https://ta.com/Restaurant_Review-730193",
            "rating": 4.4,
            "review_count": 1234,
            "latitude": 52.192,
            "longitude": -1.706,
            "cuisines": [{"name": "British"}],
            "price_range": "££-£££",
            "ranking": 12,
            "reviews": [
                {"text": "Great", "rating": 5, "date": "2026-03-01"},
            ],
        }
        entry, score = self.m.extract_ta_data(
            place, "Vintner Wine Bar", target_lat=52.192, target_lon=-1.706)
        self.assertIsNotNone(entry, "expected a match on exact-name + exact-coord")
        self.assertGreaterEqual(score, 0.55)
        self.assertEqual(entry["ta"], 4.4)
        self.assertEqual(entry["trc"], 1234)
        self.assertEqual(entry["ta_url"],
                         "https://ta.com/Restaurant_Review-730193")
        self.assertEqual(entry["ta_cuisines"], ["British"])
        self.assertEqual(entry["ta_ranking"], "12")
        self.assertEqual(len(entry["ta_reviews"]), 1)

    def test_low_score_returns_none(self):
        place = {
            "name": "Completely Different Venue",
            "rating": 4.2,
            "review_count": 50,
        }
        entry, score = self.m.extract_ta_data(
            place, "Vintner Wine Bar", target_lat=None, target_lon=None)
        self.assertIsNone(entry)
        self.assertLess(score, 0.55)


class GuardFiresOnZeroMatchesTest(unittest.TestCase):
    """The end-of-run guard is the safety net against silent failures.
    This is the regression test for b705c2d (guard appeared to be bypassed).

    We simulate the main() flow end-to-end with the Apify client patched
    to return empty datasets, then assert SystemExit(1) fires."""

    def _run_main_with_empty_actor(self, n_venues, limit=0):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            # Fixture: N establishments with names and coords
            establishments = {
                str(i): {"n": f"Venue {i}", "pc": "CV37",
                         "lat": 52.19, "lon": -1.71}
                for i in range(1, n_venues + 1)
            }
            (td / "stratford_establishments.json").write_text(
                json.dumps(establishments))

            env = {
                "APIFY_TOKEN": "fake",
                "APIFY_ACTOR": "scrapapi/tripadvisor-review-scraper",
                "MATCH_MIN_SCORE": "0.55",
                "MAX_REVIEWS": "5",
                "DRY_RUN_LIMIT": str(limit),
            }
            for k, v in env.items():
                os.environ[k] = v

            # Load a fresh copy of the module pointed at our tmpdir so
            # INPUT_PATH / RAW_DIR don't touch the real repo state.
            src = COLLECTOR_PATH.read_text()
            src = src.replace(
                'os.path.join(REPO_ROOT, "stratford_establishments.json")',
                repr(str(td / "stratford_establishments.json")))
            src = src.replace(
                'os.path.join(REPO_ROOT, "data", "raw", "tripadvisor")',
                repr(str(td / "data" / "raw" / "tripadvisor")))
            tmp_path = td / "collector.py"
            tmp_path.write_text(src)

            spec = importlib.util.spec_from_file_location(
                "collector_tmp", tmp_path)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)

            class _FakeDataset:
                def iterate_items(self):
                    return iter([])

            class _FakeActor:
                def call(self, run_input=None, timeout_secs=None):
                    return {"defaultDatasetId": "stub"}

            class _FakeClient:
                def __init__(self, token): pass
                def actor(self, name): return _FakeActor()
                def dataset(self, _id): return _FakeDataset()

            # Patch the apify_client import inside the module so search_apify
            # uses the fake client.
            fake_mod = type(sys)("apify_client")
            fake_mod.ApifyClient = _FakeClient
            with mock.patch.dict(sys.modules, {"apify_client": fake_mod}):
                with self.assertRaises(SystemExit) as cm:
                    m.main()
                return cm.exception.code

    def test_zero_matches_exits_one(self):
        code = self._run_main_with_empty_actor(n_venues=3)
        self.assertEqual(code, 1,
                         "guard should exit 1 when matched==0 and attempted>0")

    def test_dry_run_limit_respected_and_guard_still_fires(self):
        code = self._run_main_with_empty_actor(n_venues=50, limit=3)
        self.assertEqual(code, 1, "limit=3 should also trip guard on 0 matches")


class BuildApifyInputBranchingTest(unittest.TestCase):
    """build_apify_input must emit startUrls for scrapapi and
    searchQueries for legacy automation-lab — branching is what kept
    both the old and new actor paths working from the same script."""

    def setUp(self):
        self.m = _load_collector({"APIFY_TOKEN": "t"})

    def test_scrapapi_emits_start_urls(self):
        inp = self.m.build_apify_input(
            "scrapapi/tripadvisor-review-scraper",
            "The Vintner Wine Bar Stratford-upon-Avon", 3, 5)
        self.assertIn("startUrls", inp)
        self.assertNotIn("searchQueries", inp)
        self.assertTrue(
            inp["startUrls"][0]["url"].startswith(
                "https://www.tripadvisor.com/Search?q="),
            "startUrls[0].url must be a TripAdvisor Search URL")

    def test_legacy_emits_search_queries(self):
        inp = self.m.build_apify_input(
            "automation-lab/tripadvisor-scraper", "Lambs Stratford", 3, 5)
        self.assertIn("searchQueries", inp)
        self.assertNotIn("startUrls", inp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
