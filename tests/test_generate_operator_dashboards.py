#!/usr/bin/env python3
"""Offline tests for generated operator dashboards."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_module():
    path = ROOT / "scripts" / "generate_operator_dashboards.py"
    spec = importlib.util.spec_from_file_location("generate_operator_dashboards", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class OperatorDashboardGeneratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = load_module()

    def test_lambs_dashboard_builds_with_history_shape(self):
        target = {
            "venue_slug": "lambs",
            "venue": "Lambs",
            "market": "stratford-upon-avon",
            "postcode": "CV37 6EF",
            "status": "ready",
            "client_status": "review",
            "source_report": "/outputs/examples/Lambs_full_operator_report_with_tracking_2026-04.md",
        }
        snapshot = self.generator.build_dashboard(target, "2026-04")
        self.assertEqual(snapshot["venue_slug"], "lambs")
        self.assertEqual(snapshot["month"], "2026-04")
        self.assertIn("history", snapshot)
        self.assertIn("movement", snapshot)
        self.assertGreaterEqual(len(snapshot["history"]), 1)
        self.assertEqual(snapshot["history"][-1]["month"], "2026-04")
        self.assertIn("summary", snapshot["movement"])
        self.assertGreater(snapshot["headline"]["overall_total"], 0)
        self.assertIsNotNone(snapshot["scores"]["public_rcs"])

    def test_missing_dashboard_target_is_skipped_when_not_strict(self):
        manifest = self.generator.generate(month_override="2026-04", venue_filter="definitely-not-a-real-target", strict=False)
        self.assertEqual(manifest["dashboards"], [])
        self.assertIn("errors", manifest)

    def test_rank_delta_positive_means_rank_improved(self):
        history = [
            {"month": "2026-04", "overall_rank": 10, "category_rank": 4, "public_rcs": 8.9, "google_review_count": 100},
            {"month": "2026-05", "overall_rank": 8, "category_rank": 3, "public_rcs": 9.1, "google_review_count": 120},
        ]
        movement = self.generator.compute_deltas(history)
        self.assertEqual(movement["overall_rank_delta"], 2)
        self.assertEqual(movement["category_rank_delta"], 1)
        self.assertEqual(movement["public_rcs_delta"], 0.2)
        self.assertEqual(movement["review_count_delta"], 20)


if __name__ == "__main__":
    unittest.main(verbosity=2)
