"""
Tests for Proof Receipt (Acceptance #3).
"""

import sys
import tempfile
import unittest
from pathlib import Path

from v7_harness.proof_receipt import (
    ProofReceiptStore,
    compute_proof_hash,
    run_with_receipt,
)


class TestProofReceipt(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.receipt_file = Path(self.temp_dir.name) / "receipts.jsonl"
        self.store = ProofReceiptStore(self.receipt_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_run_with_receipt_success(self):
        receipt = run_with_receipt(
            command=[sys.executable, "-c", "print('hello v7')"],
            task_id="U07",
            actor="Antigravity",
            receipt_store=self.store,
        )

        self.assertEqual(receipt.exit_code, 0)
        self.assertTrue(receipt.passed)
        self.assertIn("hello v7", receipt.stdout)
        self.assertTrue(len(receipt.output_hash) == 64)

        valid, msg = self.store.verify_receipt(receipt)
        self.assertTrue(valid)
        self.assertEqual(msg, "OK")

    def test_run_with_receipt_failure(self):
        receipt = run_with_receipt(
            command=[sys.executable, "-c", "import sys; sys.exit(42)"],
            task_id="U07",
            actor="Antigravity",
            receipt_store=self.store,
        )

        self.assertEqual(receipt.exit_code, 42)
        self.assertFalse(receipt.passed)

        valid, msg = self.store.verify_receipt(receipt)
        self.assertTrue(valid)

    def test_receipt_tamper_fails_verification(self):
        receipt = run_with_receipt(
            command=[sys.executable, "-c", "print('authentic')"],
            task_id="U07",
            actor="Antigravity",
            receipt_store=self.store,
        )
        # Tamper with the receipt stdout
        receipt.stdout = "forged output"
        valid, msg = self.store.verify_receipt(receipt)
        self.assertFalse(valid)
        self.assertIn("Hash mismatch", msg)

    def test_timeout_handled_deterministically(self):
        receipt = run_with_receipt(
            command=[sys.executable, "-c", "import time; time.sleep(1)"],
            task_id="U07",
            actor="Antigravity",
            receipt_store=self.store,
            timeout=0.1,
        )
        self.assertEqual(receipt.exit_code, 124)
        self.assertFalse(receipt.passed)
        self.assertIn("timed out", receipt.stderr)


if __name__ == "__main__":
    unittest.main()
