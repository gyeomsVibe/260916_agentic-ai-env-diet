"""B20 regression test: --model flag support in pilot run and propagation to agy command."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from v7_harness.adapters.agy import AgyRequest, build_agy_command
from v7_harness.cli import build_parser, cmd_pilot_run
from v7_harness.pilot import PilotConfig


class B20ModelFlagTests(unittest.TestCase):
    def test_parser_parses_model_argument(self) -> None:
        """Verify CLI parser parses --model argument correctly."""
        parser = build_parser()
        args = parser.parse_args([
            "pilot", "run",
            "--task", "P20_TEST",
            "--source", ".",
            "--prompt", "hello",
            "--model", "gemini-3.7-flash",
        ])
        self.assertEqual(args.model, "gemini-3.7-flash")

    def test_build_agy_command_includes_model_flag(self) -> None:
        """Verify build_agy_command appends --model <name> when specified in AgyRequest."""
        req = AgyRequest(
            task_id="P20_TEST",
            title="Test Title",
            prompt="Test prompt",
            workspace=Path("/dummy/stage"),
            isolation_mode="staging",
            model="gemini-3.7-flash",
        )
        cmd = build_agy_command(req)
        self.assertIn("--model", cmd)
        model_idx = cmd.index("--model")
        self.assertEqual(cmd[model_idx + 1], "gemini-3.7-flash")

    def test_cmd_pilot_run_passes_model_to_pilot_config(self) -> None:
        """Verify cmd_pilot_run propagates args.model to PilotConfig."""
        parser = build_parser()
        args = parser.parse_args([
            "pilot", "run",
            "--task", "P20_TEST",
            "--source", ".",
            "--prompt", "hello",
            "--model", "claude-3-7-sonnet",
            "--worker", "local",  # a paid worker needs a manual since B85; this test checks CLI plumbing only
        ])

        captured_config: list[PilotConfig] = []

        def fake_run_pilot(config: PilotConfig) -> dict:
            captured_config.append(config)
            return {"state": "SUCCEEDED"}

        with mock.patch("v7_harness.pilot.run_pilot", side_effect=fake_run_pilot):
            with mock.patch("sys.stdout"):
                exit_code = cmd_pilot_run(args)

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(captured_config), 1)
        self.assertEqual(captured_config[0].model, "claude-3-7-sonnet")


if __name__ == "__main__":
    unittest.main()
