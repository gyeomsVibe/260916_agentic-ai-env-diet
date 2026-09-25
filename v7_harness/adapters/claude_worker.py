"""Claude Code as a UAOS pilot worker (U38): `claude -p` on the paid account, inside the staged copy.

This is lane_worker's benchmarked call pointed back at Anthropic instead of the local model. Same contract as the other
workers: `-p <prompt> --add-dir <workspace> --print-timeout Ns [--model M]` in, one JSON envelope out. docs/40 §2-1.

What keeps it inside its lane:
- no Bash, and tests are write-protected: the pilot runs the acceptance itself (lane bench: test tampering was the
  main failure);
- `.coord/**` is write-protected too, and `--bare` keeps project hooks and CLAUDE.md out. The staged copy holds
  `.coord/PLAN.md`, so a presence hook firing there would write into the copy and turn a good run into a
  SCOPE_VIOLATION;
- the parent session's markers are removed and UAOS_WORKER=claude is set, so hooks and logs never take the worker
  for the commander;
- every token kind and the dollar cost are reported, so the pilot's cost gate (B85) sees the whole spend.
The judge of a `worker: claude` run is Codex or the user (manual lint: SELF_JUDGE).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

DEFAULT_MODEL = os.environ.get("CLAUDE_WORKER_MODEL", "sonnet")
MAX_TURNS = os.environ.get("CLAUDE_WORKER_MAX_TURNS", "30")
TOOLS = "Read,Edit,Write,Glob,Grep"
PROTECTED = [
    "Edit(test_*)", "Edit(**/test_*)", "Edit(tests/**)", "Write(test_*)", "Write(**/test_*)", "Write(tests/**)",
    "Edit(.coord/**)", "Write(.coord/**)", "Edit(.claude/**)", "Write(.claude/**)",
]
SYSTEM = ("You are a UAOS worker editing a staged copy of a project. Follow the contract in the prompt exactly: change "
          "only the files it allows, do not edit tests, do not run commands. Stop when the change is done. Be brief.")
# Markers of the parent Claude Code session. Inherited, they would make the worker look like the commander.
PARENT_MARKERS = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SESSION_ID", "CLAUDE_PROJECT_DIR")
USAGE_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def worker_env(environ: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if environ is None else environ)
    for key in PARENT_MARKERS:
        env.pop(key, None)
    # lane points the CLI at the local Ollama endpoint; a paid worker must not inherit that redirect.
    base = env.get("ANTHROPIC_BASE_URL", "")
    ollama = env.get("OLLAMA_HOST", "127.0.0.1:11434").replace("http://", "").replace("https://", "")
    if base and (":11434" in base or ollama in base):
        env.pop("ANTHROPIC_BASE_URL", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
    env["UAOS_WORKER"] = "claude"
    env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    return env


def claude_executable() -> list[str]:
    """The claude CLI, or CLAUDE_WORKER_CMD as a JSON list (a non-standard install, or a stand-in for tests; a JSON
    list rather than a shell string so Windows paths need no quoting)."""
    override = os.environ.get("CLAUDE_WORKER_CMD")
    if override:
        value = json.loads(override)
        if isinstance(value, list) and value and all(isinstance(part, str) for part in value):
            return value
        raise ValueError("CLAUDE_WORKER_CMD must be a JSON list of strings")
    return [shutil.which("claude") or "claude"]


def worker_command(prompt: str, model: str) -> list[str]:
    return [*claude_executable(), "-p", prompt, "--bare", "--tools", TOOLS, "--strict-mcp-config",
            "--disable-slash-commands", "--system-prompt", SYSTEM, "--model", model, "--max-turns", MAX_TURNS,
            "--permission-mode", "acceptEdits", "--allowedTools", TOOLS, "--disallowedTools", *PROTECTED,
            "--output-format", "json"]


REVIEW_TOOLS = "Read,Glob,Grep"
REVIEW_SYSTEM = ("You are an independent UAOS reviewer. You may only read. Look for counterexamples: requirements of the "
                 "contract the change misses, deletions it did not ask for, edits outside its scope, tests it weakens. "
                 "Answer with one JSON object and nothing else.")


def review_command(prompt: str, model: str) -> list[str]:
    """Read-only: no Edit, Write or Bash, so the reviewer cannot change what it judges."""
    return [*claude_executable(), "-p", prompt, "--bare", "--tools", REVIEW_TOOLS, "--strict-mcp-config",
            "--disable-slash-commands", "--system-prompt", REVIEW_SYSTEM, "--model", model, "--max-turns", MAX_TURNS,
            "--allowedTools", REVIEW_TOOLS, "--disallowedTools", "Edit", "Write", "Bash", "--output-format", "json"]


def usage_from(result: dict) -> dict[str, int]:
    raw = result.get("usage") or {}
    usage = {key: int(raw[key]) for key in USAGE_KEYS if isinstance(raw.get(key), (int, float)) and not isinstance(raw.get(key), bool)}
    cost = result.get("total_cost_usd")
    if isinstance(cost, (int, float)) and not isinstance(cost, bool):
        # The pilot accepts whole numbers only; micro-dollars keep the precision.
        usage["cost_microusd"] = int(round(float(cost) * 1_000_000))
    usage["turns"] = int(result.get("num_turns") or 0)
    return usage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--prompt", required=True)
    parser.add_argument("--output-format", default="json")
    parser.add_argument("--print-timeout", default="600s")
    parser.add_argument("--add-dir", dest="workspace", required=True)
    parser.add_argument("--model", default=None)
    args, _unknown = parser.parse_known_args(argv)
    timeout_s = int(str(args.print_timeout).rstrip("s") or 600)
    model = args.model or DEFAULT_MODEL

    def envelope(status: str, response: str, usage: dict, error: str = "") -> int:
        print(json.dumps({"status": status, "response": response, "usage": usage, "conversation_id": "claude-worker",
                          "error": error}, ensure_ascii=False))
        return 0 if status == "SUCCESS" else 1

    # Nothing reported means UNKNOWN to the cost gate, which blocks the run: a failed start is not a free run.
    started = time.monotonic()
    try:
        done = subprocess.run(worker_command(args.prompt, model), cwd=args.workspace, env=worker_env(),
                              capture_output=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return envelope("ERROR", "", {}, f"claude worker timed out after {timeout_s}s")
    except (OSError, ValueError) as exc:
        return envelope("ERROR", "", {}, f"claude worker could not start: {exc}")
    try:
        result = json.loads(done.stdout.decode("utf-8", errors="replace"))
    except ValueError:
        return envelope("ERROR", "", {}, f"claude returned no JSON (rc={done.returncode}): "
                                         f"{done.stderr.decode('utf-8', errors='replace')[:200]}")
    if not isinstance(result, dict):
        return envelope("ERROR", "", {}, "claude returned a JSON value that is not an object")
    usage = usage_from(result)
    usage["elapsed_s"] = int(time.monotonic() - started)
    if result.get("is_error") and result.get("subtype") not in ("error_max_turns",):
        return envelope("ERROR", "", usage, str(result.get("subtype") or result.get("result") or "claude error")[:300])
    return envelope("SUCCESS", str(result.get("result") or "").strip()[:2000] or "(claude ended without a summary)", usage)


if __name__ == "__main__":
    sys.exit(main())
