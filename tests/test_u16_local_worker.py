"""U16: 로컬 Ollama 작업자 어댑터.

이 작업자는 약한 모델이다. 그래서 "무엇을 못 하게 막는가"를 시험한다.
작업공간 밖 쓰기, 형식 이탈, 서버 부재는 모두 실패로 끝나야 한다.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from v7_harness.adapters import ollama_worker
from v7_harness.cli import resolve_worker_command


class LocalWorkerCommandTests(unittest.TestCase):
    def test_default_worker_is_the_remote_one(self) -> None:
        self.assertEqual(["agy"], resolve_worker_command("agy", None))

    def test_local_worker_points_at_the_adapter(self) -> None:
        command = resolve_worker_command("local", None)
        self.assertEqual(2, len(command))  # [파이썬, 어댑터 경로]
        self.assertTrue(command[0].lower().endswith(("python", "python.exe", "python3", "python3.exe")))
        self.assertTrue(command[1].endswith("ollama_worker.py"))
        self.assertTrue(Path(command[1]).is_file())

    def test_explicit_command_wins(self) -> None:
        self.assertEqual(["python", "x.py"], resolve_worker_command("local", ["python", "x.py"]))


class LocalWorkerBehaviourTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name) / "stage"
        self.workspace.mkdir()
        (self.workspace / "VERSION").write_text("1.0.0\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self, model_reply: str, prompt: str = "Rewrite `VERSION`.") -> dict:
        buffer = io.StringIO()
        with mock.patch.object(ollama_worker, "_generate", return_value=(model_reply, {"input_tokens": 10, "output_tokens": 5})):
            with redirect_stdout(buffer):
                ollama_worker.main(["-p", prompt, "--add-dir", str(self.workspace), "--print-timeout", "60s"])
        return json.loads(buffer.getvalue())

    def test_file_block_is_written(self) -> None:
        payload = self._run("===FILE: VERSION===\n2.0.0")
        self.assertEqual("SUCCESS", payload["status"])
        self.assertEqual("2.0.0\n", (self.workspace / "VERSION").read_text(encoding="utf-8"))

    def test_chatty_reply_without_a_block_fails(self) -> None:
        payload = self._run("Sure! I changed VERSION to 2.0.0 for you.")
        self.assertEqual("ERROR", payload["status"])
        self.assertEqual("1.0.0\n", (self.workspace / "VERSION").read_text(encoding="utf-8"))

    def test_path_escape_is_refused(self) -> None:
        payload = self._run("===FILE: ../outside.txt===\nowned")
        self.assertEqual("ERROR", payload["status"])
        self.assertTrue(payload["error"].startswith("PATH_ESCAPE"))
        self.assertFalse((Path(self.tmp.name) / "outside.txt").exists())

    def test_unknown_directory_is_refused(self) -> None:
        payload = self._run("===FILE: nope/deep/file.txt===\nx")
        self.assertEqual("ERROR", payload["status"])
        self.assertTrue(payload["error"].startswith("UNKNOWN_DIR"))

    def test_server_down_is_reported_not_silently_passed(self) -> None:
        buffer = io.StringIO()
        with mock.patch.object(ollama_worker, "_generate", side_effect=OSError("connection refused")):
            with redirect_stdout(buffer):
                code = ollama_worker.main(["-p", "x", "--add-dir", str(self.workspace), "--print-timeout", "60s"])
        payload = json.loads(buffer.getvalue())
        self.assertEqual(1, code)
        self.assertEqual("ERROR", payload["status"])
        self.assertIn("ollama unreachable", payload["error"])

    def test_edit_block_replaces_exactly_one_occurrence(self) -> None:
        (self.workspace / "big.py").write_text("TIMEOUT_S = 30\nA = 1\nB = 2\n", encoding="utf-8")
        payload = self._run(
            "===EDIT: big.py===\n<<<<<<< SEARCH\nTIMEOUT_S = 30\n=======\nTIMEOUT_S = 90\n>>>>>>> REPLACE",
            prompt="In `big.py`, change TIMEOUT_S.",
        )
        self.assertEqual("SUCCESS", payload["status"])
        self.assertEqual("TIMEOUT_S = 90\nA = 1\nB = 2\n", (self.workspace / "big.py").read_text(encoding="utf-8"))

    def test_edit_search_not_found_changes_nothing(self) -> None:
        (self.workspace / "big.py").write_text("TIMEOUT_S = 30\n", encoding="utf-8")
        payload = self._run("===EDIT: big.py===\n<<<<<<< SEARCH\nTIMEOUT = 30\n=======\nTIMEOUT = 90\n>>>>>>> REPLACE")
        self.assertEqual("ERROR", payload["status"])
        self.assertTrue(payload["error"].startswith("EDIT_SEARCH_NOT_FOUND"))
        self.assertEqual("TIMEOUT_S = 30\n", (self.workspace / "big.py").read_text(encoding="utf-8"))

    def test_ambiguous_edit_is_refused(self) -> None:
        (self.workspace / "big.py").write_text("x = 1\nx = 1\n", encoding="utf-8")
        payload = self._run("===EDIT: big.py===\n<<<<<<< SEARCH\nx = 1\n=======\nx = 2\n>>>>>>> REPLACE")
        self.assertEqual("ERROR", payload["status"])
        self.assertTrue(payload["error"].startswith("EDIT_SEARCH_AMBIGUOUS"))
        self.assertEqual("x = 1\nx = 1\n", (self.workspace / "big.py").read_text(encoding="utf-8"))

    def test_one_bad_edit_blocks_every_edit(self) -> None:
        (self.workspace / "a.py").write_text("A = 1\n", encoding="utf-8")
        (self.workspace / "b.py").write_text("B = 1\n", encoding="utf-8")
        payload = self._run(
            "===EDIT: a.py===\n<<<<<<< SEARCH\nA = 1\n=======\nA = 2\n>>>>>>> REPLACE\n"
            "===EDIT: b.py===\n<<<<<<< SEARCH\nNOPE\n=======\nB = 2\n>>>>>>> REPLACE"
        )
        self.assertEqual("ERROR", payload["status"])
        # 첫 편집은 맞았지만 둘째가 틀렸으므로 어느 파일도 바뀌면 안 된다.
        self.assertEqual("A = 1\n", (self.workspace / "a.py").read_text(encoding="utf-8"))
        self.assertEqual("B = 1\n", (self.workspace / "b.py").read_text(encoding="utf-8"))

    def test_envelope_matches_what_the_pilot_expects(self) -> None:
        payload = self._run("===FILE: VERSION===\n2.0.0")
        for key in ("status", "response", "usage", "conversation_id"):
            self.assertIn(key, payload)
        self.assertIsInstance(payload["usage"]["input_tokens"], int)
        self.assertIsInstance(payload["usage"]["output_tokens"], int)


if __name__ == "__main__":
    unittest.main()
