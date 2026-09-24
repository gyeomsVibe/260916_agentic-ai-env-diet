"""Tests for U23 Mailbox primitive (v7_harness/coord/mailbox.py)."""

from __future__ import annotations

import json
import multiprocessing as mp
from pathlib import Path
import tempfile
import unittest

from v7_harness.coord.mailbox import Mailbox, MailboxRejected
from v7_harness.coord.sentinel import (
    check_quiet_lock,
    check_ledger_reconciliation,
    triage_failure,
    generate_briefing,
    run_sentinel_cycle,
)


def _send_proc(root_str: str, number: int) -> None:
    box = Mailbox(Path(root_str))
    box.publish(f"m{number}", {"n": number})


def _race_claim_proc(root_str: str, worker_id: int, result_queue: mp.Queue) -> None:
    box = Mailbox(Path(root_str))
    claim = box.claim("contested-msg", consumer_id=f"worker_{worker_id}")
    if claim is not None:
        box.ack(claim)
        result_queue.put((worker_id, True))
    else:
        result_queue.put((worker_id, False))


class TestMailboxPublish(unittest.TestCase):
    def test_publish_basic_and_idempotency(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            box = Mailbox(root)
            path = box.publish("stable", {"value": 1})
            first_bytes = path.read_bytes()
            data = json.loads(first_bytes)
            self.assertEqual(data, {"schema": "u23-mailbox-v1", "message_id": "stable", "payload": {"value": 1}})
            self.assertEqual(box.publish("stable", {"value": 1}), path)
            self.assertEqual(path.read_bytes(), first_bytes)

    def test_publish_collision_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            box = Mailbox(root)
            path = box.publish("stable", {"value": 1})
            first_bytes = path.read_bytes()
            with self.assertRaises(MailboxRejected):
                box.publish("stable", {"value": 2})
            self.assertEqual(path.read_bytes(), first_bytes)

    def test_publish_invalid_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            box = Mailbox(root)
            for bad in ("../escape", "a/b", "a\\b", "a:b", ".", "..", "CON", "nul", ""):
                with self.subTest(bad=bad):
                    with self.assertRaises(MailboxRejected):
                        box.publish(bad, 1)

    def test_publish_invalid_payloads_and_size(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            box = Mailbox(root)
            for payload in (object(), {"bad": object()}):
                with self.assertRaises(MailboxRejected):
                    box.publish("bad-json", payload)

            small = Mailbox(root, max_message_bytes=80)
            with self.assertRaises(MailboxRejected):
                small.publish("too-big", {"blob": "x" * 100})

    def test_multiprocessing_parallel_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            context = mp.get_context("spawn")
            processes = [context.Process(target=_send_proc, args=(directory, i)) for i in range(8)]
            for p in processes:
                p.start()
            for p in processes:
                p.join(timeout=15)
                self.assertEqual(p.exitcode, 0)

            for i in range(8):
                entry = root / "inbox" / f"m{i}.json"
                self.assertTrue(entry.exists())
                content = json.loads(entry.read_text(encoding="utf-8"))
                self.assertEqual(content["payload"], {"n": i})

            self.assertEqual(list((root / "tmp").iterdir()), [])


class TestMailboxClaimAck(unittest.TestCase):
    def test_claim_and_idempotent_ack(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            box = Mailbox(root)
            box.publish("msg1", {"key": "val1"})
            self.assertEqual(box.list_inbox(), ["msg1"])

            claim1 = box.claim("msg1", consumer_id="agent_a")
            self.assertIsNotNone(claim1)
            self.assertEqual(claim1.message_id, "msg1")
            self.assertEqual(claim1.payload, {"key": "val1"})
            self.assertEqual(box.list_inbox(), [])

            claim_dup = box.claim("msg1", consumer_id="agent_b")
            self.assertIsNone(claim_dup)

            ack_path = box.ack(claim1)
            self.assertTrue(ack_path.exists())
            ack_again = box.ack(claim1)
            self.assertEqual(ack_again, ack_path)

    def test_nack_and_reclaim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            box = Mailbox(root)
            box.publish("msg2", {"key": "val2"})
            claim = box.claim("msg2", consumer_id="agent_a")
            self.assertIsNotNone(claim)
            self.assertEqual(box.list_inbox(), [])

            nack_path = box.nack(claim)
            self.assertTrue(nack_path.exists())
            self.assertEqual(box.list_inbox(), ["msg2"])

            claim_b = box.claim("msg2", consumer_id="agent_b")
            self.assertIsNotNone(claim_b)
            box.ack(claim_b)
            self.assertEqual(box.list_inbox(), [])

    def test_multiprocessing_race_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            box = Mailbox(root)
            box.publish("contested-msg", {"data": "race"})

            context = mp.get_context("spawn")
            queue = context.Queue()
            processes = [
                context.Process(target=_race_claim_proc, args=(directory, i, queue))
                for i in range(4)
            ]
            for p in processes:
                p.start()
            for p in processes:
                p.join(timeout=15)
                self.assertEqual(p.exitcode, 0)

            results = [queue.get(timeout=5) for _ in range(4)]
            winners = [wid for wid, won in results if won]
            losers = [wid for wid, won in results if not won]

            self.assertEqual(len(winners), 1)
            self.assertEqual(len(losers), 3)
            self.assertEqual(box.list_inbox(), [])
            self.assertTrue((root / "ack" / "contested-msg.json").exists())


def _producer_stress_proc(root_str: str, prod_id: int, count: int) -> None:
    box = Mailbox(Path(root_str))
    for i in range(count):
        box.publish(f"p{prod_id}_m{i}", {"prod": prod_id, "idx": i})


def _consumer_stress_proc(root_str: str, cons_id: str, target_total: int, ack_counter: mp.Value) -> None:
    box = Mailbox(Path(root_str))
    import time
    while True:
        with ack_counter.get_lock():
            if ack_counter.value >= target_total:
                break
        items = box.list_inbox()
        claimed_any = False
        for msg_id in items:
            claim = box.claim(msg_id, consumer_id=cons_id)
            if claim is not None:
                box.ack(claim)
                with ack_counter.get_lock():
                    ack_counter.value += 1
                claimed_any = True
        if not claimed_any:
            time.sleep(0.02)


class TestMailboxRecoveryAndStress(unittest.TestCase):
    def test_secret_pattern_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            box = Mailbox(root)
            for secret_payload in (
                {"key": "sk-12345678901234567890123456789012"},
                {"token": "ghp_abcdefghijklmnopqrstuvwxyz012345"},
                {"bearer": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.t-IDcSemACt8x4iTMCda8Yhe3iZaWbvV5XKSTbuAn0M"},
            ):
                with self.assertRaises(MailboxRejected):
                    box.publish("sec-test", secret_payload)

    def test_stale_claim_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            box = Mailbox(root)
            box.publish("stale-target", {"job": 42})
            claim = box.claim("stale-target", consumer_id="worker_crashed")
            self.assertIsNotNone(claim)
            self.assertEqual(box.list_inbox(), [])

            import time
            import os
            past_time = time.time() - 120.0
            os.utime(claim.claimed_path, (past_time, past_time))

            recovered = box.recover_stale_claims(stale_timeout_s=30.0)
            self.assertIn("stale-target", recovered)
            self.assertEqual(box.list_inbox(), ["stale-target"])

            claim2 = box.claim("stale-target", consumer_id="worker_healthy")
            self.assertIsNotNone(claim2)
            box.ack(claim2)
            self.assertEqual(box.list_inbox(), [])
            self.assertTrue((root / "ack" / "stale-target.json").exists())

    def test_stale_claim_recovery_preserves_underscored_message_id_and_payload(self):
        import time
        import os
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            box = Mailbox(root)
            message_id = "evt_alpha_beta"
            payload = {"kind": "BLOCKED", "nested": {"value": 7}}

            box.publish(message_id, payload)
            claim = box.claim(message_id, consumer_id="worker_crashed")
            self.assertIsNotNone(claim)
            old = time.time() - 120.0
            os.utime(claim.claimed_path, (old, old))

            recovered = box.recover_stale_claims(stale_timeout_s=30.0)
            self.assertEqual(recovered, [message_id])
            self.assertEqual(box.list_inbox(), [message_id])

            restored_path = root / "inbox" / f"{message_id}.json"
            restored = json.loads(restored_path.read_text(encoding="utf-8"))
            self.assertEqual(restored["message_id"], message_id)
            self.assertEqual(restored["payload"], payload)

            second_claim = box.claim(message_id, consumer_id="worker_healthy")
            self.assertIsNotNone(second_claim)
            self.assertEqual(second_claim.message_id, message_id)
            self.assertEqual(second_claim.payload, payload)

    def test_eight_producers_two_consumers_stress(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            box = Mailbox(root)
            context = mp.get_context("spawn")
            num_producers = 4
            messages_per_prod = 3
            total_messages = num_producers * messages_per_prod
            ack_counter = context.Value("i", 0)

            producers = [
                context.Process(target=_producer_stress_proc, args=(directory, p_id, messages_per_prod))
                for p_id in range(num_producers)
            ]
            consumers = [
                context.Process(target=_consumer_stress_proc, args=(directory, f"cons_{c_id}", total_messages, ack_counter))
                for c_id in range(2)
            ]

            for c in consumers:
                c.start()
            for p in producers:
                p.start()

            for p in producers:
                p.join(timeout=15)
                self.assertEqual(p.exitcode, 0)

            for c in consumers:
                c.join(timeout=15)
                self.assertEqual(c.exitcode, 0)

            self.assertEqual(ack_counter.value, total_messages)
            self.assertEqual(box.list_inbox(), [])
            self.assertEqual(list((root / "tmp").iterdir()), [])
            self.assertEqual(list((root / "claimed").iterdir()), [])


class TestMailboxDeliveryAdapter(unittest.TestCase):
    def test_is_actionable_event(self):
        from v7_harness.coord.adapter import is_actionable_event
        from v7_harness.coord.stream import Event

        e_run = Event("e1", "2026-09-24T12:00:00", "antigravity", "RUN", "S1", "done", (), {"cmd": "c", "exit": 0})
        e_blocked = Event("e2", "2026-09-24T12:01:00", "antigravity", "BLOCKED", "S1", "err", (), {})
        e_handoff = Event("e3", "2026-09-24T12:02:00", "claude", "HANDOFF", "S1", "next", (), {})
        e_note = Event("e4", "2026-09-24T12:03:00", "codex", "NOTE", "S1", "info", (), {})
        e_plan = Event("e5", "2026-09-24T12:04:00", "codex", "PLAN", "S1", "plan", (), {})
        e_verdict = Event("e6", "2026-09-24T12:05:00", "codex", "VERDICT", "S1", "pass", (), {"cmd": "c", "exit": 0})
        e_req = Event("e7", "2026-09-24T12:06:00", "antigravity", "NOTE", "S1", "req", (), {"verdict_requested": True})

        self.assertTrue(is_actionable_event(e_run))
        self.assertTrue(is_actionable_event(e_blocked))
        self.assertTrue(is_actionable_event(e_handoff))
        self.assertFalse(is_actionable_event(e_note))
        self.assertFalse(is_actionable_event(e_plan))
        self.assertFalse(is_actionable_event(e_verdict))
        self.assertTrue(is_actionable_event(e_req))

        # Dict format support
        self.assertTrue(is_actionable_event({"kind": "RUN"}))
        self.assertFalse(is_actionable_event({"kind": "NOTE"}))

    def test_format_mailbox_notice(self):
        from v7_harness.coord.adapter import format_mailbox_notice

        msg_agy = format_mailbox_notice({"actor": "antigravity", "kind": "RUN", "step": "S2", "summary": "done"})
        self.assertIn("[안티그래비티에서 온 대화]", msg_agy)
        self.assertIn("[RUN]", msg_agy)

        msg_claude = format_mailbox_notice({"actor": "claude", "kind": "HANDOFF", "step": "S2", "summary": "next"})
        self.assertIn("[클로드에게서 온 대화]", msg_claude)

    def test_sync_stream_to_mailbox_and_dispatch(self):
        from v7_harness.coord.adapter import sync_stream_to_mailbox, dispatch_mailbox_messages
        from v7_harness.coord.stream import append_event

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            box_dir = root / "box"
            box_dir.mkdir(parents=True, exist_ok=True)
            box = Mailbox(box_dir)
            cursor_file = root / "cursor.json"

            append_event(root, actor="codex", kind="PLAN", step="S1", summary="planning", refs=(), evidence={})
            append_event(root, actor="antigravity", kind="RUN", step="S1", summary="run ok", refs=(), evidence={"cmd": "t", "exit": 0})
            append_event(root, actor="codex", kind="NOTE", step="S1", summary="note", refs=(), evidence={})
            append_event(root, actor="antigravity", kind="BLOCKED", step="S1", summary="blocked", refs=(), evidence={})

            synced = sync_stream_to_mailbox(root, box, cursor_file=cursor_file)
            self.assertEqual(len(synced), 2)
            self.assertEqual(len(box.list_inbox()), 2)

            # Idempotent sync
            synced_again = sync_stream_to_mailbox(root, box, cursor_file=cursor_file)
            self.assertEqual(len(synced_again), 0)
            self.assertEqual(len(box.list_inbox()), 2)

            # Durable pull fallback (sender_fn=None)
            held = dispatch_mailbox_messages(box, sender_fn=None)
            self.assertEqual(len(held), 2)
            self.assertTrue(all(h["status"] == "HELD" for h in held))
            self.assertEqual(len(box.list_inbox()), 2)

            # Dispatch with failure (NACK)
            failed = dispatch_mailbox_messages(box, sender_fn=lambda _: False, consumer_id="c1")
            self.assertEqual(len(failed), 2)
            self.assertTrue(all(f["status"] == "NACK" for f in failed))
            self.assertEqual(len(box.list_inbox()), 2)

            # Dispatch with success (ACK)
            delivered = []
            def ok_sender(text: str) -> bool:
                delivered.append(text)
                return True

            acked = dispatch_mailbox_messages(box, sender_fn=ok_sender, consumer_id="c1")
            self.assertEqual(len(acked), 2)
            self.assertTrue(all(a["status"] == "ACK" for a in acked))
            self.assertEqual(len(box.list_inbox()), 0)
            self.assertEqual(len(delivered), 2)


class TestU23S3Sentinel(unittest.TestCase):
    def test_quiet_lock_inspection(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            work_dir = root / ".work"
            work_dir.mkdir(parents=True, exist_ok=True)
            lock_file = work_dir / "QUIET_LOCK"

            # 1. Clean
            res = check_quiet_lock(root)
            self.assertEqual(res["status"], "CLEAN")
            self.assertFalse(res["is_stale"])

            # 2. Active
            import time
            import os
            active_data = {"owner": "test_owner", "task": "T01", "started_at": time.time(), "pid": os.getpid()}
            lock_file.write_text(json.dumps(active_data), encoding="utf-8")
            res = check_quiet_lock(root)
            self.assertEqual(res["status"], "ACTIVE")
            self.assertFalse(res["is_stale"])

            # 3. Stale by age
            old_data = {"owner": "test_owner", "task": "T01", "started_at": time.time() - 4000.0, "pid": os.getpid()}
            lock_file.write_text(json.dumps(old_data), encoding="utf-8")
            res = check_quiet_lock(root, max_age_s=3600.0)
            self.assertEqual(res["status"], "STALE")
            self.assertTrue(res["is_stale"])
            self.assertIn("AGE", res["reason"])

            # 4. Stale by dead PID
            dead_data = {"owner": "test_owner", "task": "T01", "started_at": time.time(), "pid": 99999999}
            lock_file.write_text(json.dumps(dead_data), encoding="utf-8")
            res = check_quiet_lock(root)
            self.assertEqual(res["status"], "STALE")
            self.assertTrue(res["is_stale"])
            self.assertIn("DEAD", res["reason"])

    def test_ledger_reconciliation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runs_dir = root / "runs"
            r1 = runs_dir / "task_reconcile"
            r1.mkdir(parents=True, exist_ok=True)
            (r1 / "summary.json").write_text(json.dumps({"task": "task_reconcile", "verdict_hint": "NEEDS_RECONCILIATION"}), encoding="utf-8")
            r2 = runs_dir / "task_pass"
            r2.mkdir(parents=True, exist_ok=True)
            (r2 / "summary.json").write_text(json.dumps({"task": "task_pass", "verdict_hint": "PASS"}), encoding="utf-8")

            tasks = check_ledger_reconciliation(root)
            self.assertEqual(tasks, ["task_reconcile"])

    def test_triage_failure(self):
        res_code = triage_failure("Traceback:\nSyntaxError: invalid syntax")
        self.assertEqual(res_code["classification"], "CODE")
        self.assertFalse(res_code["is_p1"])

        res_infra = triage_failure("'python' is not recognized as an internal or external command")
        self.assertEqual(res_infra["classification"], "INFRA")
        self.assertTrue(res_infra["is_p1"])

        res_unk = triage_failure("exit code 137")
        self.assertEqual(res_unk["classification"], "UNKNOWN")
        self.assertFalse(res_unk["is_p1"])

    def test_briefing_bounds(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            briefing = generate_briefing(root)
            lines = briefing.splitlines()
            self.assertLessEqual(len(lines), 60)
            self.assertLessEqual(len(briefing.encode("utf-8")), 6144)
            self.assertIn("# Sentinel Briefing", briefing)

    def test_sentinel_cycle_wake_gatekeeper(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            box_dir = root / ".coord" / "mailbox"
            box_dir.mkdir(parents=True, exist_ok=True)
            box = Mailbox(box_dir)

            # Clean cycle
            telemetry = run_sentinel_cycle(root, box, recipient="codex")
            self.assertEqual(telemetry["paid_api_calls"], 0)
            self.assertFalse(telemetry["p1_wake_emitted"])
            self.assertEqual(len(box.list_inbox()), 0)

            # Stale lock
            work_dir = root / ".work"
            work_dir.mkdir(parents=True, exist_ok=True)
            (work_dir / "QUIET_LOCK").write_text(
                json.dumps({"owner": "dead_worker", "task": "T02", "started_at": 0, "pid": 99999999}),
                encoding="utf-8",
            )
            telemetry = run_sentinel_cycle(root, box, recipient="codex")
            self.assertEqual(telemetry["paid_api_calls"], 0)
            self.assertTrue(telemetry["p1_wake_emitted"])

            inbox = box.list_inbox()
            self.assertEqual(len(inbox), 1)
            claimed = box.claim(inbox[0], consumer_id="test")
            self.assertIsNotNone(claimed)
            self.assertTrue(claimed.payload.get("p1_alert"))


class TestU23S4SentinelCLI(unittest.TestCase):
    def test_sentinel_cli_parser_options(self):
        from v7_harness.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["coord", "sentinel", "--once", "--interval", "10", "--write-brief"])
        self.assertTrue(args.once)
        self.assertEqual(args.interval, 10)
        self.assertTrue(args.write_brief)
        self.assertEqual(args.recipient, "codex")

    def test_sentinel_cli_execution_once(self):
        from v7_harness.cli import cmd_coord_sentinel
        import argparse

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".coord" / "mailbox").mkdir(parents=True, exist_ok=True)
            (root / ".coord" / "PLAN.md").write_text("# Test Plan\n- 상태: codex: LIMITED\n", encoding="utf-8")

            args = argparse.Namespace(
                project=str(root),
                once=True,
                loop=False,
                interval=30,
                write_brief=True,
                recipient="codex",
            )
            rc = cmd_coord_sentinel(args)
            self.assertEqual(rc, 0)

            brief_path = root / ".coord" / "codex_brief.md"
            self.assertTrue(brief_path.exists())
            content = brief_path.read_text(encoding="utf-8")
            self.assertIn("Sentinel Briefing", content)
            self.assertLessEqual(len(content.splitlines()), 60)


if __name__ == "__main__":
    unittest.main()

