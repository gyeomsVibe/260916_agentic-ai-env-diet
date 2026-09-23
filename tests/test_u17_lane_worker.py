import json
import os
import subprocess
import unittest
from contextlib import nullcontext, redirect_stdout
from io import StringIO
from unittest import mock

from v7_harness.adapters import lane_worker
from v7_harness.cli import resolve_worker_command


class LaneWorkerTest(unittest.TestCase):
    def test_env_points_at_local_ollama_and_drops_paid_credentials(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-x", "CLAUDE_CODE_OAUTH_TOKEN": "t"}):
            env = lane_worker.lane_env()
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", env)
        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], "ollama")
        self.assertTrue(env["ANTHROPIC_BASE_URL"].startswith("http://127.0.0.1") or "localhost" in env["ANTHROPIC_BASE_URL"])

    def test_command_is_bare_without_bash_and_protects_tests(self):
        cmd = lane_worker.lane_command("do it", "m")
        self.assertIn("--bare", cmd)
        self.assertNotIn("Bash", cmd[cmd.index("--tools") + 1])
        self.assertIn("Edit(tests/**)", cmd)
        self.assertIn("Write(**/test_*)", cmd)

    def _run(self, stdout: bytes):
        done = subprocess.CompletedProcess([], 0, stdout=stdout, stderr=b"")
        out = StringIO()
        with mock.patch("v7_harness.adapters.gpu_priority.pilot_holds", lambda t: nullcontext()), \
                mock.patch.object(lane_worker.subprocess, "run", return_value=done), redirect_stdout(out):
            rc = lane_worker.main(["-p", "x", "--add-dir", ".", "--print-timeout", "5s"])
        return rc, json.loads(out.getvalue())

    def test_success_envelope(self):
        rc, env = self._run(json.dumps({"result": "done", "num_turns": 4, "usage": {"input_tokens": 9}}).encode())
        self.assertEqual((rc, env["status"], env["usage"]["turns"]), (0, "SUCCESS", 4))

    def test_max_turns_left_to_acceptance_gate(self):
        rc, env = self._run(json.dumps({"is_error": True, "subtype": "error_max_turns"}).encode())
        self.assertEqual(env["status"], "SUCCESS")

    def test_garbage_output_is_error(self):
        rc, env = self._run(b"not json")
        self.assertEqual((rc, env["status"]), (1, "ERROR"))

    def test_cli_resolves_lane(self):
        self.assertEqual(resolve_worker_command("lane", None)[-1], "v7_harness.adapters.lane_worker")


if __name__ == "__main__":
    unittest.main()
