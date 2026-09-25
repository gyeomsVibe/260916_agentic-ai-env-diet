"""B25 regression test: sqlite3.DatabaseError in pilot run and reconcile converts to DB_UNAVAILABLE cleanly."""

from __future__ import annotations

import io
import json
import sqlite3
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

from v7_harness.cli import cmd_pilot_reconcile, cmd_pilot_run


class B25DbUnavailableTests(unittest.TestCase):
    def test_cmd_pilot_run_catches_database_error(self) -> None:
        """Verify DatabaseError during pilot run returns DB_UNAVAILABLE summary and exit 1."""
        args = Namespace(
            task="B25_TEST",
            source=str(Path(".")),
            prompt="test prompt",
            worker="local",  # a paid worker needs a manual since B85; this test checks CLI plumbing only
            prompt_file=None,
            work_dir=".coord/test_work",
            watch_root=None,
            agy_command=None,
            title="Test Task",
            print_timeout=5,
            approve=None,
            accept_cmd=None,
            model=None,
        )

        with mock.patch("v7_harness.pilot.run_pilot", side_effect=sqlite3.DatabaseError("database disk image is malformed")):
            with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                exit_code = cmd_pilot_run(args)

        self.assertEqual(exit_code, 1)
        summary = json.loads(mock_stdout.getvalue())
        self.assertEqual(summary["task_id"], "B25_TEST")
        self.assertEqual(summary["state"], "FAILED")
        self.assertEqual(summary["error_class"], "DB_UNAVAILABLE")
        self.assertEqual(summary["verdict_hint"], "BLOCKED")
        self.assertIn("Recovery hint", summary["message"])

    def test_cmd_pilot_reconcile_catches_database_error(self) -> None:
        """Verify DatabaseError during reconcile returns DB_UNAVAILABLE report and exit 1."""
        args = Namespace(
            task="B25_REC_TEST",
            work_dir=".coord/test_work",
        )

        with mock.patch("v7_harness.pilot.reconcile_pilot", side_effect=sqlite3.DatabaseError("malformed database")):
            with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                exit_code = cmd_pilot_reconcile(args)

        self.assertEqual(exit_code, 1)
        report = json.loads(mock_stdout.getvalue())
        self.assertEqual(report["task_id"], "B25_REC_TEST")
        self.assertEqual(report["state"], "FAILED")
        self.assertEqual(report["error_class"], "DB_UNAVAILABLE")
        self.assertIn("Recovery hint", report["message"])


if __name__ == "__main__":
    unittest.main()
