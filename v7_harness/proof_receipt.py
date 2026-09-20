"""
Proof receipt module for v7 harness.

Captures command, exit code, stdout/stderr, working directory, timestamp, actor,
and deterministic SHA-256 output hash to serve as unforgeable execution evidence.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence


@dataclass
class ProofReceipt:
    receipt_id: str
    task_id: str
    actor: str
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    output_hash: str
    timestamp: str
    cwd: str
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProofReceipt:
        return cls(
            receipt_id=data["receipt_id"],
            task_id=data["task_id"],
            actor=data["actor"],
            command=list(data["command"]) if isinstance(data["command"], list) else [str(data["command"])],
            exit_code=int(data["exit_code"]),
            stdout=str(data.get("stdout", "")),
            stderr=str(data.get("stderr", "")),
            output_hash=str(data["output_hash"]),
            timestamp=str(data["timestamp"]),
            cwd=str(data.get("cwd", "")),
            passed=bool(data.get("passed", data.get("exit_code") == 0)),
        )


def compute_proof_hash(
    command: Sequence[str],
    exit_code: int,
    stdout: str,
    stderr: str,
    cwd: str,
    timestamp: str,
) -> str:
    """Compute deterministic SHA-256 hash of execution output and metadata."""
    cmd_str = " ".join(command)
    payload = f"{cmd_str}|{exit_code}|{cwd}|{timestamp}|{stdout}|{stderr}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ProofReceiptStore:
    """Stores and verifies proof receipts in an append-only JSONL format."""

    def __init__(self, storage_path: Optional[Path | str] = None):
        self.storage_path = Path(storage_path) if storage_path else None
        self._receipts: list[ProofReceipt] = []
        if self.storage_path and self.storage_path.exists():
            self._load()

    def _load(self) -> None:
        if not self.storage_path or not self.storage_path.exists():
            return
        receipts: list[ProofReceipt] = []
        with open(self.storage_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    receipts.append(ProofReceipt.from_dict(data))
                except Exception as exc:
                    raise ValueError(f"Corrupted proof receipt at line {line_no}: {exc}") from exc
        self._receipts = receipts

    @property
    def receipts(self) -> list[ProofReceipt]:
        return list(self._receipts)

    def record(
        self,
        task_id: str,
        actor: str,
        command: Sequence[str],
        exit_code: int,
        stdout: str,
        stderr: str,
        cwd: str,
        timestamp: Optional[str] = None,
        receipt_id: Optional[str] = None,
    ) -> ProofReceipt:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        rid = receipt_id or f"RCP-{len(self._receipts) + 1:04d}"
        cmd_list = list(command)
        out_hash = compute_proof_hash(
            command=cmd_list,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            cwd=cwd,
            timestamp=ts,
        )

        receipt = ProofReceipt(
            receipt_id=rid,
            task_id=task_id,
            actor=actor,
            command=cmd_list,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            output_hash=out_hash,
            timestamp=ts,
            cwd=cwd,
            passed=(exit_code == 0),
        )

        self._receipts.append(receipt)

        if self.storage_path:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(receipt.to_dict(), ensure_ascii=False) + "\n")

        return receipt

    def verify_receipt(self, receipt: ProofReceipt) -> tuple[bool, str]:
        """Verify that a receipt's output hash matches its contents."""
        recalculated = compute_proof_hash(
            command=receipt.command,
            exit_code=receipt.exit_code,
            stdout=receipt.stdout,
            stderr=receipt.stderr,
            cwd=receipt.cwd,
            timestamp=receipt.timestamp,
        )
        if recalculated != receipt.output_hash:
            return False, f"Hash mismatch: recorded '{receipt.output_hash}' != calculated '{recalculated}'"
        return True, "OK"


def run_with_receipt(
    command: Sequence[str],
    task_id: str,
    actor: str,
    cwd: Optional[Path | str] = None,
    receipt_store: Optional[ProofReceiptStore] = None,
    timeout: Optional[float] = None,
) -> ProofReceipt:
    """Execute a command and generate an unforgeable ProofReceipt."""
    working_dir = str(Path(cwd).resolve()) if cwd else str(Path.cwd().resolve())
    cmd_list = list(command)
    if cmd_list and cmd_list[0] == "--":
        cmd_list = cmd_list[1:]

    if not cmd_list:
        ts = datetime.now(timezone.utc).isoformat()
        store = receipt_store or ProofReceiptStore()
        return store.record(
            task_id=task_id,
            actor=actor,
            command=[],
            exit_code=127,
            stdout="",
            stderr="No command specified",
            cwd=working_dir,
            timestamp=ts,
        )

    try:
        proc = subprocess.run(
            cmd_list,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as exc:
        exit_code = 124  # Standard timeout exit code
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else (exc.stdout.decode("utf-8", errors="replace") if exc.stdout else "")
        stderr = f"Command timed out after {timeout} seconds"
    except Exception as exc:
        exit_code = 127
        stdout = ""
        stderr = f"Execution failed: {exc}"

    ts = datetime.now(timezone.utc).isoformat()
    store = receipt_store or ProofReceiptStore()
    return store.record(
        task_id=task_id,
        actor=actor,
        command=cmd_list,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        cwd=working_dir,
        timestamp=ts,
    )
