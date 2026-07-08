"""Unit tests for the statistical engine (core/stats.py)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.stats import (  # noqa: E402
    compute_pass_rate,
    detect_regression,
    fisher_exact_test,
    flakiness_score,
    wilson_score_interval,
)


class WilsonScoreIntervalTests(unittest.TestCase):
    def test_interval_bounded_in_unit_range(self) -> None:
        lower, upper = wilson_score_interval(17, 20)
        self.assertGreaterEqual(lower, 0.0)
        self.assertLessEqual(upper, 1.0)
        self.assertLess(lower, upper)

    def test_small_sample_has_wider_interval_than_large_sample(self) -> None:
        small_lower, small_upper = wilson_score_interval(4, 5)
        large_lower, large_upper = wilson_score_interval(80, 100)
        self.assertGreater(small_upper - small_lower, large_upper - large_lower)

    def test_perfect_score_lower_bound_below_one(self) -> None:
        lower, upper = wilson_score_interval(20, 20)
        self.assertLessEqual(upper, 1.0)
        self.assertLess(lower, 1.0)
        self.assertGreater(lower, 0.0)

    def test_zero_total_returns_zero_interval(self) -> None:
        self.assertEqual(wilson_score_interval(0, 0), (0.0, 0.0))


class ComputePassRateTests(unittest.TestCase):
    def test_meets_threshold_true(self) -> None:
        result = compute_pass_rate(17, 20, 0.8)
        self.assertAlmostEqual(result.pass_rate, 0.85)
        self.assertTrue(result.meets_threshold)
        self.assertIn("PASS", result.verdict)

    def test_meets_threshold_false(self) -> None:
        result = compute_pass_rate(10, 20, 0.8)
        self.assertFalse(result.meets_threshold)
        self.assertIn("FAIL", result.verdict)

    def test_zero_total_raises(self) -> None:
        with self.assertRaises(ValueError):
            compute_pass_rate(0, 0, 0.8)


class FisherExactTestTests(unittest.TestCase):
    def test_obviously_different_rates_significant(self) -> None:
        p_value = fisher_exact_test(baseline_passes=19, baseline_total=20, candidate_passes=5, candidate_total=20)
        self.assertLess(p_value, 0.05)

    def test_identical_rates_not_significant(self) -> None:
        p_value = fisher_exact_test(baseline_passes=15, baseline_total=20, candidate_passes=15, candidate_total=20)
        self.assertGreaterEqual(p_value, 0.05)

    def test_slightly_different_small_sample_not_significant(self) -> None:
        p_value = fisher_exact_test(baseline_passes=9, baseline_total=10, candidate_passes=8, candidate_total=10)
        self.assertGreaterEqual(p_value, 0.05)

    def test_p_value_bounded(self) -> None:
        p_value = fisher_exact_test(10, 10, 10, 10)
        self.assertGreaterEqual(p_value, 0.0)
        self.assertLessEqual(p_value, 1.0)

    def test_symmetric(self) -> None:
        p1 = fisher_exact_test(19, 20, 5, 20)
        p2 = fisher_exact_test(5, 20, 19, 20)
        self.assertAlmostEqual(p1, p2, places=9)


class DetectRegressionTests(unittest.TestCase):
    def test_significant_drop_flagged_as_regression(self) -> None:
        result = detect_regression(baseline_passes=19, baseline_total=20, candidate_passes=5, candidate_total=20)
        self.assertTrue(result.is_regression)
        self.assertIn("REGRESSION", result.verdict)

    def test_improvement_not_flagged_as_regression(self) -> None:
        result = detect_regression(baseline_passes=5, baseline_total=20, candidate_passes=19, candidate_total=20)
        self.assertFalse(result.is_regression)

    def test_noise_not_flagged_as_regression(self) -> None:
        result = detect_regression(baseline_passes=15, baseline_total=20, candidate_passes=14, candidate_total=20)
        self.assertFalse(result.is_regression)


class FlakinessScoreTests(unittest.TestCase):
    def test_consistent_rates_score_zero(self) -> None:
        self.assertEqual(flakiness_score([0.9, 0.9, 0.9, 0.9]), 0.0)

    def test_alternating_rates_score_near_one(self) -> None:
        score = flakiness_score([0.0, 1.0, 0.0, 1.0])
        self.assertGreater(score, 0.9)

    def test_single_sample_scores_zero(self) -> None:
        self.assertEqual(flakiness_score([0.85]), 0.0)

    def test_moderate_variance_between_bounds(self) -> None:
        score = flakiness_score([0.9, 0.7, 0.85, 0.6])
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)


if __name__ == "__main__":
    unittest.main()
