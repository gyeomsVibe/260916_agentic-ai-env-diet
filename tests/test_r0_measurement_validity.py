"""Fixed R0 acceptance for P05 measurement validity.

The pilot runs this file from the original source tree while importing the
candidate ``measure_p05.py`` from staging.  The worker therefore cannot make
the gate pass by editing its staged copy of this test.
"""

from __future__ import annotations

import copy
import importlib.util
import os
import unittest
from pathlib import Path


def _load_target():
    default = Path(__file__).resolve().parents[1] / ".coord" / "runs" / "measure_p05.py"
    target = Path(os.environ.get("R0_MEASURE_TARGET", default)).resolve()
    spec = importlib.util.spec_from_file_location("r0_measure_target", target)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load measurement target: {target}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TARGET = _load_target()


def valid_evidence() -> dict:
    summary = {
        "task_id": "P05-R0-B",
        "run_id": "P05-R0-B-a001",
        "source_hash": "sha256:baseline",
        "state": "SUCCEEDED",
        "error_class": "NONE",
        "effect_state": "CONFIRMED",
        "promotion": "APPLIED",
        "bundle_id": "bundle-001",
        "acceptance_exit": 0,
        "verdict_hint": "PASS",
    }
    ledger = {
        "task_id": "P05-R0-B",
        "run_id": "P05-R0-B-a001",
        "source_hash": "sha256:baseline",
        "bundle_id": "bundle-001",
        "attempt_state": "SUCCEEDED",
        "delivery_state": "ACKED",
        "lease_state": "RELEASED",
    }
    return {
        "task": "P05",
        "baseline_source_hash": "sha256:baseline",
        "A": {
            "task": "P05",
            "source_hash": "sha256:baseline",
            "codex_exit": 0,
            "forbidden_infrastructure_errors": [],
            "direct_acceptance_exit": 0,
            "expected_behavior_passed": True,
            "input_tokens": 1000,
            "cached_input_tokens": 400,
            "wall_s": 20.0,
        },
        "B": {
            "task": "P05",
            "source_hash": "sha256:baseline",
            "codex_exit": 0,
            "forbidden_infrastructure_errors": [],
            "direct_acceptance_exit": 0,
            "expected_behavior_passed": True,
            "input_tokens": 700,
            "cached_input_tokens": 300,
            "wall_s": 10.0,
            "pilot_summary": summary,
            "ledger_terminal": ledger,
            "post_apply_acceptance_exit": 0,
            "pre_run_attempt_ids": [],
        },
    }


