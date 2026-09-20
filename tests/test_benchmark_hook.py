"""
Tests for Benchmark Hook (Acceptance #9).
"""

import time
import unittest

from v7_harness.benchmark_hook import BenchmarkHook


class TestBenchmarkHook(unittest.TestCase):

    def setUp(self):
        self.hook = BenchmarkHook("test_comparison")

    def test_benchmark_runs_and_labels_savings_unmeasured(self):
        def baseline_fn():
            time.sleep(0.01)
            return sum(i for i in range(1000))

        def candidate_fn():
            time.sleep(0.005)
            return sum(i for i in range(1000))

        result = self.hook.run_comparison(baseline_fn, candidate_fn)

        self.assertTrue(result.baseline_success)
        self.assertTrue(result.candidate_success)
        self.assertGreater(result.baseline_duration_sec, 0)
        self.assertGreater(result.candidate_duration_sec, 0)
        # Global rule adherence: savings MUST be UNMEASURED
        self.assertEqual(result.cost_savings, "UNMEASURED")
        self.assertEqual(result.token_savings, "UNMEASURED")
        self.assertIsNotNone(result.speedup_ratio)

    def test_benchmark_handles_candidate_failure(self):
        def baseline_fn():
            return 1

        def failing_candidate_fn():
            raise RuntimeError("candidate blew up")

        result = self.hook.run_comparison(baseline_fn, failing_candidate_fn)
        self.assertTrue(result.baseline_success)
        self.assertFalse(result.candidate_success)
        self.assertEqual(result.cost_savings, "UNMEASURED")
        self.assertEqual(result.token_savings, "UNMEASURED")
        self.assertIsNone(result.speedup_ratio)


if __name__ == "__main__":
    unittest.main()
