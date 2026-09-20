"""M4 acceptance tests (failing first): one-turn verdict, acceptance command, lease release, reconcile."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from v7_harness.pilot import PilotConfig, reconcile_pilot, run_pilot

FAKE_AGY = [sys.executable, str(Path(__file__).parent / "fixtures" / "fake_agy.py")]
ORIGINAL = "def mul(a, b):\n    return a * b\n"
PASS_CMD = f'"{sys.executable}" -c "import calc; assert calc.add(2, 3) == 5"'
FAIL_CMD = f'"{sys.executable}" -c "import sys; sys.exit(3)"'


class M4EfficiencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "sample"
        self.source.mkdir()
        (self.source / "calc.py").write_text(ORIGINAL, encoding="utf-8")
        self.home = self.root / "home"
        self.home.mkdir()
        self.work = self.root / "work"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _run(self, mode: str = "success", **overrides) -> dict:
        values = dict(
            task_id="P03",
            title="m4",
            prompt="Add add(a, b) to calc.py.",
            source_dir=self.source,
            work_dir=self.work,
            agy_command=FAKE_AGY,
            watch_roots=[self.home],
            print_timeout_s=60,
            approve_bundle_id=None,
            accept_cmd=None,
        )
        values.update(overrides)
        with mock.patch.dict(os.environ, {"FAKE_AGY_MODE": mode, "FAKE_AGY_OUTSIDE_DIR": str(self.home)}):
            return run_pilot(PilotConfig(**values))

    def _db(self) -> sqlite3.Connection:
        return sqlite3.connect(f"file:{self.work / 'coord.sqlite3'}?mode=ro", uri=True)

    # --- one-turn verdict ---------------------------------------------------
    def test_acceptance_pass_gives_verdict_pass(self) -> None:
        summary = self._run(accept_cmd=PASS_CMD)
        self.assertEqual(0, summary["acceptance_exit"])
        self.assertGreaterEqual(len(summary), 14)
        self.assertLessEqual(len(summary), 18)

    def test_acceptance_failure_gives_rework_and_blocks_approval(self) -> None:
        first = self._run(accept_cmd=FAIL_CMD)
        self.assertEqual(3, first["acceptance_exit"])
        self.assertEqual("REWORK", first["verdict_hint"])
        second = self._run(accept_cmd=FAIL_CMD, approve_bundle_id=first["bundle_id"])
        self.assertEqual("BLOCKED", second["promotion"])
        self.assertEqual(ORIGINAL, (self.source / "calc.py").read_text(encoding="utf-8"))

    def test_acceptance_runs_in_staging_not_source(self) -> None:
        summary = self._run(accept_cmd=PASS_CMD)  # source calc.py has no add(); passes only in staging
        self.assertEqual("PASS", summary["verdict_hint"])

    def test_failed_agy_run_is_blocked_verdict_without_running_acceptance(self) -> None:
        summary = self._run("error503_write", accept_cmd=PASS_CMD)
        self.assertEqual("BLOCKED", summary["verdict_hint"])
        self.assertIsNone(summary["acceptance_exit"])

    def test_no_accept_cmd_keeps_verdict_unknown(self) -> None:
        summary = self._run()
        self.assertIsNone(summary["acceptance_exit"])
        self.assertEqual("NEEDS_ACCEPTANCE", summary["verdict_hint"])

    # --- lease release ------------------------------------------------------
    def test_lease_released_after_finished_run(self) -> None:
        self._run(accept_cmd=PASS_CMD)
        with self._db() as db:
            states = [row[0] for row in db.execute("SELECT state FROM leases")]
        self.assertTrue(states)
        self.assertNotIn("ACTIVE", states)

    # --- reconcile interrupted run -----------------------------------------
    def _interrupt(self) -> None:
        with mock.patch("v7_harness.pilot.AgyProcessLauncher.launch", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self._run()

    def test_interrupted_run_is_reconciled_and_rerun_executes_fresh(self) -> None:
        self._interrupt()
        with self._db() as db:
            self.assertEqual("CLAIMED", db.execute("SELECT state FROM deliveries").fetchone()[0])
        report = reconcile_pilot(work_dir=self.work, task_id="P03")
        self.assertEqual("ABANDONED", report["state"])
        self.assertEqual(1, report["reconciled_attempts"])
        with self._db() as db:
            self.assertEqual({"DEAD"}, {r[0] for r in db.execute("SELECT state FROM deliveries")})
            self.assertNotIn("ACTIVE", [r[0] for r in db.execute("SELECT state FROM leases")])
            self.assertNotIn("RUNNING", [r[0] for r in db.execute("SELECT state FROM attempts")])
        rerun = self._run(accept_cmd=PASS_CMD)
        self.assertEqual("SUCCEEDED", rerun["state"])
        self.assertNotIn("replayed", rerun)
        with self._db() as db:
            attempts = sorted(r[0] for r in db.execute("SELECT attempt_id FROM attempts"))
        self.assertEqual(2, len(attempts))

    def test_reconcile_never_touches_source_or_succeeded_runs(self) -> None:
        done = self._run(accept_cmd=PASS_CMD)
        report = reconcile_pilot(work_dir=self.work, task_id="P03")
        self.assertEqual(0, report["reconciled_attempts"])
        self.assertEqual("NOTHING_TO_RECONCILE", report["state"])
        replay = self._run(accept_cmd=PASS_CMD)
        self.assertTrue(replay["replayed"])
        self.assertEqual(done["bundle_id"], replay["bundle_id"])
        self.assertEqual(ORIGINAL, (self.source / "calc.py").read_text(encoding="utf-8"))

    def test_rerun_while_interrupted_without_reconcile_is_refused(self) -> None:
        self._interrupt()
        summary = self._run()
        self.assertEqual("NEEDS_RECONCILIATION", summary["error_class"])
        self.assertEqual("BLOCKED", summary["verdict_hint"])


class M4CliTests(unittest.TestCase):
    def test_cli_accept_cmd_and_reconcile_subcommand(self) -> None:
        from v7_harness import cli

        parser = cli.build_parser()
        run_args = parser.parse_args(["pilot", "run", "--task", "P03", "--source", ".", "--prompt", "x", "--accept-cmd", "python -m unittest"])
        self.assertEqual("python -m unittest", run_args.accept_cmd)
        rec_args = parser.parse_args(["pilot", "reconcile", "--task", "P02", "--work-dir", ".coord/pilot"])
        with mock.patch("v7_harness.pilot.reconcile_pilot", return_value={"state": "ABANDONED", "reconciled_attempts": 1}) as fake:
            self.assertEqual(0, rec_args.func(rec_args))
        fake.assert_called_once()


if __name__ == "__main__":
    unittest.main()
