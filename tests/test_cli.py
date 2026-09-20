"""
Smoke tests for CLI entrypoint.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

from v7_harness.cli import main


class TestCLI(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cli_snapshot(self):
        test_file = self.root / "sample.txt"
        test_file.write_text("sample content", encoding="utf-8")
        out_snap = self.root / "snap.json"

        ret = main(["snapshot", "--target-path", str(self.root), "--output", str(out_snap)])
        self.assertEqual(ret, 0)
        self.assertTrue(out_snap.exists())

    def test_cli_ledger_append_and_verify(self):
        ledger_path = self.root / "ledger.jsonl"
        ret1 = main([
            "ledger-append",
            "--ledger-file", str(ledger_path),
            "--task-id", "U07",
            "--actor", "Antigravity",
            "--category", "REQUIREMENT",
            "--content", "Requirement content",
        ])
        self.assertEqual(ret1, 0)

        ret2 = main(["ledger-verify", "--ledger-file", str(ledger_path)])
        self.assertEqual(ret2, 0)

    def test_cli_lease_check(self):
        lease_path = self.root / "lease.json"
        lease_data = {
            "lease_id": "L-TEST",
            "document_path": "test.md",
            "authority": "FACT",
            "scope": ["*"],
            "created_at": "2026-09-17T00:00:00Z",
        }
        lease_path.write_text(json.dumps(lease_data), encoding="utf-8")
        ret = main(["lease-check", "--file", str(lease_path)])
        self.assertEqual(ret, 0)

    def test_cli_eval_next(self):
        ret = main(["eval-next", "--current-task-id", "U07", "--next-task", "U08"])
        self.assertEqual(ret, 0)

        # When failures present
        ret_fail = main(["eval-next", "--current-task-id", "U07", "--has-failures"])
        self.assertEqual(ret_fail, 1)

    def test_cli_benchmark(self):
        ret = main(["benchmark", "--name", "smoke_bench"])
        self.assertEqual(ret, 0)


if __name__ == "__main__":
    unittest.main()
