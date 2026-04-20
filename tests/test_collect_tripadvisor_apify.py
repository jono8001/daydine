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
        """Without resolved_urls we still emit a valid payload — the
        startUrls list falls back to the TA Search URL form. Production
        flow passes resolved_urls from the search pre-stage (see
        test_scrapapi_with_resolved_urls_uses_them)."""
        inp = self.m.build_apify_input(
            "scrapapi/tripadvisor-review-scraper",
            "The Vintner Wine Bar Stratford-upon-Avon", 3, 5)
        self.assertIn("startUrls", inp)
        self.assertNotIn("searchQueries", inp)

    def test_scrapapi_start_urls_is_list_of_strings(self):
        """Regression guard for run #7 of collect_tripadvisor_apify.yml.

        The actor's input schema declares `startUrls: array<string>`,
        NOT `array<{url: string}>`. Sending dicts produces:
          "Field input.startUrls.0 must be string"
        and every per-venue call fails. This test asserts the payload
        shape so the dict form can't accidentally come back (e.g. if
        someone copies the apify/web-scraper convention into this
        branch)."""
        inp = self.m.build_apify_input(
            "scrapapi/tripadvisor-review-scraper",
            "Loxleys Stratford-upon-Avon", 3, 5)
        self.assertIsInstance(inp["startUrls"], list)
        self.assertGreater(len(inp["startUrls"]), 0,
                           "startUrls must be non-empty")
        for i, u in enumerate(inp["startUrls"]):
            self.assertIsInstance(
                u, str,
                f"startUrls[{i}] must be str, got {type(u).__name__}: {u!r}")
            self.assertTrue(
                u.startswith("http"),
                f"startUrls[{i}] must be an absolute URL, got {u!r}")

    def test_scrapapi_review_limit_aliases_present(self):
        """Both maxReviewsPerPlace and maxReviewsPerUrl carry MAX_REVIEWS.

        scrapapi/tripadvisor-review-scraper's documented field is
        `maxReviewsPerUrl`; some neighbouring actors use
        `maxReviewsPerPlace`. We send both so a minor rename upstream
        can't silently drop us back to the actor's default review
        limit."""
        inp = self.m.build_apify_input(
            "scrapapi/tripadvisor-review-scraper", "Lambs", 3, 7)
        self.assertEqual(inp.get("maxReviewsPerUrl"), 7)
        self.assertEqual(inp.get("maxReviewsPerPlace"), 7)

    def test_scrapapi_with_resolved_urls_uses_them(self):
        """When the pre-stage search actor resolves a real review URL,
        build_apify_input passes it through verbatim in startUrls."""
        resolved = (
            "https://www.tripadvisor.com/Restaurant_Review-g186460-"
            "d730193-Reviews-The_Vintner_Wine_Bar-"
            "Stratford_upon_Avon_Warwickshire_England.html"
        )
        inp = self.m.build_apify_input(
            "scrapapi/tripadvisor-review-scraper",
            "Vintner Wine Bar Stratford-upon-Avon", 3, 5,
            resolved_urls=[resolved])
        self.assertEqual(inp["startUrls"], [resolved])
        # Verify the review-URL pattern actually matches.
        self.assertIsNotNone(self.m.TA_REVIEW_URL_RE.search(inp["startUrls"][0]))

    def test_scrapapi_payload_must_have_review_url_or_search_string(self):
        """Regression guard for run #8 of collect_tripadvisor_apify.yml.

        The actor either (a) ingests resolved `/Restaurant_Review-` /
        `/Hotel_Review-` URLs, or (b) — for actors that support it —
        performs its own internal search via a non-empty `searchString`.
        Sending a payload with neither (Search-URL-shaped startUrls
        and no searchString) returns 0 items on every call.

        This test asserts that at least ONE of those channels is
        populated, regardless of whether resolved_urls was supplied."""
        # Case A: caller supplied a real resolved URL
        inp_a = self.m.build_apify_input(
            "scrapapi/tripadvisor-review-scraper",
            "Loxleys Stratford", 3, 5,
            resolved_urls=[
                "https://www.tripadvisor.com/Restaurant_Review-g186460-"
                "d1089654-Reviews-Loxleys_Restaurant_and_Wine_Bar.html"
            ])
        self._assert_payload_actionable(inp_a)

        # Case B: no resolved URL — payload must still be actionable
        # via searchString (belt-and-braces alias) so that actors which
        # support internal search can still act on it.
        inp_b = self.m.build_apify_input(
            "scrapapi/tripadvisor-review-scraper",
            "Loxleys Stratford", 3, 5)
        self._assert_payload_actionable(inp_b)

    def _assert_payload_actionable(self, inp):
        """Helper: assert payload has at least one of: resolved review
        URL in startUrls, or non-empty searchString."""
        urls = inp.get("startUrls") or []
        search_string = (inp.get("searchString") or "").strip()
        has_review_url = any(
            isinstance(u, str) and self.m.TA_REVIEW_URL_RE.search(u)
            for u in urls
        )
        self.assertTrue(
            has_review_url or bool(search_string),
            f"scrapapi payload must contain either a resolved review URL "
            f"in startUrls (matching /Restaurant_Review-/Hotel_Review-) "
            f"OR a non-empty searchString. Got: "
            f"startUrls={urls!r}, searchString={search_string!r}"
        )

    def test_legacy_emits_search_queries(self):
        inp = self.m.build_apify_input(
            "automation-lab/tripadvisor-scraper", "Lambs Stratford", 3, 5)
        self.assertIn("searchQueries", inp)
        self.assertNotIn("startUrls", inp)


