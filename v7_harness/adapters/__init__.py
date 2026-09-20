"""U14 Antigravity/Codex adapters: pure argv builders, result parsers, and call guards.

Process spawning, timeouts, and process-tree containment stay in the U12 launcher.
"""

from .agy import AgyCapabilities, AgyOutcome, AgyRequest, build_agy_command, detect_agy_capabilities, parse_agy_result
from .codex import CodexRequest, build_codex_command
from .errors import AdapterPolicyError, ConversationConflictError, RecursionRejectedError
from .guard import CallEnvelope, ConversationRegistry, RecursionGuard

__all__ = [
    "AdapterPolicyError",
    "AgyCapabilities",
    "AgyOutcome",
    "AgyRequest",
    "CallEnvelope",
    "CodexRequest",
    "ConversationConflictError",
    "ConversationRegistry",
    "RecursionGuard",
    "RecursionRejectedError",
    "build_agy_command",
    "build_codex_command",
    "detect_agy_capabilities",
    "parse_agy_result",
]
