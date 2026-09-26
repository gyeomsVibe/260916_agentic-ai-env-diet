```contract
work_id: U46-H
worker: apply
goal: U46-H follow-up fixes for U45-F1..F7, U46-J2, U46-P1, U46-T1
inputs:
- v7_harness/cli.py sha256=48e1ae0c05b7cf6778b664566cad11fec840f2035085c70a43003af5c03bf0b1
- v7_harness/adapters/ollama_worker.py sha256=996bc859e0542827eb50cd27022972564686f8f4e565ed7b1f88462765b5c361
- v7_harness/adapters/claude_worker.py sha256=3ad2f4fd441d3541dda75be748e63016814c231685b8ea712345d0cd4de0e0e0
- v7_harness/pilot.py sha256=b079b001b6809522c16d6819b83f57af33e7295240c705b3243888a4eba4292c
- v7_harness/coord/hook_context.py sha256=a5eb351e126178a594f3f8d37ab0019e32a246ec2a0fe625151e0d7184c58a9f
- v7_harness/review.py sha256=345ec20af064ce6b07f2e50649a4220d15032667fbd9a396368b539342457f8e
- tests/test_u13_isolation.py sha256=ca06352a1a182a3bdd1dcb62b19cb1c8a8cb8b27ef9a13acbeada98eb09f82d2
- tests/test_u38_cost_gate_and_claude_worker.py sha256=07c7ca3db07f3b7769e9e8e4ee9b15280d6d41cd0573562a03d6024f7d376f2b
allow:
- tests/test_u46_followup_fixes.py
- v7_harness/cli.py
- v7_harness/adapters/ollama_worker.py
- v7_harness/adapters/claude_worker.py
- v7_harness/pilot.py
- v7_harness/coord/hook_context.py
- v7_harness/review.py
- tests/test_u13_isolation.py
- tests/test_u38_cost_gate_and_claude_worker.py
acceptance: python -m unittest tests.test_u46_followup_fixes tests.test_u46_pilot_judge tests.test_u46_agy_review tests.test_u38_cost_gate_and_claude_worker tests.test_u44_claude_contract tests.test_u45_conductor_succession tests.test_u13_isolation
forbidden: design changes; edits outside allow; editing or deleting tests; network; commit/push
stop: two failures with the same cause; input hash mismatch; no output
judge: antigravity
timeout_s: 300
remote_budget_tokens: 0
```

## Instructions for the worker

U46-H (2026-09-26, follow-up fixes for U45-F1..F7, U46-J2, U46-P1, U46-T1).

===FILE: tests/test_u46_followup_fixes.py===
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

===EDIT: v7_harness/cli.py===
<<<<<<< SEARCH
def cmd_pilot_run(args: argparse.Namespace) -> int:
    task_id = args.task
=======
def manual_project(manual: Path) -> Path:
    """U45-F1: the project a manual's paths are relative to, when no --source is given: the nearest folder above the
    manual that holds .coord/PLAN.md, else the current folder. Lint run from another cwd used to report INPUT_MISSING
    for files that exist under the pilot source (U45-O1b)."""
    for folder in Path(manual).resolve().parents:
        if (folder / ".coord" / "PLAN.md").is_file():
            return folder
    return Path(".")


def mandatory_watch_roots(work_dir: Path, source_dir: Path) -> list[Path]:
    """Shallow roots a worker must not write into during a run.

    U45-F5: the work dir's parent used to be watched always. When that parent is a shared `.work/` folder, the
    conductor keeps writing its own notes there during a paid run (U45-G7 a001: two conductor files flagged, run
    abandoned, $0.319 lost). A shared `.work/` is therefore not watched; home, temp, the source's parent and the stage
    stay watched. A worker writing a sibling file inside `.work/` goes unseen, and `.work/` is never committed.
    """
    work = work_dir.resolve()
    return list(dict.fromkeys([
        Path.home().resolve(),
        Path(tempfile.gettempdir()).resolve(),
        *([] if work.parent.name == ".work" else [work.parent]),
        source_dir.resolve().parent,
        (work_dir / "stage").resolve(),
    ]))


def cmd_pilot_run(args: argparse.Namespace) -> int:
    task_id = args.task
>>>>>>> REPLACE

===EDIT: v7_harness/cli.py===
<<<<<<< SEARCH
        if contract.get("work_id") != task_id:
            print(f"[manual] work_id {contract.get('work_id')} differs from --task {task_id}", file=sys.stderr)
