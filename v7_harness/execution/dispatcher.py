"""Bounded single-writer dispatcher protecting SQLite from concurrent thread access."""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from v7_harness.broker.core import BrokerCore
from v7_harness.execution.errors import DrainInProgressError, QueueSaturationError


class _SimpleFuture:
    """Thread synchronization future for bounded dispatch."""

    def __init__(self) -> None:
        self._event = threading.Event()
        self._result: Any = None
        self._exception: BaseException | None = None

    def set_result(self, value: Any) -> None:
        self._result = value
        self._event.set()

    def set_exception(self, exc: BaseException) -> None:
        self._exception = exc
        self._event.set()

    def get(self, timeout: float = 5.0) -> Any:
        if not self._event.wait(timeout):
            raise TimeoutError("DISPATCHER_RESPONSE_TIMEOUT")
        if self._exception is not None:
            raise self._exception
        return self._result


@dataclass
class _WorkItem:
    fn: Callable[[BrokerCore], Any]
    future: _SimpleFuture


class BoundedDispatcher:
    """Bounded in-memory queue with exactly one dedicated SQLite writer thread."""

    def __init__(
        self,
        core: BrokerCore,
        *,
        capacity: int = 16,
        default_enqueue_timeout: float = 0.05,
    ) -> None:
        self._core = core
        self.capacity = capacity
        self.default_enqueue_timeout = default_enqueue_timeout
        self._queue: queue.Queue[_WorkItem | None] = queue.Queue(maxsize=capacity)
        self._thread: threading.Thread | None = None
        self._stopping = threading.Event()
        self._draining = threading.Event()
        self._ready = threading.Event()
        self._owner_thread_id: int | None = None
        self._last_owner_thread_id: int | None = None
        self._writer_thread_ids: set[int] = set()

    @property
    def owner_thread_id(self) -> int | None:
        return self._owner_thread_id or self._last_owner_thread_id

    @property
    def writer_thread_ids(self) -> set[int]:
        return set(self._writer_thread_ids)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stopping.clear()
        self._draining.clear()
        self._ready.clear()
        self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="broker-owner-thread")
        self._thread.start()
        if not self._ready.wait(timeout=5.0):
            raise TimeoutError("Dispatcher thread failed to start")

    def _worker_loop(self) -> None:
        self._core.start()
        self._owner_thread_id = threading.get_ident()
        self._ready.set()
        try:
            while True:
                try:
                    item = self._queue.get(timeout=0.05)
                except queue.Empty:
                    if self._stopping.is_set():
                        break
                    continue

                if item is None:
                    self._queue.task_done()
                    break

                self._writer_thread_ids.add(threading.get_ident())
                try:
                    result = item.fn(self._core)
                    item.future.set_result(result)
                except BaseException as exc:
                    item.future.set_exception(exc)
                finally:
                    self._queue.task_done()
        finally:
            self._last_owner_thread_id = self._owner_thread_id
            self._core.close()
            self._owner_thread_id = None

    def submit_and_wait(
        self,
        fn: Callable[[BrokerCore], Any],
        *,
        timeout: float = 5.0,
        enqueue_timeout: float | None = None,
    ) -> Any:
        """Submit command to bounded queue; fail fast on saturation, no DB bypass."""
        if self._draining.is_set() or self._stopping.is_set():
            raise DrainInProgressError("DRAIN_IN_PROGRESS")

        enq_timeout = enqueue_timeout if enqueue_timeout is not None else self.default_enqueue_timeout
        item = _WorkItem(fn=fn, future=_SimpleFuture())
        try:
            self._queue.put(item, block=True, timeout=enq_timeout)
        except queue.Full:
            # Saturated: bounded fast failure, strictly retryable, NO direct DB bypass
            raise QueueSaturationError("QUEUE_SATURATED")

        return item.future.get(timeout=timeout)

    def drain(self, timeout: float = 5.0) -> None:
        """Gracefully stop accepting new work and wait for queued work to finish."""
        self._draining.set()
        deadline = time.monotonic() + timeout
        while self._queue.unfinished_tasks and time.monotonic() < deadline:
            time.sleep(0.01)
        if self._queue.unfinished_tasks:
            raise TimeoutError("DISPATCHER_DRAIN_TIMEOUT")
        self.stop(timeout=max(0.01, deadline - time.monotonic()))

    def stop(self, timeout: float = 5.0) -> None:
        self._stopping.set()
        try:
            self._queue.put(None, timeout=min(timeout, 0.1))
        except queue.Full as exc:
            raise TimeoutError("DISPATCHER_STOP_QUEUE_TIMEOUT") from exc
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                raise TimeoutError("DISPATCHER_STOP_TIMEOUT")
        self._thread = None
