"""U15 S7: 조율 CLI. 세 도구가 같은 입구를 쓰는지, 거부가 종료 코드로 드러나는지 본다."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from v7_harness.cli import main


class U15CoordCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self, *argv: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(list(argv))
        return code, buffer.getvalue()

    def _log(self, *extra: str) -> tuple[int, str]:
        return self._run(
            "coord", "log",
            "--project", str(self.project),
            "--actor", "claude",
            "--kind", "NOTE",
            "--step", "U15",
            "--summary", "사건 한 줄",
            *extra,
        )

    def test_log_writes_one_event(self) -> None:
        code, out = self._log("--ref", "docs/claude-assist/71_pending-three-items-plan_2026-09-20.md")
        self.assertEqual(0, code)
        payload = json.loads(out)
        self.assertTrue(payload["ok"])
        stream = list((self.project / ".coord" / "stream").glob("*.jsonl"))
        self.assertEqual(1, len(stream))
        self.assertEqual(1, len(stream[0].read_text(encoding="utf-8").splitlines()))

    def test_verdict_from_a_worker_exits_nonzero(self) -> None:
        code, out = self._run(
            "coord", "log",
            "--project", str(self.project),
            "--actor", "antigravity",
            "--kind", "VERDICT",
            "--step", "R2",
            "--summary", "통과로 판정",
            "--cmd", "python -m unittest",
            "--exit-code", "0",
        )
        self.assertEqual(1, code)
        self.assertEqual("VERDICT_ACTOR_NOT_ALLOWED", json.loads(out)["error"])

    def test_run_without_evidence_exits_nonzero(self) -> None:
        code, out = self._run(
            "coord", "log",
            "--project", str(self.project),
            "--actor", "claude",
            "--kind", "RUN",
            "--step", "U15",
            "--summary", "증거 없는 실행",
        )
        self.assertEqual(1, code)
        self.assertIn("MISSING_EVIDENCE", json.loads(out)["error"])

    def test_brief_prints_and_writes(self) -> None:
        self._log()
        code, printed = self._run("coord", "brief", "--project", str(self.project), "--owner", "claude")
        self.assertEqual(0, code)
        self.assertIn("# Codex coordination brief", printed)

        code, out = self._run(
            "coord", "brief",
            "--project", str(self.project),
            "--pending", "R4-FINAL 재검토",
            "--next", "표본 적립",
            "--write",
        )
        self.assertEqual(0, code)
        payload = json.loads(out)
        self.assertTrue((self.project / ".coord" / "codex_brief.md").is_file())
        self.assertLessEqual(payload["lines"], 60)
        self.assertIn("R4-FINAL 재검토", (self.project / ".coord" / "codex_brief.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
