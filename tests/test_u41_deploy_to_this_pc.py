"""U41: the one-command PC rollout (deploy_to_this_pc). Every step runs through a fake runner; nothing touches git,
the real home folder or the real canon repository."""

from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from v7_harness import deploy_pc as dp
from v7_harness import global_install as gi


class FakeRunner:
    def __init__(self, fail: dict[str, int] | None = None, branch: str = dp.BRANCH, dirty: str = ""):
        self.calls: list[list[str]] = []
        self.fail = fail or {}
        self.branch = branch
        self.dirty = dirty

    def __call__(self, command, **kwargs):
        self.calls.append(list(command))
        text = " ".join(command)
        if command[:3] == ["git", "rev-parse", "--abbrev-ref"]:
            return subprocess.CompletedProcess(command, 0, self.branch, "")
        if command[:3] == ["git", "status", "--porcelain"]:
            return subprocess.CompletedProcess(command, 0, self.dirty, "")
        for marker, code in self.fail.items():
            if marker in text:
                return subprocess.CompletedProcess(command, code, "", f"{marker} failed")
        return subprocess.CompletedProcess(command, 0, "ok", "")


class DeployTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.canon = root / "canon"
        src = self.canon / "shared" / "global-rules"
        (src / "dist" / "claude").mkdir(parents=True)
        (src / "src").mkdir()
        for name in ("claude.md", "AGENTS.md", "GEMINI.md"):
            (src / "src" / name).write_text("# rules\n", encoding="utf-8")
        (src / "dist" / "claude" / "CLAUDE.md").write_text("# generated\n", encoding="utf-8")  # must be ignored
        self.home = root / "home"
        for rel in dp.RUNTIME_RULES.values():
            (self.home / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.home / rel).write_text("# x\n" + gi.BLOCK_BEGIN + "\nbody\n" + gi.BLOCK_END + "\n", encoding="utf-8")
        self.receipts = root / "receipts"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _main(self, *args: str, runner: FakeRunner | None = None) -> tuple[int, dict, FakeRunner]:
        runner = runner or FakeRunner()
        out = io.StringIO()
        with redirect_stdout(out):
            code = dp.main(["--canon", str(self.canon), "--home", str(self.home), "--receipt-dir", str(self.receipts),
                            "--no-sentinel", *args], runner=runner)
        return code, json.loads(out.getvalue()), runner

    def test_canon_sources_one_per_runtime_and_dist_is_ignored(self) -> None:
        found, problems = dp.find_canon_sources(self.canon)
        self.assertEqual([], problems)
        self.assertEqual({"claude": "claude.md", "codex": "AGENTS.md", "antigravity": "GEMINI.md"},
                         {k: v.name for k, v in found.items()})

    def test_ambiguous_sources_stop_without_guessing_and_an_override_resolves(self) -> None:
        (self.canon / "shared" / "global-rules" / "src" / "codex-extra.md").write_text("x", encoding="utf-8")
        _found, problems = dp.find_canon_sources(self.canon)
        self.assertTrue(problems[0].startswith("CANON_SOURCES_AMBIGUOUS:codex"))
        code, out, runner = self._main("--apply")
        self.assertEqual((1, "STOPPED", "canon_sources"), (code, out["result"], out["stopped_at"]))
        self.assertEqual([], runner.calls)
        override = self.canon / "shared" / "global-rules" / "src" / "AGENTS.md"
        found, problems = dp.find_canon_sources(self.canon, {"codex": override})
        self.assertEqual(([], override), (problems, found["codex"]))

    def test_dry_run_changes_nothing(self) -> None:
        code, out, runner = self._main()
        self.assertEqual((0, "DRY_RUN"), (code, out["result"]))
        self.assertEqual([], runner.calls)
        self.assertFalse(self.receipts.exists())
        names = [s["step"] for s in out["steps"][1:]]
        self.assertEqual(["on_branch", "canon_clean", "fetch", "merge", "regression", "install_hooks", "canon_block",
                          "generator_build", "generator_sourcecheck", "generator_apply", "generator_check",
                          "runtime_rules", "installer_check"], names)

    def test_full_run_with_push_in_order(self) -> None:
        code, out, runner = self._main("--apply", "--push")
        self.assertEqual((0, "DONE"), (code, out["result"]), out)
        commands = [" ".join(c) for c in runner.calls]
        self.assertIn("merge --no-edit origin/" + dp.BRANCH, commands[3])
        self.assertTrue(any("--portable" in c and "--rules-file" in c for c in commands))
        tail = [c for c in commands if c.startswith("git") and ("commit" in c or "push" in c or "add" in c)]
        self.assertEqual(["git add", "git commit", "git push", "git add", "git commit", "git push"],
                         [" ".join(c.split()[:2]) for c in tail])
        self.assertIn(f"HEAD:{dp.BRANCH}", tail[-1])
        receipt = json.loads(next(self.receipts.glob("deploy_receipt_*.json")).read_text(encoding="utf-8"))
        self.assertEqual("DONE", receipt["result"])
        self.assertNotIn("rebase", " ".join(commands))

    def test_the_rollout_runs_from_main_after_the_merge(self) -> None:
        self.assertEqual("main", dp.BRANCH)
        code, out, runner = self._main("--apply", "--push", runner=FakeRunner(branch="main"))
        self.assertEqual((0, "DONE"), (code, out["result"]), out)
        commands = [" ".join(c) for c in runner.calls]
        self.assertIn("git push origin HEAD:main", commands[-1])
        code, out, _ = self._main("--apply", "--branch", "release", runner=FakeRunner(branch="release"))
        self.assertEqual((0, "DONE"), (code, out["result"]), out)

    def test_the_first_failed_gate_stops_the_run(self) -> None:
        code, out, runner = self._main("--apply", "--push", runner=FakeRunner(fail={"run_regression.py": 1}))
        self.assertEqual((1, "STOPPED", "regression"), (code, out["result"], out["stopped_at"]))
        self.assertFalse(any("install_uaos_everywhere" in " ".join(c) for c in runner.calls))
        self.assertFalse(any(c[:2] == ["git", "push"] for c in runner.calls))

    def test_wrong_branch_and_a_dirty_canon_stop_first(self) -> None:
        _code, out, _ = self._main("--apply", runner=FakeRunner(branch="claude/old-branch"))
        self.assertEqual("on_branch", out["stopped_at"])
        _code, out, runner = self._main("--apply", runner=FakeRunner(dirty=" M shared/global-rules/src/claude.md"))
        self.assertEqual("canon_clean", out["stopped_at"])
        self.assertIn("CANON_DIRTY", out["steps"][-1]["output_tail"])
        self.assertFalse(any(c[:2] == ["git", "fetch"] for c in runner.calls))

    def test_runtime_rules_without_the_block_stop_before_the_final_check(self) -> None:
        (self.home / dp.RUNTIME_RULES["codex"]).write_text("# regenerated without UAOS\n", encoding="utf-8")
        _code, out, runner = self._main("--apply")
        self.assertEqual("runtime_rules", out["stopped_at"])
        self.assertIn("AGENTS.md", out["steps"][-1]["output_tail"])

    def test_the_canon_block_is_portable(self) -> None:
        block = gi.rule_block("C:/Users/Kim/python.exe", Path("C:/Users/Kim/.uaos/uaos.py"), portable=True)
        self.assertIn('python "$HOME/.uaos/uaos.py"', block)
        self.assertNotIn("C:/Users", block)
        self.assertIn("C:/Users/Kim/python.exe", gi.rule_block("C:/Users/Kim/python.exe", Path("C:/Users/Kim/.uaos/uaos.py")))


if __name__ == "__main__":
    unittest.main()
