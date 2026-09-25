"""U38: the remote budget gate for every paid worker (B85) and Claude Code as a formal UAOS worker.

B85 (Codex, 2026-09-25): a direct `worker: agy` run spent 655,207 tokens against a 120,000 budget and still ended
PASS and approvable, because the cost gate lived only in the cascade branch and counted input tokens only.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from v7_harness.cli import main
from v7_harness.manual import lint, new_manual
from v7_harness.pilot import PilotConfig, evaluate_cost_gate, run_pilot

FAKE_WORKER = textwrap.dedent('''
    import argparse, json, os, pathlib, sys
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--prompt", required=True)
    parser.add_argument("--add-dir", dest="workspace", required=True)
    args, _ = parser.parse_known_args()
    (pathlib.Path(args.workspace) / "calc.py").write_text("def add(a, b):\\n    return a + b\\n", encoding="utf-8")
    print(json.dumps({"status": "SUCCESS", "response": "wrote calc.py", "conversation_id": "fake",
                      "usage": json.loads(os.environ["FAKE_USAGE"])}))
''')


def _project(root: Path) -> tuple[Path, list[str]]:
    source = root / "proj"
    (source / ".coord").mkdir(parents=True)
    (source / ".coord" / "PLAN.md").write_text("# plan\n", encoding="utf-8")
    (source / "calc.py").write_text("def add(a, b):\n    return 0\n", encoding="utf-8")
    worker = root / "fake_worker.py"
    worker.write_text(FAKE_WORKER, encoding="utf-8")
    return source, [sys.executable, str(worker)]


def _run(root: Path, usage: dict, budget: int | None, approve: str | None = None, task: str = "B85_T") -> dict:
    source, command = _project(root) if not (root / "proj").exists() else (root / "proj", [sys.executable, str(root / "fake_worker.py")])
    with mock.patch.dict(os.environ, {"FAKE_USAGE": json.dumps(usage)}):
        return run_pilot(PilotConfig(
            task_id=task, title="cost", prompt="Make add return a + b in calc.py", source_dir=source,
            work_dir=root / "work", agy_command=command, watch_roots=[], print_timeout_s=60,
            accept_cmd=f'"{sys.executable}" -c "import calc; assert calc.add(1, 2) == 3"', allowed_scopes=["calc.py"],
            approve_bundle_id=approve, remote_budget_tokens=budget,
        ))


class CostGateUnitTests(unittest.TestCase):
    def test_every_token_kind_counts(self) -> None:
        usage = {"input_tokens": 602482, "output_tokens": 52725}
        self.assertEqual("EXCEEDED:655207>120000", evaluate_cost_gate(usage, 120000))
        cached = {"input_tokens": 10, "output_tokens": 10, "cache_creation_input_tokens": 50, "cache_read_input_tokens": 40}
        self.assertEqual("EXCEEDED:110>100", evaluate_cost_gate(cached, 100))
        self.assertEqual("WITHIN", evaluate_cost_gate({"input_tokens": 50, "output_tokens": 50}, 100))

    def test_missing_counts_are_unknown_not_zero(self) -> None:
        self.assertEqual("UNKNOWN", evaluate_cost_gate({"input_tokens": 500}, 1000))
        self.assertEqual("UNKNOWN", evaluate_cost_gate({}, 1000))
        self.assertEqual("UNKNOWN", evaluate_cost_gate(None, 1000))
        self.assertEqual("UNKNOWN", evaluate_cost_gate({"input_tokens": True, "output_tokens": 1}, 1000))


class CostGateInThePilotTests(unittest.TestCase):
    """The gate runs inside the pilot, before summary.json and the ledger row are written."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _ledger_row(self) -> dict:
        lines = (self.root / "proj" / ".coord" / "usage" / "runs.jsonl").read_text(encoding="utf-8").splitlines()
        return json.loads(lines[-1])

    def test_a_direct_remote_run_over_budget_is_blocked_and_cannot_be_approved(self) -> None:
        summary = _run(self.root, {"input_tokens": 602482, "output_tokens": 52725}, 120000)
        self.assertEqual(("BLOCKED", "COST_EXCEEDED"), (summary["verdict_hint"], summary["error_class"]))
        self.assertEqual("EXCEEDED:655207>120000", summary["cost_gate"])
        row = self._ledger_row()
        self.assertEqual(("BLOCKED", "COST_EXCEEDED"), (row["outcome"], row["error_class"]))
        approved = _run(self.root, {"input_tokens": 602482, "output_tokens": 52725}, 120000, approve=summary["bundle_id"])
        self.assertEqual("BLOCKED", approved["promotion"])
        self.assertEqual("def add(a, b):\n    return 0\n", (self.root / "proj" / "calc.py").read_text(encoding="utf-8"))

    def test_within_budget_passes_and_records_the_gate(self) -> None:
        summary = _run(self.root, {"input_tokens": 500, "output_tokens": 100}, 120000)
        self.assertEqual(("PASS", "WITHIN"), (summary["verdict_hint"], summary["cost_gate"]))

    def test_unreported_usage_with_a_budget_is_blocked(self) -> None:
        summary = _run(self.root, {"input_tokens": 500}, 120000)
        self.assertEqual(("BLOCKED", "COST_UNKNOWN", "UNKNOWN"),
                         (summary["verdict_hint"], summary["error_class"], summary["cost_gate"]))

    def test_no_budget_keeps_the_old_behavior(self) -> None:
        summary = _run(self.root, {"input_tokens": 0, "output_tokens": 0}, None)
        self.assertEqual("PASS", summary["verdict_hint"])
        self.assertNotIn("cost_gate", summary)


