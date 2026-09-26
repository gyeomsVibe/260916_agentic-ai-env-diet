```contract
work_id: U46-J4
worker: apply
goal: pilot judge --judge agy: Antigravity's binding CLI verdict drives the unchanged approve gate, only while Codex is LIMITED or ABSENT.
inputs:
- v7_harness/cli.py sha256=465e4e613774ea434349596338aa9a86ae0c972a0004d8debd794cb3638104b4
- v7_harness/review.py sha256=345ec20af064ce6b07f2e50649a4220d15032667fbd9a396368b539342457f8e
- v7_harness/adapters/agy.py sha256=dd8dcf48569acf0614e6b013cce3200b54c3cab8329354779b5f8fcd31b4604c
- v7_harness/coord/presence.py sha256=43e091d5720d57facd7c08f0547412502ccc2497068b91b089cc11f0668ffb82
allow:
- v7_harness/judge.py
- v7_harness/cli.py
- tests/test_u46_pilot_judge.py
acceptance: python -m unittest tests.test_u46_pilot_judge tests.test_u46_agy_review tests.test_u38_cost_gate_and_claude_worker tests.test_u44_claude_contract tests.test_u45_conductor_succession tests.test_cli
forbidden: design changes; edits outside allow; editing or deleting tests; network; commit/push
stop: two failures with the same cause; input hash mismatch; no output
judge: antigravity
timeout_s: 300
remote_budget_tokens: 0
```

## Instructions for the worker

