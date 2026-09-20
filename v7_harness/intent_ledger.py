"""
Append-only Intent Ledger for v7 harness.

Separates requirements, decisions, rationales, assumptions, and invalidation conditions
from code, preserving the 'why' behind implementation choices with cryptographic hash chaining.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

GENESIS_HASH = "0" * 64

VALID_CATEGORIES = {
    "REQUIREMENT",
    "DECISION",
    "RATIONALE",
    "ASSUMPTION",
    "INVALIDATION_CONDITION",
}


@dataclass
class IntentEntry:
    entry_id: str
    timestamp: str
    task_id: str
    actor: str
    category: str
    content: str
    rationale: Optional[str] = None
    assumption: Optional[str] = None
    invalidation_condition: Optional[str] = None
    superseded_by: Optional[str] = None
    prev_hash: str = GENESIS_HASH
    entry_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntentEntry:
        return cls(
            entry_id=data["entry_id"],
            timestamp=data["timestamp"],
            task_id=data["task_id"],
            actor=data["actor"],
            category=data["category"],
            content=data["content"],
            rationale=data.get("rationale"),
            assumption=data.get("assumption"),
            invalidation_condition=data.get("invalidation_condition"),
            superseded_by=data.get("superseded_by"),
            prev_hash=data.get("prev_hash", GENESIS_HASH),
            entry_hash=data.get("entry_hash", ""),
        )


def compute_entry_hash(
    prev_hash: str,
    entry_id: str,
    timestamp: str,
    task_id: str,
    actor: str,
    category: str,
    content: str,
    rationale: Optional[str],
    assumption: Optional[str],
    invalidation_condition: Optional[str],
    superseded_by: Optional[str],
) -> str:
    payload = (
        f"{prev_hash}|{entry_id}|{timestamp}|{task_id}|{actor}|"
        f"{category}|{content}|{rationale or ''}|{assumption or ''}|"
        f"{invalidation_condition or ''}|{superseded_by or ''}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class IntentLedger:
    """
    Append-only intent ledger with cryptographic hash chaining.
    """

    def __init__(self, ledger_path: Optional[Path | str] = None):
        self.ledger_path = Path(ledger_path) if ledger_path else None
        self._entries: list[IntentEntry] = []
        if self.ledger_path and self.ledger_path.exists():
            self._load_from_disk()

    def _load_from_disk(self) -> None:
        if not self.ledger_path or not self.ledger_path.exists():
            return
        entries: list[IntentEntry] = []
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entries.append(IntentEntry.from_dict(data))
                except Exception as exc:
                    raise ValueError(f"Corrupted intent ledger at line {line_no}: {exc}") from exc
        self._entries = entries

    @property
    def entries(self) -> list[IntentEntry]:
        return list(self._entries)

    @property
    def latest_hash(self) -> str:
        if not self._entries:
            return GENESIS_HASH
        return self._entries[-1].entry_hash

    def append(
        self,
        task_id: str,
        actor: str,
        category: str,
        content: str,
        rationale: Optional[str] = None,
        assumption: Optional[str] = None,
        invalidation_condition: Optional[str] = None,
        timestamp: Optional[str] = None,
        entry_id: Optional[str] = None,
    ) -> IntentEntry:
        if category not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category '{category}'. Must be one of {sorted(VALID_CATEGORIES)}")

        ts = timestamp or datetime.now(timezone.utc).isoformat()
        eid = entry_id or f"INT-{len(self._entries) + 1:04d}"
        prev_h = self.latest_hash

        h = compute_entry_hash(
            prev_hash=prev_h,
            entry_id=eid,
            timestamp=ts,
            task_id=task_id,
            actor=actor,
            category=category,
            content=content,
            rationale=rationale,
            assumption=assumption,
            invalidation_condition=invalidation_condition,
            superseded_by=None,
        )

        entry = IntentEntry(
            entry_id=eid,
            timestamp=ts,
            task_id=task_id,
            actor=actor,
            category=category,
            content=content,
            rationale=rationale,
            assumption=assumption,
            invalidation_condition=invalidation_condition,
            superseded_by=None,
            prev_hash=prev_h,
            entry_hash=h,
        )

        self._entries.append(entry)

        if self.ledger_path:
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.ledger_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

        return entry

    def invalidate(
        self,
        target_entry_id: str,
        actor: str,
        task_id: str,
        reason: str,
    ) -> IntentEntry:
        """
        Record an invalidation of a prior entry by appending an INVALIDATION_CONDITION entry.
        """
        target = next((e for e in self._entries if e.entry_id == target_entry_id), None)
        if not target:
            raise KeyError(f"Entry '{target_entry_id}' not found in intent ledger")

        inv_entry = self.append(
            task_id=task_id,
            actor=actor,
            category="INVALIDATION_CONDITION",
            content=f"Invalidates {target_entry_id}: {reason}",
            rationale=f"Target entry {target_entry_id} invalidated",
            invalidation_condition=reason,
        )
        return inv_entry

    def verify_integrity(self) -> tuple[bool, str]:
        """
        Validates hash chaining and cryptographic integrity of the entire ledger.
        Returns (True, 'OK') or (False, failure_reason).
        """
        if not self._entries:
            return True, "Empty ledger is valid"

        expected_prev = GENESIS_HASH
        for idx, entry in enumerate(self._entries):
            if entry.prev_hash != expected_prev:
                return False, (
                    f"Integrity failure at entry index {idx} ({entry.entry_id}): "
                    f"prev_hash '{entry.prev_hash}' != expected '{expected_prev}'"
                )

            recalculated = compute_entry_hash(
                prev_hash=entry.prev_hash,
                entry_id=entry.entry_id,
                timestamp=entry.timestamp,
                task_id=entry.task_id,
                actor=entry.actor,
                category=entry.category,
                content=entry.content,
                rationale=entry.rationale,
                assumption=entry.assumption,
                invalidation_condition=entry.invalidation_condition,
                superseded_by=entry.superseded_by,
            )

            if recalculated != entry.entry_hash:
                return False, (
                    f"Integrity failure at entry index {idx} ({entry.entry_id}): "
                    f"recorded hash '{entry.entry_hash}' != recalculated '{recalculated}'"
                )

            expected_prev = entry.entry_hash

        return True, "OK"

    def get_active_entries(self, task_id: Optional[str] = None) -> list[IntentEntry]:
        """
        Returns active (non-invalidated) entries, optionally filtered by task_id.
        """
        invalidated_ids: set[str] = set()
        for e in self._entries:
            if e.category == "INVALIDATION_CONDITION" and "Invalidates " in e.content:
                parts = e.content.split(":")
                target_part = parts[0].replace("Invalidates ", "").strip()
                invalidated_ids.add(target_part)

        active = [
            e
            for e in self._entries
            if e.entry_id not in invalidated_ids
            and e.category != "INVALIDATION_CONDITION"
            and (task_id is None or e.task_id == task_id)
        ]
        return active
