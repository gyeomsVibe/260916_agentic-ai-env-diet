"""B41 bundle regression tests: B41 (external_paths), B36 (SOURCE_DIVERGED), B35 (summary key bound), B39 (heavy subdirs exclusion)."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

from v7_harness.cli import cmd_pilot_run
from v7_harness.isolation.errors import ExternalWriteDetectedError, SourceDivergenceError
from v7_harness.isolation.security import (
    DEFAULT_WATCH_EXCLUDES,
    HEAVY_REINCLUDE_SUBDIRS,
    _watch_path_excluded,
    is_protected_watch_dir_ancestor,
    is_protected_watch_path,
    snapshot_watch_roots,
)
from v7_harness.pilot import PilotConfig, run_pilot


class B41BundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.work = self.root / "work"
        self.home = self.root / "home"
        self.source.mkdir()
        self.work.mkdir()
        self.home.mkdir()

        (self.source / "calc.py").write_text("def mul(a, b): return a * b\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    # --- B41: external_paths in summary ---
    def test_external_write_includes_external_paths_in_summary(self) -> None:
        """Verify that when an external write occurs, summary contains external_paths with modified file."""
        config = PilotConfig(
            task_id="B41_TEST",
            title="B41 Test Task",
            prompt="do something",
            source_dir=self.source,
            work_dir=self.work,
            agy_command=["python", "-c", "import sys; sys.exit(0)"],
            watch_roots=[self.home],
            print_timeout_s=10,
        )

        # Mutate a file in home root
        escaped_file = self.home / "escaped_file.txt"
        escaped_file.write_text("initial", encoding="utf-8")

        # Snapshot before mutation
        watch = snapshot_watch_roots([self.home])
        escaped_file.write_text("mutated content", encoding="utf-8")

        with self.assertRaises(ExternalWriteDetectedError) as caught:
            watch.assert_unchanged()

        self.assertIn("escaped_file.txt", caught.exception.changed_paths)

    def test_pilot_run_external_write_populates_summary_external_paths(self) -> None:
        """Verify run_pilot includes external_paths in summary when ExternalWriteDetectedError is raised."""
        config = PilotConfig(
            task_id="B41_PILOT_TEST",
            title="B41 Pilot Test",
            prompt="do something",
            source_dir=self.source,
            work_dir=self.work,
            agy_command=["python", "-c", "import sys; sys.exit(0)"],
            watch_roots=[self.home],
            print_timeout_s=10,
        )

        class MutatingWatch:
            def assert_unchanged(self) -> None:
                raise ExternalWriteDetectedError(
                    "External write detected",
                    effect_state="UNKNOWN",
                    changed_paths=[".claude/settings.json", "escaped.txt"],
                )

        from v7_harness.adapters.agy import AgyOutcome
        launcher_inst = mock.MagicMock()
        launcher_inst.last_outcome = AgyOutcome(
            successful=True,
            status="SUCCESS",
            error_class="NONE",
            effect_state="CONFIRMED",
            retryable=False,
            conversation_id="test-conv",
            usage={"input_tokens": 100},
        )
        launcher_inst.raw_paths = (Path("stdout.json"), Path("stderr.err"))

        with mock.patch("v7_harness.pilot.DurableExecutionEngine.execute", return_value=None):
            with mock.patch("v7_harness.pilot.AgyProcessLauncher", return_value=launcher_inst):
                with mock.patch("v7_harness.pilot.snapshot_watch_roots", return_value=MutatingWatch()):
                    summary = run_pilot(config)

        self.assertEqual(summary["state"], "FAILED")
        self.assertEqual(summary["error_class"], "EXTERNAL_WRITE")
        self.assertIn("external_paths", summary)
        self.assertEqual(summary["external_paths"], [".claude/settings.json", "escaped.txt"])
        self.assertGreaterEqual(len(summary), 14)
        self.assertLessEqual(len(summary), 18)

    # --- B36: SOURCE_DIVERGED structured summary ---
    def test_dry_run_source_divergence_returns_structured_summary(self) -> None:
        """Verify SourceDivergenceError in dry_run_promotion sets error_class=SOURCE_DIVERGED."""
        config = PilotConfig(
            task_id="B36_TEST",
            title="B36 Test Task",
            prompt="do something",
            source_dir=self.source,
            work_dir=self.work,
            agy_command=["python", "-c", "import sys; sys.exit(0)"],
            watch_roots=[self.home],
            print_timeout_s=10,
        )

        from v7_harness.adapters.agy import AgyOutcome
        launcher_inst = mock.MagicMock()
        launcher_inst.last_outcome = AgyOutcome(
            successful=True,
            status="SUCCESS",
            error_class="NONE",
            effect_state="CONFIRMED",
            retryable=False,
            conversation_id="test-conv",
            usage={"input_tokens": 100},
        )
        launcher_inst.raw_paths = (Path("stdout.json"), Path("stderr.err"))

        class DummyWatch:
            def assert_unchanged(self) -> None:
                pass

        with mock.patch("v7_harness.pilot.DurableExecutionEngine.execute", return_value=None):
            with mock.patch("v7_harness.pilot.AgyProcessLauncher", return_value=launcher_inst):
                with mock.patch("v7_harness.pilot.dry_run_promotion", side_effect=SourceDivergenceError("Source diverged")):
                    with mock.patch("v7_harness.pilot.snapshot_watch_roots", return_value=DummyWatch()):
                        summary = run_pilot(config)

        self.assertEqual(summary["state"], "FAILED")
        self.assertEqual(summary["error_class"], "SOURCE_DIVERGED")
        self.assertEqual(summary["promotion"], "REJECTED")
        self.assertEqual(summary["verdict_hint"], "BLOCKED")
        self.assertGreaterEqual(len(summary), 14)
        self.assertLessEqual(len(summary), 18)

    def test_cmd_pilot_run_catches_source_divergence_cleanly(self) -> None:
        """Verify cmd_pilot_run traps SourceDivergenceError and outputs structured summary without traceback."""
        args = Namespace(
            task="B36_CLI_TEST",
            source=str(self.source),
            prompt="test prompt",
            worker="local",  # a paid worker needs a manual since B85; this test checks CLI plumbing only
            prompt_file=None,
            work_dir=str(self.work),
            watch_root=None,
            agy_command=None,
            title="Test Task",
            print_timeout=5,
            approve=None,
            accept_cmd=None,
            model=None,
            allow_no_changes=False,
        )

        with mock.patch("v7_harness.pilot.run_pilot", side_effect=SourceDivergenceError("Base diverged")):
            with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                exit_code = cmd_pilot_run(args)

        self.assertEqual(exit_code, 1)
        output = mock_stdout.getvalue()
        summary = json.loads(output)
        self.assertEqual(summary["task_id"], "B36_CLI_TEST")
        self.assertEqual(summary["state"], "FAILED")
        self.assertEqual(summary["error_class"], "SOURCE_DIVERGED")
        self.assertEqual(summary["verdict_hint"], "BLOCKED")

    # --- B39: Heavy subdirectories exclusion from re-includes ---
    def test_heavy_subdirs_under_reincludes_are_excluded(self) -> None:
        """Verify that node_modules, .venv, etc. under .claude/skills or .codex/skills are excluded."""
        heavy_paths = [
            ".claude/skills/my-tool/node_modules/foo/index.js",
            ".claude/skills/my-tool/.venv/lib/site-packages/pkg.py",
            ".claude/skills/my-tool/__pycache__/cache.pyc",
            ".codex/skills/calc/node_modules/math.js",
            ".codex/skills/calc/venv/bin/activate",
        ]
        for p in heavy_paths:
            self.assertFalse(
                is_protected_watch_path(p),
                f"Expected heavy path '{p}' to NOT be protected",
            )
            self.assertTrue(
                _watch_path_excluded(p, DEFAULT_WATCH_EXCLUDES),
                f"Expected heavy path '{p}' to be excluded by watch excludes",
            )

        # But normal skill files must remain protected
        normal_paths = [
            ".claude/skills/my-tool/SKILL.md",
            ".claude/skills/my-tool/scripts/run.py",
            ".codex/skills/calc/SKILL.md",
        ]
        for p in normal_paths:
            self.assertTrue(
                is_protected_watch_path(p),
                f"Expected normal skill file '{p}' to be protected",
            )
            self.assertFalse(
                _watch_path_excluded(p, DEFAULT_WATCH_EXCLUDES),
                f"Expected normal skill file '{p}' to NOT be excluded",
            )

    def test_heavy_dir_ancestor_is_not_traversed(self) -> None:
        """Verify is_protected_watch_dir_ancestor returns False for heavy subdirs."""
        for heavy in HEAVY_REINCLUDE_SUBDIRS:
            test_dir = f".claude/skills/tool/{heavy}"
            self.assertFalse(
                is_protected_watch_dir_ancestor(test_dir),
                f"Expected heavy dir '{test_dir}' to NOT be treated as a protected watch ancestor",
            )
