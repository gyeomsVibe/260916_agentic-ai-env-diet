"""Antigravity CLI (`agy`) headless adapter.

Success is decided by the JSON envelope and stderr evidence, never by exit code or prose.
Local evidence (agy 1.2.4): exit 0 with `status=ERROR` (503) while a file was actually written.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import AdapterPolicyError
from .validation import is_partial_timeout, require_identifier, require_no_control_characters, validate_usage

ISOLATION_MODES = frozenset({"staging", "worktree", "source"})
REQUIRED_HEADLESS_FLAGS = ("--output-format", "--json-schema", "--conversation", "--add-dir", "--print-timeout")


@dataclass(frozen=True)
class AgyRequest:
    task_id: str
    title: str
    prompt: str
    workspace: Path
    isolation_mode: str
    conversation_id: str | None = None
    model: str | None = None
    print_timeout_s: int = 600
    schema_path: Path | None = None
    skip_permissions: bool = False


@dataclass(frozen=True)
class AgyOutcome:
    successful: bool
    status: str
    error_class: str
    effect_state: str
    retryable: bool
    conversation_id: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    stderr_sha256: str = ""


@dataclass(frozen=True)
class AgyCapabilities:
    flags: frozenset[str]

    @property
    def headless_json(self) -> bool:
        return all(flag in self.flags for flag in REQUIRED_HEADLESS_FLAGS)

    def require_headless_json(self) -> None:
        missing = [flag for flag in REQUIRED_HEADLESS_FLAGS if flag not in self.flags]
        if missing:
            raise AdapterPolicyError(f"CAPABILITY: agy lacks required headless flags: {', '.join(missing)}")


def build_agy_command(request: AgyRequest, *, executable: str = "agy") -> list[str]:
    if request.isolation_mode not in ISOLATION_MODES:
        raise AdapterPolicyError(f"unknown isolation_mode: {request.isolation_mode}")
    if request.skip_permissions and request.isolation_mode != "staging":
        raise AdapterPolicyError("--dangerously-skip-permissions is allowed only inside an isolated staging copy")
    if request.print_timeout_s <= 0:
        raise AdapterPolicyError("print_timeout_s must be positive")
    require_no_control_characters(request.task_id, "task_id", AdapterPolicyError)
    require_no_control_characters(request.title, "title", AdapterPolicyError)
    if request.conversation_id is not None:
        require_identifier(request.conversation_id, "conversation_id", AdapterPolicyError)
    if request.model is not None:
        require_identifier(request.model, "model", AdapterPolicyError)
    prompt = f"[{request.task_id}] {request.title}\n{request.prompt}"
    cmd = [
        executable,
        "-p",
        prompt,
        "--output-format",
        "json",
        "--print-timeout",
        f"{int(request.print_timeout_s)}s",
        "--add-dir",
        str(request.workspace),
    ]
    if request.conversation_id is not None:
        cmd += ["--conversation", request.conversation_id]
    if request.model is not None:
        cmd += ["--model", request.model]
    if request.schema_path is not None:
        cmd += ["--json-schema", str(request.schema_path)]
    if request.skip_permissions:
        cmd.append("--dangerously-skip-permissions")
    return cmd


_LOGIN_COMMAND_RE = re.compile(r"(?:^|(?<=\s))/login(?=[\s\W]|$)")


def _classify_provider_error(text: str) -> str:
    lowered = text.casefold()
    if any(token in lowered for token in ("oauth", "unauthenticated", "authentication", "required scopes")):
        return "AUTH"
    if _LOGIN_COMMAND_RE.search(lowered):
        return "AUTH"
    if any(token in lowered for token in ("429", "quota", "resource_exhausted", "rate limit")):
        return "QUOTA"
    if any(token in lowered for token in ("503", "no capacity", "unavailable")):
        return "TRANSIENT_CAPACITY"
    return "PROVIDER_ERROR"


def parse_agy_result(*, stdout: bytes, stderr: bytes, exit_code: int) -> AgyOutcome:
    stderr_hash = hashlib.sha256(stderr).hexdigest()
    stderr_text = stderr.decode("utf-8", errors="replace").casefold()

    def failed(error_class: str, status: str = "INVALID", conversation_id: str | None = None, usage: dict[str, int] | None = None) -> AgyOutcome:
        # The worker may already have acted; effects must be reconciled, never blindly retried.
        return AgyOutcome(False, status, error_class, "UNKNOWN", False, conversation_id, usage or {}, stderr_hash)

    try:
        envelope: Any = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        envelope = None
    partial_timeout = is_partial_timeout(stderr_text)
    if not isinstance(envelope, dict):
        return failed("TIMEOUT_PARTIAL" if partial_timeout else "VALIDATION")

    status = str(envelope.get("status", "")).strip().upper()
    conversation_id = envelope.get("conversation_id") if isinstance(envelope.get("conversation_id"), str) else None
    usage = validate_usage(envelope.get("usage"))

    if partial_timeout:
        return failed("TIMEOUT_PARTIAL", status, conversation_id, usage)
    if usage is None:
        # NaN/Infinity/bool/negative/fractional/string token counts are untrustworthy evidence.
        return failed("VALIDATION", status, conversation_id)
    if status == "SUCCESS" and exit_code != 0:
        # Contradictory evidence (envelope success, process failure) is never accepted as success.
        return failed("VALIDATION", status, conversation_id, usage)
    if status != "SUCCESS":
        return failed(_classify_provider_error(str(envelope.get("error", ""))), status or "INVALID", conversation_id, usage)
    response = envelope.get("response")
    structured = envelope.get("structured_output")
    if not (isinstance(response, str) and response.strip()) and structured in (None, "", {}, []):
        return failed("VALIDATION", status, conversation_id, usage)
    # Success of the envelope only; file effects still require diff/scope verification downstream.
    return AgyOutcome(True, status, "NONE", "PENDING_VERIFICATION", False, conversation_id, usage, stderr_hash)


def detect_agy_capabilities(help_text: str) -> AgyCapabilities:
    flags = frozenset(token.strip(",") for token in help_text.split() if token.startswith("--"))
    return AgyCapabilities(flags)