class RemoteBudgetContractTests(unittest.TestCase):
    def _manual(self, root: Path, **overrides) -> str:
        (root / "pkg").mkdir(exist_ok=True)
        (root / "pkg" / "config.py").write_text("TIMEOUT = 30\n", encoding="utf-8")
        values = dict(work_id="U38_T", worker="agy", goal="Replace TIMEOUT = 30 with TIMEOUT = 60 in `pkg/config.py`.",
                      inputs=["pkg/config.py"], allow=["pkg/config.py"], acceptance="python -c \"import pkg.config\"",
                      judge="codex")
        values.update(overrides)
        return new_manual(root, **values)

    def test_a_paid_worker_needs_a_budget(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertIn("REMOTE_WITHOUT_BUDGET: worker agy needs remote_budget_tokens > 0",
                          lint(self._manual(root), root).errors)
            self.assertTrue(lint(self._manual(root, remote_budget_tokens=120000), root).ok)
            self.assertFalse(any(e.startswith("REMOTE_WITHOUT_BUDGET")
                                 for e in lint(self._manual(root, worker="local"), root).errors))

    def test_the_cli_hands_the_budget_to_the_pilot(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "m.md").write_text(self._manual(root, remote_budget_tokens=120000), encoding="utf-8")
            with mock.patch("v7_harness.pilot.run_pilot", return_value={"state": "SUCCEEDED", "verdict_hint": "PASS"}) as run, \
                    redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                main(["pilot", "run", "--task", "U38_T", "--source", d, "--manual", str(root / "m.md")])
            self.assertEqual(120000, run.call_args.args[0].remote_budget_tokens)

    def test_an_unidentified_approver_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "m.md").write_text(self._manual(root, remote_budget_tokens=120000), encoding="utf-8")
            out = io.StringIO()
            with mock.patch("v7_harness.pilot.run_pilot") as run, mock.patch("v7_harness.cli.detect_actor", return_value=None), \
                    redirect_stdout(out), redirect_stderr(io.StringIO()):
                code = main(["pilot", "run", "--task", "U38_T", "--source", d, "--manual", str(root / "m.md"),
                             "--approve", "b" * 64])
            self.assertEqual(2, code)
            run.assert_not_called()
            self.assertEqual("APPROVER_UNKNOWN", json.loads(out.getvalue())["error_class"])



