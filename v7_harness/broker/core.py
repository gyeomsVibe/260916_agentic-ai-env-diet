"""Single-writer SQLite core used only by the foreground U11 broker."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from v7_harness.contracts.database import apply_migrations
from v7_harness.contracts.schemas import SchemaValidationError, validate_document


class BrokerError(RuntimeError):
    """Base class for fail-closed broker errors."""


class BrokerAlreadyRunning(BrokerError):
    pass


class BrokerOwnershipError(BrokerError):
    pass


class _ExclusiveFileLock:
    """Process-scoped lock proving one foreground broker owns the DB writer."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._file: Any = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise BrokerAlreadyRunning("BROKER_ALREADY_RUNNING") from exc
        self._file = handle

    def release(self) -> None:
        if self._file is None:
            return
        self._file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        finally:
            self._file.close()
            self._file = None


class BrokerCore:
    """Own the sole writable connection and expose command-level mutations only."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = Path(database_path).resolve()
        self._lock = _ExclusiveFileLock(self._database_path.with_suffix(self._database_path.suffix + ".writer.lock"))
        self._connection: sqlite3.Connection | None = None
        self._owner_thread: int | None = None

    def start(self) -> None:
        if self._connection is not None:
            raise BrokerOwnershipError("BROKER_ALREADY_STARTED")
        self._preflight()
        self._lock.acquire()
        try:
            connection = sqlite3.connect(self._database_path, timeout=1.0, isolation_level=None)
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=1000")
            apply_migrations(connection, app_version="0.3.0-u12")
            self._connection = connection
            self._owner_thread = threading.get_ident()
        except Exception:
            self._lock.release()
            raise

    def _preflight(self) -> None:
        parent = self._database_path.parent
        if not parent.is_dir():
            raise BrokerError("DB_PARENT_MISSING")
        if str(self._database_path).startswith("\\\\"):
            raise BrokerError("UNSAFE_STORAGE")

    def close(self) -> None:
        if self._connection is not None:
            self._assert_owner()
            self._connection.close()
            self._connection = None
            self._owner_thread = None
        self._lock.release()

    def _assert_owner(self) -> sqlite3.Connection:
        if self._connection is None or self._owner_thread != threading.get_ident():
            raise BrokerOwnershipError("BROKER_WRITER_OWNER_REQUIRED")
        return self._connection

    @property
    def connection(self) -> sqlite3.Connection:
        return self._assert_owner()

    @property
    def owner_thread(self) -> int | None:
        return self._owner_thread

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._assert_owner()
        connection.execute("BEGIN IMMEDIATE")
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()

    @staticmethod
    def _payload_hash(command: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(command, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    def enqueue(self, command: dict[str, Any]) -> dict[str, Any]:
        """Validate fully, then atomically record one durable pending delivery."""
        validate_document("command", command, version=1)
        payload_hash = self._payload_hash(command)
        dedupe_key = command["idempotency_key"]
        delivery_id = command["command_id"]
        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT delivery_id,payload_ref,state FROM deliveries WHERE dedupe_key=?",
                (dedupe_key,),
            ).fetchone()
            if existing is not None:
                event = connection.execute(
                    "SELECT payload_hash FROM events WHERE aggregate_id=? AND kind='COMMAND_ENQUEUED'",
                    (existing[0],),
                ).fetchone()
                if event is None or event[0] != payload_hash:
                    raise BrokerError("DEDUPE_CONFLICT")
                return {"delivery_id": existing[0], "state": existing[2], "duplicate": True, "durable": True}
            if connection.execute(
                "SELECT 1 FROM deliveries WHERE delivery_id=?", (delivery_id,)
            ).fetchone() is not None:
                raise BrokerError("COMMAND_ID_CONFLICT")
            connection.execute(
                "INSERT INTO deliveries(delivery_id,direction,dedupe_key,payload_ref,state,available_at) "
                "VALUES(?, 'INBOX', ?, ?, 'PENDING', datetime('now'))",
                (delivery_id, dedupe_key, command["payload_ref"]),
            )
            connection.execute(
                "INSERT INTO events(aggregate_id,kind,payload_hash,created_at) VALUES(?, 'COMMAND_ENQUEUED', ?, datetime('now'))",
                (delivery_id, payload_hash),
            )
        return {"delivery_id": delivery_id, "state": "PENDING", "duplicate": False, "durable": True}

    def delivery(self, delivery_id: str) -> dict[str, Any] | None:
        connection = self._assert_owner()
        row = connection.execute(
            "SELECT delivery_id,state,result_hash,acked_at FROM deliveries WHERE delivery_id=?",
            (delivery_id,),
        ).fetchone()
        if row is None:
            return None
        return {"delivery_id": row[0], "state": row[1], "result_hash": row[2], "acked_at": row[3]}

    def counts(self) -> dict[str, int]:
        connection = self._assert_owner()
        return {
            "deliveries": int(connection.execute("SELECT count(*) FROM deliveries").fetchone()[0]),
            "acked": int(connection.execute("SELECT count(*) FROM deliveries WHERE state='ACKED'").fetchone()[0]),
            "succeeded": int(connection.execute("SELECT count(*) FROM attempts WHERE state='SUCCEEDED'").fetchone()[0]),
        }

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(request, dict) or request.get("protocol_version") != 1:
            raise SchemaValidationError("$: unsupported protocol_version")
        if set(request) - {"protocol_version", "kind", "command", "delivery_id"}:
            raise SchemaValidationError("$: unknown request fields")
        kind = request.get("kind")
        if kind == "ENQUEUE" and isinstance(request.get("command"), dict):
            return self.enqueue(request["command"])
        if kind == "GET" and isinstance(request.get("delivery_id"), str):
            return {"delivery": self.delivery(request["delivery_id"])}
        if kind == "COUNTS":
            return self.counts()
        if kind == "STOP":
            return {"stopping": True}
        raise SchemaValidationError("$: malformed request")
