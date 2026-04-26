#!/usr/bin/env python3
"""Offline tests for the generic DayDine market-pipeline runner."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_module():
    path = ROOT / "scripts" / "run_market_pipeline.py"
    spec = importlib.util.spec_from_file_location("run_market_pipeline", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RunMarketPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline = load_module()

    def test_resolves_configured_public_market(self):
        area = self.pipeline.resolve_area("stratford-upon-avon")
        self.assertEqual(area["slug"], "stratford-upon-avon")
        self.assertTrue(area["public"])

    def test_resolves_legacy_slug(self):
        area = self.pipeline.resolve_area("stratford-on-avon")
        self.assertEqual(area["slug"], "stratford-upon-avon")

    def test_data_prefix_is_config_driven_with_legacy_fallback(self):
        area = self.pipeline.resolve_area("stratford-upon-avon")
        self.assertEqual(self.pipeline.data_prefix_for_area(area), "stratford")
        custom = {"slug": "oxford", "display_name": "Oxford", "data_source_prefix": "oxford"}
        self.assertEqual(self.pipeline.data_prefix_for_area(custom), "oxford")

    def test_file_plan_uses_market_prefix(self):
        plan = self.pipeline.file_plan("leamington")
        self.assertEqual(plan["establishments"], "leamington_establishments.json")
        self.assertEqual(plan["scores_json"], "leamington_rcs_v4_scores.json")
        self.assertEqual(plan["scores_csv"], "leamington_rcs_v4_scores.csv")

    def test_next_steps_for_missing_source_are_actionable(self):
        steps = self.pipeline.next_steps_for(
            "blocked_missing_source",
            "oxford",
            self.pipeline.file_plan("oxford"),
        )
        joined = "\n".join(steps)
        self.assertIn("oxford_establishments.json", joined)
        self.assertIn("data/ranking_areas.json", joined)
        self.assertIn("run_market_pipeline.py", joined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
