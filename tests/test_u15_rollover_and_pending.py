"""U15 S9·S10: 판정 완료 사건 보관(롤오버)과 판정 대기 자동 추출."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from v7_harness.coord.brief import pending_from_plan, render_brief
from v7_harness.coord.stream import append_event, archive_settled, read_events, stream_dir

KST = timezone(timedelta(hours=9))


class U15RolloverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        self.clock = datetime(2026, 9, 20, 21, 0, tzinfo=KST)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _event(self, **kwargs):
        self.clock += timedelta(minutes=1)
        params = {"actor": "claude", "kind": "NOTE", "step": "U15", "summary": "사건", "now": self.clock}
        params.update(kwargs)
        return append_event(self.project, **params)

    def test_without_a_verdict_nothing_moves(self) -> None:
        self._event()
        self._event()
        report = archive_settled(self.project, now=self.clock)
        self.assertEqual(0, report["archived"])
        self.assertEqual(2, len(read_events(self.project)))
        self.assertFalse((stream_dir(self.project) / "archive").exists())

    def test_settled_events_move_to_archive_and_are_not_lost(self) -> None:
        self._event(summary="판정 전 1")
        self._event(actor="codex", kind="VERDICT", summary="R2 DONE", evidence={"cmd": "unittest", "exit": 0})
        self._event(summary="판정 후 1")
        report = archive_settled(self.project, now=self.clock)

        self.assertEqual(2, report["archived"])
        self.assertEqual(1, report["kept"])
        live = read_events(self.project)
        self.assertEqual(["판정 후 1"], [event["summary"] for event in live])

        archived = (self.project / report["archive"]).read_text(encoding="utf-8").splitlines()
        self.assertEqual(2, len(archived))
        self.assertIn("판정 전 1", archived[0])
        self.assertIn("R2 DONE", archived[1])

    def test_archive_is_invisible_to_the_brief_but_readable_on_disk(self) -> None:
        self._event(summary="옛 사건")
        self._event(actor="codex", kind="VERDICT", summary="판정", evidence={"cmd": "c", "exit": 0})
        self._event(summary="새 사건")
        archive_settled(self.project, now=self.clock)
        text = render_brief(self.project)
        self.assertIn("새 사건", text)
        self.assertNotIn("옛 사건", text)
        self.assertTrue(any((stream_dir(self.project) / "archive").glob("settled-*.jsonl")))

    def test_new_events_still_append_after_a_rollover(self) -> None:
        self._event(actor="codex", kind="VERDICT", summary="판정", evidence={"cmd": "c", "exit": 0})
        archive_settled(self.project, now=self.clock)
        self._event(summary="롤오버 이후")
        self.assertEqual(["롤오버 이후"], [event["summary"] for event in read_events(self.project)])


class U15PendingFromPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / ".coord").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _plan(self, body: str) -> None:
        (self.project / ".coord" / "PLAN.md").write_text(body, encoding="utf-8")

    def test_waiting_rows_are_picked_and_done_rows_are_not(self) -> None:
        self._plan(
            "| ID | 상태 | 소유자 |\n"
            "|---|---|---|\n"
            "| R2 | DONE | Codex |\n"
            "| U15 | REVIEW (S1~S8, Codex 재검토 대기) | Claude |\n"
            "| R1 | BLOCKED | Codex |\n"
            "| B60 | READY | Codex |\n"
        )
        items = pending_from_plan(self.project)
        self.assertEqual(3, len(items))
        self.assertTrue(items[0].startswith("U15: REVIEW"))
        self.assertFalse(any(item.startswith("R2:") for item in items))

    def test_header_row_is_not_an_item(self) -> None:
        self._plan("| ID | 상태 |\n|---|---|\n| U15 | REVIEW |\n")
        self.assertEqual(["U15: REVIEW"], pending_from_plan(self.project))

    def test_missing_plan_returns_nothing(self) -> None:
        self.assertEqual([], pending_from_plan(self.project))

    def test_limit_caps_the_list(self) -> None:
        rows = "".join(f"| S{index} | READY | x |\n" for index in range(10))
        self._plan("| ID | 상태 | 소유자 |\n|---|---|---|\n" + rows)
        self.assertEqual(3, len(pending_from_plan(self.project, limit=3)))


if __name__ == "__main__":
    unittest.main()


class U15RolloverConcurrencyTests(unittest.TestCase):
    """보관과 기록이 겹쳐도 사건이 사라지면 안 된다."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        self.base = datetime(2026, 9, 20, 23, 50, tzinfo=KST)
        append_event(self.project, actor="codex", kind="VERDICT", step="R2", summary="판정",
                     evidence={"cmd": "c", "exit": 0}, now=self.base)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_archive_during_appends_keeps_every_live_event(self) -> None:
        import threading

        errors: list[BaseException] = []
        # 자정을 넘긴 시각으로 기록한다. 날짜별 파일 잠금이었다면 보관이 이 파일을 함께 지웠다.
        next_day = self.base + timedelta(minutes=20)

        def writer(index: int) -> None:
            try:
                append_event(self.project, actor="claude", kind="NOTE", step=f"S{index}",
                             summary=f"자정 이후 {index}", now=next_day)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        def archiver() -> None:
            try:
                archive_settled(self.project, now=next_day)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(6)]
        threads.insert(3, threading.Thread(target=archiver))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)

        self.assertEqual([], errors)
        live = [event["summary"] for event in read_events(self.project)]
        archived_files = list((stream_dir(self.project) / "archive").glob("settled-*.jsonl"))
        archived = []
        for path in archived_files:
            archived.extend(line for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        # 살아있는 사건 + 보관된 사건 = 기록한 사건 전부(판정 1 + 기록 6)
        self.assertEqual(7, len(live) + len(archived))
        for index in range(6):
            self.assertTrue(
                any(f"자정 이후 {index}" in item for item in live)
                or any(f"자정 이후 {index}" in item for item in archived),
                f"사건 {index} 유실",
            )
