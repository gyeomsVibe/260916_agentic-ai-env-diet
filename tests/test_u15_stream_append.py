"""U15 S2: 사건 스트림 계약.

반례 위주로 쓴다. 기록이 남는 것보다 잘못된 기록이 남지 않는 것이 중요하다.
"""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from v7_harness.coord.stream import (
    StreamRejected,
    append_event,
    read_events,
    stream_path,
)

KST = timezone(timedelta(hours=9))


class U15StreamAppendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        self.now = datetime(2026, 9, 20, 20, 30, 0, tzinfo=KST)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _append(self, **kwargs):
        params = {
            "actor": "claude",
            "kind": "NOTE",
            "step": "U15",
            "summary": "설계 카드 갱신",
            "now": self.now,
        }
        params.update(kwargs)
        return append_event(self.project, **params)

    def test_event_is_written_as_one_json_line(self) -> None:
        event = self._append()
        path = stream_path(self.project, now=self.now)
        lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(1, len(lines))
        payload = json.loads(lines[0])
        self.assertEqual(event.id, payload["id"])
        self.assertEqual("claude", payload["actor"])
        self.assertEqual("2026-09-20T20:30:00+09:00", payload["ts"])

    def test_verdict_is_reserved_for_codex(self) -> None:
        for actor in ("claude", "antigravity"):
            with self.subTest(actor=actor):
                with self.assertRaises(StreamRejected) as caught:
                    self._append(actor=actor, kind="VERDICT", evidence={"cmd": "x", "exit": 0})
                self.assertEqual("VERDICT_ACTOR_NOT_ALLOWED", str(caught.exception))
        codex = self._append(actor="codex", kind="VERDICT", evidence={"cmd": "python -m unittest", "exit": 0})
        self.assertEqual("VERDICT", codex.kind)

    def test_run_and_verdict_require_evidence(self) -> None:
        with self.assertRaises(StreamRejected) as missing_cmd:
            self._append(kind="RUN", evidence={"exit": 0})
        self.assertEqual("MISSING_EVIDENCE_CMD", str(missing_cmd.exception))
        with self.assertRaises(StreamRejected) as missing_exit:
            self._append(kind="RUN", evidence={"cmd": "python -m unittest"})
        self.assertEqual("MISSING_EVIDENCE_EXIT", str(missing_exit.exception))

    def test_rejected_event_leaves_no_trace(self) -> None:
        with self.assertRaises(StreamRejected):
            self._append(kind="RUN")
        self.assertEqual([], read_events(self.project))

    def test_summary_limits(self) -> None:
        with self.assertRaises(StreamRejected) as too_long:
            self._append(summary="가" * 201)
        self.assertEqual("SUMMARY_TOO_LONG", str(too_long.exception))
        with self.assertRaises(StreamRejected) as multiline:
            self._append(summary="첫 줄\n둘째 줄")
        self.assertEqual("MULTILINE_SUMMARY", str(multiline.exception))
        with self.assertRaises(StreamRejected) as empty:
            self._append(summary="   ")
        self.assertEqual("EMPTY_SUMMARY", str(empty.exception))

    def test_secret_shaped_text_is_refused(self) -> None:
        for summary in ("api_key: abcdef", "토큰 유출 sk-abcdefghijklmnopqrstuvwx"):
            with self.subTest(summary=summary):
                with self.assertRaises(StreamRejected) as caught:
                    self._append(summary=summary)
                self.assertEqual("SECRET_IN_SUMMARY", str(caught.exception))

    def test_refs_must_stay_inside_the_project(self) -> None:
        for ref in ("../outside.md", "/etc/passwd", "C:/Windows/system.ini"):
            with self.subTest(ref=ref):
                with self.assertRaises(StreamRejected) as caught:
                    self._append(refs=[ref])
                self.assertEqual("INVALID_REF", str(caught.exception))
        event = self._append(refs=[".coord\\tasks\\U15-coordination-stream.md", ".coord/tasks/U15-coordination-stream.md"])
        self.assertEqual((".coord/tasks/U15-coordination-stream.md",), event.refs)

    def test_unknown_actor_or_kind_is_refused(self) -> None:
        with self.assertRaises(StreamRejected):
            self._append(actor="gemini")
        with self.assertRaises(StreamRejected):
            self._append(kind="APPROVE")

    def test_concurrent_appends_keep_every_line_and_id_unique(self) -> None:
        errors: list[BaseException] = []

        def worker(index: int) -> None:
            try:
                append_event(
                    self.project,
                    actor="antigravity",
                    kind="RUN",
                    step=f"S{index}",
                    summary=f"파일럿 {index} 종료",
                    evidence={"cmd": "python -m v7_harness.cli pilot run", "exit": 0},
                    now=self.now,
                )
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(index,)) for index in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)

        self.assertEqual([], errors)
        events = read_events(self.project)
        self.assertEqual(8, len(events))
        self.assertEqual(8, len({event["id"] for event in events}))
        raw = stream_path(self.project, now=self.now).read_text(encoding="utf-8").splitlines()
        self.assertEqual(8, len(raw))
        for line in raw:
            json.loads(line)

    def test_corrupt_line_is_reported_not_skipped(self) -> None:
        self._append()
        path = stream_path(self.project, now=self.now)
        with path.open("a", encoding="utf-8") as handle:
            handle.write("{not json}\n")
        with self.assertRaises(StreamRejected) as caught:
            read_events(self.project)
        self.assertTrue(str(caught.exception).startswith("CORRUPT_LINE:"))


if __name__ == "__main__":
    unittest.main()
