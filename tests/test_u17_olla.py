"""U17: olla — 파일럿 밖에서 로컬 모델을 부려 쓰는 공용 명령.

파일럿의 게이트가 없으므로, 명령 자체가 지켜야 하는 것을 시험한다.
- 편집 전 백업, 적용 전 diff
- 모델 출력이 형식을 벗어나면 원본 무변경
- 현재 프로젝트 밖 파일은 거부
- dry-run 은 아무것도 바꾸지 않음
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from v7_harness import olla


class OllaEditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        self.root.mkdir()
        (self.root / "config.py").write_text("TIMEOUT_S = 30\nRETRIES = 3\n", encoding="utf-8")
        self.cwd = os.getcwd()
        os.chdir(self.root)

    def tearDown(self) -> None:
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def _edit(self, reply: str, *extra: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(olla.worker, "_generate", return_value=(reply, {"input_tokens": 5, "output_tokens": 5})):
            with redirect_stdout(out), redirect_stderr(err):
                code = olla.main(["edit", "set TIMEOUT_S to 90", "-f", "config.py", *extra])
        return code, out.getvalue(), err.getvalue()

    def test_edit_applies_backs_up_and_prints_a_diff(self) -> None:
        code, out, err = self._edit("===FILE: config.py===\nTIMEOUT_S = 90\nRETRIES = 3")
        self.assertEqual(0, code)
        self.assertIn("-TIMEOUT_S = 30", out)
        self.assertIn("+TIMEOUT_S = 90", out)
        self.assertEqual("TIMEOUT_S = 90\nRETRIES = 3\n", (self.root / "config.py").read_text(encoding="utf-8"))
        backups = list((self.root / ".work").glob("backup_olla_*/config.py"))
        self.assertEqual(1, len(backups))
        self.assertEqual("TIMEOUT_S = 30\nRETRIES = 3\n", backups[0].read_text(encoding="utf-8"))

    def test_dry_run_changes_nothing(self) -> None:
        code, out, _ = self._edit("===FILE: config.py===\nTIMEOUT_S = 90\nRETRIES = 3", "--dry-run")
        self.assertEqual(0, code)
        self.assertIn("+TIMEOUT_S = 90", out)
        self.assertEqual("TIMEOUT_S = 30\nRETRIES = 3\n", (self.root / "config.py").read_text(encoding="utf-8"))
        self.assertEqual([], list((self.root / ".work").glob("backup_olla_*")))

    def test_chatty_output_leaves_the_file_untouched(self) -> None:
        code, _, err = self._edit("Sure! I set it to 90.")
        self.assertEqual(3, code)
        self.assertIn("changed nothing", err)
        self.assertEqual("TIMEOUT_S = 30\nRETRIES = 3\n", (self.root / "config.py").read_text(encoding="utf-8"))

    def test_bad_search_block_leaves_the_file_untouched(self) -> None:
        code, _, err = self._edit("===EDIT: config.py===\n<<<<<<< SEARCH\nNOPE\n=======\nX\n>>>>>>> REPLACE")
        self.assertEqual(3, code)
        self.assertIn("rejected", err)
        self.assertEqual("TIMEOUT_S = 30\nRETRIES = 3\n", (self.root / "config.py").read_text(encoding="utf-8"))

    def test_files_outside_the_project_are_refused(self) -> None:
        outside = Path(self.tmp.name) / "other.py"
        outside.write_text("x = 1\n", encoding="utf-8")
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            code = olla.main(["edit", "change x", "-f", str(outside)])
        self.assertEqual(2, code)
        self.assertIn("outside", err.getvalue())
        self.assertEqual("x = 1\n", outside.read_text(encoding="utf-8"))

    def test_no_scratch_directory_is_left_behind(self) -> None:
        self._edit("===FILE: config.py===\nTIMEOUT_S = 90\nRETRIES = 3")
        self.assertEqual([], list((self.root / ".work").glob("olla_scratch_*")))


class OllaAskAndStatusTests(unittest.TestCase):
    def test_ask_prints_the_answer(self) -> None:
        out = io.StringIO()
        with mock.patch.object(olla.worker, "_generate", return_value=("요약입니다", {"input_tokens": 3, "output_tokens": 2})):
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                code = olla.main(["ask", "한 줄로 요약해"])
        self.assertEqual(0, code)
        self.assertEqual("요약입니다", out.getvalue().strip())

    def test_ask_reports_a_down_server(self) -> None:
        err = io.StringIO()
        with mock.patch.object(olla.worker, "_generate", side_effect=OSError("refused")):
            with redirect_stdout(io.StringIO()), redirect_stderr(err):
                code = olla.main(["ask", "x"])
        self.assertEqual(1, code)
        self.assertIn("unreachable", err.getvalue())

    def test_status_reports_a_down_server(self) -> None:
        out = io.StringIO()
        with mock.patch.object(olla, "_get", side_effect=OSError("refused")):
            with redirect_stdout(out):
                code = olla.main(["status"])
        self.assertEqual(1, code)
        self.assertIn('"ok": false', out.getvalue())


class OllaBudgetTests(unittest.TestCase):
    """토큰 0 활용: 추정, 경로 결정, 요약본."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.big = self.base / "big.py"
        self.big.write_text("x = 1\n" * 4000, encoding="utf-8")
        # Windows 는 줄바꿈을 \r\n 으로 저장한다. 기대값은 실제 파일 크기에서 계산한다.
        self.big_tokens = round(self.big.stat().st_size / olla.BYTES_PER_TOKEN)
        self.small = self.base / "small.py"
        self.small.write_text("x = 1\n", encoding="utf-8")
        # 요약본 캐시는 시험마다 비운 임시 폴더로 — 실제 사용자 캐시를 건드리지 않는다
        cache = mock.patch.object(olla, "DIGEST_CACHE_DIR", self.base / "cache")
        cache.start()
        self.addCleanup(cache.stop)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_digest_cache_skips_the_model_until_the_file_changes(self) -> None:
        calls = []

        def fake(model, prompt, timeout):
            calls.append(prompt)
            return ("- L1-300: x", {"input_tokens": 1, "output_tokens": 1})

        def run() -> str:
            err = io.StringIO()
            with mock.patch.object(olla.worker, "_generate", side_effect=fake):
                with redirect_stdout(io.StringIO()), redirect_stderr(err):
                    self.assertEqual(0, olla.main(["digest", "-f", str(self.small), "--focus", "q"]))
            return err.getvalue()

        self.assertIn('"cached": false', run())
        self.assertIn('"cached": true', run())
        self.assertEqual(1, len(calls))
        self.small.write_text("y = 2\n", encoding="utf-8")
        self.assertIn('"cached": false', run())
        self.assertEqual(2, len(calls))

    def test_estimate_counts_rereads(self) -> None:
        cost = olla.estimate_tokens([str(self.big)])
        self.assertEqual(self.big_tokens, cost["read_once"])
        self.assertEqual(self.big_tokens * (1 + olla.REREAD_TURNS), cost["with_rereads"])

    def test_large_read_goes_through_a_local_digest(self) -> None:
        decision = olla.decide_route("이 파일 구조를 설명해줘", [str(self.big)])
        self.assertEqual("local-digest-then-self", decision["route"])
        self.assertGreater(decision["tokens_saved_estimate"], 0)

    def test_specific_edit_goes_local(self) -> None:
        decision = olla.decide_route("In `config.py`, change TIMEOUT_S from 30 to 90.", [])
        self.assertEqual("local-edit", decision["route"])

    def test_small_judgement_task_stays_with_the_paid_model(self) -> None:
        decision = olla.decide_route("이 모듈 설계를 어떻게 바꿀지 판단해줘", [str(self.small)])
        self.assertEqual("self", decision["route"])
        self.assertEqual(0, decision["tokens_saved_estimate"])

    def test_draft_task_goes_local_answer(self) -> None:
        decision = olla.decide_route("write a commit message for this change", [str(self.small)])
        self.assertEqual("local-answer", decision["route"])

    def test_digest_keeps_line_anchors_per_chunk(self) -> None:
        calls = []

        def fake(model, prompt, timeout):
            calls.append(prompt)
            return ("- L1-10: assignments", {"input_tokens": 10, "output_tokens": 3})

        with mock.patch.object(olla.worker, "_generate", side_effect=fake):
            digest, usage = olla.digest_file(self.big, "x", "m", 60)
        # 4,000줄 → 300줄씩 14조각, 조각마다 줄 번호가 붙어 넘어간다
        self.assertEqual(14, len(calls))
        self.assertIn("\n1: x = 1", calls[0])
        self.assertIn("\n301: x = 1", calls[1])
        self.assertTrue(digest.startswith("# digest:"))
        self.assertEqual(140, usage["input_tokens"])

    def test_digest_cli_reports_savings(self) -> None:
        err = io.StringIO()
        with mock.patch.object(olla.worker, "_generate", return_value=("- L1-300: x", {"input_tokens": 1, "output_tokens": 1})):
            with redirect_stdout(io.StringIO()), redirect_stderr(err):
                code = olla.main(["digest", "-f", str(self.big)])
        self.assertEqual(0, code)
        report = err.getvalue()
        self.assertIn("saved_pct", report)
        self.assertIn(f'"paid_tokens_if_read": {self.big_tokens}', report)


