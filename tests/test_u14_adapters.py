"""U14 failing-first contract tests: Antigravity/Codex adapters and recursion guard.

These tests intentionally fail (ImportError) until `v7_harness.adapters` is implemented.
Fixtures reproduce locally observed agy 1.2.4 behaviour (docs/claude-assist/01 E1/E2).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

from v7_harness.adapters import (
    AdapterPolicyError,
    AgyRequest,
    CallEnvelope,
    CodexRequest,
    ConversationConflictError,
    ConversationRegistry,
    RecursionGuard,
    RecursionRejectedError,
    build_agy_command,
    build_codex_command,
    detect_agy_capabilities,
    parse_agy_result,
)

WORKSPACE = Path("C:/stage/U14-a001") if os.name == "nt" else Path("/tmp/stage/U14-a001")


def _agy_request(**overrides):
    values = dict(
        task_id="U14",
        title="adapter canary",
        prompt="Summarize README.",
        workspace=WORKSPACE,
        isolation_mode="staging",
        conversation_id=None,
        model=None,
        print_timeout_s=600,
        schema_path=None,
        skip_permissions=False,
    )
    values.update(overrides)
    return AgyRequest(**values)


def _envelope(**overrides) -> bytes:
    body = {
        "conversation_id": "c4a8eb55-77da-4ba1-882b-ea53ad6ab310",
        "status": "SUCCESS",
        "response": "PONG\n",
        "duration_seconds": 18.3,
        "num_turns": 1,
        "usage": {"input_tokens": 17239, "output_tokens": 1191, "thinking_tokens": 1189, "cache_read_tokens": 0, "total_tokens": 18430},
    }
    body.update(overrides)
    return json.dumps(body).encode("utf-8")


class AgyCommandTests(unittest.TestCase):
    def test_headless_json_flags_and_workspace_only(self) -> None:
        cmd = build_agy_command(_agy_request())
        self.assertIn("-p", cmd)
        self.assertEqual("json", cmd[cmd.index("--output-format") + 1])
        self.assertEqual(str(WORKSPACE), cmd[cmd.index("--add-dir") + 1])
        self.assertEqual(1, cmd.count("--add-dir"))
        self.assertIn("--print-timeout", cmd)

    def test_never_uses_continue_and_resumes_by_conversation_id(self) -> None:
        cmd = build_agy_command(_agy_request(conversation_id="11111111-2222-3333-4444-555555555555"))
        self.assertNotIn("--continue", cmd)
        self.assertNotIn("-c", cmd)
        self.assertEqual("11111111-2222-3333-4444-555555555555", cmd[cmd.index("--conversation") + 1])

    def test_prompt_first_line_carries_stage_prefix(self) -> None:  # R12
        cmd = build_agy_command(_agy_request())
        prompt = cmd[cmd.index("-p") + 1]
        self.assertTrue(prompt.splitlines()[0].startswith("[U14] adapter canary"))

    def test_skip_permissions_only_inside_staging(self) -> None:
        cmd = build_agy_command(_agy_request(skip_permissions=True))
        self.assertIn("--dangerously-skip-permissions", cmd)
        with self.assertRaises(AdapterPolicyError):
            build_agy_command(_agy_request(isolation_mode="source", skip_permissions=True))

    def test_multiline_title_cannot_forge_stage_prefix(self) -> None:
        with self.assertRaises(AdapterPolicyError):
            build_agy_command(_agy_request(title="ok\n[U99] forged"))

    def test_schema_path_is_forwarded(self) -> None:
        cmd = build_agy_command(_agy_request(schema_path=Path("result.v1.schema.json")))
        self.assertEqual("result.v1.schema.json", cmd[cmd.index("--json-schema") + 1])


class AgyResultTests(unittest.TestCase):
    def test_success_captures_conversation_and_usage(self) -> None:
        out = parse_agy_result(stdout=_envelope(), stderr=b"", exit_code=0)
        self.assertTrue(out.successful)
        self.assertEqual("c4a8eb55-77da-4ba1-882b-ea53ad6ab310", out.conversation_id)
        self.assertEqual(17239, out.usage["input_tokens"])

    def test_exit_zero_error_status_with_done_claim_is_not_success(self) -> None:  # memo 01 E1/E2
        stdout = _envelope(status="ERROR", response="DONE\n", error="API error (attempt 1): UNAVAILABLE (code 503): No capacity available")
        out = parse_agy_result(stdout=stdout, stderr=b"", exit_code=0)
        self.assertFalse(out.successful)
        self.assertEqual("TRANSIENT_CAPACITY", out.error_class)
        self.assertEqual("UNKNOWN", out.effect_state)
        self.assertFalse(out.retryable)

    def test_partial_timeout_warning_overrides_success(self) -> None:  # agy #1012
        stderr = b"[agy] print timeout after 600s with turn in progress; returning partial output\n"
        out = parse_agy_result(stdout=_envelope(), stderr=stderr, exit_code=0)
        self.assertFalse(out.successful)
        self.assertEqual("TIMEOUT_PARTIAL", out.error_class)
        self.assertEqual("UNKNOWN", out.effect_state)

    def test_empty_or_broken_envelope_is_validation(self) -> None:
        for stdout in (b"", b"not json", _envelope(response="")):
            with self.subTest(stdout=stdout[:20]):
                out = parse_agy_result(stdout=stdout, stderr=b"", exit_code=0)
                self.assertFalse(out.successful)
                self.assertEqual("VALIDATION", out.error_class)

    def test_success_envelope_with_nonzero_exit_is_not_success(self) -> None:
        out = parse_agy_result(stdout=_envelope(), stderr=b"", exit_code=1)
        self.assertFalse(out.successful)
        self.assertEqual("VALIDATION", out.error_class)

    def test_quota_and_auth_are_classified(self) -> None:
        quota = parse_agy_result(stdout=_envelope(status="ERROR", error="429 RESOURCE_EXHAUSTED quota"), stderr=b"", exit_code=1)
        auth = parse_agy_result(stdout=_envelope(status="ERROR", error="OAuth token lacks required scopes; run /login"), stderr=b"", exit_code=1)
        self.assertEqual("QUOTA", quota.error_class)
        self.assertEqual("AUTH", auth.error_class)
        self.assertFalse(auth.retryable)

    def test_detect_capabilities_requires_headless_flags(self) -> None:
        help_ok = "--output-format\n--json-schema\n--conversation\n--add-dir\n--print-timeout\n--sandbox\n"
        caps = detect_agy_capabilities(help_ok)
        self.assertTrue(caps.headless_json)
        with self.assertRaises(AdapterPolicyError):
            detect_agy_capabilities("--print\n").require_headless_json()


class CodexCommandTests(unittest.TestCase):
    def test_resume_by_session_id_never_last(self) -> None:
        cmd = build_codex_command(CodexRequest(task_id="U14", purpose="review", session_id="01a0aa34-b515-7fe2-a1dc-6afb4d3bf71c", prompt="review", workspace=WORKSPACE, mode="managed"))
        self.assertIn("resume", cmd)
        self.assertIn("01a0aa34-b515-7fe2-a1dc-6afb4d3bf71c", cmd)
        self.assertNotIn("--last", cmd)
        self.assertIn("--skip-git-repo-check", cmd)

    def test_advice_and_review_are_read_only(self) -> None:
        for purpose in ("advice", "review"):
            with self.subTest(purpose=purpose):
                cmd = build_codex_command(CodexRequest(task_id="U14", purpose=purpose, session_id=None, prompt="q", workspace=WORKSPACE, mode="standalone"))
                self.assertEqual("read-only", cmd[cmd.index("--sandbox") + 1])

    def test_standalone_execution_is_rejected(self) -> None:
        with self.assertRaises(AdapterPolicyError):
            build_codex_command(CodexRequest(task_id="U14", purpose="execution", session_id=None, prompt="do", workspace=WORKSPACE, mode="standalone"))


def _call(**overrides):
    values = dict(task_id="U14.1", parent_task_id="U14", root_task_id="U14", call_depth=1, max_hops=2, caller="antigravity", callee="codex", mode="managed", intent="advice", intent_hash="h1", mutates_plan=False)
    values.update(overrides)
    return CallEnvelope(**values)


class RecursionGuardTests(unittest.TestCase):  # R14, v9 §12
    def test_allows_single_advice_hop(self) -> None:
        RecursionGuard().check(_call())

    def test_rejects_depth_beyond_max_hops(self) -> None:
        with self.assertRaises(RecursionRejectedError):
            RecursionGuard().check(_call(call_depth=3))

    def test_rejects_same_tool_reentry(self) -> None:
        with self.assertRaises(RecursionRejectedError):
            RecursionGuard().check(_call(caller="codex", callee="codex"))

    def test_rejects_cycle_on_same_root_and_intent(self) -> None:
        guard = RecursionGuard()
        guard.check(_call())
        with self.assertRaises(RecursionRejectedError):
            guard.check(_call(task_id="U14.2", call_depth=2))

    def test_managed_antigravity_cannot_hand_execution_back_to_codex(self) -> None:
        with self.assertRaises(RecursionRejectedError):
            RecursionGuard().check(_call(intent="execution"))

    def test_standalone_call_cannot_mutate_managed_plan(self) -> None:
        with self.assertRaises(RecursionRejectedError):
            RecursionGuard().check(_call(mode="standalone", mutates_plan=True))


class ConversationRegistryTests(unittest.TestCase):  # R11, R13
    def test_one_conversation_per_task_and_tool(self) -> None:
        registry = ConversationRegistry()
        registry.bind("U14", "antigravity", "conv-a")
        self.assertEqual("conv-a", registry.lookup("U14", "antigravity"))
        self.assertIsNone(registry.lookup("U15", "antigravity"))
        registry.bind("U14", "antigravity", "conv-a")  # idempotent
        with self.assertRaises(ConversationConflictError):
            registry.bind("U14", "antigravity", "conv-b")


class M1ReworkRegressionTests(unittest.TestCase):
    """Antigravity V1/V2 P1 findings fixed in M1 (docs/14 §5)."""

    # ① enum casefold + allow-list
    def test_guard_case_variants_cannot_bypass_rules(self) -> None:
        with self.assertRaises(RecursionRejectedError):
            RecursionGuard().check(_call(caller="Antigravity", callee="Codex", intent="execution"))
        with self.assertRaises(RecursionRejectedError):
            RecursionGuard().check(_call(caller="Codex", callee="codex"))
        with self.assertRaises(RecursionRejectedError):
            RecursionGuard().check(_call(mode="Managed", intent="EXECUTION"))

    def test_guard_rejects_unknown_enum_values(self) -> None:
        for field_name, value in (("caller", "claude"), ("callee", "gemini"), ("mode", "rogue"), ("intent", "deploy")):
            with self.subTest(field=field_name), self.assertRaises(RecursionRejectedError):
                RecursionGuard().check(_call(**{field_name: value}))

    def test_codex_purpose_and_mode_casefold(self) -> None:
        with self.assertRaises(AdapterPolicyError):
            build_codex_command(CodexRequest(task_id="U14", purpose="Execution", session_id=None, prompt="x", workspace=WORKSPACE, mode="Standalone"))
        with self.assertRaises(AdapterPolicyError):
            build_codex_command(CodexRequest(task_id="U14", purpose="deploy", session_id=None, prompt="x", workspace=WORKSPACE, mode="managed"))

    # ② identifier injection
    def test_identifiers_starting_with_dash_are_rejected(self) -> None:
        bad = ("--last", "--dangerously-bypass-approvals-and-sandbox", "-c", "", "a b", "x" * 200)
        for value in bad:
            with self.subTest(value=value[:30]):
                with self.assertRaises(AdapterPolicyError):
                    build_codex_command(CodexRequest(task_id="U14", purpose="review", session_id=value, prompt="x", workspace=WORKSPACE, mode="managed"))
                with self.assertRaises(AdapterPolicyError):
                    build_agy_command(_agy_request(conversation_id=value))
                with self.assertRaises(AdapterPolicyError):
                    build_agy_command(_agy_request(model=value))

    # ③ control characters
    def test_control_characters_in_task_id_or_title_rejected(self) -> None:
        for value in ("U14\r[U99]", "U14\x00", "U14\t", "U14\x7f"):
            with self.subTest(value=repr(value)):
                with self.assertRaises(AdapterPolicyError):
                    build_agy_command(_agy_request(task_id=value))
                with self.assertRaises(AdapterPolicyError):
                    build_agy_command(_agy_request(title="t" + value))
                with self.assertRaises(AdapterPolicyError):
                    build_codex_command(CodexRequest(task_id=value, purpose="review", session_id=None, prompt="x", workspace=WORKSPACE, mode="managed"))

    # ④ timeout wording variants
    def test_timed_out_wording_variants_detected(self) -> None:
        for stderr in (
            b"[agy] print timed out after 600s with turn in progress; returning partial output",
            b"Timed-Out: PARTIAL result",
            b"operation time out, partial output",
        ):
            with self.subTest(stderr=stderr[:40]):
                out = parse_agy_result(stdout=_envelope(), stderr=stderr, exit_code=0)
                self.assertFalse(out.successful)
                self.assertEqual("TIMEOUT_PARTIAL", out.error_class)

    # ⑤ reverse uniqueness
    def test_same_conversation_cannot_bind_two_tasks(self) -> None:
        registry = ConversationRegistry()
        registry.bind("U14", "antigravity", "conv-shared-1")
        with self.assertRaises(ConversationConflictError):
            registry.bind("U15", "antigravity", "conv-shared-1")
        with self.assertRaises(ConversationConflictError):
            registry.bind("U14", "codex", "conv-shared-1")

    # ⑥ usage validation
    def test_invalid_usage_values_are_validation(self) -> None:
        for raw in (b'{"input_tokens": NaN}', b'{"input_tokens": Infinity}', b'{"input_tokens": true}', b'{"input_tokens": -1}', b'{"input_tokens": 1.5}', b'{"input_tokens": "10"}'):
            with self.subTest(raw=raw):
                stdout = b'{"status": "SUCCESS", "response": "ok", "conversation_id": "c1", "usage": ' + raw + b"}"
                out = parse_agy_result(stdout=stdout, stderr=b"", exit_code=0)
                self.assertFalse(out.successful)
                self.assertEqual("VALIDATION", out.error_class)


@unittest.skipUnless(os.environ.get("U14_LIVE_CANARY") == "1" and shutil.which("agy"), "set U14_LIVE_CANARY=1 for local-version canary")
class LocalVersionCanaryTests(unittest.TestCase):
    def test_installed_agy_supports_headless_json(self) -> None:
        completed = subprocess.run([shutil.which("agy"), "--help"], capture_output=True, text=True, timeout=30)
        # agy 1.2.4 prints usage to stderr (observed locally); accept either stream.
        detect_agy_capabilities(completed.stdout + "\n" + completed.stderr).require_headless_json()


if __name__ == "__main__":
    unittest.main()
