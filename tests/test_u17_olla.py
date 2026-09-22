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

# 사용 기록은 실제 사용자 파일(~/.cache/olla/usage.jsonl)을 오염시키면 안 된다(한 번 21줄 섞였다).
_USAGE_TMP = tempfile.TemporaryDirectory()
_USAGE_PATCH = mock.patch.object(olla, "USAGE_LOG", Path(_USAGE_TMP.name) / "usage.jsonl")


_CACHE_PATCH = mock.patch.object(olla, "DIGEST_CACHE_DIR", Path(_USAGE_TMP.name) / "digest")
# 읽기 훅은 서버가 살아 있으면 실제 요약 작업을 뒤에서 띄운다. 시험 중에는 꺼진 것으로 둔다.
_SERVER_PATCH = mock.patch.object(olla, "_server_up", return_value=False)


def setUpModule() -> None:
    _USAGE_PATCH.start()
    _CACHE_PATCH.start()
    _SERVER_PATCH.start()


def tearDownModule() -> None:
    _SERVER_PATCH.stop()
    _CACHE_PATCH.stop()
    _USAGE_PATCH.stop()
    _USAGE_TMP.cleanup()


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

    def _ask_ko(self, replies: list[str]) -> tuple[int, str, str, list[str]]:
        prompts: list[str] = []

        def fake(model, prompt, timeout):
            prompts.append(prompt)
            return replies[len(prompts) - 1], {"input_tokens": 1, "output_tokens": 1}

        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(olla.worker, "_generate", side_effect=fake):
            with redirect_stdout(out), redirect_stderr(err):
                code = olla.main(["ask", "커밋 제목 한 줄", "--ko"])
        return code, out.getvalue().strip(), err.getvalue(), prompts

    def test_ko_wraps_the_request_in_korean_rules(self) -> None:
        code, out, _, prompts = self._ask_ko(["feat(olla): 캐시 추가"])
        self.assertEqual((0, "feat(olla): 캐시 추가"), (code, out))
        self.assertTrue(prompts[0].startswith(olla.KO_RULES))
        self.assertEqual(1, len(prompts))

    def test_ko_retries_once_when_the_answer_is_english(self) -> None:
        code, out, err, prompts = self._ask_ko(["feat(olla): add cache", "feat(olla): 캐시 추가"])
        self.assertEqual((0, "feat(olla): 캐시 추가"), (code, out))
        self.assertEqual(2, len(prompts))
        self.assertIn('"attempts": 2', err)

    def test_ko_gives_up_with_code_4_so_the_caller_writes_it(self) -> None:
        code, _, err, _ = self._ask_ko(["add cache", "still english"])
        self.assertEqual(4, code)
        self.assertIn("write it yourself", err)

    def test_ask_refuses_an_empty_input_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "input.md"
            empty.write_text("  \n", encoding="utf-8")
            err = io.StringIO()
            with mock.patch.object(olla.worker, "_generate") as generate:
                with redirect_stdout(io.StringIO()), redirect_stderr(err):
                    code = olla.main(["ask", "summarize", "-f", str(empty)])
        self.assertEqual(2, code)
        self.assertIn("empty input file", err.getvalue())
        generate.assert_not_called()

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
        self.assertIn("offset/limit", payload["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("permissionDecision", payload["hookSpecificOutput"])

    def test_cached_digest_is_handed_over_inline(self) -> None:
        cache = olla._digest_cache_path(self.big, "", olla.CHAT_MODEL)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"path": "x", "digest": "- L1-300: assignments"}), encoding="utf-8")
        self.addCleanup(cache.unlink)
        _, out = self._hook(json.dumps({"tool_input": {"file_path": str(self.big)}}))
        context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("- L1-300: assignments", context)
        self.assertIn("cached, 0 paid tokens", context)

    def test_uncached_digest_is_prewarmed_once(self) -> None:
        with mock.patch.object(olla, "_server_up", return_value=True), \
                mock.patch("subprocess.Popen") as popen:
            _, first = self._hook(json.dumps({"tool_input": {"file_path": str(self.big)}}))
            _, second = self._hook(json.dumps({"tool_input": {"file_path": str(self.big)}}))
        self.assertEqual(1, popen.call_count)  # 두 번째는 만드는 중 표식 때문에 다시 띄우지 않음
        self.assertIn("digest", popen.call_args.args[0])
        self.assertIn("background", first)
        self.assertNotIn("background", second)
        olla._digest_cache_path(self.big, "", olla.CHAT_MODEL).with_suffix(".pending").unlink()

    def test_korean_path_through_real_stdin_bytes(self) -> None:
        # StringIO 모의로는 못 잡는다. 실제 프로세스에 UTF-8 바이트로 넣어야 cp949 오독이 드러난다.
        import subprocess
        import sys as _sys

        folder = Path(self.tmp.name) / "한글폴더"
        folder.mkdir()
        target = folder / "큰파일.py"
        target.write_text("x = 1\n" * 4000, encoding="utf-8")
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONPATH=str(root), OLLA_USAGE=str(Path(self.tmp.name) / "u.jsonl"),
                   OLLA_CACHE=str(Path(self.tmp.name) / "cache"), OLLAMA_HOST="http://127.0.0.1:9")
        env.pop("PYTHONIOENCODING", None)
        env.pop("PYTHONUTF8", None)
        done = subprocess.run([_sys.executable, "-m", "v7_harness.olla", "hook-read"], cwd=root, env=env,
                              input=json.dumps({"tool_input": {"file_path": str(target)}}, ensure_ascii=False).encode("utf-8"),
                              capture_output=True, timeout=60)
        self.assertEqual(0, done.returncode)
        self.assertIn("tokens", done.stdout.decode("utf-8"))

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
            self.assertIn("tokens", payload["additionalContext"], command)

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
            self.assertIn("tokens", out, command)

    def test_garbage_input_never_blocks(self) -> None:
        for stdin in ("", "not json", "[]", '{"tool_input": {"command": "cat \\"unterminated"}}'):
            out = io.StringIO()
            with mock.patch("sys.stdin", io.StringIO(stdin)), redirect_stdout(out):
                self.assertEqual(0, olla.main(["hook-shell"]))
            self.assertEqual("", out.getvalue())


