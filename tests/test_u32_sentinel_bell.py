"""U32b: the switchboard operator checks, recovers and rings; the presence file says who is at the desk."""

from __future__ import annotations

import argparse
import io
import json
import os
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from v7_harness.coord.mailbox import Mailbox
from v7_harness.coord.notify import is_codex_absent
from v7_harness.coord.presence import PresenceRejected, mark, read
from v7_harness.coord.sentinel import check_all_pilot_dirs, needs_reconciliation, run_sentinel_cycle
from v7_harness.coord.stream import append_event
from v7_harness.isolation.manifest import build_manifest

SESSION_ID = "0199aaaa-bbbb-cccc-dddd-eeeeffff0000"


class _Completed:
    returncode = 0


def _project(directory: str) -> tuple[Path, Mailbox]:
    root = Path(directory)
    box_dir = root / ".coord" / "mailbox"
    box_dir.mkdir(parents=True)
    return root, Mailbox(box_dir)


def _stale_lock(root: Path) -> None:
    (root / ".work").mkdir(exist_ok=True)
    (root / ".work" / "QUIET_LOCK").write_text(json.dumps({"pid": 99999999, "started_at": time.time()}), encoding="utf-8")


def _codex_session(root: Path) -> Path:
    sessions = root / "sessions"
    sessions.mkdir()
    (sessions / "s.jsonl").write_text(json.dumps({"cwd": str(root), "session_id": SESSION_ID}) + "\n", encoding="utf-8")
    return sessions


class PresenceTests(unittest.TestCase):
    def test_fresh_heartbeat_reads_back_and_expires_to_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            mark(root, "codex", "ACTIVE", ttl_s=60, now=1000.0)
            self.assertEqual("ACTIVE", read(root, "codex", now=1030.0)["state"])
            self.assertEqual("UNKNOWN", read(root, "codex", now=1061.0)["state"])

    def test_missing_or_corrupt_heartbeat_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertEqual("UNKNOWN", read(root, "claude")["state"])
            path = root / ".coord" / "presence" / "claude.json"
            path.parent.mkdir(parents=True)
            for broken in ("{not json", "[]", json.dumps({"state": "ACTIVE", "expires_at": True})):
                path.write_text(broken, encoding="utf-8")
                self.assertEqual("UNKNOWN", read(root, "claude")["state"])

    def test_unknown_tool_or_state_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(PresenceRejected):
                mark(Path(d), "gpt", "ACTIVE")
            with self.assertRaises(PresenceRejected):
                mark(Path(d), "codex", "SLEEPY")

    def test_fresh_heartbeat_overrides_a_stale_plan_line(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".coord").mkdir()
            (root / ".coord" / "PLAN.md").write_text("- codex: ABSENT(USER_DECLARED)\n", encoding="utf-8")
            self.assertTrue(is_codex_absent(root))
            mark(root, "codex", "ACTIVE")
            self.assertFalse(is_codex_absent(root))
            mark(root, "codex", "LIMITED")
            self.assertTrue(is_codex_absent(root))

    def test_presence_files_do_not_change_the_source_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.py").write_text("x = 1\n", encoding="utf-8")
            before = build_manifest(root).manifest_hash
            mark(root, "antigravity", "ACTIVE")
            self.assertEqual(before, build_manifest(root).manifest_hash)


