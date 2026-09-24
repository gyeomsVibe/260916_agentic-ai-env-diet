from __future__ import annotations
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid

class MailboxRejected(ValueError):
    pass

WINDOWS_RESERVED_NAMES = frozenset({
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
})

SECRET_PATTERNS = (
    re.compile(r"sk-[a-zA-Z0-9_\-]{20,}"),
    re.compile(r"ghp_[a-zA-Z0-9]{20,}"),
    re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]{20,}"),
    re.compile(r"(?:api[_-]?key|secret|token|password|credential)[\"']?\s*[:=]\s*[\"']?[a-zA-Z0-9_\-]{16,}", re.IGNORECASE),
)

def _is_symlink_or_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        if hasattr(path, "is_junction") and path.is_junction():
            return True
        st = path.lstat()
        attrs = getattr(st, "st_file_attributes", 0)
        if attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            return True
    except (OSError, ValueError):
        pass
    return False

@dataclass(frozen=True)
class ClaimedMessage:
    message_id: str
    consumer_id: str
    claimed_path: Path
    payload: object
    schema: str = "u23-mailbox-v1"

class Mailbox:
    def __init__(self, root: Path, *, max_message_bytes: int = 65536):
        if max_message_bytes <= 0:
            raise MailboxRejected("max_message_bytes must be positive")
        self.root = Path(root)
        if not self.root.exists() or not self.root.is_dir():
            raise MailboxRejected("root must exist and be a directory")
        if _is_symlink_or_reparse(self.root):
            raise MailboxRejected("root cannot be a symlink or reparse point")
        self.max_message_bytes = max_message_bytes
        self.tmp_dir = self.root / "tmp"
        self.inbox_dir = self.root / "inbox"
        self.claimed_dir = self.root / "claimed"
        self.ack_dir = self.root / "ack"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.claimed_dir.mkdir(parents=True, exist_ok=True)
        self.ack_dir.mkdir(parents=True, exist_ok=True)
        if (
            _is_symlink_or_reparse(self.tmp_dir)
            or _is_symlink_or_reparse(self.inbox_dir)
            or _is_symlink_or_reparse(self.claimed_dir)
            or _is_symlink_or_reparse(self.ack_dir)
        ):
            raise MailboxRejected("directories cannot be symlinks or reparse points")

    def publish(self, message_id: str, payload: object) -> Path:
        if not isinstance(message_id, str):
            raise MailboxRejected("message_id must be a string")
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$", message_id):
            raise MailboxRejected(f"invalid message_id: {message_id!r}")
        if message_id.upper() in WINDOWS_RESERVED_NAMES:
            raise MailboxRejected(f"reserved device name: {message_id}")

        data = {
            "schema": "u23-mailbox-v1",
            "message_id": message_id,
            "payload": payload,
        }
        try:
            encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise MailboxRejected(f"non-JSON payload: {exc}")

        if len(encoded) > self.max_message_bytes:
            raise MailboxRejected(f"encoded message exceeds max_message_bytes ({len(encoded)} > {self.max_message_bytes})")

        raw_str = encoded.decode("utf-8", errors="replace")
        for pat in SECRET_PATTERNS:
            if pat.search(raw_str):
                raise MailboxRejected("secret detected in message payload")

        tmp_name = f"{message_id}_{os.getpid()}_{uuid.uuid4().hex}.tmp"
        tmp_file = self.tmp_dir / tmp_name
        inbox_file = self.inbox_dir / f"{message_id}.json"

        try:
            with open(tmp_file, "wb") as f:
                f.write(encoded)
                f.flush()
                os.fsync(f.fileno())
            try:
                os.link(str(tmp_file), str(inbox_file))
                return inbox_file
            except FileExistsError:
                existing_bytes = inbox_file.read_bytes()
                if existing_bytes == encoded:
                    return inbox_file
                raise MailboxRejected(f"collision with different content for {message_id}")
        finally:
            try:
                tmp_file.unlink(missing_ok=True)
            except OSError:
                pass

    def list_inbox(self) -> list[str]:
        return sorted([p.stem for p in self.inbox_dir.glob("*.json") if p.is_file()])

    def claim(self, message_id: str, consumer_id: str) -> ClaimedMessage | None:
        inbox_file = self.inbox_dir / f"{message_id}.json"
        if not inbox_file.is_file():
            return None
        claimed_name = f"{message_id}_{consumer_id}_{os.getpid()}_{uuid.uuid4().hex}.json"
        claimed_file = self.claimed_dir / claimed_name
        try:
            os.rename(str(inbox_file), str(claimed_file))
        except (FileNotFoundError, FileExistsError, OSError):
            return None
        try:
            data = json.loads(claimed_file.read_text(encoding="utf-8"))
        except Exception:
            return None
        return ClaimedMessage(
            message_id=message_id,
            consumer_id=consumer_id,
            claimed_path=claimed_file,
            payload=data.get("payload"),
            schema=data.get("schema", "u23-mailbox-v1"),
        )

    def ack(self, claim: ClaimedMessage) -> Path:
        ack_file = self.ack_dir / f"{claim.message_id}.json"
        if ack_file.is_file():
            if claim.claimed_path.exists():
                try:
                    claim.claimed_path.unlink(missing_ok=True)
                except OSError:
                    pass
            return ack_file
        if claim.claimed_path.exists():
            try:
                os.link(str(claim.claimed_path), str(ack_file))
            except FileExistsError:
                pass
            finally:
                try:
                    claim.claimed_path.unlink(missing_ok=True)
                except OSError:
                    pass
        return ack_file

    def nack(self, claim: ClaimedMessage) -> Path:
        inbox_file = self.inbox_dir / f"{claim.message_id}.json"
        if claim.claimed_path.exists():
            try:
                os.rename(str(claim.claimed_path), str(inbox_file))
            except (FileExistsError, OSError):
                pass
            finally:
                try:
                    claim.claimed_path.unlink(missing_ok=True)
                except OSError:
                    pass
        return inbox_file

    def recover_stale_claims(self, stale_timeout_s: float = 60.0) -> list[str]:
        recovered: list[str] = []
        now = time.time()
        for path in sorted(self.claimed_dir.glob("*.json")):
            if not path.is_file():
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if now - mtime >= stale_timeout_s:
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    msg_id = data.get("message_id")
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if not isinstance(msg_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", msg_id):
                    continue
                if msg_id.upper() in WINDOWS_RESERVED_NAMES:
                    continue
                target_inbox = self.inbox_dir / f"{msg_id}.json"
                try:
                    os.rename(str(path), str(target_inbox))
                    recovered.append(msg_id)
                except (FileExistsError, OSError):
                    pass
        return recovered
