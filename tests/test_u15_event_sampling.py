"""U15 S14: 사건이 기록될 때 운용 표본이 함께 남는지.

하루 집계에서 수집기가 세션 타이머에 묶여 23.4시간 공백이 났다. 표본을 일이 일어나는
자리로 옮겼으므로, 사건이 생기면 표본이 생겨야 하고, 몰려도 폭주하지 않아야 하며,
표본이 실패해도 사건은 남아야 한다.
"""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from v7_harness.coord import metrics
from v7_harness.coord.stream import append_event, read_events


class EventSamplingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _samples(self) -> list[dict]:
        path = metrics.samples_path(self.project)
        if not path.is_file():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _log(self, summary: str = "사건") -> None:
        append_event(self.project, actor="claude", kind="NOTE", step="U15", summary=summary)

    def test_an_event_leaves_a_sample(self) -> None:
        self._log()
        samples = self._samples()
        self.assertEqual(1, len(samples))
        self.assertEqual("event", samples[0]["source"])
        self.assertEqual(1, samples[0]["events_total"])
        self.assertEqual({"NOTE": 1}, samples[0]["events_by_kind"])

    def test_bursts_do_not_flood_samples(self) -> None:
        for index in range(20):
            self._log(f"사건 {index}")
        self.assertEqual(1, len(self._samples()))
        self.assertEqual(20, len(read_events(self.project)))

    def test_a_new_sample_after_the_interval(self) -> None:
        self._log("첫 사건")
        path = metrics.samples_path(self.project)
        old = time.time() - metrics.MIN_INTERVAL_S - 5
        import os

        os.utime(path, (old, old))
        self._log("둘째 사건")
        samples = self._samples()
        self.assertEqual(2, len(samples))
        self.assertEqual(2, samples[-1]["events_total"])

    def test_samples_are_not_read_as_events(self) -> None:
        self._log()
        # 표본 파일은 스트림 하위 폴더에 있어 사건 읽기에 섞이면 안 된다.
        self.assertEqual(1, len(read_events(self.project)))

    def test_a_failing_sampler_never_blocks_the_event(self) -> None:
        with mock.patch.object(metrics, "_brief_stats", side_effect=OSError("disk")):
            self._log("표본 실패")
        self.assertEqual(["표본 실패"], [event["summary"] for event in read_events(self.project)])


if __name__ == "__main__":
    unittest.main()