class ReconciliationTests(unittest.TestCase):
    def test_real_pilot_summary_shapes(self) -> None:
        self.assertTrue(needs_reconciliation({"state": "FAILED", "error_class": "NEEDS_RECONCILIATION", "verdict_hint": "BLOCKED"}))
        self.assertTrue(needs_reconciliation({"state": "FAILED", "error_class": "TIMEOUT", "verdict_hint": "BLOCKED"}))
        self.assertTrue(needs_reconciliation({"state": "FAILED", "error_class": "EXTERNAL_WRITE", "effect_state": "UNKNOWN"}))
        self.assertFalse(needs_reconciliation({"state": "ABANDONED", "error_class": "ABANDONED", "effect_state": "UNKNOWN"}))
        self.assertFalse(needs_reconciliation({"state": "SUCCEEDED", "verdict_hint": "PASS", "effect_state": "CONFIRMED"}))

    def test_runs_under_any_work_dir_are_found(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for work_dir, task in ((".coord/pilot", "A"), (".work/pilot_P08", "B")):
                run = root / work_dir / "runs" / task
                run.mkdir(parents=True)
                (run / "summary.json").write_text(json.dumps({"state": "FAILED", "error_class": "TIMEOUT"}), encoding="utf-8")
            self.assertEqual(["A", "B"], check_all_pilot_dirs(root))


class CycleTests(unittest.TestCase):
    def test_acked_stream_event_is_not_redelivered(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root, box = _project(d)
            append_event(root, actor="claude", kind="RUN", step="S1", summary="done", evidence={"cmd": "x", "exit": 0})
            run_sentinel_cycle(root, box)
            (event_id,) = box.list_inbox()
            box.ack(box.claim(event_id, "codex"))
            run_sentinel_cycle(root, box)
            self.assertEqual([], box.list_inbox())

    def test_cycle_only_reads_the_inbox(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root, box = _project(d)
            box.publish("blocked1", {"kind": "BLOCKED", "step": "U99"})
            with mock.patch.object(Mailbox, "claim", side_effect=AssertionError("sentinel must not claim")):
                result = run_sentinel_cycle(root, box)
            self.assertTrue(result["p1_wake_emitted"])
            self.assertIn("blocked1", box.list_inbox())

    def test_claimed_wake_is_not_published_again(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root, box = _project(d)
            _stale_lock(root)
            self.assertTrue(run_sentinel_cycle(root, box)["p1_wake_emitted"])
            (wake_id,) = box.list_inbox()
            box.claim(wake_id, "codex")
            self.assertFalse(run_sentinel_cycle(root, box)["p1_wake_emitted"])
            self.assertEqual([], box.list_inbox())

    def test_crashed_consumer_gets_its_message_back(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root, box = _project(d)
            box.publish("job", {"kind": "RUN"})
            claim = box.claim("job", "crashed")
            moment = time.time() - 3600
            os.utime(claim.claimed_path, (moment, moment))
            self.assertEqual(["job"], run_sentinel_cycle(root, box)["recovered_claims"])
            self.assertEqual(["job"], box.list_inbox())


class BellTests(unittest.TestCase):
    def _ring(self, root: Path, box: Mailbox, calls: list) -> dict:
        def runner(argv, **_kwargs):
            calls.append(list(argv))
            return _Completed()

        return run_sentinel_cycle(root, box, ring=True, runner=runner, sessions_dir=root / "sessions")

    def test_rings_codex_once_for_the_same_waiting_wakes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root, box = _project(d)
            _codex_session(root)
            _stale_lock(root)
            mark(root, "codex", "ACTIVE")
            calls: list = []
            first = self._ring(root, box, calls)
            self.assertTrue(first["bell"]["rung"])
            self.assertEqual(["queue", "--thread", SESSION_ID], calls[0][1:4])
            self.assertTrue(calls[0][-1].startswith("[DATA] from=sentinel verdict_requested=yes"))
            second = self._ring(root, box, calls)
            self.assertFalse(second["bell"]["rung"])
            self.assertEqual(1, len(calls))

    def test_absent_or_unknown_codex_is_never_rung(self) -> None:
        for state in ("ABSENT", "LIMITED", None):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as d:
                root, box = _project(d)
                _codex_session(root)
                _stale_lock(root)
                if state:
                    mark(root, "codex", state)
                calls: list = []
                result = self._ring(root, box, calls)
                self.assertFalse(result["bell"]["rung"])
                self.assertEqual(f"CODEX_{state or 'UNKNOWN'}", result["bell"]["reason"])
                self.assertEqual([], calls)
                self.assertEqual(1, len(box.list_inbox()))

    def test_ring_is_off_unless_asked(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root, box = _project(d)
            _stale_lock(root)
            self.assertEqual("RING_OFF", run_sentinel_cycle(root, box)["bell"]["reason"])


class CliTests(unittest.TestCase):
    def test_loop_survives_a_failing_cycle(self) -> None:
        from v7_harness.cli import cmd_coord_sentinel

        with tempfile.TemporaryDirectory() as d:
            args = argparse.Namespace(project=d, once=False, loop=True, interval=0, write_brief=False,
                                      recipient="codex", ring=False)
            out = io.StringIO()
            with mock.patch("v7_harness.coord.sentinel.run_sentinel_cycle",
                            side_effect=[RuntimeError("boom"), KeyboardInterrupt()]), \
                    mock.patch("time.sleep"), redirect_stdout(out):
                with self.assertRaises(KeyboardInterrupt):
                    cmd_coord_sentinel(args)
            self.assertIn("RuntimeError: boom", out.getvalue())

    def test_presence_inbox_and_ack_commands(self) -> None:
        from v7_harness.cli import main

        with tempfile.TemporaryDirectory() as d:
            root, box = _project(d)
            box.publish("wake_x", {"p1_alert": True, "wake_reason": "STALE_LOCK"})
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(0, main(["coord", "presence", "--project", d, "--tool", "codex", "--state", "ACTIVE"]))
                self.assertEqual(0, main(["coord", "inbox", "--project", d]))
                self.assertEqual(0, main(["coord", "ack", "--project", d, "--id", "wake_x"]))
                self.assertEqual(1, main(["coord", "ack", "--project", d, "--id", "missing"]))
            lines = [json.loads(line) for line in out.getvalue().splitlines()]
            self.assertEqual("ACTIVE", lines[0]["presence"]["codex"]["state"])
            self.assertEqual([{"id": "wake_x", "kind": "P1", "step": None, "summary": "STALE_LOCK"}], lines[1]["messages"])
            self.assertTrue(lines[2]["ok"])
            self.assertEqual([], box.list_inbox())


if __name__ == "__main__":
    unittest.main()
