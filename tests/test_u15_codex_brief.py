"""U15 S3: Codex 브리핑 계약 — 결정성, 상한, 접기."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from v7_harness.coord.brief import (
    HEADER,
    MAX_BYTES,
    MAX_LINES,
    brief_hash,
    render_brief,
    write_brief,
)
from v7_harness.coord.stream import append_event

KST = timezone(timedelta(hours=9))


class U15CodexBriefTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        self.clock = datetime(2026, 9, 20, 20, 0, 0, tzinfo=KST)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _event(self, **kwargs):
        self.clock += timedelta(minutes=1)
        params = {
            "actor": "claude",
            "kind": "NOTE",
            "step": "U15",
            "summary": "사건",
            "now": self.clock,
        }
        params.update(kwargs)
        return append_event(self.project, **params)

    def test_same_stream_renders_identically(self) -> None:
        self._event()
        self._event(actor="antigravity", kind="RUN", summary="파일럿 종료", evidence={"cmd": "pilot run", "exit": 0})
        first = render_brief(self.project, owner="claude")
        second = render_brief(self.project, owner="claude")
        self.assertEqual(brief_hash(first), brief_hash(second))

    def test_header_is_byte_stable_prefix(self) -> None:
        self._event()
        text = render_brief(self.project)
        self.assertTrue(text.startswith(HEADER.rstrip()))

    def test_events_before_the_last_verdict_are_folded_away(self) -> None:
        self._event(summary="판정 전 사건")
        self._event(actor="codex", kind="VERDICT", summary="R2 DONE", evidence={"cmd": "unittest", "exit": 0})
        self._event(summary="판정 후 사건")
        text = render_brief(self.project)
        self.assertIn("판정 후 사건", text)
        self.assertNotIn("판정 전 사건", text)
        self.assertNotIn("R2 DONE", text)

    def test_limits_hold_under_a_long_stream(self) -> None:
        for index in range(40):
            self._event(summary=f"사건 {index} " + "가" * 150)
        text = render_brief(
            self.project,
            owner="antigravity",
            lock=".work/QUIET_LOCK",
            pending=["bundle fec3bded 판정", "R4-FINAL 재검토"],
            next_candidates=["U15 S4", "B57 재측정", "U13 정리"],
        )
        self.assertLessEqual(len(text.splitlines()), MAX_LINES)
        self.assertLessEqual(len(text.encode("utf-8")), MAX_BYTES)
        self.assertIn("bundle fec3bded 판정", text)

    def test_blocked_events_are_always_shown(self) -> None:
        self._event(kind="BLOCKED", summary="쿼터 소진으로 중단")
        for index in range(15):
            self._event(summary=f"이후 사건 {index}")
        text = render_brief(self.project)
        self.assertIn("쿼터 소진으로 중단", text)

    def test_empty_stream_still_renders_a_usable_page(self) -> None:
        text = render_brief(self.project, owner="codex")
        self.assertIn("## Awaiting Codex verdict", text)
        self.assertIn("- none", text)

    def test_write_brief_puts_it_where_codex_reads(self) -> None:
        self._event()
        path = write_brief(self.project, render_brief(self.project))
        self.assertEqual(self.project / ".coord" / "codex_brief.md", path)
        self.assertTrue(path.read_text(encoding="utf-8").startswith("# Codex coordination brief"))


if __name__ == "__main__":
    unittest.main()
