from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest

from v7_harness.control import ControlConfig, run_control
from v7_harness.isolation.manifest import build_manifest


class FakePilotRunner:
    """A deterministic local-process double; it never executes a worker."""

    def __init__(self, config: ControlConfig, *, defect: str | None = None) -> None:
        self.config = config
        self.defect = defect
        self.calls: list[tuple[list[str], str | None]] = []
        self.bundle_id = "b" * 64
        self.run_id = f"{config.task_id}-a001"

    def _write_first_run(self) -> None:
        run_dir = self.config.work_dir / "runs" / self.config.task_id
        run_dir.mkdir(parents=True, exist_ok=True)
        source_hash = build_manifest(self.config.source_dir).manifest_hash
        task_id = self.config.task_id
        run_id = self.run_id
        bundle_id = self.bundle_id

        if self.defect == "task_mismatch":
            task_id = "WRONG-TASK"
        elif self.defect == "run_mismatch":
            run_id = "WRONG-RUN"
        elif self.defect == "source_mismatch":
            source_hash = "0" * 64
        elif self.defect == "bundle_mismatch":
            bundle_id = "c" * 64

        summary = {
            "state": "SUCCEEDED",
            "error_class": None,
            "effect_state": "NONE",
            "promotion": "DRY_RUN_PASSED",
            "bundle_id": self.bundle_id,
            "changed_files": ["calc.py"],
            "acceptance_exit": 0,
            "verdict_hint": "PASS",
        }
        if self.defect == "unknown_effect":
            summary["effect_state"] = "UNKNOWN"
        if self.defect != "missing_summary":
            text = "{" if self.defect == "non_json_summary" else json.dumps(summary)
            (run_dir / "summary.json").write_text(text, encoding="utf-8")

        identity = {
            "task_id": task_id,
            "run_id": run_id,
            "source_hash": f"sha256:{source_hash}",
            "bundle_id": bundle_id,
        }
        (run_dir / "identity.json").write_text(json.dumps(identity), encoding="utf-8")

        db_path = self.config.work_dir / "coord.sqlite3"
        with sqlite3.connect(db_path) as conn:
            conn.executescript(
                "CREATE TABLE attempts(attempt_id TEXT, task_id TEXT, state TEXT);"
                "CREATE TABLE checkpoints(attempt_id TEXT, base_manifest_hash TEXT, artifact_set_hash TEXT);"
            )
            ledger_run = self.run_id if self.defect != "run_mismatch" else "LEDGER-RUN"
            conn.execute(
                "INSERT INTO attempts VALUES(?,?,?)",
                (ledger_run, self.config.task_id, "SUCCEEDED"),
            )
            conn.execute(
                "INSERT INTO checkpoints VALUES(?,?,?)",
                (ledger_run, build_manifest(self.config.source_dir).manifest_hash, self.bundle_id),
            )
            if self.defect == "stale_ledger":
                conn.execute(
                    "INSERT INTO attempts VALUES(?,?,?)",
                    (f"{self.config.task_id}-old", self.config.task_id, "SUCCEEDED"),
                )
        if self.defect == "stale_ledger":
            os.utime(db_path, (1, 1))

    def __call__(
        self,
        argv: list[str],
        *,
        cwd: str | None = None,
        capture_output: bool = True,
        text: bool = True,
        timeout: int | float | None = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        del capture_output, text, timeout, check
        self.calls.append((list(argv), cwd))
        if len(self.calls) == 1:
            if self.defect == "not_started":
                raise FileNotFoundError("pilot executable unavailable")
            if self.defect == "timeout":
                raise subprocess.TimeoutExpired(argv, 1)
            self._write_first_run()
            stderr = "helper_unknown_error: setup refresh had errors" if self.defect == "helper_exit_zero" else ""
            return subprocess.CompletedProcess(argv, 0, stdout="{}", stderr=stderr)

        if "--approve" in argv:
            approval = {
                "state": "SUCCEEDED",
                "effect_state": "NONE",
                "verdict_hint": "PASS",
                "bundle_id": self.bundle_id,
                "promotion": "APPLIED",
            }
            if self.defect == "pass_without_applied":
                approval["promotion"] = "DRY_RUN_PASSED"
            if self.defect == "approval_mismatch":
                approval["promotion"] = "APPROVAL_MISMATCH"
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(approval), stderr="")

        exit_code = 1 if self.defect == "post_acceptance_failure" else 0
        return subprocess.CompletedProcess(argv, exit_code, stdout="", stderr="acceptance failed" if exit_code else "")


