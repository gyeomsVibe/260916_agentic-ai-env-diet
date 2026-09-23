"""U22: 로컬 작업자 출력 상한·과대 프롬프트 즉시 실패·자리표시자 무시, 관문 --install."""

import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from v7_harness import calculator_gate as g
from v7_harness.adapters import ollama_worker as w


class OllamaWorkerLimitsTest(unittest.TestCase):
    def test_num_predict_in_payload(self):
        class R:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                return False

            def read(self):
                return json.dumps({"response": "x", "prompt_eval_count": 1, "eval_count": 1}).encode()

        stored = {}

        def fake_urlopen(req, timeout=None):
            stored.update(json.loads(req.data.decode()))
            return R()

        with mock.patch.object(w.urllib.request, "urlopen", side_effect=fake_urlopen):
            w._generate("m", "p", 5)

        self.assertEqual(stored["options"]["num_predict"], w.NUM_PREDICT)
        self.assertEqual(stored["options"]["num_ctx"], w.NUM_CTX)

    def test_oversized_prompt_fails_without_calling_model(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "big.md").write_text("가" * 60000, encoding="utf-8")
            mock_gen = mock.Mock()
            with mock.patch.object(w, "_generate", mock_gen):
                stdout_buf = io.StringIO()
                with redirect_stdout(stdout_buf):
                    rc = w.main(["-p", "Edit `big.md`.", "--add-dir", d])
                self.assertEqual(rc, 1)
                mock_gen.assert_not_called()
                out = json.loads(stdout_buf.getvalue())
                self.assertTrue(out["error"].startswith("PROMPT_TOO_LARGE"))

    def test_small_prompt_reaches_model(self):
        with tempfile.TemporaryDirectory() as d:
            small_path = Path(d) / "small.md"
            small_path.write_text("hello\n", encoding="utf-8")
            with mock.patch.object(
                w,
                "_generate",
                return_value=("===FILE: small.md===\nhi\n", {"input_tokens": 1, "output_tokens": 1}),
            ):
                stdout_buf = io.StringIO()
                with redirect_stdout(stdout_buf):
                    rc = w.main(["-p", "Edit `small.md`.", "--add-dir", d])
                self.assertEqual(rc, 0)
                self.assertEqual(small_path.read_text(encoding="utf-8"), "hi\n")

    def test_template_echo_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            a_path = Path(d) / "a.py"
            a_path.write_text("x = 1\ny = 2\n", encoding="utf-8")
            text = (
                "===EDIT: <relative/path>===\n"
                "<<<<<<< SEARCH\n"
                "<exact lines copied from the current file>\n"
                "=======\n"
                "<the lines that replace them>\n"
                ">>>>>>> REPLACE\n"
                "===EDIT: a.py===\n"
                "<<<<<<< SEARCH\n"
                "y = 2\n"
                "=======\n"
                "y = 3\n"
                ">>>>>>> REPLACE\n"
            )
            self.assertEqual(w._apply(text, Path(d)), ["a.py"])
            self.assertEqual(a_path.read_text(encoding="utf-8"), "x = 1\ny = 3\n")

    def test_template_only_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(w._apply("===FILE: <relative/path>===\nbody\n", Path(d)), [])


class CalculatorGateInstallTest(unittest.TestCase):
    def test_install_sets_hooks_path(self):
        mock_run = mock.Mock()
        with mock.patch.object(g.subprocess, "run", mock_run):
            stdout_buf = io.StringIO()
            with redirect_stdout(stdout_buf):
                rc = g.main(["--install"])
            self.assertEqual(rc, 0)
            mock_run.assert_called_once_with(["git", "config", "core.hooksPath", ".githooks"], check=True)

    def test_no_arguments_is_an_error(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            g.main([])

    def test_commit_msg_with_pilot_dir_runs_check(self):
        with tempfile.TemporaryDirectory() as d:
            msg_path = Path(d) / "MSG"
            msg_path.write_text("feat: x\n", encoding="utf-8")
            with mock.patch.object(g.subprocess, "check_output", return_value=""):
                rc = g.main(["--commit-msg", str(msg_path), "--pilot-dir", d])
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