U46-J4 (2026-09-26, Claude acting conductor; user allowed option A scoped to Codex's absence): `pilot judge --judge agy` gets Antigravity's binding verdict through its CLI and runs the unchanged `pilot run --approve` gate, only while Codex is LIMITED or ABSENT. While Codex is ACTIVE or UNKNOWN, Codex judges (default logic).

===FILE: v7_harness/judge.py===
"""U46-J4: while Codex is away, the acting conductor gets a binding Antigravity verdict through the agy CLI
(`pilot judge`), so no person relays a mailbox letter. docs/47 §2-1; Antigravity's consult
.coord/notes/U46_J3_agy_consult.md (option A); user decision 2026-09-26: "허용한다 — codex 부재중 권한대행 프로세스".

Default logic stays: while Codex is ACTIVE (or its state is not known), Codex judges and this command refuses.
agy only reads and answers: plan mode, a JSON schema, no permission bypass, the run folder as its only workspace.
The unchanged `pilot run --approve` gate applies the bundle, and only for an APPROVE that names this bundle within the
token budget. The approval stays attributable: the record keeps agy's conversation id and the sha256 of its verdict
(B83: an actor name alone proves nothing). One call per bundle, never retried; a failed call leaves the mailbox route.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

JUDGE_TOOL = {"agy": "antigravity"}
# U46-J1 live review used 71,299 tokens and the U46-J3 consult 89,263; 100,000 is the cap the consult proposed.
DEFAULT_BUDGET = 100_000
VERDICT_SCHEMA = {
    "type": "object",
    "required": ["verdict", "bundle_id", "evidence"],
    "properties": {
        "verdict": {"type": "string", "enum": ["APPROVE", "REJECT"]},
        "bundle_id": {"type": "string"},
        "evidence": {"type": "array", "items": {"type": "string"}},
    },
}
# Enough of the acceptance log to show the failing or passing summary without flooding the judge prompt.
ACCEPTANCE_TAIL_CHARS = 4_000


class JudgeRefused(Exception):
    pass


def codex_away(desk: dict[str, Any]) -> tuple[bool, str]:
    """Only a recorded LIMITED or ABSENT Codex hands judging to this path; ACTIVE or an expired heartbeat does not."""
    state = (desk.get("codex") or {}).get("state") or "UNKNOWN"
    if state in ("LIMITED", "ABSENT"):
        return True, f"codex {state}"
    return False, f"CODEX_JUDGES: codex is {state}; while Codex is active or unknown it judges (default logic)"


def judge_prompt(task_id: str, bundle_id: str, manual_text: str, diff: str, acceptance_exit: Any,
                 acceptance_tail: str) -> str:
    from .review import MAX_DIFF_CHARS

    return (f"[{task_id}] You are the judge named in this contract, acting while Codex is away. Decide whether bundle "
            f"{bundle_id} meets it. The diff is the complete change and the pilot already ran the acceptance command; "
            "judge from them. Do not edit any file.\n\n"
            f"## Contract\n{manual_text}\n\n## Acceptance (exit {acceptance_exit}, last lines)\n```\n{acceptance_tail}\n```\n\n"
            f"## Diff\n```diff\n{diff[:MAX_DIFF_CHARS]}\n```\n\n"
            'Reply with one JSON object: {"verdict": "APPROVE" or "REJECT", "bundle_id": "<the id above>", '
            '"evidence": ["path:line quote or failing check", "..."]}')


def gate_usage(usage: dict[str, int]) -> dict[str, int]:
    """agy reports thinking_tokens apart from output_tokens; they are paid output, so the gate counts them."""
    if not usage:
        return {}
    return {"input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0) + usage.get("thinking_tokens", 0)}


def parse_judgement(envelope: dict[str, Any]) -> dict[str, Any] | None:
    raw = envelope.get("structured_output")
    if not isinstance(raw, dict):
        match = re.search(r"\{.*\}", str(envelope.get("response") or ""), re.S)
        try:
            raw = json.loads(match.group(0)) if match else None
        except json.JSONDecodeError:
            raw = None
    if not isinstance(raw, dict) or raw.get("verdict") not in ("APPROVE", "REJECT"):
        return None
    return {"verdict": raw["verdict"], "bundle_id": str(raw.get("bundle_id") or ""),
            "evidence": [str(x)[:300] for x in raw.get("evidence") or []][:40]}


def run_judge(*, task_id: str, work_dir: Path, source: Path, manual_path: Path, project: Path | None = None,
              judge: str = "agy", budget: int = DEFAULT_BUDGET, timeout_s: int = 600, apply: bool = True,
              runner: Any = subprocess.run, approver: Any = subprocess.run,
              desk: dict[str, Any] | None = None) -> dict[str, Any]:
    from .adapters.agy import AgyRequest, build_agy_command, parse_agy_result
    from .coord.presence import read_all
    from .manual import parse_contract
    from .pilot import evaluate_cost_gate
    from .review import bundle_diff

    if judge not in JUDGE_TOOL:
        raise JudgeRefused(f"UNKNOWN_JUDGE:{judge}")
    if budget <= 0:
        raise JudgeRefused("JUDGE_WITHOUT_BUDGET: pass --budget > 0 (a judgement is a paid call)")
    work_dir, source, manual_path = Path(work_dir).resolve(), Path(source).resolve(), Path(manual_path).resolve()
    away, why = codex_away(desk if desk is not None else read_all(Path(project or source).resolve()))
    if not away:
        raise JudgeRefused(why)
    manual_text = manual_path.read_text(encoding="utf-8")
    contract = parse_contract(manual_text) or {}
    if contract.get("work_id") != task_id:
        raise JudgeRefused(f"TASK_MISMATCH: manual work_id {contract.get('work_id')!r} is not {task_id!r}")
    if contract.get("judge") != JUDGE_TOOL[judge]:
        raise JudgeRefused(f"NOT_THE_NAMED_JUDGE: the contract names judge {contract.get('judge')!r}")
    runs = work_dir / "runs" / task_id
    try:
        summary = json.loads((runs / "summary.json").read_text(encoding="utf-8"))
        author = (runs / "worker").read_text(encoding="utf-8").strip()
    except (OSError, json.JSONDecodeError) as exc:
        raise JudgeRefused(f"NO_PILOT_RUN:{runs} ({type(exc).__name__})") from exc
    if author in (judge, JUDGE_TOOL[judge]):
        raise JudgeRefused(f"JUDGE_IS_AUTHOR:{judge} wrote this bundle")
    if summary.get("promotion") != "DRY_RUN_PASSED" or summary.get("acceptance_exit") != 0:
        raise JudgeRefused(f"NOT_READY: promotion {summary.get('promotion')!r}, "
                           f"acceptance_exit {summary.get('acceptance_exit')!r}")
    bundle_id = str(summary.get("bundle_id") or "")
    out = runs / f"judge_{judge}.json"
    if out.is_file():
        # One call per bundle: a second call would buy a second opinion; a failed one goes to the mailbox route.
        raise JudgeRefused(f"ALREADY_JUDGED:{out}")
    staging = Path(summary.get("agy_workspace") or "")
    changed = [str(x) for x in summary.get("changed_files") or []]
    if not changed or not staging.is_dir():
        raise JudgeRefused("NOTHING_TO_JUDGE: no changed files or no staged copy")
    log = Path(summary.get("acceptance_log_path") or "")
    log = log if log.is_absolute() else source / log
    tail = log.read_text(encoding="utf-8", errors="replace")[-ACCEPTANCE_TAIL_CHARS:] if log.is_file() else "(no log)"

    request = runs / "judge_agy_request.md"
    request.write_text(judge_prompt(task_id, bundle_id, manual_text, bundle_diff(source, staging, changed),
                                    summary.get("acceptance_exit"), tail), encoding="utf-8")
    schema = runs / "judge_verdict.schema.json"
    schema.write_text(json.dumps(VERDICT_SCHEMA), encoding="utf-8")
    short = (f"Read {request.name} in this folder: a judge request with the contract, the acceptance result and the "
             "complete diff. Do not edit any file. Answer with the JSON verdict it asks for.")
    argv = build_agy_command(AgyRequest(task_id=task_id, title="judge", prompt=short, workspace=runs,
                                        isolation_mode="staging", print_timeout_s=timeout_s, schema_path=schema))
    # Read-only planning (consult "Facts about agy"); skip_permissions stays False, so no bypass flag is added.
    argv += ["--mode", "plan"]
    started = time.monotonic()
    usage: dict[str, int] = {}
    conversation_id = None
    judgement = None
    error = ""
    envelope_sha = ""
    try:
        done = runner(argv, cwd=str(runs), env={**os.environ, "UAOS_WORKER": "1"}, capture_output=True,
                      timeout=timeout_s + 60)
        stdout = done.stdout or b""
        envelope_sha = hashlib.sha256(stdout).hexdigest()
        outcome = parse_agy_result(stdout=stdout, stderr=done.stderr or b"", exit_code=done.returncode)
        usage, conversation_id = dict(outcome.usage), outcome.conversation_id
        if outcome.successful:
            judgement = parse_judgement(json.loads(stdout.decode("utf-8", errors="replace")))
            if judgement is None:
                error = "JUDGE_UNPARSED: agy did not return the JSON verdict"
        else:
            error = f"JUDGE_FAILED:agy {outcome.error_class}"
    except subprocess.TimeoutExpired:
        error = f"JUDGE_TIMEOUT:{timeout_s}s"
    except (OSError, ValueError) as exc:
        error = f"JUDGE_FAILED:{type(exc).__name__}: {exc}"[:300]
    cost_gate = evaluate_cost_gate(gate_usage(usage), budget)
    verdict = "UNUSABLE"
    if judgement and cost_gate == "WITHIN":
        if judgement["bundle_id"] == bundle_id:
            verdict = judgement["verdict"]
        else:
            error = f"BUNDLE_MISMATCH: verdict names {judgement['bundle_id']!r}"
    record: dict[str, Any] = {
        "task_id": task_id, "judge": JUDGE_TOOL[judge], "acting_for": "codex", "codex_state": why,
        "author_worker": author, "bundle_id": bundle_id, "verdict": verdict,
        "evidence": (judgement or {}).get("evidence", []),
        "judge_conversation_id": conversation_id, "envelope_sha256": envelope_sha,
        "verdict_sha256": (hashlib.sha256(json.dumps(judgement, sort_keys=True).encode("utf-8")).hexdigest()
                           if judgement else ""),
        "cost_gate": cost_gate, "usage": usage, "elapsed_s": int(time.monotonic() - started), "error": error,
        "applied": False,
    }
    if verdict == "APPROVE" and apply:
        # The unchanged approval gate does the promotion and re-checks digest, scope and the recorded cost gate.
        cmd = [sys.executable, "-m", "v7_harness.cli", "pilot", "run", "--task", task_id, "--worker", author,
               "--source", str(source), "--work-dir", str(work_dir), "--manual", str(manual_path),
               "--approve", bundle_id, "--coord-actor", JUDGE_TOOL[judge]]
        done = approver(cmd, cwd=str(Path(__file__).resolve().parents[1]), capture_output=True, timeout=900)
        tail_out = (done.stdout or b"").decode("utf-8", errors="replace")
        record["approve_exit"] = done.returncode
        record["approve_tail"] = tail_out[-1500:]
        record["applied"] = done.returncode == 0 and "APPLIED" in tail_out
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    record["judge_path"] = str(out)
    _record_usage(source, task_id, usage, record, out)
    return record


def _record_usage(source: Path, task_id: str, usage: dict[str, int], record: dict, receipt: Path) -> None:
    if not ((source / ".git").exists() or (source / ".coord" / "PLAN.md").is_file()):
        return
    from .coord.usage_ledger import record_usage

    entry = {
        "schema": "uaos-usage-v2", "work_id": f"{task_id}-judge-agy", "actor": "antigravity", "model": "agy-default",
        "kind": "judge", "collection_mode": "automatic",
        "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
        "wall_time_s": record["elapsed_s"], "outcome": record["verdict"], "receipt": str(receipt.resolve()),
        "independent_verifier": "antigravity", "rsi_eligible": False, "exclusion_reason": "JUDGEMENT",
        "worker": "agy", "cost_gate": record["cost_gate"],
    }
    if "thinking_tokens" in usage:
        entry["thinking_tokens"] = usage["thinking_tokens"]
    try:
        record_usage(source, entry)
    except Exception as exc:  # noqa: BLE001 - judge_agy.json is the receipt; the ledger is best effort
        record["usage_ledger_error"] = f"{type(exc).__name__}: {exc}"[:200]

===FILE: tests/test_u46_pilot_judge.py===
"""U46-J4: `pilot judge --judge agy` — while Codex is away, Antigravity's CLI verdict drives the unchanged approval gate."""

import json
import tempfile
import unittest
from pathlib import Path

from v7_harness import judge

MANUAL = """```contract
work_id: T1
worker: apply
goal: g
allow:
- a.py
acceptance: python -c "pass"
judge: {judge}
remote_budget_tokens: 0
```
"""


class Done:
    def __init__(self, stdout=b"", returncode=0):
        self.stdout = stdout
        self.stderr = b""
        self.returncode = returncode


class JudgeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.work, self.source, stage = root / "work", root / "src", root / "stage"
        self.runs = self.work / "runs" / "T1"
        for folder in (self.runs, self.source, stage):
            folder.mkdir(parents=True)
        (self.source / "a.py").write_text("X = 1\n", encoding="utf-8")
        (stage / "a.py").write_text("X = 2\n", encoding="utf-8")
        (self.runs / "worker").write_text("claude", encoding="utf-8")
        (self.runs / "summary.json").write_text(json.dumps(
            {"agy_workspace": str(stage), "changed_files": ["a.py"], "bundle_id": "b1",
             "promotion": "DRY_RUN_PASSED", "acceptance_exit": 0}), encoding="utf-8")
        self.manual = root / "m.md"
        self.manual.write_text(MANUAL.format(judge="antigravity"), encoding="utf-8")
        self.calls, self.approvals = [], []

    def tearDown(self):
        self._tmp.cleanup()

    def runner(self, verdict="APPROVE", bundle_id="b1", usage=None, status="SUCCESS"):
        envelope = {"status": status, "conversation_id": "conv-9",
                    "usage": usage or {"input_tokens": 100, "output_tokens": 20},
                    "structured_output": {"verdict": verdict, "bundle_id": bundle_id, "evidence": ["a.py:1 ok"]}}

        def run(argv, **kwargs):
            self.calls.append((argv, kwargs))
            return Done(json.dumps(envelope).encode("utf-8"))
        return run

    def approver(self, argv, **kwargs):
        self.approvals.append(argv)
        return Done(b'{"state": "APPLIED"}')

    def judge(self, codex="LIMITED", **kw):
        kw.setdefault("runner", self.runner())
        return judge.run_judge(task_id="T1", work_dir=self.work, source=self.source, manual_path=self.manual,
                               budget=10_000, approver=self.approver, desk={"codex": {"state": codex}}, **kw)

    def test_codex_active_or_unknown_judges_itself(self):
        for state in ("ACTIVE", "UNKNOWN"):
            with self.assertRaises(judge.JudgeRefused) as caught:
                self.judge(codex=state)
            self.assertIn("CODEX_JUDGES", str(caught.exception))
        self.assertEqual([], self.calls)

    def test_approve_while_codex_away_applies_through_the_unchanged_gate(self):
        record = self.judge(codex="ABSENT")
        self.assertEqual("APPROVE", record["verdict"])
        self.assertTrue(record["applied"])
        self.assertEqual("conv-9", record["judge_conversation_id"])
        self.assertTrue(record["verdict_sha256"])
        argv, kwargs = self.calls[0]
        self.assertNotIn("--dangerously-skip-permissions", argv)
        self.assertIn("plan", argv[argv.index("--mode") + 1])
        self.assertIn("--json-schema", argv)
        self.assertEqual(str(self.runs.resolve()), kwargs["cwd"])  # resolve() expands a Windows 8.3 temp path
        cmd = self.approvals[0]
        self.assertEqual(["--approve", "b1"], cmd[cmd.index("--approve"):cmd.index("--approve") + 2])
        self.assertEqual("antigravity", cmd[cmd.index("--coord-actor") + 1])
        self.assertEqual("claude", cmd[cmd.index("--worker") + 1])
        self.assertTrue((self.runs / "judge_agy.json").is_file())

    def test_reject_mismatch_or_over_budget_never_applies(self):
        cases = [dict(verdict="REJECT"), dict(bundle_id="other"), dict(usage={"input_tokens": 9_000,
                                                                             "output_tokens": 500,
                                                                             "thinking_tokens": 800})]
        for case in cases:
            (self.runs / "judge_agy.json").unlink(missing_ok=True)
            record = self.judge(runner=self.runner(**case))
            self.assertFalse(record["applied"])
            self.assertIn(record["verdict"], ("REJECT", "UNUSABLE"))
        self.assertEqual([], self.approvals)

    def test_failed_call_is_unusable(self):
        record = self.judge(runner=self.runner(status="ERROR"))
        self.assertEqual("UNUSABLE", record["verdict"])
        self.assertEqual([], self.approvals)

    def test_one_call_per_bundle(self):
        self.judge(apply=False)
        with self.assertRaises(judge.JudgeRefused) as caught:
            self.judge()
        self.assertIn("ALREADY_JUDGED", str(caught.exception))
        self.assertEqual(1, len(self.calls))

    def test_agy_never_judges_its_own_bundle_or_a_contract_naming_another_judge(self):
        (self.runs / "worker").write_text("agy", encoding="utf-8")
        with self.assertRaises(judge.JudgeRefused) as caught:
            self.judge()
        self.assertIn("JUDGE_IS_AUTHOR", str(caught.exception))
        (self.runs / "worker").write_text("claude", encoding="utf-8")
        self.manual.write_text(MANUAL.format(judge="codex"), encoding="utf-8")
        with self.assertRaises(judge.JudgeRefused) as caught:
            self.judge()
        self.assertIn("NOT_THE_NAMED_JUDGE", str(caught.exception))
        self.assertEqual([], self.calls)

    def test_a_bundle_that_did_not_pass_acceptance_is_not_judged(self):
        summary = json.loads((self.runs / "summary.json").read_text(encoding="utf-8"))
        summary["acceptance_exit"] = 1
        (self.runs / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        with self.assertRaises(judge.JudgeRefused) as caught:
            self.judge()
        self.assertIn("NOT_READY", str(caught.exception))

    def test_cli_parses_pilot_judge(self):
        from v7_harness.cli import build_parser
        args = build_parser().parse_args(["pilot", "judge", "--task", "T1", "--work-dir", "w", "--manual", "m"])
        self.assertEqual(("agy", 100_000, True), (args.judge, args.budget, not args.no_apply))


if __name__ == "__main__":
    unittest.main()

===EDIT: v7_harness/cli.py===
<<<<<<< SEARCH
    p_pilot_review.set_defaults(func=cmd_pilot_review)
=======
    p_pilot_review.set_defaults(func=cmd_pilot_review)

    # U46-J4: binding judgement by the contract's judge tool through its CLI, only while Codex is LIMITED/ABSENT.
    p_pilot_judge = p_pilot_subs.add_parser("judge", help="U46-J4: Antigravity judges a bundle via its CLI while Codex is away")
    p_pilot_judge.add_argument("--task", required=True)
    p_pilot_judge.add_argument("--work-dir", required=True)
    p_pilot_judge.add_argument("--source", default=".")
    p_pilot_judge.add_argument("--manual", required=True, help="The contract manual the bundle was built from")
    p_pilot_judge.add_argument("--project", default=None, help="Project whose presence desk says Codex is away")
    p_pilot_judge.add_argument("--judge", default="agy", choices=["agy"])
    p_pilot_judge.add_argument("--budget", type=int, default=100_000,
                               help="Token cap (J1 review used 71,299 and the J3 consult 89,263)")
    p_pilot_judge.add_argument("--timeout", type=int, default=600)
    p_pilot_judge.add_argument("--no-apply", action="store_true", help="Record the verdict without running --approve")
    p_pilot_judge.set_defaults(func=cmd_pilot_judge)
>>>>>>> REPLACE

===EDIT: v7_harness/cli.py===
<<<<<<< SEARCH
def resolve_worker_command(worker: str, explicit: Optional[Sequence[str]]) -> list[str]:
=======
def cmd_pilot_judge(args: argparse.Namespace) -> int:
    from .judge import JudgeRefused, run_judge

    try:
        record = run_judge(task_id=args.task, work_dir=Path(args.work_dir), source=Path(args.source),
                           manual_path=Path(args.manual), project=Path(args.project) if args.project else None,
                           judge=args.judge, budget=args.budget, timeout_s=args.timeout, apply=not args.no_apply)
    except (JudgeRefused, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:400]}, ensure_ascii=False))
        return 2
    print(json.dumps({"ok": True, **record}, ensure_ascii=False, indent=2))
    return 0 if record["verdict"] in ("APPROVE", "REJECT") else 3


def resolve_worker_command(worker: str, explicit: Optional[Sequence[str]]) -> list[str]:
>>>>>>> REPLACE


## Output

- Reply with ===FILE / ===EDIT blocks only. No explanations. Do not claim success; the acceptance command decides.
