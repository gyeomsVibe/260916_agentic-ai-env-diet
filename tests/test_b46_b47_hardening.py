"""B46 residual + B47: pre-snapshot instability must yield a structured summary; checkpoint recording must not fabricate attempts."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import v7_harness.pilot as pilot_mod
from v7_harness.isolation.errors import WatchScanUnavailableError
from v7_harness.pilot import PilotConfig, run_pilot

FAKE_AGY = [sys.executable, str(Path(__file__).parent / "fixtures" / "fake_agy.py")]


class PreSnapshotInstabilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.source = root / "sample"
        self.source.mkdir()
        (self.source / "calc.py").write_text("x = 1\n", encoding="utf-8")
        self.home = root / "home"
        self.home.mkdir()
        self.work = root / "work"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _config(self) -> PilotConfig:
        return PilotConfig(task_id="B46X", title="t", prompt="p", source_dir=self.source, work_dir=self.work,
                           agy_command=FAKE_AGY, watch_roots=[self.home], print_timeout_s=60)

    def test_transient_instability_is_retried_once(self) -> None:
        real = pilot_mod.snapshot_watch_roots
        calls = {"n": 0}

        def flaky(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise WatchScanUnavailableError("WATCH_SCAN_UNAVAILABLE: unstable file during fingerprint x.log")
            return real(*a, **k)

        with mock.patch.object(pilot_mod, "snapshot_watch_roots", flaky), \
             mock.patch.dict(os.environ, {"FAKE_AGY_MODE": "success", "FAKE_AGY_OUTSIDE_DIR": str(self.home)}):
            summary = run_pilot(self._config())
        self.assertEqual("SUCCEEDED", summary["state"])
        self.assertGreaterEqual(calls["n"], 2)

    def test_persistent_instability_returns_structured_summary(self) -> None:
        def always(*a, **k):
            raise WatchScanUnavailableError("WATCH_SCAN_UNAVAILABLE: unstable file during fingerprint x.log")

        with mock.patch.object(pilot_mod, "snapshot_watch_roots", always), \
             mock.patch.dict(os.environ, {"FAKE_AGY_MODE": "success", "FAKE_AGY_OUTSIDE_DIR": str(self.home)}):
            summary = run_pilot(self._config())
        self.assertEqual("FAILED", summary["state"])
        self.assertEqual("WATCH_SCAN_UNAVAILABLE", summary["error_class"])
        self.assertEqual("BLOCKED", summary["verdict_hint"])
        self.assertIn("error_detail", summary)


class NoFabricatedAttemptTest(unittest.TestCase):
    def test_checkpoint_for_unknown_attempt_is_refused(self) -> None:
        import inspect
        src = inspect.getsource(pilot_mod._record_checkpoint_and_identity)
        self.assertNotIn("INSERT OR IGNORE INTO attempts", src)
        self.assertNotIn("INSERT OR IGNORE INTO plans", src)


if __name__ == "__main__":
    unittest.main()
