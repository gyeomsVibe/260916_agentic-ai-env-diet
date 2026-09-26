"""U44 W6: keep every worker prompt off an over-long Windows command line.

Windows caps a whole command line at 32,767 characters (CreateProcess; WinError 206). The pilot passed each contract
to its worker as `-p <prompt>`, and the claude adapters passed it on to `claude -p` the same way, so a large contract
plus diff could not start at all (U44-FIX4 review). Two hops, two carriers:

- pilot launcher -> our Python adapters: the prompt is written to a file and `-p` carries FILE_MARKER + path;
- claude adapters -> `claude -p`: the prompt goes on standard input, which claude -p reads together with a short
  argv note (live 2026-09-26: 46,529 characters read correctly).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# Past this many characters a prompt leaves the command line: 20,000 leaves room under 32,767 for the system
# prompt, flags and paths that share the line.
ARGV_PROMPT_CHARS = 20_000
WINDOWS_ARGV_LIMIT = 32_767
FILE_MARKER = "@@UAOS_PROMPT_FILE@@"
STDIN_NOTE = "The full task is on standard input. Follow it."


def command_line_chars(argv: list[str]) -> int:
    return len(subprocess.list2cmdline([str(part) for part in argv]))


def resolve_prompt(value: str) -> str:
    """An adapter's -p value: the prompt itself, or FILE_MARKER + the path the pilot launcher wrote it to."""
    if value.startswith(FILE_MARKER):
        return Path(value[len(FILE_MARKER):]).read_text(encoding="utf-8")
    return value


def split_for_stdin(prompt: str) -> tuple[str, bytes | None]:
    """(argv prompt, stdin bytes) for `claude -p`: a long prompt goes on standard input, a short one stays in argv."""
    if len(prompt) > ARGV_PROMPT_CHARS:
        return STDIN_NOTE, prompt.encode("utf-8")
    return prompt, None