class OllaReadHookTests(unittest.TestCase):
    """Read 직전 훅: 큰 파일만 알리고, 무슨 입력이 와도 막지 않는다."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.big = Path(self.tmp.name) / "big.py"
        self.big.write_text("x = 1\n" * 4000, encoding="utf-8")
        self.small = Path(self.tmp.name) / "small.py"
        self.small.write_text("x = 1\n", encoding="utf-8")

    def _hook(self, stdin: str) -> tuple[int, str]:
        out = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(stdin)), redirect_stdout(out):
            code = olla.main(["hook-read"])
        return code, out.getvalue()

    def test_large_whole_file_read_gets_a_digest_hint(self) -> None:
        code, out = self._hook(json.dumps({"tool_name": "Read", "tool_input": {"file_path": str(self.big)}}))
        self.assertEqual(0, code)
        payload = json.loads(out)
        self.assertEqual("PreToolUse", payload["hookSpecificOutput"]["hookEventName"])
        self.assertIn("olla digest", payload["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("permissionDecision", payload["hookSpecificOutput"])

    def test_small_or_targeted_reads_stay_silent(self) -> None:
        for tool_input in ({"file_path": str(self.small)}, {"file_path": str(self.big), "offset": 100, "limit": 40}):
            code, out = self._hook(json.dumps({"tool_input": tool_input}))
            self.assertEqual((0, ""), (code, out))

    def test_garbage_input_never_blocks(self) -> None:
        for stdin in ("", "not json", "[]", json.dumps({"tool_input": {"file_path": "Z:/missing.py"}})):
            self.assertEqual((0, ""), self._hook(stdin))


class OllaShellHookTests(unittest.TestCase):
    """Codex 읽은 직후 훅: 셸로 큰 파일을 통째로 출력했을 때만 알리고, 막지 않는다."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        (self.base / "big.py").write_text("x = 1\n" * 4000, encoding="utf-8")
        (self.base / "small.py").write_text("x = 1\n", encoding="utf-8")

    def _hook(self, command, cwd=None) -> tuple[int, str]:
        event = {"hook_event_name": "PostToolUse", "tool_name": "Bash",
                 "cwd": str(cwd or self.base), "tool_input": {"command": command}}
        out = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(json.dumps(event))), redirect_stdout(out):
            code = olla.main(["hook-shell"])
        return code, out.getvalue()

    def test_whole_file_dumps_get_a_digest_hint(self) -> None:
        for command in ("cat big.py", "Get-Content big.py", "cd x && type big.py", f'cat "{self.base / "big.py"}"'):
            code, out = self._hook(command)
            self.assertEqual(0, code, command)
            payload = json.loads(out)["hookSpecificOutput"]
            self.assertEqual("PostToolUse", payload["hookEventName"])
            self.assertIn("olla digest", payload["additionalContext"], command)

    def test_ranged_piped_or_small_reads_stay_silent(self) -> None:
        for command in ("cat small.py", "sed -n '1,40p' big.py", "cat big.py | head -40",
                        "Get-Content big.py -TotalCount 40", "grep -n def big.py", "cat missing.py"):
            self.assertEqual((0, ""), self._hook(command), command)

    def test_argv_list_commands_are_read_too(self) -> None:
        for command in (["cat", "big.py"], ["powershell.exe", "-Command", "Get-Content big.py"], ["bash", "-lc", "cat big.py"],
                        ["powershell.exe", "-NoProfile", "-Command", "Get-Content big.py"],
                        'powershell -NoProfile -Command "Get-Content big.py"'):
            code, out = self._hook(command)
            self.assertEqual(0, code)
            self.assertIn("olla digest", out, command)

    def test_garbage_input_never_blocks(self) -> None:
        for stdin in ("", "not json", "[]", '{"tool_input": {"command": "cat \\"unterminated"}}'):
            out = io.StringIO()
            with mock.patch("sys.stdin", io.StringIO(stdin)), redirect_stdout(out):
                self.assertEqual(0, olla.main(["hook-shell"]))
            self.assertEqual("", out.getvalue())


class OllaFindTests(unittest.TestCase):
    def test_ranks_files_by_similarity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "cache.md").write_text("캐시 만료 정책", encoding="utf-8")
            (base / "auth.md").write_text("로그인 토큰 갱신", encoding="utf-8")
            def fake_embed(texts):
                # 파일을 읽는 순서와 무관하게 내용으로 벡터를 정한다. "캐시"가 든 글은 질문과 같은 방향.
                return [[1.0, 0.0] if "캐시" in text else [0.0, 1.0] for text in texts]

            out = io.StringIO()
            with mock.patch.object(olla, "_embed", side_effect=fake_embed):
                with redirect_stdout(out):
                    code = olla.main(["find", "캐시", "-d", str(base)])
            self.assertEqual(0, code)
            lines = out.getvalue().splitlines()
            self.assertTrue(lines[0].endswith("cache.md"))
            self.assertTrue(lines[1].endswith("auth.md"))


if __name__ == "__main__":
    unittest.main()
