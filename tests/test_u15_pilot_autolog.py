"""U15 S13: 파일럿 결과가 저절로 조율 스트림에 남는지.

사람이 기억해서 적는 기록은 빠진다. 실행이 끝나는 자리에서 남아야 한다.
동시에, 기록이 실패해도 실행 결과 보고를 덮어서는 안 된다.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from v7_harness.cli import record_pilot_in_stream
from v7_harness.coord.stream import read_events


class PilotAutoLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_successful_run_is_recorded_as_run_with_evidence(self) -> None:
        event_id = record_pilot_in_stream(self.project, {
            "task_id": "T01",
            "state": "SUCCEEDED",
            "verdict_hint": "PASS",
            "promotion": "APPLIED",
            "error_class": "NONE",
            "changed_files": ["a.py", "b.py"],
            "bundle_id": "b" * 64,
            "summary_path": ".work\\pilot_T01\\runs\\T01\\summary.json",
        })
        self.assertIsNotNone(event_id)
        events = read_events(self.project)
        self.assertEqual(1, len(events))
        event = events[0]
        self.assertEqual("RUN", event["kind"])
        self.assertEqual("T01", event["step"])
        self.assertIn("SUCCEEDED/PASS/APPLIED", event["summary"])
        self.assertIn("변경 2개", event["summary"])
        self.assertEqual(0, event["evidence"]["exit"])
        self.assertEqual("b" * 64, event["evidence"]["bundle"])
        self.assertEqual([".work/pilot_T01/runs/T01/summary.json"], event["refs"])

    def test_failed_run_is_recorded_as_blocked_with_the_error_class(self) -> None:
        record_pilot_in_stream(self.project, {
            "task_id": "T02",
            "state": "FAILED",
            "verdict_hint": "BLOCKED",
            "error_class": "SOURCE_DIVERGED",
            "changed_files": [],
        })
        event = read_events(self.project)[0]
        self.assertEqual("BLOCKED", event["kind"])
        self.assertIn("SOURCE_DIVERGED", event["summary"])
        self.assertEqual(1, event["evidence"]["exit"])

    def test_long_summary_is_trimmed_to_the_stream_limit(self) -> None:
        record_pilot_in_stream(self.project, {
            "task_id": "T03",
            "state": "SUCCEEDED",
            "verdict_hint": "PASS",
            "error_class": "NONE",
            "changed_files": ["f.py"],
            "promotion": "X" * 300,
        })
        event = read_events(self.project)[0]
        self.assertLessEqual(len(event["summary"]), 200)

    def test_a_failing_stream_never_breaks_the_pilot_report(self) -> None:
        with mock.patch("v7_harness.coord.stream.append_event", side_effect=OSError("disk full")):
            result = record_pilot_in_stream(self.project, {
                "task_id": "T04",
                "state": "SUCCEEDED",
                "verdict_hint": "PASS",
                "changed_files": [],
            })
        self.assertIsNone(result)
        self.assertEqual([], read_events(self.project))


if __name__ == "__main__":
    unittest.main()
