"""B23 regression test: BrokerAlreadyRunning handling in CLI and Claude runtime noise exclusions."""

from __future__ import annotations

import io
import json
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

from v7_harness.broker.core import BrokerAlreadyRunning
from v7_harness.cli import cmd_pilot_run
from v7_harness.isolation.security import DEFAULT_WATCH_EXCLUDES, _watch_path_excluded


class B23ConcurrencySummaryTests(unittest.TestCase):
    def test_default_watch_excludes_includes_claude_runtime_paths(self) -> None:
        """Verify Claude Code runtime noise paths are safely excluded from external write watch."""
        claude_noise_targets = [
            ".claude.json",
            ".claude/cache/session.tmp",
            "claude/cache.tmp",
        ]
        patterns = DEFAULT_WATCH_EXCLUDES
        for target in claude_noise_targets:
            self.assertTrue(
                _watch_path_excluded(target, patterns),
                f"Expected '{target}' to be excluded by DEFAULT_WATCH_EXCLUDES",
            )
        # B28: Verify .claude/settings.json is protected and NOT excluded
        self.assertFalse(
            _watch_path_excluded(".claude/settings.json", patterns),
            "Expected '.claude/settings.json' to NOT be excluded (protected watch file)",
        )

    def test_cmd_pilot_run_catches_broker_already_running(self) -> None:
        """Verify BrokerAlreadyRunning is captured cleanly without traceback, returning BLOCKED summary and exit 1."""
        args = Namespace(
            task="B23_TEST",
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

        with mock.patch("v7_harness.pilot.run_pilot", side_effect=BrokerAlreadyRunning("BROKER_ALREADY_RUNNING")):
            with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                exit_code = cmd_pilot_run(args)

        self.assertEqual(exit_code, 1)
        output = mock_stdout.getvalue()
        summary = json.loads(output)

        self.assertEqual(summary["task_id"], "B23_TEST")
        self.assertEqual(summary["state"], "FAILED")
        self.assertEqual(summary["error_class"], "BROKER_ALREADY_RUNNING")
        self.assertEqual(summary["verdict_hint"], "BLOCKED")
        self.assertEqual(summary["effect_state"], "NONE")
        self.assertIn("Another broker is currently running", summary["message"])


if __name__ == "__main__":
    unittest.main()
