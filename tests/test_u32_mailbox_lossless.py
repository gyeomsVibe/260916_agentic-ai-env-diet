"""U32a: the voicemail keeps every message (at-least-once, deduplicated by message id).

Each test pins one way a message could vanish or be reported as delivered without being delivered.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from v7_harness.coord.mailbox import Mailbox, MailboxRejected


def _box(directory: str) -> Mailbox:
    return Mailbox(Path(directory))


def _backdate(path: Path, seconds: float) -> None:
    moment = time.time() - seconds
    os.utime(path, (moment, moment))


class LeaseTests(unittest.TestCase):
    def test_fresh_claim_is_not_recovered_even_if_the_message_is_old(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            box = _box(d)
            _backdate(box.publish("old", {"n": 1}), 120)
            claim = box.claim("old", "worker")
            self.assertEqual([], box.recover_stale_claims(stale_timeout_s=60))
            self.assertTrue(box.ack(claim).is_file())
            self.assertEqual([], box.list_inbox())

    def test_renew_extends_the_lease(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            box = _box(d)
            box.publish("long", {"n": 1})
            claim = box.claim("long", "worker")
            _backdate(claim.claimed_path, 120)
            self.assertTrue(box.renew(claim))
            self.assertEqual([], box.recover_stale_claims(stale_timeout_s=60))


class AckTests(unittest.TestCase):
    def test_ack_after_the_claim_was_lost_raises_instead_of_reporting_success(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            box = _box(d)
            box.publish("m", {"n": 1})
            claim = box.claim("m", "worker")
            _backdate(claim.claimed_path, 120)
            self.assertEqual(["m"], box.recover_stale_claims(stale_timeout_s=60))
            with self.assertRaises(MailboxRejected):
                box.ack(claim)
            self.assertEqual(["m"], box.list_inbox())

    def test_ack_link_failure_keeps_the_claimed_message(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            box = _box(d)
            box.publish("m", {"n": 1})
            claim = box.claim("m", "worker")
            with mock.patch("v7_harness.coord.mailbox.os.link", side_effect=PermissionError("locked")):
                with self.assertRaises(PermissionError):
                    box.ack(claim)
            self.assertTrue(claim.claimed_path.is_file())


class NackTests(unittest.TestCase):
    def test_nack_failure_keeps_the_claimed_message_for_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            box = _box(d)
            box.publish("m", {"n": 1})
            claim = box.claim("m", "worker")
            with mock.patch("v7_harness.coord.mailbox.os.link", side_effect=PermissionError("locked")):
                box.nack(claim)
            self.assertTrue(claim.claimed_path.is_file())
            _backdate(claim.claimed_path, 120)
            self.assertEqual(["m"], box.recover_stale_claims(stale_timeout_s=60))

    def test_recovery_never_overwrites_a_message_already_in_the_inbox(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            box = _box(d)
            box.publish("m", {"n": 1})
            claim = box.claim("m", "worker")
            (box.inbox_dir / "m.json").write_bytes(claim.claimed_path.read_bytes())
            _backdate(claim.claimed_path, 120)
            box.recover_stale_claims(stale_timeout_s=60)
            self.assertEqual(["m"], box.list_inbox())
            self.assertEqual([], list(box.claimed_dir.glob("*.json")))


class MessageIdentityTests(unittest.TestCase):
    """One message id means one content, across inbox, claimed and ack."""

    def test_republish_while_claimed_with_other_content_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            box = _box(d)
            box.publish("m", {"v": "old"})
            claim = box.claim("m", "worker")
            with self.assertRaises(MailboxRejected):
                box.publish("m", {"v": "new"})
            box.nack(claim)
            restored = json.loads((box.inbox_dir / "m.json").read_text(encoding="utf-8"))
            self.assertEqual({"v": "old"}, restored["payload"])

    def test_identical_republish_while_claimed_does_not_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            box = _box(d)
            box.publish("m", {"v": 1})
            claim = box.claim("m", "worker")
            box.publish("m", {"v": 1})
            self.assertEqual([], box.list_inbox())
            box.ack(claim)
            self.assertEqual([], box.list_inbox())

    def test_acked_message_is_not_redelivered_by_an_identical_republish(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            box = _box(d)
            box.publish("m", {"v": 1})
            box.ack(box.claim("m", "worker"))
            self.assertEqual(box.ack_dir / "m.json", box.publish("m", {"v": 1}))
            self.assertEqual([], box.list_inbox())
            self.assertTrue(box.has_message("m"))

    def test_acked_id_with_other_content_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            box = _box(d)
            box.publish("m", {"v": 1})
            box.ack(box.claim("m", "worker"))
            with self.assertRaises(MailboxRejected):
                box.publish("m", {"v": 2})


class MessageIdTests(unittest.TestCase):
    def test_trailing_newline_id_is_rejected(self) -> None:
        # re.match with "$" accepts a trailing newline, which would put a newline into the file name.
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(MailboxRejected):
                _box(d).publish("abc\n", {"n": 1})


class DamagedFileTests(unittest.TestCase):
    def test_unreadable_claimed_file_is_quarantined_and_counted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            box = _box(d)
            broken = box.claimed_dir / "x_worker_1_abc.json"
            broken.write_text("{not json", encoding="utf-8")
            _backdate(broken, 120)
            box.recover_stale_claims(stale_timeout_s=60)
            self.assertEqual([], list(box.claimed_dir.glob("*.json")))
            self.assertEqual(1, len(box.list_bad()))

    def test_unreadable_inbox_file_is_quarantined_on_claim(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            box = _box(d)
            (box.inbox_dir / "x.json").write_text("{not json", encoding="utf-8")
            self.assertIsNone(box.claim("x", "worker"))
            self.assertEqual([], list(box.claimed_dir.glob("*.json")))
            self.assertEqual(1, len(box.list_bad()))


class PeekTests(unittest.TestCase):
    def test_peek_reads_payloads_without_moving_anything(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            box = _box(d)
            box.publish("a", {"kind": "BLOCKED"})
            box.publish("b", {"kind": "RUN"})
            self.assertEqual([("a", {"kind": "BLOCKED"}), ("b", {"kind": "RUN"})], box.peek())
            self.assertEqual(["a", "b"], box.list_inbox())
            self.assertEqual([], list(box.claimed_dir.glob("*.json")))


if __name__ == "__main__":
    unittest.main()
