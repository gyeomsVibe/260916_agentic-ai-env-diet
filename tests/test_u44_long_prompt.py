"""U44 W6: a long contract reaches every worker without overflowing the Windows command line (32,767 characters).

The U44-FIX4 review failed with WinError 206 before starting; worker prompts took the same `-p <prompt>` route.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from v7_harness.adapters import apply_worker, claude_worker, lane_worker
from v7_harness.adapters.long_prompt import (ARGV_PROMPT_CHARS, FILE_MARKER, STDIN_NOTE, command_line_chars,
                                             resolve_prompt, split_for_stdin)
from v7_harness.execution.agy_launcher import fit_command_line

LONG = "".join(f"line {i} of a long contract\n" for i in range(2500))  # about 62k characters


class LongPromptTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_the_long_fixture_really_overflows_windows(self):
        self.assertGreater(len(LONG), 32_767)

    def test_resolve_prompt_passes_text_through_and_reads_a_marked_file(self):
        self.assertEqual("do it", resolve_prompt("do it"))
        path = self.root / "p.md"
        path.write_text(LONG, encoding="utf-8")
        self.assertEqual(LONG, resolve_prompt(FILE_MARKER + str(path)))

    def test_split_for_stdin_moves_only_long_prompts(self):
        self.assertEqual(("short", None), split_for_stdin("short"))
        note, data = split_for_stdin(LONG)
        self.assertEqual(STDIN_NOTE, note)
        self.assertEqual(LONG, data.decode("utf-8"))

    def test_launcher_hands_a_python_adapter_a_prompt_file(self):
        argv = [sys.executable, "x/claude_worker.py", "-p", LONG, "--output-format", "json", "--add-dir", "ws"]
        path = self.root / "a1.prompt.md"
        fitted, error = fit_command_line(argv, 2, path)
        self.assertEqual("", error)
        self.assertLess(command_line_chars(fitted), ARGV_PROMPT_CHARS)
        self.assertEqual(argv[:3], fitted[:3])
        self.assertEqual(argv[4:], fitted[4:])
        self.assertEqual(LONG, resolve_prompt(fitted[3]))

    def test_launcher_leaves_a_short_prompt_in_argv(self):
        argv = [sys.executable, "x/claude_worker.py", "-p", "short", "--add-dir", "ws"]
        path = self.root / "a1.prompt.md"
        self.assertEqual((argv, ""), fit_command_line(argv, 2, path))
        self.assertFalse(path.exists())

    def test_launcher_refuses_an_over_long_agy_line_on_windows_only(self):
        argv = ["agy", "-p", LONG, "--add-dir", "ws"]
        path = self.root / "a1.prompt.md"
        fitted, error = fit_command_line(argv, 1, path, windows=True)
        self.assertTrue(error.startswith("PROMPT_TOO_LONG_FOR_ARGV"), error)
        self.assertEqual((argv, ""), fit_command_line(argv, 1, path, windows=False))
        self.assertFalse(path.exists())

    def _fake_claude(self):
        log = self.root / "fake.log"
        fake = self.root / "fake_claude.py"
        fake.write_text(
            "import json, sys\n"
            "argv = sys.argv[1:]\n"
            "data = sys.stdin.read()\n"
            f"open({str(log)!r}, 'w', encoding='utf-8').write(json.dumps({{'p': argv[argv.index('-p') + 1], "
            "'stdin': data}))\n"
            "print(json.dumps({'result': 'done', 'num_turns': 1, 'total_cost_usd': 0.01,"
            " 'usage': {'input_tokens': 1, 'output_tokens': 1}}))\n",
            encoding="utf-8")
        return fake, log

    def test_claude_worker_reads_the_file_and_sends_the_prompt_on_stdin(self):
        fake, log = self._fake_claude()
        path = self.root / "a1.prompt.md"
        path.write_text(LONG, encoding="utf-8")
        with mock.patch.dict(os.environ, {"CLAUDE_WORKER_CMD": json.dumps([sys.executable, str(fake)])}):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = claude_worker.main(["-p", FILE_MARKER + str(path), "--add-dir", str(self.root),
                                         "--max-budget-usd", "0.10"])
        self.assertEqual(0, rc, out.getvalue())
        seen = json.loads(log.read_text(encoding="utf-8"))
        self.assertEqual(STDIN_NOTE, seen["p"])
        self.assertEqual(LONG, seen["stdin"])

    def test_lane_worker_sends_a_long_prompt_on_stdin(self):
        calls = []

        class Done:
            returncode = 0
            stdout = json.dumps({"result": "done", "num_turns": 1, "usage": {"input_tokens": 1,
                                                                            "output_tokens": 1}}).encode("utf-8")
            stderr = b""

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return Done()

        with mock.patch.object(lane_worker.subprocess, "run", fake_run), \
                mock.patch("v7_harness.adapters.gpu_priority.pilot_holds", lambda _t: contextlib.nullcontext()):
            with contextlib.redirect_stdout(io.StringIO()):
                lane_worker.main(["-p", LONG, "--add-dir", str(self.root)])
        cmd, kwargs = calls[0]
        self.assertEqual(STDIN_NOTE, cmd[cmd.index("-p") + 1])
        self.assertEqual(LONG.encode("utf-8"), kwargs["input"])

    def test_apply_worker_applies_blocks_from_a_prompt_file(self):
        ws = self.root / "ws"
        ws.mkdir()
        path = self.root / "a1.prompt.md"
        path.write_text(LONG + "\n===FILE: note.txt===\nhello from a long contract\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            rc = apply_worker.main(["-p", FILE_MARKER + str(path), "--add-dir", str(ws)])
        self.assertEqual(0, rc, out.getvalue())
        self.assertEqual("hello from a long contract\n", (ws / "note.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
