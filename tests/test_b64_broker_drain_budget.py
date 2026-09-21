"""B64: 정상 STOP 인데 브로커 자식이 exit 1 로 끝나던 간헐 실패.

회귀 로그(2026-09-22 01:58)의 자식 스택: serve_forever → drain(timeout=max(0.1, 남은 기한)) →
stop → DISPATCHER_STOP_TIMEOUT. 연결 작업자를 기다리다 기한을 다 쓰면 소유 스레드가 SQLite 를
닫을 시간이 0.1초만 남는다. 부하 재현은 0/47 로 드물어서, 느린 close 를 직접 만들어 결정적으로 재현한다.
"""

from __future__ import annotations

import time
import unittest

from v7_harness.broker.ipc import DRAIN_FLOOR_S, drain_budget
from v7_harness.execution.dispatcher import BoundedDispatcher

SLOW_CLOSE_S = 0.5  # 부하 중 SQLite close 가 0.1초를 넘는 상황


class SlowClosingCore:
    def start(self) -> None:
        pass

    def close(self) -> None:
        time.sleep(SLOW_CLOSE_S)


class DrainBudgetTests(unittest.TestCase):
    def test_old_budget_reproduces_the_stop_timeout(self) -> None:
        dispatcher = BoundedDispatcher(SlowClosingCore())
        dispatcher.start()
        with self.assertRaisesRegex(TimeoutError, "DISPATCHER_STOP_TIMEOUT"):
            dispatcher.drain(timeout=0.1)  # 수정 전 식: max(0.1, 이미 지난 기한)
        time.sleep(SLOW_CLOSE_S + 0.2)

    def test_new_budget_survives_an_exhausted_deadline(self) -> None:
        dispatcher = BoundedDispatcher(SlowClosingCore())
        dispatcher.start()
        now = time.monotonic()
        budget = drain_budget(deadline=now - 1.0, now=now)
        self.assertGreaterEqual(budget, DRAIN_FLOOR_S)
        self.assertGreater(DRAIN_FLOOR_S, SLOW_CLOSE_S)
        dispatcher.drain(timeout=budget)  # 예외 없이 끝나야 한다


if __name__ == "__main__":
    unittest.main()