=======
        if contract.get("work_id") != task_id:
            # U45-F7: refuse before any worker runs. A warning here let a paid run finish first (U45-G7r, $0.263 lost).
            print(json.dumps({"task_id": task_id, "state": "REFUSED", "error_class": "MANUAL_TASK_MISMATCH",
                              "verdict_hint": "BLOCKED", "manual_work_id": contract.get("work_id")},
                             indent=2, ensure_ascii=False))
            return 2
>>>>>>> REPLACE

===EDIT: v7_harness/cli.py===
<<<<<<< SEARCH
    mandatory_roots = [
        Path.home().resolve(),
        Path(tempfile.gettempdir()).resolve(),
        work_dir.resolve().parent,
        source_dir.resolve().parent,
        (work_dir / "stage").resolve(),
    ]
=======
    mandatory_roots = mandatory_watch_roots(work_dir, source_dir)
>>>>>>> REPLACE

===EDIT: v7_harness/cli.py===
<<<<<<< SEARCH
    report = lint(Path(args.manual).read_text(encoding="utf-8"), Path(args.source))
    print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False))
    return 0 if report.ok else 1
=======
    source = Path(args.source) if args.source else manual_project(Path(args.manual))
    report = lint(Path(args.manual).read_text(encoding="utf-8"), source)
    print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False))
    return 0 if report.ok else 1
>>>>>>> REPLACE

===EDIT: v7_harness/cli.py===
<<<<<<< SEARCH
    p_manual_lint.add_argument("--source", default=".", help="Project the manual's paths are relative to")
=======
    p_manual_lint.add_argument("--source", default=None,
                               help="Project the manual's paths are relative to (default: the folder above the manual "
                                    "that holds .coord/PLAN.md, else the current folder)")
>>>>>>> REPLACE

===EDIT: v7_harness/cli.py===
<<<<<<< SEARCH
            line = p1_line(project, presence) if say == "p1" else brief_line(project, presence)
=======
            line = p1_line(project, presence) if say == "p1" else brief_line(project, presence)
            if say == "p1" and not p1_is_new(project, line):
                line = ""  # U46-P1: an unchanged P1 set is ACK_ONLY; it was repeated on every prompt
>>>>>>> REPLACE

===EDIT: v7_harness/cli.py===
<<<<<<< SEARCH
        from .coord.hook_context import brief_line, hook_project, p1_line, read_stdin
=======
        from .coord.hook_context import brief_line, hook_project, p1_is_new, p1_line, read_stdin
>>>>>>> REPLACE

===EDIT: v7_harness/coord/hook_context.py===
<<<<<<< SEARCH
import json
import os
import sys
import threading
=======
import hashlib
import json
import os
import sys
import threading
>>>>>>> REPLACE

===EDIT: v7_harness/coord/hook_context.py===
<<<<<<< SEARCH
    return (f"UAOS P1 waiting ({len(wakes)}), Codex {codex}: {reason or 'see mailbox'}. Claude acts as deputy: "
            "`coord inbox`, handle it, then `coord ack --id <id>`.")[:400]
=======
    return (f"UAOS P1 waiting ({len(wakes)}), Codex {codex}: {reason or 'see mailbox'}. Claude acts as deputy: "
            "`coord inbox`, handle it, then `coord ack --id <id>`.")[:400]


# Runtime state beside the presence files (.coord/presence/ is git-ignored); presence reads only <tool>.json.
P1_SEEN = Path(".coord") / "presence" / "p1_hook_seen.txt"


def p1_is_new(project: Path, line: str) -> bool:
    """U46-P1: say a P1 line only when it differs from the last one said. The line carries the wake count, Codex's
    state and the first reason, and the fingerprint adds the wake ids, so any new wake or state change speaks again."""
    if not line:
        return False
    box_dir = Path(project) / ".coord" / "mailbox" / "inbox"
    ids = sorted(path.stem for path in box_dir.glob("wake_*.json")) if box_dir.is_dir() else []
    fingerprint = hashlib.sha256("\n".join([line, *ids]).encode("utf-8")).hexdigest()
    seen = Path(project) / P1_SEEN
    try:
        if seen.read_text(encoding="utf-8").strip() == fingerprint:
            return False
    except OSError:
        pass
    try:
        seen.parent.mkdir(parents=True, exist_ok=True)
        seen.write_text(fingerprint, encoding="utf-8")
    except OSError:
        pass  # a hook never fails the session; the line is said again next time
    return True
