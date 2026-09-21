"""U17: olla — 파일럿 밖에서 로컬 모델을 부려 쓰는 공용 명령.

파일럿의 게이트가 없으므로, 명령 자체가 지켜야 하는 것을 시험한다.
- 편집 전 백업, 적용 전 diff
- 모델 출력이 형식을 벗어나면 원본 무변경
- 현재 프로젝트 밖 파일은 거부
- dry-run 은 아무것도 바꾸지 않음
"""

from __future__ import annotations

import io
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
