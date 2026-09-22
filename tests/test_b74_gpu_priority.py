"""B74: GPU 우선순위 — 파일럿 로컬 작업자가 먼저, olla·MCP 보조 호출은 양보. 만료로 죽은 표식을 넘는다."""

from __future__ import annotations

import io
import json
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from v7_harness import olla
from v7_harness.adapters import gpu_priority


class GpuPriorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for target, name, value in ((gpu_priority, "GPU_DIR", Path(self.tmp.name) / "gpu"),
                                    (olla, "USAGE_LOG", Path(self.tmp.name) / "u.jsonl")):
            patch = mock.patch.object(target, name, value)
            patch.start()
            self.addCleanup(patch.stop)

    def test_marker_lives_only_inside_the_block(self) -> None:
        self.assertFalse(gpu_priority.pilot_active())
        with gpu_priority.pilot_holds(60):
            self.assertTrue(gpu_priority.pilot_active())
        self.assertFalse(gpu_priority.pilot_active())

    def test_a_crashed_pilot_stops_blocking_after_expiry(self) -> None:
        gpu_priority.GPU_DIR.mkdir(parents=True)
        (gpu_priority.GPU_DIR / "pilot-99999.json").write_text(json.dumps({"expires_at": time.time() - 1}), encoding="utf-8")
        self.assertFalse(gpu_priority.pilot_active())
        (gpu_priority.GPU_DIR / "pilot-99998.json").write_text("not json", encoding="utf-8")
        self.assertFalse(gpu_priority.pilot_active())

    def test_olla_cli_yields_with_exit_6_and_logs_it(self) -> None:
        err = io.StringIO()
        with gpu_priority.pilot_holds(60), mock.patch.object(olla.worker, "_generate") as gen:
            with redirect_stdout(io.StringIO()), redirect_stderr(err):
                code = olla.main(["ask", "summarize"])
        gen.assert_not_called()
        self.assertEqual(olla.GPU_BUSY_EXIT, code)
        self.assertIn("GPU busy", err.getvalue())
        self.assertIn('"yield_to_pilot"', olla.USAGE_LOG.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
