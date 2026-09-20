"""Recursion guard (v9 §12) and per-task conversation registry (R11/R13)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import ConversationConflictError, RecursionRejectedError
from .validation import normalize_enum

TOOLS = frozenset({"codex", "antigravity"})
MODES = frozenset({"managed", "standalone", "imported"})
INTENTS = frozenset({"advice", "review", "execution"})


@dataclass(frozen=True)
class CallEnvelope:
    task_id: str
    parent_task_id: str
    root_task_id: str
    call_depth: int
    max_hops: int
    caller: str
    callee: str
    mode: str
    intent: str
    intent_hash: str
    mutates_plan: bool = False


@dataclass
class RecursionGuard:
    _seen: set[tuple[str, str, str, str]] = field(default_factory=set)

    def check(self, call: CallEnvelope) -> None:
        caller = normalize_enum(call.caller, TOOLS, "caller", RecursionRejectedError)
        callee = normalize_enum(call.callee, TOOLS, "callee", RecursionRejectedError)
        mode = normalize_enum(call.mode, MODES, "mode", RecursionRejectedError)
        intent = normalize_enum(call.intent, INTENTS, "intent", RecursionRejectedError)
        if call.call_depth < 1 or call.call_depth > call.max_hops:
            raise RecursionRejectedError(f"call_depth {call.call_depth} outside 1..max_hops({call.max_hops})")
        if caller == callee:
            raise RecursionRejectedError(f"same-tool reentry: {caller}")
        if mode == "managed" and caller == "antigravity" and callee == "codex" and intent == "execution":
            raise RecursionRejectedError("managed Antigravity cannot hand execution back to Codex")
        if mode != "managed" and call.mutates_plan:
            raise RecursionRejectedError(f"{mode} call cannot mutate the managed plan")
        key = (call.root_task_id, caller, callee, call.intent_hash)
        if key in self._seen:
            raise RecursionRejectedError(f"cycle detected for {key}")
        self._seen.add(key)


@dataclass
class ConversationRegistry:
    _bindings: dict[tuple[str, str], str] = field(default_factory=dict)
    _owners: dict[str, tuple[str, str]] = field(default_factory=dict)

    def bind(self, task_id: str, tool: str, conversation_id: str) -> None:
        key = (task_id, tool)
        existing = self._bindings.get(key)
        if existing is not None and existing != conversation_id:
            raise ConversationConflictError(f"{task_id}/{tool} already bound to {existing}")
        owner = self._owners.get(conversation_id)
        if owner is not None and owner != key:
            raise ConversationConflictError(f"conversation {conversation_id} already bound to {owner[0]}/{owner[1]}")
        self._bindings[key] = conversation_id
        self._owners[conversation_id] = key

    def lookup(self, task_id: str, tool: str) -> str | None:
        return self._bindings.get((task_id, tool))