# A stand-in for the claude CLI: records its argv, cwd and environment, edits calc.py in worker mode, answers a
# JSON verdict in review mode, and reports usage the way `claude -p --output-format json` does.
FAKE_CLAUDE = textwrap.dedent("""
    import json, os, pathlib, sys
    argv = sys.argv[1:]
    log = pathlib.Path(os.environ["FAKE_CLAUDE_LOG"])
    log.write_text(json.dumps({"argv": argv, "cwd": os.getcwd(),
                               "env": {k: os.environ.get(k) for k in ("CLAUDECODE", "UAOS_WORKER", "ANTHROPIC_BASE_URL")}}))
    tools = argv[argv.index("--tools") + 1]
    if "Edit" in tools:
        pathlib.Path("calc.py").write_text("def add(a, b):\\n    return a + b\\n", encoding="utf-8")
        result = "fixed add"
    else:
        result = json.dumps({"verdict": "REWORK", "counterexamples": ["add(0, 0) path untested"],
                             "evidence_lines": ["calc.py:2 return a + b"]})
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": result, "num_turns": 3,
                      "total_cost_usd": 0.0123, "usage": json.loads(os.environ["FAKE_CLAUDE_USAGE"])}))
""")


class ClaudeWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source, _ = _project(self.root)
        fake = self.root / "fake_claude.py"
        fake.write_text(FAKE_CLAUDE, encoding="utf-8")
        self.log = self.root / "claude_call.json"
        self.env = {"CLAUDE_WORKER_CMD": json.dumps([sys.executable, str(fake)]), "FAKE_CLAUDE_LOG": str(self.log),
                    "CLAUDECODE": "1", "ANTHROPIC_BASE_URL": "http://127.0.0.1:11434"}

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _pilot(self, usage: dict, budget: int, task: str = "U38_W") -> dict:
        from v7_harness.cli import resolve_worker_command

        with mock.patch.dict(os.environ, {**self.env, "FAKE_CLAUDE_USAGE": json.dumps(usage)}):
            return run_pilot(PilotConfig(
                task_id=task, title="claude", prompt="Make add return a + b in calc.py", source_dir=self.source,
                work_dir=self.root / "work", agy_command=resolve_worker_command("claude", None), watch_roots=[],
                print_timeout_s=60, accept_cmd=f'"{sys.executable}" -c "import calc; assert calc.add(1, 2) == 3"',
                allowed_scopes=["calc.py"], remote_budget_tokens=budget, model="claude-haiku-4-5-20251001",
            ))

    def test_a_budgeted_claude_run_passes_and_is_recorded_as_claude(self) -> None:
        usage = {"input_tokens": 1200, "output_tokens": 300, "cache_creation_input_tokens": 500, "cache_read_input_tokens": 2000}
        summary = self._pilot(usage, 60000)
        worker = (self.root / "work" / "runs" / "U38_W" / "worker").read_text(encoding="utf-8")
        self.assertEqual(("PASS", "WITHIN", "claude"), (summary["verdict_hint"], summary["cost_gate"], worker))
        row = json.loads((self.source / ".coord" / "usage" / "runs.jsonl").read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(("claude", "claude-haiku-4-5-20251001", 12300, 2000),
                         (row["worker"], row["model"], row["cost_microusd"], row["cache_read_input_tokens"]))

    def test_the_worker_is_fenced(self) -> None:
        self._pilot({"input_tokens": 1, "output_tokens": 1}, 60000)
        call = json.loads(self.log.read_text(encoding="utf-8"))
        argv = call["argv"]
        self.assertIn("--bare", argv)
        self.assertEqual("Read,Edit,Write,Glob,Grep", argv[argv.index("--tools") + 1])
        for fence in ("Write(tests/**)", "Edit(.coord/**)", "Write(.claude/**)"):
            self.assertIn(fence, argv)
        self.assertEqual("claude-haiku-4-5-20251001", argv[argv.index("--model") + 1])
        # The parent session's marker and lane's local-model redirect do not reach the paid worker.
        self.assertEqual({"CLAUDECODE": None, "UAOS_WORKER": "claude", "ANTHROPIC_BASE_URL": None}, call["env"])
        self.assertNotEqual(Path(call["cwd"]).resolve(), self.source.resolve())

    def test_cache_tokens_count_against_the_budget(self) -> None:
        usage = {"input_tokens": 100, "output_tokens": 100, "cache_read_input_tokens": 900}
        summary = self._pilot(usage, 1000)
        self.assertEqual(("BLOCKED", "COST_EXCEEDED", "EXCEEDED:1100>1000"),
                         (summary["verdict_hint"], summary["error_class"], summary["cost_gate"]))

    def test_a_non_ollama_base_url_is_kept(self) -> None:
        from v7_harness.adapters.claude_worker import worker_env

        env = worker_env({"ANTHROPIC_BASE_URL": "https://proxy.example/v1", "CLAUDE_PROJECT_DIR": "/x"})
        self.assertEqual("https://proxy.example/v1", env["ANTHROPIC_BASE_URL"])
        self.assertNotIn("CLAUDE_PROJECT_DIR", env)

    def test_review_is_read_only_advisory_and_never_by_the_author(self) -> None:
        from v7_harness.review import ReviewRefused, run_review

        manual = "```contract\nwork_id: U38_R\n```\n"
        with mock.patch.dict(os.environ, {"FAKE_USAGE": json.dumps({"input_tokens": 10, "output_tokens": 5})}):
            _run(self.root, {"input_tokens": 10, "output_tokens": 5}, None, task="U38_R")  # an agy-labelled bundle
        with mock.patch.dict(os.environ, {**self.env, "FAKE_CLAUDE_USAGE": json.dumps({"input_tokens": 800, "output_tokens": 90})}):
            with self.assertRaises(ReviewRefused):
                run_review(task_id="U38_R", work_dir=self.root / "work", source=self.source, manual_text=manual,
                           reviewer="claude", budget=0)
            record = run_review(task_id="U38_R", work_dir=self.root / "work", source=self.source, manual_text=manual,
                                reviewer="claude", budget=5000)
        self.assertEqual((True, "REWORK", "agy", "WITHIN"),
                         (record["advisory"], record["verdict"], record["author_worker"], record["cost_gate"]))
        argv = json.loads(self.log.read_text(encoding="utf-8"))["argv"]
        self.assertEqual("Read,Glob,Grep", argv[argv.index("--tools") + 1])
        for denied in ("Edit", "Write", "Bash"):
            self.assertIn(denied, argv[argv.index("--disallowedTools") + 1:])
        self.assertIn("```diff", argv[argv.index("-p") + 1])
        rows = [json.loads(line) for line in (self.source / ".coord" / "usage" / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(("review", "U38_R-review-claude"), (rows[-1]["kind"], rows[-1]["work_id"]))
        # A claude-built bundle is not reviewed by claude.
        self._pilot({"input_tokens": 1, "output_tokens": 1}, 60000, task="U38_SELF")
        with mock.patch.dict(os.environ, self.env), self.assertRaises(ReviewRefused) as caught:
            run_review(task_id="U38_SELF", work_dir=self.root / "work", source=self.source, manual_text=manual,
                       reviewer="claude", budget=5000)
        self.assertIn("REVIEWER_IS_AUTHOR", str(caught.exception))
        (self.root / "work" / "runs" / "U38_R" / "worker").unlink()
        with mock.patch.dict(os.environ, self.env), self.assertRaises(ReviewRefused) as caught:
            run_review(task_id="U38_R", work_dir=self.root / "work", source=self.source, manual_text=manual,
                       reviewer="claude", budget=5000)
        self.assertIn("AUTHOR_UNKNOWN", str(caught.exception))


class ClaudeMembershipTests(unittest.TestCase):
    def test_contract_rules_for_a_claude_worker(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            helper = RemoteBudgetContractTests()
            self.assertIn("SELF_JUDGE:claude cannot accept work done by --worker claude",
                          lint(helper._manual(root, worker="claude", judge="claude", remote_budget_tokens=60000), root).errors)
            self.assertIn("REMOTE_WITHOUT_BUDGET: worker claude needs remote_budget_tokens > 0",
                          lint(helper._manual(root, worker="claude"), root).errors)
            self.assertTrue(lint(helper._manual(root, worker="claude", remote_budget_tokens=60000), root).ok)

    def test_a_limited_claude_is_not_sent_to_work(self) -> None:
        from v7_harness.coord.presence import mark

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "m.md").write_text(RemoteBudgetContractTests()._manual(root, worker="claude", remote_budget_tokens=60000),
                                       encoding="utf-8")
            mark(root, "claude", "LIMITED")
            out = io.StringIO()
            with mock.patch("v7_harness.pilot.run_pilot") as run, redirect_stdout(out), redirect_stderr(io.StringIO()):
                code = main(["pilot", "run", "--task", "U38_T", "--source", d, "--manual", str(root / "m.md")])
            self.assertEqual((2, "CLAUDE_LIMITED"), (code, json.loads(out.getvalue())["error_class"]))
            run.assert_not_called()

    def test_worker_labels(self) -> None:
        from v7_harness.pilot import worker_label

        self.assertEqual(["claude", "lane", "apply", "ollama", "agy"],
                         [worker_label(["py", f"x/{name}"]) for name in
                          ("claude_worker.py", "lane_worker.py", "apply_worker.py", "ollama_worker.py", "agy")])

    def test_p1_reaches_claude_only_while_codex_is_away(self) -> None:
        from v7_harness.coord.hook_context import p1_line
        from v7_harness.coord.mailbox import Mailbox
        from v7_harness.coord.presence import mark

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".coord" / "mailbox").mkdir(parents=True)
            (root / ".coord" / "PLAN.md").write_text("# plan\n", encoding="utf-8")
            self.assertEqual("", p1_line(root, {"codex": {"state": "UNKNOWN"}}))
            Mailbox(root / ".coord" / "mailbox").publish("wake_abc", {"wake_reason": "STALE_LOCK: PID_DEAD"})
            self.assertIn("STALE_LOCK: PID_DEAD", p1_line(root, {"codex": {"state": "UNKNOWN"}}))
            self.assertEqual("", p1_line(root, {"codex": {"state": "ACTIVE"}}))
            mark(root, "codex", "ACTIVE")
            out = io.StringIO()
            with redirect_stdout(out), mock.patch("v7_harness.coord.hook_context.read_stdin", return_value="{}"), \
                    mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": ""}):
                main(["coord", "presence", "--tool", "claude", "--state", "ACTIVE", "--from-hook", "--project", d, "--say", "p1"])
            self.assertEqual("", out.getvalue())

    def test_hooks_inside_a_worker_write_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".coord").mkdir()
            (Path(d) / ".coord" / "PLAN.md").write_text("# plan\n", encoding="utf-8")
            with redirect_stdout(io.StringIO()), mock.patch.dict(os.environ, {"UAOS_WORKER": "claude"}), \
                    mock.patch("v7_harness.coord.hook_context.read_stdin", return_value="{}"):
                self.assertEqual(0, main(["coord", "presence", "--tool", "claude", "--state", "ACTIVE", "--from-hook",
                                          "--project", d]))
            self.assertFalse((Path(d) / ".coord" / "presence").exists())

if __name__ == "__main__":
    unittest.main()