class OllaPlanHookTests(unittest.TestCase):
    """작업 시작 훅: 서버가 살아 있을 때만 분업 한 줄을 넣고, 막지 않는다."""

    def _hook(self, stdin: str, up: bool) -> tuple[int, str]:
        out = io.StringIO()
        with mock.patch.object(olla, "_server_up", return_value=up), \
                mock.patch("sys.stdin", io.StringIO(stdin)), redirect_stdout(out):
            code = olla.main(["hook-plan"])
        return code, out.getvalue()

    def test_task_prompt_gets_the_split_reminder(self) -> None:
        code, out = self._hook(json.dumps({"prompt": "니가 할 수 있는 일을 찾아봐"}), up=True)
        self.assertEqual(0, code)
        payload = json.loads(out)["hookSpecificOutput"]
        self.assertEqual("UserPromptSubmit", payload["hookEventName"])
        self.assertIn("olla ask", payload["additionalContext"])
        self.assertIn("English prompt", payload["additionalContext"])

    def test_silent_when_the_server_is_down_or_input_is_garbage(self) -> None:
        self.assertEqual((0, ""), self._hook(json.dumps({"prompt": "x"}), up=False))
        for stdin in ("not json", "[]"):
            self.assertEqual((0, ""), self._hook(stdin, up=True))