class ApplyingFakePilotRunner(FakePilotRunner):
    """Simulate the independently observable source mutation of APPLIED."""

    def __init__(self, config: ControlConfig, *, extra_change: bool = False, defect: str | None = None) -> None:
        super().__init__(config, defect=defect)
        self.extra_change = extra_change

    def __call__(self, argv: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        result = super().__call__(argv, **kwargs)
        if "--approve" in argv:
            approval = json.loads(result.stdout)
            if approval.get("promotion") == "APPLIED":
                (self.config.source_dir / "calc.py").write_text("VALUE = 2\n", encoding="utf-8")
                if self.extra_change:
                    (self.config.source_dir / "undeclared.py").write_text("UNDECLARED = True\n", encoding="utf-8")
        return result


class MinimalControlLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "calc.py").write_text("VALUE = 1\n", encoding="utf-8")
        self.prompt = self.root / "prompt.md"
        self.prompt.write_text("Make the requested deterministic change.", encoding="utf-8")
        self.config = ControlConfig(
            task_id="R2-LIVE-001",
            title="R2 deterministic controller",
            source_dir=self.source,
            prompt_file=self.prompt,
            work_dir=self.root / "fresh-work",
            agy_command=["python", "fake_agy.py"],
            accept_cmd="python -m unittest -q",
            watch_roots=[self.root / "home", self.root / "temp"],
            timeout_s=30,
        )
        self.before = build_manifest(self.source).manifest_hash

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _run(self, defect: str | None = None):
        runner = FakePilotRunner(self.config, defect=defect)
        receipt = run_control(self.config, runner=runner)
        return receipt, runner

    def _assert_failed_closed(self, defect: str, expected: str) -> None:
        receipt, runner = self._run(defect)
        self.assertFalse(receipt["ok"])
        self.assertNotEqual(receipt["exit_code"], 0)
        self.assertEqual(receipt["error_class"], expected)
        self.assertLessEqual(len(runner.calls), 1, "failure must not reach approval or post-apply acceptance")
        self.assertEqual(build_manifest(self.source).manifest_hash, self.before)

    def test_happy_path_runs_one_worker_exact_approval_and_post_acceptance(self) -> None:
        runner = ApplyingFakePilotRunner(self.config)
        receipt = run_control(self.config, runner=runner)
        self.assertTrue(receipt["ok"])
        self.assertEqual(receipt["exit_code"], 0)
        self.assertEqual(receipt["promotion"], "APPLIED")
        self.assertEqual(receipt["post_acceptance_exit"], 0)
        self.assertEqual(receipt["pilot_invocations"], 1)
        self.assertEqual(receipt["approval_invocations"], 1)
        self.assertEqual(len(runner.calls), 3)
        first, approval, acceptance = (call[0] for call in runner.calls)
        self.assertEqual(first[:4], [first[0], "-m", "v7_harness.cli", "pilot"])
        self.assertEqual(first.count("run"), 1)
        self.assertNotIn("--approve", first)
        self.assertEqual(approval[approval.index("--approve") + 1], "b" * 64)
        self.assertEqual(acceptance, ["python", "-m", "unittest", "-q"])
        self.assertNotEqual(build_manifest(self.source).manifest_hash, self.before)

    def test_applied_without_observed_source_change_fails_closed(self) -> None:
        receipt, runner = self._run()
        self.assertFalse(receipt["ok"])
        self.assertNotEqual(receipt["exit_code"], 0)
        self.assertEqual(receipt["error_class"], "APPLY_NOT_OBSERVED")
        self.assertEqual(len(runner.calls), 2, "post-apply acceptance must not run without observed apply")
        self.assertEqual(build_manifest(self.source).manifest_hash, self.before)

    def test_applied_with_undeclared_source_change_fails_closed(self) -> None:
        runner = ApplyingFakePilotRunner(self.config, extra_change=True)
        receipt = run_control(self.config, runner=runner)
        self.assertFalse(receipt["ok"])
        self.assertNotEqual(receipt["exit_code"], 0)
        self.assertEqual(receipt["error_class"], "APPLY_MISMATCH")
        self.assertEqual(len(runner.calls), 2, "post-apply acceptance must not run after apply mismatch")

    def test_pilot_process_not_started_is_structured_failure(self) -> None:
        self._assert_failed_closed("not_started", "PILOT_NOT_STARTED")

    def test_missing_and_non_json_summary_fail_closed(self) -> None:
        for defect, expected in (("missing_summary", "SUMMARY_MISSING"), ("non_json_summary", "SUMMARY_INVALID")):
            with self.subTest(defect=defect):
                self._assert_failed_closed(defect, expected)
                self.config.work_dir = self.root / f"fresh-{defect}"

    def test_stale_ledger_is_rejected(self) -> None:
        self._assert_failed_closed("stale_ledger", "STALE_LEDGER")

    def test_task_run_source_and_bundle_identity_mismatches_are_rejected(self) -> None:
        cases = {
            "task_mismatch": "TASK_ID_MISMATCH",
            "run_mismatch": "RUN_ID_MISMATCH",
            "source_mismatch": "SOURCE_ID_MISMATCH",
            "bundle_mismatch": "BUNDLE_ID_MISMATCH",
        }
        for defect, expected in cases.items():
            with self.subTest(defect=defect):
                self._assert_failed_closed(defect, expected)
                self.config.work_dir = self.root / f"fresh-{defect}"

    def test_pass_without_applied_and_approval_mismatch_fail(self) -> None:
        for defect, expected in (
            ("pass_without_applied", "PASS_WITHOUT_APPLIED"),
            ("approval_mismatch", "APPROVAL_MISMATCH"),
        ):
            with self.subTest(defect=defect):
                receipt, runner = self._run(defect)
                self.assertFalse(receipt["ok"])
                self.assertNotEqual(receipt["exit_code"], 0)
                self.assertEqual(receipt["error_class"], expected)
                self.assertEqual(len(runner.calls), 2)
                self.assertEqual(build_manifest(self.source).manifest_hash, self.before)
                self.config.work_dir = self.root / f"fresh-{defect}"

    def test_post_apply_acceptance_failure_is_not_success(self) -> None:
        runner = ApplyingFakePilotRunner(self.config, defect="post_acceptance_failure")
        receipt = run_control(self.config, runner=runner)
        self.assertFalse(receipt["ok"])
        self.assertNotEqual(receipt["exit_code"], 0)
        self.assertEqual(receipt["error_class"], "POST_APPLY_ACCEPTANCE_FAILED")
        self.assertEqual(len(runner.calls), 3)

    def test_raw_helper_error_with_exit_zero_is_not_success(self) -> None:
        self._assert_failed_closed("helper_exit_zero", "HELPER_FAILURE")

    def test_existing_work_dir_rejects_duplicate_before_process_start(self) -> None:
        self.config.work_dir.mkdir()
        runner = FakePilotRunner(self.config)
        receipt = run_control(self.config, runner=runner)
        self.assertFalse(receipt["ok"])
        self.assertNotEqual(receipt["exit_code"], 0)
        self.assertEqual(receipt["error_class"], "WORK_DIR_NOT_FRESH")
        self.assertEqual(runner.calls, [])

    def test_timeout_and_unknown_effect_fail_closed(self) -> None:
        for defect, expected in (("timeout", "PILOT_TIMEOUT"), ("unknown_effect", "UNKNOWN_EFFECT")):
            with self.subTest(defect=defect):
                self._assert_failed_closed(defect, expected)
                self.config.work_dir = self.root / f"fresh-{defect}"


if __name__ == "__main__":
    unittest.main()
