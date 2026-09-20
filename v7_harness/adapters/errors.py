"""Adapter policy errors."""

from __future__ import annotations


class AdapterPolicyError(ValueError):
    """Request violates adapter safety policy or the installed CLI lacks a required capability."""


class RecursionRejectedError(RuntimeError):
    """Cross-tool call rejected by the recursion guard (v9 §12)."""


class ConversationConflictError(RuntimeError):
    """A task/tool pair is already bound to a different conversation."""