class OllaUsageLogTests(unittest.TestCase):
    """실제 세션 절감을 재기 위한 기록: 병렬로 써도 줄을 잃지 않고, 집계가 맞는다."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patch = mock.patch.object(olla, "USAGE_LOG", Path(self.tmp.name) / "usage.jsonl")
        patch.start()
        self.addCleanup(patch.stop)

    def test_parallel_writers_lose_no_lines(self) -> None:
        # 스레드는 한 프로세스 안 잠금으로 직렬화되므로, 세 도구처럼 별도 프로세스 4개로 동시에 쓴다.
        import subprocess
        import sys as _sys

        root = Path(__file__).resolve().parents[1]
        code = ("import sys;from pathlib import Path;from v7_harness import olla;"
                "olla.USAGE_LOG=Path(sys.argv[1]);[olla.log_usage('ask',w=int(sys.argv[2]),n=i) for i in range(50)]")
        env = dict(os.environ, PYTHONPATH=str(root))
        procs = [subprocess.Popen([_sys.executable, "-c", code, str(olla.USAGE_LOG), str(w)], env=env, cwd=root)
                 for w in range(4)]
        self.assertEqual([0, 0, 0, 0], [p.wait(timeout=60) for p in procs])
        lines = olla.USAGE_LOG.read_text(encoding="utf-8").splitlines()
        self.assertEqual(200, len(lines))
        self.assertEqual({(w, n) for w in range(4) for n in range(50)},
                         {(json.loads(line)["w"], json.loads(line)["n"]) for line in lines})

    def test_stats_counts_savings_and_followed_hints(self) -> None:
        lines = [json.dumps(r) for r in (
            {"ts": "2026-09-22T10:00:00", "event": "hint_read", "caller": "claude", "file": "a.py"},
            {"ts": "2026-09-22T10:01:00", "event": "digest", "caller": "claude", "file": "a.py",
             "paid_tokens_if_read": 10000, "paid_tokens_digest": 800, "cached": False},
            {"ts": "2026-09-22T10:30:00", "event": "hint_read", "caller": "claude", "file": "b.py"},
            {"ts": "2026-09-22T10:31:00", "event": "digest", "caller": "codex", "file": "c.py",
             "paid_tokens_if_read": 5000, "paid_tokens_digest": 400, "cached": True},
        )] + ["not json"]
        stats = olla.usage_stats(lines)
        claude, codex = stats["by_caller"]["claude"], stats["by_caller"]["codex"]
        self.assertEqual((2, 1, 9200), (claude["hint_read"], claude["hint_read_followed"], claude["paid_tokens_saved"]))
        self.assertEqual((1, 1, 4600), (codex["digest"], codex["digest_cached"], codex["paid_tokens_saved"]))

    def test_logging_failure_never_breaks_the_command(self) -> None:
        with mock.patch.object(olla, "USAGE_LOG", Path(self.tmp.name) / "missing_dir_is_file"):
            (Path(self.tmp.name) / "missing_dir_is_file").mkdir()
            olla.log_usage("ask")  # 디렉터리에 append 실패 — 예외 없이 지나가야 한다


class OllaTurnShapeTests(unittest.TestCase):
    """Stop 훅: 진행 설명 수와 최종 보고 길이를 두 도구 기록 형식에서 모두 잰다."""

    def _write(self, rows: list[dict]) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "t.jsonl"
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
        return path

    def test_claude_transcript(self) -> None:
        path = self._write([
            {"type": "user", "message": {"content": "이전 지시"}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "옛 보고"}]}},
            {"type": "user", "message": {"content": "새 지시"}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "진행 설명"}, {"type": "tool_use"}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result"}]}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "결과 1\n결과 2"}]}},
        ])
        self.assertEqual({"narration_blocks": 1, "final_lines": 2, "final_chars": 9, "nested_lines": 0}, olla.turn_shape(path))

    def test_codex_rollout(self) -> None:
        msg = lambda t: {"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [{"text": t}]}}
        path = self._write([{"type": "event_msg", "payload": {"type": "task_started"}}, msg("a"), msg("b"), msg("끝")])
        self.assertEqual(2, olla.turn_shape(path)["narration_blocks"])

    def test_stats_counts_turns_within_rule(self) -> None:
        lines = [json.dumps({"ts": "2026-09-22T10:00:00", "event": "turn_shape", "caller": "claude", **shape}) for shape in (
            {"narration_blocks": 0, "final_lines": 3}, {"narration_blocks": 2, "final_lines": 3}, {"narration_blocks": 0, "final_lines": 7})]
        row = olla.usage_stats(lines)["by_caller"]["claude"]
        self.assertEqual((3, 1), (row["turns"], row["turns_within_rule"]))

    def _stop(self, lines: int, active: bool) -> str:
        path = self._write([{"type": "user", "message": {"content": "지시"}},
                            {"type": "assistant", "message": {"content": [{"type": "text", "text": "\n".join(["줄"] * lines)}]}}])
        out = io.StringIO()
        event = {"transcript_path": str(path), "stop_hook_active": active}
        with mock.patch("sys.stdin", io.StringIO(json.dumps(event))), redirect_stdout(out):
            self.assertEqual(0, olla.main(["hook-stop"]))
        return out.getvalue()

    def test_nested_or_wordy_report_is_sent_back(self) -> None:
        for text in ("**결과**: x\n- 근거:\n  - a\n  - b", "**결과**: " + "가" * (olla.REPORT_MAX_CHARS + 1)):
            path = self._write([{"type": "user", "message": {"content": "지시"}},
                                {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}])
            out = io.StringIO()
            with mock.patch("sys.stdin", io.StringIO(json.dumps({"transcript_path": str(path)}))), redirect_stdout(out):
                olla.main(["hook-stop"])
            self.assertEqual("block", json.loads(out.getvalue())["decision"], text[:20])

    def test_long_report_is_sent_back_once(self) -> None:
        self.assertEqual("block", json.loads(self._stop(olla.REPORT_MAX_LINES + 3, active=False))["decision"])
        self.assertEqual("", self._stop(olla.REPORT_MAX_LINES + 3, active=True))  # 두 번째는 막지 않음
        self.assertEqual("", self._stop(olla.REPORT_MAX_LINES, active=False))

    def test_hook_never_blocks(self) -> None:
        for stdin in ("", "x", json.dumps({"transcript_path": "Z:/none.jsonl"})):
            out = io.StringIO()
            with mock.patch("sys.stdin", io.StringIO(stdin)), redirect_stdout(out):
                self.assertEqual(0, olla.main(["hook-stop"]))
            self.assertEqual("", out.getvalue())


class OllaRecurringFailureGuardTests(unittest.TestCase):
    """반복 오류 차단: 세션 성적 되비춤, 260자 한도에 가까운 cd 거부."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patch = mock.patch.object(olla, "USAGE_LOG", Path(self.tmp.name) / "usage.jsonl")
        patch.start()
        self.addCleanup(patch.stop)

    def test_scorecard_reports_only_this_session(self) -> None:
        rows = [
            {"event": "hint_read", "session": "s1"}, {"event": "digest", "session": "s1"},
            {"event": "turn_shape", "session": "s1", "narration_blocks": 0, "final_lines": 9},
            {"event": "turn_shape", "session": "s1", "narration_blocks": 0, "final_lines": 3, "final_chars": 100},
            {"event": "ask", "session": "other"},
        ]
        olla.USAGE_LOG.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        card = olla.session_scorecard("s1")
        self.assertIn("olla used 1x", card)
        self.assertIn("big-read hints 1", card)
        self.assertIn("output rule 1/2", card)
        self.assertEqual("", olla.session_scorecard("nobody"))

    def test_plan_hint_carries_the_scorecard(self) -> None:
        olla.USAGE_LOG.write_text(json.dumps({"event": "hint_read", "session": "s9"}), encoding="utf-8")
        out = io.StringIO()
        with mock.patch.object(olla, "_server_up", return_value=True), \
                mock.patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": "s9"}), \
                mock.patch("sys.stdin", io.StringIO("{}")), redirect_stdout(out):
            olla.main(["hook-plan"])
        self.assertIn("This session so far", json.loads(out.getvalue())["hookSpecificOutput"]["additionalContext"])

    def _bash(self, command: str, cwd: str) -> str:
        out = io.StringIO()
        event = {"tool_input": {"command": command}, "cwd": cwd}
        with mock.patch("sys.stdin", io.StringIO(json.dumps(event))), redirect_stdout(out):
            self.assertEqual(0, olla.main(["hook-bash"]))
        return out.getvalue()

    def test_deep_cd_is_denied_shallow_is_allowed(self) -> None:
        deep = "D:/" + "a" * olla.CWD_MAX_CHARS
        payload = json.loads(self._bash(f'cd "{deep}" && ls', "D:/proj"))["hookSpecificOutput"]
        self.assertEqual("deny", payload["permissionDecision"])
        self.assertEqual("", self._bash("cd src && ls", "D:/proj"))
        self.assertEqual("", self._bash("git status", "D:/" + "a" * 250))
        self.assertEqual("", self._bash("", ""))


