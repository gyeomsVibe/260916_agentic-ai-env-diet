```contract
work_id: U46-J1
worker: apply
goal: pilot review --reviewer agy wakes Antigravity through its CLI, read-only, token budget gated, advisory evidence.
inputs:
- v7_harness/review.py sha256=7d9996360a68b23419e7d3287d521178b69f6244ebf70dd8e720c15260fefe54
- v7_harness/cli.py sha256=43d9e434addb66761956ad5c1b286dd5be11ce88c803b4b10bd3d1bb16a35bdf
- v7_harness/adapters/agy.py sha256=dd8dcf48569acf0614e6b013cce3200b54c3cab8329354779b5f8fcd31b4604c
allow:
- v7_harness/review.py
- v7_harness/cli.py
- tests/test_u46_agy_review.py
acceptance: python -m unittest tests.test_u46_agy_review tests.test_u38_cost_gate_and_claude_worker tests.test_u44_claude_contract tests.test_u45_conductor_succession
forbidden: design changes; edits outside allow; editing or deleting existing tests; network; real agy call; commit/push
stop: two failures with the same cause; input hash mismatch; no output
judge: antigravity
timeout_s: 300
remote_budget_tokens: 0
```

## Instructions for the worker

U46-J1 (2026-09-26, Claude acting conductor): Antigravity reviews a bundle through its CLI (`pilot review --reviewer agy`),
so a conductor can wake the judge tool without a person relaying a mailbox letter (docs/47 C5). Read-only: the request is a
file in the run folder and agy runs without a permission bypass; the review stays advisory evidence (B83).

===FILE: tests/test_u46_agy_review.py===
"""U46-J1: `pilot review --reviewer agy` asks Antigravity through its CLI, read-only, under the token budget gate."""

import json
import tempfile
import unittest
from pathlib import Path

from v7_harness import review


class Done:
    def __init__(self, envelope, returncode=0):
        self.stdout = json.dumps(envelope).encode("utf-8")
        self.stderr = b""
        self.returncode = returncode


class AgyReviewTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.work, self.source, stage = root / "work", root / "src", root / "stage"
        self.runs = self.work / "runs" / "T1"
        for folder in (self.runs, self.source, stage):
            folder.mkdir(parents=True)
        (self.source / "a.py").write_text("X = 1\n", encoding="utf-8")
        (stage / "a.py").write_text("X = 2\n", encoding="utf-8")
        (self.runs / "worker").write_text("apply", encoding="utf-8")
        (self.runs / "summary.json").write_text(json.dumps(
            {"agy_workspace": str(stage), "changed_files": ["a.py"], "bundle_id": "b1"}), encoding="utf-8")
        self.calls = []

    def tearDown(self):
        self._tmp.cleanup()

    def runner(self, envelope, returncode=0):
        def run(argv, **kwargs):
            self.calls.append((argv, kwargs))
            return Done(envelope, returncode)
        return run

    def ok(self, text, usage=None):
        return {"status": "SUCCESS", "conversation_id": "conv-1", "response": text,
                "usage": usage or {"input_tokens": 100, "output_tokens": 20}}

    def test_agy_review_is_read_only_advisory_and_keeps_the_conversation_id(self):
        record = review.run_review(task_id="T1", work_dir=self.work, source=self.source, manual_text="contract",
                                   reviewer="agy", budget=10_000,
                                   runner=self.runner(self.ok('{"verdict": "PASS", "counterexamples": []}')))
        self.assertEqual("PASS", record["verdict"])
        self.assertTrue(record["advisory"])
        self.assertEqual("conv-1", record["judge_conversation_id"])
        argv, kwargs = self.calls[0]
        self.assertEqual("agy", Path(argv[0]).stem)
        self.assertNotIn("--dangerously-skip-permissions", argv)
        self.assertEqual(str(self.runs), kwargs["cwd"])
        request = (self.runs / "review_agy_request.md").read_text(encoding="utf-8")
        self.assertIn("```diff", request)
        self.assertIn("+X = 2", request)
        self.assertLess(len(" ".join(argv)), 32_767)
        self.assertTrue((self.runs / "review_agy.json").is_file())

    def test_agy_review_needs_a_token_budget_but_no_dollar_cap(self):
        with self.assertRaises(review.ReviewRefused):
            review.run_review(task_id="T1", work_dir=self.work, source=self.source, manual_text="c",
                              reviewer="agy", budget=0, runner=self.runner(self.ok("{}")))
        record = review.run_review(task_id="T1", work_dir=self.work, source=self.source, manual_text="c",
                                   reviewer="agy", budget=5_000, budget_usd=0,
                                   runner=self.runner(self.ok('{"verdict": "REWORK", "counterexamples": ["x"]}')))
        self.assertEqual("REWORK", record["verdict"])

    def test_agy_never_reviews_its_own_bundle(self):
        (self.runs / "worker").write_text("agy", encoding="utf-8")
        with self.assertRaises(review.ReviewRefused) as caught:
            review.run_review(task_id="T1", work_dir=self.work, source=self.source, manual_text="c",
                              reviewer="agy", budget=5_000, runner=self.runner(self.ok("{}")))
        self.assertIn("REVIEWER_IS_AUTHOR", str(caught.exception))

    def test_over_budget_or_failed_agy_review_is_unusable(self):
        record = review.run_review(task_id="T1", work_dir=self.work, source=self.source, manual_text="c",
                                   reviewer="agy", budget=50,
                                   runner=self.runner(self.ok('{"verdict": "PASS"}')))
        self.assertEqual("UNUSABLE", record["verdict"])
        failed = review.run_review(task_id="T1", work_dir=self.work, source=self.source, manual_text="c",
                                   reviewer="agy", budget=5_000,
                                   runner=self.runner({"status": "ERROR", "error": "429 quota", "usage": {}}))
        self.assertEqual("UNUSABLE", failed["verdict"])
        self.assertIn("QUOTA", failed["error"])

    def test_the_claude_reviewer_still_needs_a_dollar_cap(self):
        with self.assertRaises(review.ReviewRefused) as caught:
            review.run_review(task_id="T1", work_dir=self.work, source=self.source, manual_text="c",
                              reviewer="claude", budget=5_000, budget_usd=0)
        self.assertIn("REVIEW_WITHOUT_USD_CAP", str(caught.exception))

    def test_cli_accepts_the_agy_reviewer_without_a_dollar_cap(self):
        from v7_harness.cli import build_parser
        args = build_parser().parse_args(["pilot", "review", "--task", "T1", "--work-dir", "w", "--manual", "m",
                                          "--reviewer", "agy", "--budget", "5000"])
        self.assertEqual("agy", args.reviewer)


if __name__ == "__main__":
    unittest.main()

===EDIT: v7_harness/review.py===
<<<<<<< SEARCH
REVIEWERS = ("claude",)
=======
# U46-J1: agy lets a conductor wake Antigravity through its CLI instead of a mailbox letter a person must relay.
REVIEWERS = ("claude", "agy")
>>>>>>> REPLACE

===EDIT: v7_harness/review.py===
<<<<<<< SEARCH
    if not budget_usd > 0:
        raise ReviewRefused("REVIEW_WITHOUT_USD_CAP: pass --budget-usd > 0 (claude --max-budget-usd, before spending)")
=======
    if reviewer == "claude" and not budget_usd > 0:
        # agy has no dollar cap option; its review is held by the token budget gate alone (B85).
        raise ReviewRefused("REVIEW_WITHOUT_USD_CAP: pass --budget-usd > 0 (claude --max-budget-usd, before spending)")
>>>>>>> REPLACE

===EDIT: v7_harness/review.py===
<<<<<<< SEARCH
    verdict = None
    try:
        from .adapters.long_prompt import ARGV_PROMPT_CHARS
=======
    verdict = None
    conversation_id = None
    try:
        if reviewer == "agy":
            usage, verdict, error, conversation_id = _agy_review(task_id, prompt, runs, timeout_s, runner)
            raise _Reviewed
        from .adapters.long_prompt import ARGV_PROMPT_CHARS
>>>>>>> REPLACE