>>>>>>> REPLACE

===EDIT: v7_harness/adapters/ollama_worker.py===
<<<<<<< SEARCH
BLOCK_RE = re.compile(r"^===FILE:\s*(?P<path>[^\n=]+?)\s*===\n(?P<body>.*?)(?=^===(?:FILE|EDIT):|\Z)", re.M | re.S)
=======
# U45-F2: a FILE block also ends at an explicit `===END===` line or at the `## Output` section `pilot manual new`
# appends, so a trailing FILE block no longer swallows that text (U45-G2: SYNTAX_ERROR).
BLOCK_RE = re.compile(
    r"^===FILE:\s*(?P<path>[^\n=]+?)\s*===\n(?P<body>.*?)"
    r"(?=^===(?:FILE|EDIT):|^===END===[ \t]*$|^## Output\n\n- (?:Reply with|Edit the files)|\Z)",
    re.M | re.S,
)
>>>>>>> REPLACE

===EDIT: v7_harness/adapters/ollama_worker.py===
<<<<<<< SEARCH
def _log(event: str, **fields) -> None:
=======
def context_files(prompt: str, workspace: Path) -> list[str]:
    """Files whose current content goes with the task. The contract's pinned inputs come first (U45-F3: the local
    worker got the manual but not the input it had to read, and guessed ids 1..38), then the files the task names."""
    def present(raw: str) -> str | None:
        rel = raw.strip().replace("\\", "/")
        return rel if (workspace / rel).is_file() else None

    pinned = [p for p in (present(m) for m in re.findall(r"^- (\S+) sha256=[0-9a-f]{64}\s*$", prompt, re.M)) if p]
    named = sorted({p for p in (present(m) for m in re.findall(r"`([^`\n]+\.(?:md|py|txt))`", prompt)) if p}
                   | {p for p in (present(m) for m in re.findall(r"^===(?:FILE|EDIT):\s*([^\n=]+?)\s*===", prompt,
                                                                 re.M)) if p}
                   | {name for name in ("core.md", "GLOBAL_RULES.ko.md", "VERSION", "history.md")
                      if (workspace / name).is_file() and name in prompt})
    return list(dict.fromkeys([*pinned, *named]))


def _log(event: str, **fields) -> None:
>>>>>>> REPLACE

===EDIT: v7_harness/adapters/ollama_worker.py===
<<<<<<< SEARCH
    # 과제가 가리키는 파일의 현재 내용을 함께 준다. 7B 모델은 파일을 스스로 찾지 못한다.
    named = sorted({
        candidate.replace("\\", "/")
        for candidate in re.findall(r"`([^`\n]+\.(?:md|py|txt))`", args.prompt)
        if (workspace / candidate.replace("\\", "/")).is_file()
    } | {
        candidate.strip().replace("\\", "/")
        for candidate in re.findall(r"^===(?:FILE|EDIT):\s*([^\n=]+?)\s*===", args.prompt, re.M)
        if (workspace / candidate.strip().replace("\\", "/")).is_file()
    } | {
        name for name in ("core.md", "GLOBAL_RULES.ko.md", "VERSION", "history.md")
        if (workspace / name).is_file() and name in args.prompt
    })
=======
    # 과제가 가리키는 파일의 현재 내용을 함께 준다. 7B 모델은 파일을 스스로 찾지 못한다.
    named = context_files(args.prompt, workspace)
>>>>>>> REPLACE

===EDIT: v7_harness/pilot.py===
<<<<<<< SEARCH
def evaluate_cost_gate(usage: dict[str, Any] | None, budget: int) -> str:
=======
def delegator() -> str | None:
    """U45-F4: which tool ordered this run (codex, claude, antigravity), from its shell environment; None for a plain
    terminal. The ledger needs it to measure how much Claude conducted while Codex was away."""
    import os as _os

    names = _os.environ.keys()
    if any(n.upper().startswith(("ANTIGRAVITY", "GEMINI_CLI")) for n in names):
        return "antigravity"
    if "CLAUDECODE" in names:
        return "claude"
    if any(n.upper().startswith("CODEX_") for n in names):
        return "codex"
    return None


def evaluate_cost_gate(usage: dict[str, Any] | None, budget: int) -> str:
>>>>>>> REPLACE

