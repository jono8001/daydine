#!/usr/bin/env python3
"""Offline data-integrity tests for DayDine public market outputs.

These tests deliberately avoid network calls. They protect against silent
venue disappearance, especially the class of bug where an alias/review/report
artifact exists but the canonical establishments or public ranking output loses
that venue.

Run with:
    python -m tests.test_market_data_integrity
"""
from __future__ import annotations

import glob
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_readiness_module():
    path = ROOT / "scripts" / "check_market_readiness.py"
    spec = importlib.util.spec_from_file_location("check_market_readiness", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AliasGuardrailIntegrityTest(unittest.TestCase):
    def setUp(self):
        self.establishments = read_json(ROOT / "stratford_establishments.json", {}) or {}
        self.aliases = (read_json(ROOT / "data" / "entity_aliases.json", {}) or {}).get("aliases", [])
        self.known_missing = {}
        for file_name in glob.glob(str(ROOT / "data" / "known_missing_*_venues.json")):
            data = read_json(Path(file_name), {}) or {}
            for venue in data.get("venues", []) or []:
                fhrsid = str(venue.get("fhrsid") or "").strip()
                if fhrsid:
                    self.known_missing[fhrsid] = venue

    def test_every_alias_exists_or_has_known_missing_guardrail(self):
        failures = []
        for alias in self.aliases:
            fhrsid = str(alias.get("fhrsid") or "").strip()
            if not fhrsid:
                continue
            if fhrsid in self.establishments:
                continue
            if fhrsid in self.known_missing:
                continue
            failures.append({
                "fhrsid": fhrsid,
                "public_name": alias.get("public_name"),
                "postcode": alias.get("postcode"),
            })
        self.assertEqual(
            failures,
            [],
            "Every alias FHRSID must either exist in stratford_establishments.json "
            "or be explicitly documented in data/known_missing_*_venues.json."
        )

    def test_known_missing_guardrails_are_explained_and_actionable(self):
        required = {"fhrsid", "public_name", "postcode", "reason", "status"}
        failures = []
        for fhrsid, venue in self.known_missing.items():
            missing_fields = sorted(field for field in required if not venue.get(field))
            if missing_fields:
                failures.append({"fhrsid": fhrsid, "missing_fields": missing_fields})
            self.assertIn(
                venue.get("status"),
                {"needs_canonical_rebuild", "not_public", "resolved"},
                f"Known-missing venue {fhrsid} must have an explicit actionable status."
            )
        self.assertEqual(failures, [])

    def test_known_missing_public_venues_are_surfaced_by_search_layer(self):
        """Known missing venues are a temporary safety valve. If they are public,
        search-v2 must load the guardrail file so users don't get a dead result.
        """
        public_known_missing = [
            v for v in self.known_missing.values()
            if v.get("status") != "not_public"
        ]
        if not public_known_missing:
            self.skipTest("No public known-missing venues configured")
        search_html = (ROOT / "search-v2.html").read_text(encoding="utf-8")
        self.assertIn("known_missing_stratford_venues.json", search_html)
        self.assertIn("Known missing venue", search_html)


class MarketReadinessScriptTest(unittest.TestCase):
    def test_stratford_readiness_summary_has_expected_shape(self):
        module = load_readiness_module()
        summary = module.build_summary("stratford-upon-avon")
        self.assertEqual(summary["market"], "stratford-upon-avon")
        self.assertIn(summary["status"], {"ready", "warning", "blocked"})
        self.assertGreater(summary["counts"]["total_establishments"], 0)
        self.assertGreater(summary["counts"]["total_scored"], 0)
        self.assertGreater(summary["counts"]["total_public_ranking_venues"], 0)
        self.assertEqual(
            summary["counts"]["aliases_unresolved_without_guardrail"],
            0,
            "Alias FHRSIDs must not be unresolved without an explicit guardrail."
        )

    def test_vintner_guardrail_remains_visible_until_canonical_rebuild(self):
        module = load_readiness_module()
        summary = module.build_summary("stratford-upon-avon")
        known = {str(v.get("fhrsid")): v for v in summary["known_missing_venues"]}
        if "503480" not in known:
            self.skipTest("Vintner has been canonicalised; guardrail can now be removed after verifying rankings.")
        self.assertEqual(known["503480"].get("status"), "needs_canonical_rebuild")
        self.assertIn("Vintner", known["503480"].get("public_name", ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
