"""U33: a pilot run reports itself to the coordination stream without anyone remembering a flag."""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from v7_harness.cli import build_parser, main, record_pilot_in_stream
from v7_harness.coord.stream import read_events

SUMMARY = {
    "state": "SUCCEEDED",
    "error_class": "NONE",
    "effect_state": "CONFIRMED",
    "promotion": "DRY_RUN_PASSED",
    "bundle_id": "b" * 64,
    "changed_files": ["a.py"],
    "acceptance_exit": 0,
    "verdict_hint": "PASS",
}


def _uaos_project(directory: str) -> Path:
    root = Path(directory)
    (root / ".coord").mkdir()
    (root / ".coord" / "PLAN.md").write_text("# plan\n", encoding="utf-8")
    return root


def _run(root: Path, *extra: str, env: dict | None = None) -> None:
    # Strip every tool marker so the test decides the caller, not the session that runs the suite.
    markers = ("UAOS_STREAM_AUTOLOG", "CLAUDECODE", "CODEX_", "ANTIGRAVITY", "GEMINI_CLI")
    environment = {k: v for k, v in os.environ.items() if not k.upper().startswith(markers)}
    environment.update(env or {})
    with mock.patch.dict(os.environ, environment, clear=True), \
            mock.patch("v7_harness.pilot.run_pilot", return_value=dict(SUMMARY)), \
            redirect_stdout(io.StringIO()):
        main(["pilot", "run", "--task", "T33", "--source", str(root), "--prompt", "x", "--worker", "local", *extra])


class DefaultOnTests(unittest.TestCase):
    def test_flag_defaults(self) -> None:
        parser = build_parser()
        base = ["pilot", "run", "--task", "T", "--source", ".", "--prompt", "x", "--worker", "local"]
        self.assertTrue(parser.parse_args(base).coord_log)
        self.assertFalse(parser.parse_args([*base, "--no-coord-log"]).coord_log)

    def test_run_is_recorded_with_its_task_id_and_actor(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = _uaos_project(d)
            _run(root, "--coord-actor", "codex")
            (event,) = read_events(root)
            self.assertEqual(("codex", "RUN", "T33"), (event["actor"], event["kind"], event["step"]))

    def test_actor_is_detected_from_the_calling_tool(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = _uaos_project(d)
            _run(root, env={"CODEX_SANDBOX": "1"})
            self.assertEqual("codex", read_events(root)[0]["actor"])

    def test_unknown_caller_without_actor_records_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = _uaos_project(d)
            _run(root)
            self.assertEqual([], read_events(root))

    def test_non_uaos_source_and_the_test_switch_record_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            _run(Path(d), "--coord-actor", "claude")
            self.assertFalse((Path(d) / ".coord" / "stream").exists())
        with tempfile.TemporaryDirectory() as d:
            root = _uaos_project(d)
            _run(root, "--coord-actor", "claude", env={"UAOS_STREAM_AUTOLOG": "0"})
            self.assertEqual([], read_events(root))
        with tempfile.TemporaryDirectory() as d:
            root = _uaos_project(d)
            _run(root, "--coord-actor", "claude", "--no-coord-log")
            self.assertEqual([], read_events(root))


class RefTests(unittest.TestCase):
    def test_absolute_summary_path_inside_the_project_becomes_relative(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path = root / ".work" / "pilot_T" / "runs" / "T" / "summary.json"
            record_pilot_in_stream(root, {**SUMMARY, "summary_path": str(path)}, task="T")
            self.assertEqual([".work/pilot_T/runs/T/summary.json"], read_events(root)[0]["refs"])

    def test_absolute_summary_path_outside_the_project_keeps_the_event(self) -> None:
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as elsewhere:
            root = Path(d)
            record_pilot_in_stream(root, {**SUMMARY, "summary_path": str(Path(elsewhere) / "s.json")}, task="T")
            (event,) = read_events(root)
            self.assertEqual([], event["refs"])


if __name__ == "__main__":
    unittest.main()
