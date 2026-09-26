"""U46-H: follow-up fixes found while Claude acted for Codex (U45-F1..F7, U46-J2, U46-P1)."""

import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from v7_harness.adapters import claude_worker, ollama_worker
from v7_harness.cli import main, mandatory_watch_roots, manual_project
from v7_harness.coord.hook_context import p1_is_new
from v7_harness.manual import new_manual


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ManualSourceTest(unittest.TestCase):
    def test_f1_lint_resolves_inputs_against_the_manuals_project(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".coord" / "tasks").mkdir(parents=True)
            (root / ".coord" / "PLAN.md").write_text("plan\n", encoding="utf-8")
            manual = root / ".coord" / "tasks" / "m.md"
            self.assertEqual(root.resolve(), manual_project(manual))
            self.assertEqual(Path("."), manual_project(Path(tempfile.gettempdir()) / "no_uaos_here" / "m.md"))


class DictationTest(unittest.TestCase):
    def test_f2_a_trailing_file_block_ends_before_the_generated_output_section(self):
        text = new_manual(Path("."), work_id="X", worker="apply", goal="g", inputs=[], allow=["a.md"],
                          acceptance="python -c pass", judge="codex",
                          instructions="===FILE: a.md===\nhello\n")
        body = next(ollama_worker.BLOCK_RE.finditer(text)).group("body")
        self.assertNotIn("## Output", body)
        self.assertEqual("hello", body.strip())

    def test_f2_an_explicit_end_marker_closes_a_file_block(self):
        text = "===FILE: a.md===\nline\n===END===\ntrailing prose\n"
        self.assertEqual("line\n", next(ollama_worker.BLOCK_RE.finditer(text)).group("body"))

    def test_f3_pinned_inputs_reach_the_local_worker(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "ids.txt").write_text("1\n2\n", encoding="utf-8")
            prompt = f"```contract\ninputs:\n- ids.txt sha256={_sha(root / 'ids.txt')}\n```\nUse the ids."
            self.assertIn("ids.txt", ollama_worker.context_files(prompt, root))


class LedgerTest(unittest.TestCase):
    def test_f4_delegator_names_the_calling_tool(self):
        from v7_harness.pilot import delegator
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}, clear=True):
            self.assertEqual("claude", delegator())
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(delegator())

    def test_f6_a_dollar_cap_overshoot_is_recorded(self):
        self.assertEqual(19_000, claude_worker.cap_overshoot({"cost_microusd": 319_000}, 0.30))
        self.assertIsNone(claude_worker.cap_overshoot({"cost_microusd": 200_000}, 0.30))
        self.assertIsNone(claude_worker.cap_overshoot({}, 0.30))

    def test_j2_review_receipt_is_absolute(self):
        from v7_harness import review
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".coord").mkdir()
            (root / ".coord" / "PLAN.md").write_text("plan\n", encoding="utf-8")
            record = {"verdict": "PASS", "cost_gate": "WITHIN"}
            review._record_usage(root, "T", "agy", "agy-default", {"input_tokens": 1, "output_tokens": 1}, record,
                                 Path("runs") / "T" / "review_agy.json")
            rows = [json.loads(line) for line in
                    (root / ".coord" / "usage" / "runs.jsonl").read_text(encoding="utf-8").splitlines() if line]
            self.assertTrue(Path(rows[-1]["receipt"]).is_absolute(), rows[-1]["receipt"])


class WatchTest(unittest.TestCase):
    def test_f5_a_shared_work_folder_is_not_watched_but_home_temp_and_stage_are(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            shared = root / "proj" / ".work"
            roots = mandatory_watch_roots(shared / "u_run", root / "proj")
            self.assertNotIn(shared, roots)
            self.assertIn(Path.home().resolve(), roots)
            self.assertIn((shared / "u_run" / "stage").resolve(), roots)
            other = mandatory_watch_roots(root / "runs_here" / "w", root / "proj")
            self.assertIn(root / "runs_here", other)


class TaskMismatchTest(unittest.TestCase):
    def test_f7_a_manual_for_another_task_is_refused_before_any_worker(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.md").write_text("a\n", encoding="utf-8")
            manual = root / "m.md"
            manual.write_text(new_manual(root, work_id="OTHER", worker="apply", goal="Write `a.md`.",
                                         inputs=["a.md"], allow=["a.md"], acceptance="python -c pass",
                                         judge="codex", instructions="===FILE: a.md===\nb\n"), encoding="utf-8")
            out = io.StringIO()
            with mock.patch("v7_harness.pilot.run_pilot") as run, redirect_stdout(out):
                code = main(["pilot", "run", "--task", "MINE", "--source", d, "--manual", str(manual),
                             "--work-dir", str(root / "w")])
            self.assertEqual(2, code)
            run.assert_not_called()
            self.assertEqual("MANUAL_TASK_MISMATCH", json.loads(out.getvalue())["error_class"])


class P1HookTest(unittest.TestCase):
    def test_p1_line_is_said_once_until_it_changes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertFalse(p1_is_new(root, ""))
            self.assertTrue(p1_is_new(root, "UAOS P1 waiting (7)"))
            self.assertFalse(p1_is_new(root, "UAOS P1 waiting (7)"))
            self.assertTrue(p1_is_new(root, "UAOS P1 waiting (8)"))


if __name__ == "__main__":
    unittest.main()
