"""U36: evidence-gated self-improvement. The loop observes and proposes; the gate reads the ledger; a separate judge adopts.

Each test pins one blind spot from docs/38: evaluator gaming, self-reported numbers, self-verification, weakening the
gate's own thresholds, optimizing one metric while another regresses, stacking changes, and no way back.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from v7_harness import rsi
from v7_harness.adapters import apply_worker
from v7_harness.cli import main
from v7_harness.coord.mailbox import Mailbox
from v7_harness.coord.sentinel import generate_briefing, run_sentinel_cycle
from v7_harness.manual import lint, new_manual
from v7_harness.pilot import PilotConfig, run_pilot

APPLY = [sys.executable, str(Path(apply_worker.__file__).resolve())]


def _row(work_id: str, outcome: str, *, worker: str = "ollama", ts: float = 0.0, tokens: int | None = 1000,
         error_class: str | None = None) -> dict:
    return {"schema": "uaos-usage-v2", "kind": "pilot", "work_id": work_id, "worker": worker, "outcome": outcome,
            "ts": ts, "input_tokens": tokens, "error_class": error_class}


def _ledger(root: Path, rows: list[dict]) -> None:
    path = root / ".coord" / "usage" / "runs.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _before_after(root: Path, *, before_pass: int, after_pass: int, n: int = 4, after_worker: str = "ollama",
                  after_tokens: int = 1000) -> tuple[list[str], list[str]]:
    before = [_row(f"B{i}", "PASS" if i < before_pass else "REWORK", ts=i, error_class=None if i < before_pass else "SYNTAX_ERROR")
              for i in range(n)]
    after = [_row(f"A{i}", "PASS" if i < after_pass else "REWORK", ts=100 + i, worker=after_worker, tokens=after_tokens)
             for i in range(n)]
    _ledger(root, before + after)
    return [r["work_id"] for r in before], [r["work_id"] for r in after]


def _candidate(before_ids: list[str], after_ids: list[str], **overrides) -> dict:
    values = {"id": "rsi_test", "author": "claude", "verifier": "antigravity",
              "changed_paths": [".coord/tasks/U99-template.md"], "before_work_ids": before_ids, "after_work_ids": after_ids}
    values.update(overrides)
    return values


class PathAndPolicyTests(unittest.TestCase):
    def test_dot_prefixed_paths_keep_their_dot(self) -> None:
        # lstrip("./") once turned ".coord/rsi/policy.json" into "coord/rsi/policy.json" and nothing matched.
        self.assertTrue(rsi._matches(".coord/rsi/policy.json", rsi.RSI_TARGET_PATTERNS))
        self.assertTrue(rsi._matches("./docs/guide/a.md", rsi.RSI_TARGET_PATTERNS))
        self.assertTrue(rsi._matches(".coord/usage/runs.jsonl", rsi.EVALUATOR_PATTERNS))
        self.assertTrue(rsi._matches(".githooks/pre-commit", rsi.EVALUATOR_PATTERNS))
        self.assertTrue(rsi._matches("tests\\sub\\test_x.py", rsi.EVALUATOR_PATTERNS))
        self.assertFalse(rsi._matches("coord/rsi/policy.json", rsi.RSI_TARGET_PATTERNS))

    def test_policy_file_cannot_weaken_the_documented_floors(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".coord" / "rsi").mkdir(parents=True)
            (root / rsi.POLICY_PATH).write_text(json.dumps({
                "local_min_specificity": 50, "remote_min_specificity": 90, "min_samples": 1,
                "max_cost_ratio": 10, "window": 20, "unknown": 1}), encoding="utf-8")
            policy = rsi.load_policy(root)
            self.assertEqual(80, policy["local_min_specificity"])
            self.assertEqual(90, policy["remote_min_specificity"])
            self.assertEqual(3, policy["min_samples"])
            self.assertEqual(3.0, policy["max_cost_ratio"])
            self.assertEqual(20, policy["window"])
            self.assertNotIn("unknown", policy)

    def test_broken_policy_file_falls_back_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".coord" / "rsi").mkdir(parents=True)
            (root / rsi.POLICY_PATH).write_text("{not json", encoding="utf-8")
            self.assertEqual(rsi.DEFAULT_POLICY, rsi.load_policy(root))

    def test_manual_lint_reads_a_stricter_adopted_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "pkg").mkdir()
            (root / "pkg" / "config.py").write_text("TIMEOUT = 30\n", encoding="utf-8")
            text = new_manual(root, work_id="U36_T", worker="local",
                              goal="Replace TIMEOUT = 30 with TIMEOUT = 60 in `pkg/config.py`.",
                              inputs=["pkg/config.py"], allow=["pkg/config.py"],
                              acceptance="python -c \"import pkg.config\"", judge="codex")
            self.assertTrue(lint(text, root).ok)
            (root / ".coord" / "rsi").mkdir(parents=True)
            (root / rsi.POLICY_PATH).write_text(json.dumps({"local_min_specificity": 100}), encoding="utf-8")
            report = lint(text, root)
            self.assertFalse(report.ok)
            self.assertTrue(any(error.startswith("LOW_SPECIFICITY:") and error.endswith("<100 for a local model")
                                for error in report.errors), report.errors)


class ObserveAndProposeTests(unittest.TestCase):
    def test_window_status_follows_sample_count(self) -> None:
        rows = [_row(f"W{i}", "PASS", ts=i) for i in range(12)]
        self.assertEqual("INSUFFICIENT_SAMPLES", rsi.analyze(rows[:2])["workers"]["ollama"]["status"])
        self.assertEqual("PARTIAL_WINDOW", rsi.analyze(rows[:5])["workers"]["ollama"]["status"])
        ready = rsi.analyze(rows)["workers"]["ollama"]
        self.assertEqual(("WINDOW_READY", 10, 12), (ready["status"], ready["n"], ready["total"]))

    def test_causes_come_from_error_class_and_recur(self) -> None:
        rows = [
            _row("C1", "REWORK", ts=1, error_class="SCOPE_VIOLATION"),
            _row("C2", "REWORK", ts=2, error_class="SCOPE_VIOLATION"),
            {**_row("C3", "BLOCKED", ts=3), "error_detail": "PROMPT_TOO_LARGE: 9000 tokens"},
            _row("C4", "PASS", ts=4),
        ]
        info = rsi.analyze(rows)["workers"]["ollama"]
        self.assertEqual([("SCOPE_VIOLATION", 2), ("PROMPT_TOO_LARGE", 1)], info["causes"])
        self.assertEqual(["SCOPE_VIOLATION"], info["recurring"])
        proposals = rsi.propose(rsi.analyze(rows))
        self.assertEqual("SCOPE_VIOLATION", proposals[0]["cause"])
        self.assertTrue(proposals[0]["recurring"])
        self.assertEqual("manual_template", proposals[0]["target"])

    def test_high_local_rework_proposes_a_stricter_policy_within_bounds(self) -> None:
        rows = [_row(f"R{i}", "REWORK" if i < 7 else "PASS", ts=i, error_class="SYNTAX_ERROR" if i < 7 else None)
                for i in range(10)]
        policy = {**rsi.DEFAULT_POLICY, "local_min_specificity": 98}
        proposals = rsi.propose(rsi.analyze(rows, policy), policy)
        raise_it = [p for p in proposals if p["cause"] == "HIGH_REWORK_RATE"][0]
        self.assertEqual({"local_min_specificity": 100}, raise_it["policy"])
        template = rsi.candidate_template(raise_it, "claude")
        self.assertEqual([rsi.POLICY_PATH.as_posix()], template["changed_paths"])
        self.assertNotIn("before", template)

    def test_unreadable_ledger_line_is_counted_not_dropped(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _ledger(root, [_row("OK1", "PASS", ts=1)])
            with (root / ".coord" / "usage" / "runs.jsonl").open("a", encoding="utf-8") as handle:
                handle.write("{broken\n")
            rows = rsi.load_rows(root)
            self.assertEqual(["PASS", "UNREADABLE"], sorted(row["outcome"] for row in rows))

    def test_a_line_still_being_appended_is_not_counted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _ledger(root, [_row("OK1", "PASS", ts=1)])
            with (root / ".coord" / "usage" / "runs.jsonl").open("a", encoding="utf-8") as handle:
                handle.write('{"kind": "pilot", "work_id": "HALF", "outc')
            self.assertEqual(["OK1"], [row["work_id"] for row in rsi.load_rows(root)])


class GateTests(unittest.TestCase):
    def _metrics(self, n=4, p=0.5, r=0.5, b=0.0, t=1000) -> dict:
        return {"n": n, "pass_rate": p, "rework_rate": r, "blocked_rate": b, "median_input_tokens": t}

    def _gate(self, **overrides) -> dict:
        values = {"id": "x", "author": "claude", "verifier": "codex", "changed_paths": ["docs/guide.md"],
                  "before": self._metrics(), "after": self._metrics(p=0.75, r=0.25)}
        values.update(overrides)
        return rsi.gate(values)

    def test_a_real_improvement_becomes_a_candidate_not_an_adoption(self) -> None:
        verdict = self._gate()
        self.assertEqual("ADOPT_CANDIDATE", verdict["decision"], verdict["reasons"])
        self.assertIn("never automatic", verdict["next"])

    def test_evaluators_and_evidence_cannot_be_touched(self) -> None:
        for path in ("tests/test_u36_evidence_gated_rsi.py", ".coord/usage/runs.jsonl", "v7_harness/rsi.py",
                     ".coord/rsi/decisions.jsonl", "v7_harness/manual.py", ".coord/runs/run_regression.py"):
            verdict = self._gate(changed_paths=[path])
            self.assertTrue(any(r.startswith("EVALUATOR_TOUCHED") for r in verdict["reasons"]), (path, verdict))

    def test_code_goes_through_the_reviewed_path(self) -> None:
        verdict = self._gate(changed_paths=["v7_harness/pilot.py"])
        self.assertTrue(any(r.startswith("OUT_OF_RSI_SCOPE:v7_harness/pilot.py") for r in verdict["reasons"]))
        self.assertIn("NO_CHANGE_LISTED", self._gate(changed_paths=[])["reasons"])

    def test_the_author_cannot_verify_itself_and_ollama_cannot_verify(self) -> None:
        for verifier in ("claude", "ollama", ""):
            verdict = self._gate(verifier=verifier)
            self.assertTrue(any(r.startswith("SELF_OR_INVALID_VERIFIER") for r in verdict["reasons"]), verifier)

    def test_policy_changes_may_only_tighten_and_must_be_listed(self) -> None:
        weaker = self._gate(changed_paths=[".coord/rsi/policy.json"], policy={"local_min_specificity": 70})
        self.assertTrue(any(r.startswith("POLICY_OUT_OF_BOUNDS:local_min_specificity") for r in weaker["reasons"]))
        gate_itself = self._gate(changed_paths=[".coord/rsi/policy.json"], policy={"min_samples": 1})
        self.assertTrue(any(r.startswith("POLICY_OUT_OF_BOUNDS:min_samples") for r in gate_itself["reasons"]))
        hidden = self._gate(policy={"local_min_specificity": 85})
        self.assertIn("POLICY_CHANGE_NOT_LISTED:.coord/rsi/policy.json", hidden["reasons"])
        unknown = self._gate(changed_paths=[".coord/rsi/policy.json"], policy={"auto_adopt": True})
        self.assertIn("POLICY_UNKNOWN_KEY:auto_adopt", unknown["reasons"])

    def test_one_better_number_does_not_hide_a_worse_one(self) -> None:
        verdict = self._gate(after=self._metrics(p=0.75, r=0.0, b=0.25))
        self.assertIn("REGRESSION:blocked_rate 0.0→0.25", verdict["reasons"])
        costly = self._gate(after=self._metrics(p=0.75, r=0.25, t=3500))
        self.assertIn("COST_REGRESSION:1000→3500", costly["reasons"])
        same = self._gate(after=self._metrics())
        self.assertIn("NO_GAIN", same["reasons"])
        few = self._gate(after=self._metrics(n=2, p=1.0, r=0.0))
        self.assertTrue(any(r.startswith("INSUFFICIENT_SAMPLES") for r in few["reasons"]))


class LedgerGateAndJudgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_metrics_are_read_from_the_ledger_not_typed_in(self) -> None:
        before, after = _before_after(self.root, before_pass=1, after_pass=3)
        verdict = rsi.gate_from_ledger(self.root, _candidate(before, after))
        self.assertEqual("ADOPT_CANDIDATE", verdict["decision"], verdict["reasons"])
        self.assertEqual((0.25, 0.75), (verdict["before"]["pass_rate"], verdict["after"]["pass_rate"]))
        typed = rsi.gate_from_ledger(self.root, _candidate(before, after, after={"n": 99, "pass_rate": 1.0}))
        self.assertEqual("REJECT", typed["decision"])
        self.assertTrue(typed["reasons"][0].startswith("SELF_REPORTED_METRICS"))

    def test_missing_overlapping_and_incomparable_evidence_is_rejected(self) -> None:
        before, after = _before_after(self.root, before_pass=1, after_pass=3)
        missing = rsi.gate_from_ledger(self.root, _candidate(before, after + ["GHOST"]))
        self.assertIn("EVIDENCE_NOT_IN_LEDGER:GHOST", missing["reasons"])
        overlap = rsi.gate_from_ledger(self.root, _candidate(before, after + [before[0]]))
        self.assertIn(f"OVERLAPPING_SAMPLES:{before[0]}", overlap["reasons"])

    def test_different_workers_are_not_comparable(self) -> None:
        before, after = _before_after(self.root, before_pass=1, after_pass=3, after_worker="apply")
        verdict = rsi.gate_from_ledger(self.root, _candidate(before, after))
        self.assertTrue(any(r.startswith("NOT_COMPARABLE") for r in verdict["reasons"]), verdict["reasons"])

    def test_adoption_needs_an_independent_judge(self) -> None:
        before, after = _before_after(self.root, before_pass=1, after_pass=3)
        candidate = _candidate(before, after)
        for judge in ("claude", "antigravity", "ollama"):
            with self.assertRaises(rsi.RsiRefused):
                rsi.adopt(self.root, candidate, judge)
        self.assertEqual([], rsi.read_decisions(self.root))
        result = rsi.adopt(self.root, candidate, "codex")
        self.assertEqual("rsi_test", result["adopted"])
        self.assertFalse(result["policy_written"])

    def test_a_rejected_adoption_is_recorded(self) -> None:
        before, after = _before_after(self.root, before_pass=3, after_pass=1)
        with self.assertRaises(rsi.RsiRefused) as caught:
            rsi.adopt(self.root, _candidate(before, after), "codex")
        self.assertIn("GATE_REJECTED", str(caught.exception))
        decision = rsi.read_decisions(self.root)[-1]
        self.assertEqual("REJECTED", decision["action"])
        self.assertTrue(any(r.startswith("REGRESSION:pass_rate") for r in decision["reasons"]))

    def test_policy_adoption_keeps_the_old_value_and_rolls_back(self) -> None:
        before, after = _before_after(self.root, before_pass=1, after_pass=3)
        candidate = _candidate(before, after, changed_paths=[".coord/rsi/policy.json"],
                               policy={"local_min_specificity": 85})
        rsi.adopt(self.root, candidate, "codex")
        self.assertEqual(85, rsi.load_policy(self.root)["local_min_specificity"])
        adopted = rsi.read_decisions(self.root)[-1]
        self.assertEqual(80, adopted["previous_policy"]["local_min_specificity"])
        self.assertEqual(len(rsi.load_rows(self.root)) + 10, adopted["recheck_at_rows"])
        result = rsi.rollback(self.root, "codex", "rework did not fall in the next window")
        self.assertEqual("rsi_test", result["rolled_back"])
        self.assertEqual(80, rsi.load_policy(self.root)["local_min_specificity"])
        with self.assertRaises(rsi.RsiRefused):
            rsi.rollback(self.root, "codex", "again")

    def test_one_change_per_window(self) -> None:
        before, after = _before_after(self.root, before_pass=1, after_pass=3)
        rsi.adopt(self.root, _candidate(before, after), "codex")
        second = _candidate(before, after, id="rsi_second", changed_paths=["docs/other.md"])
        with self.assertRaises(rsi.RsiRefused) as caught:
            rsi.adopt(self.root, second, "codex")
        self.assertIn("ONE_CHANGE_PER_WINDOW:rsi_test", str(caught.exception))
        self.assertFalse(rsi.open_trials(self.root)[0]["due"])
        _ledger(self.root, [_row(f"N{i}", "PASS", ts=200 + i) for i in range(10)])
        self.assertTrue(rsi.open_trials(self.root)[0]["due"])
        self.assertEqual("rsi_second", rsi.adopt(self.root, second, "user")["adopted"])


class SentinelAndCliTests(unittest.TestCase):
    def test_sentinel_publishes_one_review_per_window_and_never_p1(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".coord" / "mailbox").mkdir(parents=True)
            box = Mailbox(root / ".coord" / "mailbox")
            _ledger(root, [_row(f"S{i}", "REWORK", ts=i, error_class="SYNTAX_ERROR") for i in range(10)])
            first = run_sentinel_cycle(root, box)
            self.assertEqual(["rsi_review_ollama_10x1"], first["rsi_review_published"])
            self.assertFalse(first["p1_wake_emitted"])
            self.assertIsNone(first["rsi_error"])
            self.assertIn("RSI reviews waiting: rsi_review_ollama_10x1", generate_briefing(root, box))
            self.assertEqual([], run_sentinel_cycle(root, box)["rsi_review_published"])
            claim = box.claim("rsi_review_ollama_10x1", "codex")
            box.ack(claim)
            self.assertEqual([], run_sentinel_cycle(root, box)["rsi_review_published"])
            _ledger(root, [_row(f"T{i}", "PASS", ts=100 + i) for i in range(10)])
            self.assertEqual(["rsi_review_ollama_10x2"], run_sentinel_cycle(root, box)["rsi_review_published"])

    def test_a_broken_policy_or_ledger_does_not_stop_the_operator(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".coord" / "mailbox").mkdir(parents=True)
            box = Mailbox(root / ".coord" / "mailbox")
            (root / ".coord" / "usage").mkdir()
            (root / ".coord" / "usage" / "runs.jsonl").write_bytes(b"\xff\xfe not utf-8")
            result = run_sentinel_cycle(root, box)
            self.assertIn("UnicodeDecodeError", result["rsi_error"])

    def test_cli_gate_exit_codes_and_candidate_template(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            before, after = _before_after(root, before_pass=1, after_pass=3)
            good = root / "good.json"
            good.write_text(json.dumps(_candidate(before, after)), encoding="utf-8")
            bad = root / "bad.json"
            bad.write_text(json.dumps(_candidate(before, after, verifier="claude")), encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["rsi", "gate", "--project", d, "--candidate", str(good)]))
                self.assertEqual(2, main(["rsi", "gate", "--project", d, "--candidate", str(bad)]))
                self.assertEqual(2, main(["rsi", "adopt", "--project", d, "--candidate", str(good), "--judge", "claude"]))
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(0, main(["rsi", "report", "--project", d]))
            report = json.loads(out.getvalue())
            self.assertEqual(8, report["samples"])
            self.assertEqual(rsi.DEFAULT_POLICY, report["policy"])
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(0, main(["rsi", "propose", "--project", d]))
            proposal_id = json.loads(out.getvalue())["proposals"][0]["id"]
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(0, main(["rsi", "propose", "--project", d, "--candidate-for", proposal_id,
                                          "--author", "claude"]))
            template = json.loads(out.getvalue())
            self.assertEqual("claude", template["author"])
            self.assertIn("after_work_ids", template)


class LedgerCauseTests(unittest.TestCase):
    def test_pilot_ledger_row_names_the_error_class(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "proj"
            (source / ".coord").mkdir(parents=True)
            (source / ".coord" / "PLAN.md").write_text("# plan\n", encoding="utf-8")
            (source / "calc.py").write_text("def mul(a, b):\n    return a * b\n", encoding="utf-8")
            (source / "other.py").write_text("X = 1\n", encoding="utf-8")
            prompt = "===FILE: other.py===\nX = 2\n"
            summary = run_pilot(PilotConfig(
                task_id="U36_SCOPE", title="scope", prompt=prompt, source_dir=source, work_dir=root / "work",
                agy_command=APPLY, watch_roots=[], print_timeout_s=60,
                accept_cmd=f'"{sys.executable}" -c "pass"', allowed_scopes=["calc.py"],
            ))
            self.assertNotEqual("PASS", summary["verdict_hint"])
            row = json.loads((source / ".coord" / "usage" / "runs.jsonl").read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual("SCOPE_VIOLATION", row["error_class"])
            self.assertEqual("SCOPE_VIOLATION", rsi._cause(row))


if __name__ == "__main__":
    unittest.main()
