"""B44 fixed acceptance: a real (fake-agy) pilot run must yield independently cross-checkable identity.

Ledger identity must come from SQLite (attempts + checkpoints), not from summary.json, so that
evaluate_measurement compares two independent sources.
"""

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from v7_harness.isolation.promotion import build_manifest
from v7_harness.pilot import PilotConfig, run_pilot

ROOT = Path(__file__).resolve().parents[1]
FAKE_AGY = [sys.executable, str(ROOT / "tests" / "fixtures" / "fake_agy.py")]


def _load_measure():
    target = Path(os.environ.get("R0_MEASURE_TARGET", ROOT / ".coord" / "runs" / "measure_p05.py"))
    spec = importlib.util.spec_from_file_location("b44_measure", target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LiveIdentityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.source = root / "sample"
        self.source.mkdir()
        (self.source / "calc.py").write_text("def mul(a, b):\n    return a * b\n", encoding="utf-8")
        self.home = root / "home"
        self.home.mkdir()
        self.work = root / "work"
        self.base_hash = build_manifest(self.source).manifest_hash

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _run(self, approve=None) -> dict:
        config = PilotConfig(
            task_id="P05-R0-B", title="t", prompt="Add add(a, b) to calc.py.",
            source_dir=self.source, work_dir=self.work, agy_command=FAKE_AGY,
            watch_roots=[self.home], print_timeout_s=60, approve_bundle_id=approve,
        )
        env = {"FAKE_AGY_MODE": "success", "FAKE_AGY_OUTSIDE_DIR": str(self.home)}
        with mock.patch.dict(os.environ, env):
            return run_pilot(config)

    def test_ledger_identity_is_real_and_independent_of_summary(self) -> None:
        first = self._run()
        self._run(approve=first["bundle_id"])
        measure = _load_measure()
        ledger = measure.read_terminal_ledger(self.work, "P05-R0-B")
        self.assertIsNotNone(ledger, "ledger read must not silently fail")
        self.assertEqual("P05-R0-B", ledger["task_id"])
        self.assertNotIn(ledger["source_hash"], (None, "", "UNKNOWN"))
        self.assertEqual(self.base_hash, ledger["source_hash"].removeprefix("sha256:"))
        self.assertEqual(first["bundle_id"], ledger["bundle_id"])
        self.assertIn(ledger["attempt_state"], ("SUCCEEDED",))
        # Independence: identity survives even if summary.json is removed.
        (self.work / "runs" / "P05-R0-B" / "summary.json").unlink()
        again = measure.read_terminal_ledger(self.work, "P05-R0-B")
        self.assertEqual(first["bundle_id"], again["bundle_id"])
        self.assertEqual(ledger["source_hash"], again["source_hash"])

    def test_live_summary_identity_matches_ledger(self) -> None:
        first = self._run()
        self._run(approve=first["bundle_id"])
        measure = _load_measure()
        ident = measure.read_pilot_identity(self.work, "P05-R0-B")
        ledger = measure.read_terminal_ledger(self.work, "P05-R0-B")
        for key in ("task_id", "run_id", "source_hash", "bundle_id"):
            self.assertEqual(ledger[key], ident[key], key)


if __name__ == "__main__":
    unittest.main()