===EDIT: v7_harness/pilot.py===
<<<<<<< SEARCH
                    "worker": worker_type,
                    "exit_code": acceptance_exit if acceptance_exit is not None else (0 if state == "SUCCEEDED" else 1),
=======
                    "worker": worker_type,
                    "delegator": delegator(),
                    "exit_code": acceptance_exit if acceptance_exit is not None else (0 if state == "SUCCEEDED" else 1),
>>>>>>> REPLACE

===EDIT: v7_harness/pilot.py===
<<<<<<< SEARCH
                for extra in ("cache_creation_input_tokens", "cache_read_input_tokens", "cost_microusd"):
                    value = usage_dict.get(extra) if isinstance(usage_dict, dict) else None
=======
                for extra in ("cache_creation_input_tokens", "cache_read_input_tokens", "cost_microusd",
                              "usd_cap_overshoot_microusd"):
                    value = usage_dict.get(extra) if isinstance(usage_dict, dict) else None
>>>>>>> REPLACE

===EDIT: v7_harness/adapters/claude_worker.py===
<<<<<<< SEARCH
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--prompt", required=True)
=======
def cap_overshoot(usage: dict, cap_usd: float) -> int | None:
    """U45-F6: claude checks --max-budget-usd after a turn, so a run can end above it (U45-G7 a001: $0.319 on a $0.30
    cap, +6%). The overshoot in micro-dollars is recorded as a gate result instead of being lost."""
    cost = usage.get("cost_microusd")
    if not isinstance(cost, int) or isinstance(cost, bool):
        return None
    over = cost - int(round(cap_usd * 1_000_000))
    return over if over > 0 else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--prompt", required=True)
>>>>>>> REPLACE

===EDIT: v7_harness/adapters/claude_worker.py===
<<<<<<< SEARCH
    usage = usage_from(result)
    usage["elapsed_s"] = int(time.monotonic() - started)
=======
    usage = usage_from(result)
    usage["elapsed_s"] = int(time.monotonic() - started)
    overshoot = cap_overshoot(usage, cap)
    if overshoot is not None:
        usage["usd_cap_overshoot_microusd"] = overshoot
>>>>>>> REPLACE

===EDIT: v7_harness/review.py===
<<<<<<< SEARCH
        "wall_time_s": None, "outcome": record["verdict"], "receipt": str(receipt), "independent_verifier": None,
=======
        # U46-J2: absolute, so the receipt resolves from any cwd (it was stored as ..\..\runs\...).
        "wall_time_s": None, "outcome": record["verdict"], "receipt": str(Path(receipt).resolve()),
        "independent_verifier": None,
>>>>>>> REPLACE

===EDIT: tests/test_u13_isolation.py===
<<<<<<< SEARCH
        started = time.perf_counter()
        before = snapshot_watch_roots([watched])
        before.assert_unchanged()
        self.assertLess(time.perf_counter() - started, 30.0)
=======
        # U46-T1: CPU time of this process, not wall time. Wall time failed under a loaded machine (43 s, 51 s) while
        # passing alone; the budget is about the scan's own cost, which other processes cannot inflate.
        started = time.process_time()
        before = snapshot_watch_roots([watched])
        before.assert_unchanged()
        self.assertLess(time.process_time() - started, 30.0)
>>>>>>> REPLACE

===EDIT: tests/test_u38_cost_gate_and_claude_worker.py===
<<<<<<< SEARCH
            helper = RemoteBudgetContractTests()
            (root / "m.md").write_text(helper._manual(root, worker="cascade", remote_budget_tokens=120000), encoding="utf-8")
=======
            helper = RemoteBudgetContractTests()
            (root / "m.md").write_text(helper._manual(root, work_id="R1", worker="cascade", remote_budget_tokens=120000), encoding="utf-8")
>>>>>>> REPLACE

===EDIT: tests/test_u38_cost_gate_and_claude_worker.py===
<<<<<<< SEARCH
            (root / "m.md").write_text(RemoteBudgetContractTests()._manual(root, worker="cascade", remote_budget_tokens=120000),
                                       encoding="utf-8")
=======
            (root / "m.md").write_text(RemoteBudgetContractTests()._manual(root, work_id="R2", worker="cascade", remote_budget_tokens=120000),
                                       encoding="utf-8")
>>>>>>> REPLACE

## Output

- Reply with ===FILE / ===EDIT blocks only. No explanations. Do not claim success; the acceptance command decides.