class OllaAntigravityHookTests(unittest.TestCase):
    """Antigravity 형식: 입력·출력 모양이 달라 어댑터로 옮긴다. 승인을 대신 내주지 않는다."""

    def test_pre_invocation_injects_once_per_turn(self) -> None:
        with mock.patch.object(olla, "_server_up", return_value=True):
            first = olla.agy_hook("PreInvocation", {"invocationNum": 0, "conversationId": "c1"})
            later = olla.agy_hook("PreInvocation", {"invocationNum": 3})
        self.assertIn("olla", first["injectSteps"][0]["ephemeralMessage"])
        self.assertIsNone(later)

    def test_pre_tool_use_denies_only_deep_cd_and_never_allows(self) -> None:
        deep = "D:/" + "a" * olla.CWD_MAX_CHARS
        denied = olla.agy_hook("PreToolUse", {"toolCall": {"name": "run_command", "args": {"CommandLine": f"cd {deep}", "Cwd": "D:/p"}}})
        self.assertEqual("deny", denied["decision"])
        self.assertIsNone(olla.agy_hook("PreToolUse", {"toolCall": {"name": "run_command", "args": {"CommandLine": "git status"}}}))
        self.assertIsNone(olla.agy_hook("PreToolUse", {"toolCall": {"name": "view_file", "args": {"AbsolutePath": "x"}}}))

    def test_stop_sends_a_long_report_back_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.jsonl"
            path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in (
                {"type": "user", "message": {"content": "x"}},
                {"type": "assistant", "message": {"content": [{"type": "text", "text": "\n".join(["줄"] * 9)}]}})), encoding="utf-8")
            with mock.patch.object(olla, "USAGE_LOG", Path(tmp) / "u.jsonl"):
                first = olla.agy_hook("Stop", {"transcriptPath": str(path), "executionNum": 0})
                again = olla.agy_hook("Stop", {"transcriptPath": str(path), "executionNum": 1})
        self.assertEqual("continue", first["decision"])
        self.assertIsNone(again)


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