===EDIT: v7_harness/review.py===
<<<<<<< SEARCH
        else:
            error = "REVIEW_NOT_JSON_OBJECT"
    except subprocess.TimeoutExpired:
=======
        else:
            error = "REVIEW_NOT_JSON_OBJECT"
    except _Reviewed:
        pass
    except subprocess.TimeoutExpired:
>>>>>>> REPLACE

===EDIT: v7_harness/review.py===
<<<<<<< SEARCH
        "cost_gate": cost_gate, "usage": usage, "elapsed_s": int(time.monotonic() - started), "error": error,
    }
=======
        "cost_gate": cost_gate, "usage": usage, "elapsed_s": int(time.monotonic() - started), "error": error,
    }
    if reviewer == "agy":
        record["judge_conversation_id"] = conversation_id
>>>>>>> REPLACE

===EDIT: v7_harness/review.py===
<<<<<<< SEARCH
    _record_usage(Path(source), task_id, reviewer, model or DEFAULT_MODEL, usage, record, out)
    return record
=======
    _record_usage(Path(source), task_id, reviewer, model or (DEFAULT_MODEL if reviewer == "claude" else "agy-default"),
                  usage, record, out)
    return record


class _Reviewed(Exception):
    """Leaves the claude call path once the agy review has run."""


def _agy_review(task_id: str, prompt: str, runs: Path, timeout_s: int,
                runner: Any) -> tuple[dict[str, int], dict[str, Any] | None, str, str | None]:
    """Antigravity reads the request from a file in the run folder (a diff can pass the 32,767-character Windows
    command line) and answers in JSON. No permission bypass: it can read, and only the pilot applies anything."""
    import os

    from .adapters.agy import AgyRequest, build_agy_command, parse_agy_result

    request = runs / "review_agy_request.md"
    request.write_text(prompt, encoding="utf-8")
    short = (f"Read {request.name} in this folder: a review request with the contract and the complete diff. "
             f"Do not edit any file. Reply with exactly one JSON object: {SCHEMA_HINT}")
    argv = build_agy_command(AgyRequest(task_id=task_id, title="review", prompt=short, workspace=runs,
                                        isolation_mode="staging", print_timeout_s=timeout_s))
    done = runner(argv, cwd=str(runs), env={**os.environ, "UAOS_WORKER": "1"}, capture_output=True,
                  timeout=timeout_s + 60)
    outcome = parse_agy_result(stdout=done.stdout or b"", stderr=done.stderr or b"", exit_code=done.returncode)
    usage = dict(outcome.usage)
    if not outcome.successful:
        return usage, None, f"REVIEW_FAILED:agy {outcome.error_class}", outcome.conversation_id
    envelope = json.loads(done.stdout.decode("utf-8", errors="replace"))
    text = envelope.get("response") if isinstance(envelope.get("response"), str) else json.dumps(
        envelope.get("structured_output"))
    verdict = parse_verdict(text)
    return (usage, verdict, "" if verdict else "REVIEW_UNPARSED: the reviewer did not return the JSON verdict (agy)",
            outcome.conversation_id)
>>>>>>> REPLACE

===EDIT: v7_harness/cli.py===
<<<<<<< SEARCH
    p_pilot_review.add_argument("--reviewer", default="claude", choices=["claude"])
=======
    p_pilot_review.add_argument("--reviewer", default="claude", choices=["claude", "agy"],
                                help="agy = Antigravity CLI, read-only, token budget only (U46-J1, docs/47)")
>>>>>>> REPLACE

===EDIT: v7_harness/cli.py===
<<<<<<< SEARCH
    p_pilot_review.add_argument("--budget-usd", type=float, required=True,
                                help="Dollar cap passed to claude --max-budget-usd (checked before spending)")
=======
    # Not required by argparse any more: run_review refuses a claude review without it (agy has no dollar option).
    p_pilot_review.add_argument("--budget-usd", type=float, default=0.0,
                                help="Dollar cap passed to claude --max-budget-usd (checked before spending); "
                                     "required for --reviewer claude")
>>>>>>> REPLACE
