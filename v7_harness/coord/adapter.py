"""U23 S2: Stream-to-Mailbox Delivery Adapter.

Bridges append-only coordination stream events to the atomic disk mailbox,
enabling zero-token asynchronous communication and durable pull fallback.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .mailbox import Mailbox, ClaimedMessage, MailboxRejected
from .stream import Event, read_events

ACTIONABLE_KINDS = frozenset({"RUN", "BLOCKED", "HANDOFF"})


def is_actionable_event(event: Any) -> bool:
    """Judge whether an event requires coordinator action/verdict."""
    if isinstance(event, dict):
        kind = event.get("kind", "")
        evidence = event.get("evidence") or {}
    else:
        kind = getattr(event, "kind", "")
        evidence = getattr(event, "evidence", {}) or {}

    if kind in ACTIONABLE_KINDS:
        return True
    if evidence and evidence.get("verdict_requested"):
        return True
    return False


def format_mailbox_notice(payload: dict[str, Any]) -> str:
    """Format human/agent readable notification text for mailbox messages."""
    actor = str(payload.get("actor", "")).lower()
    if actor in ("agy", "antigravity"):
        prefix = "[안티그래비티에서 온 대화]"
    elif actor == "claude":
        prefix = "[클로드에게서 온 대화]"
    else:
        raw_actor = payload.get("actor", "알수없음")
        prefix = f"[{raw_actor}에서 온 대화]"

    kind = payload.get("kind", "EVENT")
    step = payload.get("step", "")
    summary = payload.get("summary", "")
    return f"{prefix} [{kind}] {step}: {summary}"


def sync_stream_to_mailbox(
    project: Path,
    box: Mailbox,
    cursor_file: Path | None = None,
) -> list[str]:
    """Sync actionable stream events into mailbox inbox.

    Idempotent: uses cursor tracking and stable message IDs (evt_{event.id}).
    """
    synced_ids: set[str] = set()
    if cursor_file and cursor_file.is_file():
        try:
            data = json.loads(cursor_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                synced_ids = set(data)
            elif isinstance(data, dict):
                synced_ids = set(data.get("synced_ids", []))
        except Exception:
            synced_ids = set()

    events = read_events(project)
    published: list[str] = []

    for event in events:
        event_id = event.get("id", "") if isinstance(event, dict) else getattr(event, "id", "")
        if not event_id or event_id in synced_ids:
            continue
        if not is_actionable_event(event):
            continue

        message_id = f"evt_{event_id}"
        if isinstance(event, dict):
            payload = {
                "event_id": event_id,
                "ts": event.get("ts", ""),
                "actor": event.get("actor", ""),
                "kind": event.get("kind", ""),
                "step": event.get("step", ""),
                "summary": event.get("summary", ""),
                "refs": list(event.get("refs") or ()),
                "actionable": True,
            }
        else:
            payload = {
                "event_id": event_id,
                "ts": getattr(event, "ts", ""),
                "actor": getattr(event, "actor", ""),
                "kind": getattr(event, "kind", ""),
                "step": getattr(event, "step", ""),
                "summary": getattr(event, "summary", ""),
                "refs": list(getattr(event, "refs", ())),
                "actionable": True,
            }
        try:
            box.publish(message_id, payload)
            published.append(message_id)
            synced_ids.add(event_id)
        except MailboxRejected:
            # Permanent (secret, size, id collision): retrying cannot help.
            synced_ids.add(event_id)
        except OSError:
            # Transient (locked file, full disk): leave it unsynced so the next cycle retries.
            continue

    if cursor_file:
        cursor_file.parent.mkdir(parents=True, exist_ok=True)
        cursor_file.write_text(
            json.dumps(sorted(list(synced_ids)), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    return published


def dispatch_mailbox_messages(
    box: Mailbox,
    sender_fn: Callable[[str], bool] | None = None,
    consumer_id: str = "adapter",
) -> list[dict[str, Any]]:
    """Dispatch inbox messages.

    If sender_fn is None, preserves messages in inbox (durable pull fallback).
    If sender_fn returns True, acks the message.
    If sender_fn returns False or raises, nacks the message back to inbox.
    """
    inbox_ids = box.list_inbox()
    results: list[dict[str, Any]] = []

    if sender_fn is None:
        for msg_id in inbox_ids:
            results.append({"message_id": msg_id, "status": "HELD"})
        return results

    for msg_id in inbox_ids:
        claim = box.claim(msg_id, consumer_id)
        if claim is None:
            continue

        try:
            text = format_mailbox_notice(claim.payload if isinstance(claim.payload, dict) else {})
            ok = sender_fn(text)
        except Exception:
            ok = False

        if ok:
            box.ack(claim)
            results.append({"message_id": msg_id, "status": "ACK"})
        else:
            box.nack(claim)
            results.append({"message_id": msg_id, "status": "NACK"})

    return results
