"""Codex CLI (`codex exec`) adapter for review/advice/execution calls.

`codex exec resume` (0.154.0) does not accept `--sandbox`/`-C`, so the sandbox is set via `-c`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import AdapterPolicyError
from .validation import normalize_enum, require_identifier, require_no_control_characters

PURPOSES = frozenset({"advice", "review", "execution"})
MODES = frozenset({"managed", "standalone", "imported"})


@dataclass(frozen=True)
class CodexRequest:
    task_id: str
    purpose: str
    session_id: str | None
    prompt: str
    workspace: Path
    mode: str


def build_codex_command(request: CodexRequest, *, executable: str = "codex") -> list[str]:
    purpose = normalize_enum(request.purpose, PURPOSES, "purpose", AdapterPolicyError)
    mode = normalize_enum(request.mode, MODES, "mode", AdapterPolicyError)
    require_no_control_characters(request.task_id, "task_id", AdapterPolicyError)
    if purpose == "execution" and mode != "managed":
        raise AdapterPolicyError("Codex execution is allowed only for managed tasks with a coordinator lease")
    sandbox = "workspace-write" if purpose == "execution" else "read-only"
    prompt = f"[{request.task_id}] {request.prompt}"
    if request.session_id is not None:
        session_id = require_identifier(request.session_id, "session_id", AdapterPolicyError)
        return [
            executable, "exec", "resume", "--skip-git-repo-check",
            "-c", f'sandbox_mode="{sandbox}"',
            session_id, prompt,
        ]
    return [
        executable, "exec", "--skip-git-repo-check",
        "--sandbox", sandbox,
        "-C", str(request.workspace),
        prompt,
    ]
