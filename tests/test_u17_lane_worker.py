import json
import os
import subprocess
import tempfile
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

    def test_envelope_passes_the_pilot_parser(self):
        # regression: fractional elapsed_s and an empty response made the pilot block every lane run
        from v7_harness.adapters.agy import parse_agy_result

        for result in ({"result": "done", "num_turns": 3}, {"result": "", "num_turns": 2}):
            _rc, env = self._run(json.dumps(result).encode())
            outcome = parse_agy_result(stdout=json.dumps(env).encode(), stderr=b"", exit_code=0)
            self.assertTrue(outcome.successful, outcome.error_class)

    def test_max_turns_left_to_acceptance_gate(self):
        rc, env = self._run(json.dumps({"is_error": True, "subtype": "error_max_turns"}).encode())
        self.assertEqual(env["status"], "SUCCESS")

    def test_garbage_output_is_error(self):
        rc, env = self._run(b"not json")
        self.assertEqual((rc, env["status"]), (1, "ERROR"))

    def test_cli_resolves_lane(self):
        self.assertTrue(resolve_worker_command("lane", None)[-1].endswith("lane_worker.py"))


class CascadeTest(unittest.TestCase):
    def _main(self, verdicts, extra=()):
        from v7_harness import cli

        calls = []

        def fake_run(config):
            calls.append((config.task_id, config.agy_command[-1]))
            return {"task_id": config.task_id, "state": "SUCCEEDED", "verdict_hint": verdicts[len(calls) - 1]}

        with mock.patch("v7_harness.pilot.run_pilot", fake_run), redirect_stdout(StringIO()):
            cli.main(["pilot", "run", "--task", "C1", "--source", ".", "--prompt", "fix x", "--worker", "cascade",
                      "--work-dir", ".work/_cascade_test", *extra])
        return calls

    def test_rework_on_local_is_not_escalated_to_a_paid_worker_without_a_manual(self):
        # B85 rework (2026-09-25): this test used to expect C1 -> C1-agy with no contract budget, which is the
        # bypass Codex reproduced. A paid escalation now needs a manual (tests.test_u38 covers the budgeted route).
        calls = self._main(["REWORK", "PASS"])
        self.assertEqual([c[0] for c in calls], ["C1"])
        self.assertTrue(calls[0][1].endswith("ollama_worker.py"))

    def test_rework_on_local_with_escalate_to_lane(self):
        calls = self._main(["REWORK", "PASS"], ["--escalate-to", "lane"])
        self.assertEqual([c[0] for c in calls], ["C1", "C1-lane"])
        self.assertTrue(calls[0][1].endswith("ollama_worker.py"))
        self.assertTrue(calls[1][1].endswith("lane_worker.py"))

    def test_workers_start_by_path_without_pythonpath(self):
        # regression: the pilot runs workers by path with no PYTHONPATH; the package import used to fail
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        for w in ("local", "lane"):
            cmd = resolve_worker_command(w, None)
            code = f"import runpy,sys; sys.argv=['x']; runpy.run_path({cmd[-1]!r}, run_name='probe'); import v7_harness.adapters.gpu_priority"
            r = subprocess.run([cmd[0], "-c", code], cwd=tempfile.gettempdir(), env=env, capture_output=True)
            self.assertEqual(r.returncode, 0, r.stderr[-300:])

    def test_pass_or_blocked_stays_on_local(self):
        self.assertEqual(len(self._main(["PASS"])), 1)
        self.assertEqual(len(self._main(["BLOCKED"])), 1)

    def test_approve_never_cascades(self):
        self.assertEqual(len(self._main(["REWORK"], ["--approve", "b1"])), 1)


if __name__ == "__main__":
    unittest.main()
