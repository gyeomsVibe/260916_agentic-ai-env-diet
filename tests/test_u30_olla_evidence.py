"""Fixed U30 acceptance for source-anchored, fail-closed Ollama extraction."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from v7_harness import olla_evidence


class EvidenceValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evidence = "VERSION working tree: 5.21.0\nCodex runtime: v5.22.0\n"
        self.keys = ["version_quote", "live_quote"]
        self.valid = json.dumps(
            {
                "version_quote": "VERSION working tree: 5.21.0",
                "live_quote": "Codex runtime: v5.22.0",
            }
        )

    def test_exact_quotes_pass(self) -> None:
        result = olla_evidence.validate_response(self.valid, self.evidence, self.keys)
        self.assertEqual(self.keys, list(result))

    def test_markdown_fence_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            olla_evidence.validate_response("```json\n" + self.valid + "\n```", self.evidence, self.keys)

    def test_invented_file_or_phrase_is_rejected(self) -> None:
        bad = self.valid.replace("Codex runtime: v5.22.0", "invented.py")
        with self.assertRaises(ValueError):
            olla_evidence.validate_response(bad, self.evidence, self.keys)

    def test_duplicate_key_is_rejected(self) -> None:
        bad = '{"version_quote":"VERSION working tree: 5.21.0","version_quote":"VERSION working tree: 5.21.0","live_quote":"Codex runtime: v5.22.0"}'
        with self.assertRaises(ValueError):
            olla_evidence.validate_response(bad, self.evidence, self.keys)

    def test_missing_extra_and_nonstring_values_are_rejected(self) -> None:
        for bad in (
            '{"version_quote":"VERSION working tree: 5.21.0"}',
            self.valid[:-1] + ',"extra":"VERSION"}',
            '{"version_quote":1,"live_quote":"Codex runtime: v5.22.0"}',
            '{"version_quote":"","live_quote":"Codex runtime: v5.22.0"}',
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                olla_evidence.validate_response(bad, self.evidence, self.keys)


class EvidenceCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.manual = root / "manual.md"
        self.evidence = root / "evidence.txt"
        self.manual.write_text("Copy only exact quotes. No judgment.\n", encoding="utf-8")
        self.evidence.write_text("SOURCE: alpha\n", encoding="utf-8")
        self.digest = hashlib.sha256(self.evidence.read_bytes()).hexdigest()
        self.argv = [
            "--manual", str(self.manual), "--evidence", str(self.evidence),
            "--sha256", self.digest, "--keys", "quote", "--prompt", "Copy SOURCE line",
            "--timeout", "60",
        ]

    def call(self, argv: list[str], response: str) -> tuple[int, str, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with patch.object(olla_evidence.worker, "_generate", return_value=(response, {"input_tokens": 10, "output_tokens": 4})) as gen:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                exit_code = olla_evidence.main(argv)
        return exit_code, out.getvalue(), err.getvalue(), gen.call_args.args[1] if gen.called else ""

    def test_valid_output_only_after_checks_and_manual_is_transmitted(self) -> None:
        code, out, err, prompt = self.call(self.argv, '{"quote":"SOURCE: alpha"}')
        self.assertEqual(0, code)
        self.assertEqual({"quote": "SOURCE: alpha"}, json.loads(out))
        self.assertIn("Copy only exact quotes", prompt)
        self.assertIn("SOURCE: alpha", prompt)
        self.assertIn("input_tokens", err)

    def test_wrong_hash_blocks_model_call_and_output(self) -> None:
        code, out, _, prompt = self.call(self.argv[:self.argv.index("--sha256") + 1] + ["0" * 64] + self.argv[self.argv.index("--keys"):], '{"quote":"SOURCE: alpha"}')
        self.assertNotEqual(0, code)
        self.assertEqual("", out)
        self.assertEqual("", prompt)

    def test_bad_model_response_never_reaches_stdout(self) -> None:
        code, out, _, _ = self.call(self.argv, '{"quote":"invented.py"}')
        self.assertNotEqual(0, code)
        self.assertEqual("", out)


if __name__ == "__main__":
    unittest.main()