class R0MeasurementValidityTests(unittest.TestCase):
    def evaluate(self, evidence: dict) -> dict:
        result = TARGET.evaluate_measurement(evidence)
        self.assertIsInstance(result, dict)
        return result

    def assert_invalid(self, evidence: dict, status: str) -> None:
        result = self.evaluate(evidence)
        self.assertEqual(status, result["status"])
        self.assertNotIn("savings", result)
        self.assertNotEqual("MEASURED_AND_VERIFIED", result["status"])

    def test_valid_run_computes_identity_and_savings_from_evidence(self) -> None:
        result = self.evaluate(valid_evidence())
        self.assertEqual("MEASURED_AND_VERIFIED", result["status"])
        self.assertTrue(result["task_identical"])
        self.assertTrue(result["starting_state_identical"])
        self.assertEqual(50.0, result["savings"]["wall_reduction_pct"])
        self.assertEqual(30.0, result["savings"]["input_token_reduction_pct"])
        # noncached A = 1000-400 = 600, B = 700-300 = 400 -> (600-400)/600 = 33.3%
        self.assertEqual(33.3, result["savings"]["noncached_input_token_reduction_pct"])

    def test_missing_summary_is_invalid_setup_even_with_tools_and_tests(self) -> None:
        evidence = valid_evidence()
        evidence["B"].update({"pilot_summary": None, "tool_call_events": 9, "test_count": 999})
        self.assert_invalid(evidence, "INVALID_SETUP")

    def test_codex_failure_and_forbidden_infrastructure_error_are_invalid(self) -> None:
        failed = valid_evidence()
        failed["B"]["codex_exit"] = 1
        self.assert_invalid(failed, "INVALID_CODEX_EXECUTION")
        infra = valid_evidence()
        infra["B"]["forbidden_infrastructure_errors"] = ["helper_unknown_error"]
        self.assert_invalid(infra, "INVALID_INFRASTRUCTURE")

    def test_baseline_hash_mismatch_is_invalid_measurement(self) -> None:
        evidence = valid_evidence()
        evidence["B"]["source_hash"] = "sha256:different"
        self.assert_invalid(evidence, "INVALID_START_STATE")

    def test_direct_behavior_not_test_count_controls_acceptance(self) -> None:
        evidence = valid_evidence()
        evidence["B"].update({"expected_behavior_passed": False, "tool_call_events": 4, "test_count": 999})
        self.assert_invalid(evidence, "INVALID_ACCEPTANCE")

    def test_summary_identity_mismatch_is_rejected(self) -> None:
        for key, value in (
            ("task_id", "other-task"),
            ("run_id", "other-run"),
            ("source_hash", "sha256:other"),
            ("bundle_id", "other-bundle"),
        ):
            with self.subTest(key=key):
                evidence = valid_evidence()
                evidence["B"]["pilot_summary"][key] = value
                self.assert_invalid(evidence, "INVALID_PILOT_IDENTITY")

    def test_summary_and_ledger_must_match_top_level_task_and_baseline(self) -> None:
        # r3 counterexample: a consistent summary+ledger from another task or a stale baseline must not pass.
        for key, value in (("task_id", "P99-WRONG"), ("source_hash", "sha256:stale")):
            with self.subTest(key=key):
                evidence = valid_evidence()
                evidence["B"]["pilot_summary"][key] = value
                evidence["B"]["ledger_terminal"][key] = value
                self.assert_invalid(evidence, "INVALID_PILOT_IDENTITY")

    def test_savings_are_computed_not_hardcoded(self) -> None:
        evidence = valid_evidence()
        evidence["A"].update({"input_tokens": 2000, "cached_input_tokens": 1000, "wall_s": 40.0})
        evidence["B"].update({"input_tokens": 1500, "cached_input_tokens": 1250, "wall_s": 30.0})
        result = self.evaluate(evidence)
        self.assertEqual("MEASURED_AND_VERIFIED", result["status"])
        self.assertEqual(25.0, result["savings"]["wall_reduction_pct"])
        self.assertEqual(25.0, result["savings"]["input_token_reduction_pct"])
        self.assertEqual(75.0, result["savings"]["noncached_input_token_reduction_pct"])

    def test_stale_ledger_from_before_the_b_run_is_rejected(self) -> None:
        # r6 P1: a B run that did nothing must not borrow an earlier successful attempt.
        evidence = valid_evidence()
        evidence["B"]["pre_run_attempt_ids"] = ["P05-R0-B-a001"]
        self.assert_invalid(evidence, "INVALID_STALE_RUN")

    def test_missing_pre_run_snapshot_is_rejected(self) -> None:
        evidence = valid_evidence()
        del evidence["B"]["pre_run_attempt_ids"]
        self.assert_invalid(evidence, "INVALID_STALE_RUN")

    def test_nonterminal_or_mismatched_ledger_is_rejected(self) -> None:
        evidence = valid_evidence()
        evidence["B"]["ledger_terminal"]["attempt_state"] = "RUNNING"
        self.assert_invalid(evidence, "INVALID_LEDGER")
        # Any summary<->ledger disagreement is one rule: INVALID_PILOT_IDENTITY (r4: no format heuristics).
        for bundle in ("other", "bundle-002", "bundle002"):
            with self.subTest(bundle=bundle):
                evidence = valid_evidence()
                evidence["B"]["ledger_terminal"]["bundle_id"] = bundle
                self.assert_invalid(evidence, "INVALID_PILOT_IDENTITY")

    def test_pass_without_applied_and_post_apply_acceptance_is_rejected(self) -> None:
        evidence = valid_evidence()
        evidence["B"]["pilot_summary"]["promotion"] = "DRY_RUN_PASSED"
        self.assert_invalid(evidence, "INVALID_PROMOTION")
        evidence = valid_evidence()
        evidence["B"]["post_apply_acceptance_exit"] = 2
        self.assert_invalid(evidence, "INVALID_POST_ACCEPTANCE")


if __name__ == "__main__":
    unittest.main()
