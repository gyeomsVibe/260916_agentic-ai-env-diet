"""
Tests for Intent Ledger (Acceptance #2).
"""

import json
import tempfile
import unittest
from pathlib import Path

from v7_harness.intent_ledger import IntentLedger


class TestIntentLedger(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ledger_file = Path(self.temp_dir.name) / "intent.jsonl"
        self.ledger = IntentLedger(self.ledger_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_append_and_hash_chain(self):
        e1 = self.ledger.append(
            task_id="U07",
            actor="Codex",
            category="REQUIREMENT",
            content="Context lease must fail closed upon expiry.",
            rationale="Prevent stale context leakage.",
            assumption="System clocks are synchronized.",
        )
        e2 = self.ledger.append(
            task_id="U07",
            actor="Antigravity",
            category="DECISION",
            content="Implement UTC ISO-8601 validation.",
            rationale="Satisfy lease expiry requirement.",
        )

        self.assertEqual(len(self.ledger.entries), 2)
        self.assertEqual(e2.prev_hash, e1.entry_hash)

        valid, reason = self.ledger.verify_integrity()
        self.assertTrue(valid)
        self.assertEqual(reason, "OK")

    def test_invalidation(self):
        e1 = self.ledger.append(
            task_id="U07",
            actor="Codex",
            category="DECISION",
            content="Use SQLite for receipts.",
        )
        self.ledger.invalidate(
            target_entry_id=e1.entry_id,
            actor="Codex",
            task_id="U07",
            reason="Avoid external binaries; use pure stdlib jsonl instead.",
        )

        active = self.ledger.get_active_entries("U07")
        self.assertEqual(len(active), 0)

        valid, reason = self.ledger.verify_integrity()
        self.assertTrue(valid)

    def test_tamper_detection_fails_closed(self):
        self.ledger.append(
            task_id="U07",
            actor="Codex",
            category="REQUIREMENT",
            content="Initial requirement.",
        )
        self.ledger.append(
            task_id="U07",
            actor="Antigravity",
            category="DECISION",
            content="Initial decision.",
        )

        # Tamper with the disk file
        lines = self.ledger_file.read_text(encoding="utf-8").strip().splitlines()
        first_entry = json.loads(lines[0])
        first_entry["content"] = "TAMPERED CONTENT"
        lines[0] = json.dumps(first_entry)
        self.ledger_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Reload
        tampered_ledger = IntentLedger(self.ledger_file)
        valid, reason = tampered_ledger.verify_integrity()
        self.assertFalse(valid)
        self.assertIn("Integrity failure", reason)


if __name__ == "__main__":
    unittest.main()