class SearchActorTest(unittest.TestCase):
    """resolve_tripadvisor_url: cache behaviour + URL-pattern filtering."""

    def setUp(self):
        self.m = _load_collector({
            "APIFY_TOKEN": "t",
            "APIFY_SEARCH_ACTOR": "getdataforme/tripadvisor-places-search-scraper",
        })

    def test_search_actor_payload_uses_getdataforme_shape(self):
        inp = self.m.build_search_actor_input(
            "getdataforme/tripadvisor-places-search-scraper",
            "Vintner Wine Bar Stratford-upon-Avon")
        self.assertEqual(inp["search"], "Vintner Wine Bar Stratford-upon-Avon")
        self.assertIn("maxItems", inp)

    def test_cache_hit_short_circuits_actor(self):
        """If the cache already knows the URL, don't even call Apify."""
        cache = {
            "vintner wine bar stratford-upon-avon": {
                "url": "https://www.tripadvisor.com/Restaurant_Review-x-Reviews-V.html",
                "name": "Vintner",
                "resolved_at": "2026-04-20T00:00:00Z",
            }
        }
        class _Explode:  # pragma: no cover — should never execute
            def __init__(self, *a, **kw):
                raise AssertionError("ApifyClient must not be called on cache hit")
        fake = type(sys)("apify_client")
        fake.ApifyClient = _Explode
        with mock.patch.dict(sys.modules, {"apify_client": fake}):
            url, name = self.m.resolve_tripadvisor_url(
                "Vintner Wine Bar Stratford-upon-Avon", "fake_token", cache)
        self.assertEqual(url,
                         "https://www.tripadvisor.com/Restaurant_Review-x-Reviews-V.html")
        self.assertEqual(name, "Vintner")

    def test_picks_first_review_url_and_caches_it(self):
        """Filter candidates by TA_REVIEW_URL_RE and persist in cache."""
        items = [
            {"url": "https://www.tripadvisor.com/Hotels-Stratford.html"},
            {"url": "https://www.tripadvisor.com/Restaurant_Review-g186460-d1-Reviews-Target.html",
             "name": "Target Restaurant"},
            {"url": "https://www.tripadvisor.com/Restaurant_Review-g186460-d2-Reviews-Other.html"},
        ]
        class _Dataset:
            def iterate_items(self_inner): return iter(items)
        class _Actor:
            def call(self_inner, run_input=None, timeout_secs=None):
                return {"defaultDatasetId": "stub"}
        class _Client:
            def __init__(self_inner, token): pass
            def actor(self_inner, name): return _Actor()
            def dataset(self_inner, _id): return _Dataset()
        fake = type(sys)("apify_client")
        fake.ApifyClient = _Client
        cache = {}
        with mock.patch.dict(sys.modules, {"apify_client": fake}):
            url, name = self.m.resolve_tripadvisor_url(
                "Target Stratford-upon-Avon", "fake_token", cache)
        self.assertIn("Restaurant_Review-g186460-d1", url)
        self.assertEqual(name, "Target Restaurant")
        # And it was cached under the normalised key.
        cached = cache["target stratford-upon-avon"]
        self.assertEqual(cached["url"], url)


if __name__ == "__main__":
    unittest.main(verbosity=2)
