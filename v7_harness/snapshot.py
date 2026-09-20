"""
Snapshot module for v7 harness.

Generates deterministic environment snapshots:
- For Git repositories: HEAD commit hash, status porcelain, diff patch.
- For Non-Git directories: Deterministic file manifest (sorted relative paths, file sizes, SHA-256 content hashes).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

DEFAULT_EXCLUDES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    ".coord/receipts",
}


@dataclass
class ManifestEntry:
    path: str
    size: int
    sha256: str


@dataclass
class Snapshot:
    snapshot_type: str  # "GIT" or "NON_GIT"
    root_path: str
    timestamp: str
    snapshot_hash: str
    git_head: Optional[str] = None
    git_status: Optional[str] = None
    git_diff: Optional[str] = None
    manifest: list[ManifestEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Snapshot:
        manifest_entries = [
            ManifestEntry(**entry) for entry in data.get("manifest", [])
        ]
        return cls(
            snapshot_type=data["snapshot_type"],
            root_path=data["root_path"],
            timestamp=data["timestamp"],
            snapshot_hash=data["snapshot_hash"],
            git_head=data.get("git_head"),
            git_status=data.get("git_status"),
            git_diff=data.get("git_diff"),
            manifest=manifest_entries,
        )


def _is_git_repository(path: Path) -> bool:
    """Check if the directory is inside a valid git repository."""
    # Quick check for .git dir or file
    if (path / ".git").exists():
        return True
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(path),
            capture_output=True,
            text=True,
            check=False,
            shell=False,
        )
        return res.returncode == 0 and res.stdout.strip() == "true"
    except Exception:
        return False


def _hash_file(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def create_git_snapshot(repo_path: Path, timestamp: str) -> Snapshot:
    """Create a snapshot from a Git repository based on HEAD, status, and diff."""
    # 1. HEAD
    try:
        head_proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=False,
            shell=False,
        )
        head_commit = head_proc.stdout.strip() if head_proc.returncode == 0 else "UNCOMMITTED_ROOT"
    except Exception:
        head_commit = "UNKNOWN_HEAD"

    # 2. Status porcelain
    try:
        status_proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=False,
            shell=False,
        )
        git_status = status_proc.stdout
    except Exception:
        git_status = ""

    # 3. Diff (both staged and unstaged)
    try:
        diff_proc = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=False,
            shell=False,
        )
        git_diff = diff_proc.stdout if diff_proc.returncode == 0 else ""
        if not git_diff:
            # Maybe HEAD doesn't exist yet, try plain diff
            diff_proc2 = subprocess.run(
                ["git", "diff"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                check=False,
                shell=False,
            )
            git_diff = diff_proc2.stdout
    except Exception:
        git_diff = ""

    payload = f"GIT|{head_commit}|{git_status}|{git_diff}"
    snap_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    return Snapshot(
        snapshot_type="GIT",
        root_path=str(repo_path.resolve()),
        timestamp=timestamp,
        snapshot_hash=snap_hash,
        git_head=head_commit,
        git_status=git_status,
        git_diff=git_diff,
        manifest=[],
    )


def create_non_git_snapshot(
    root_path: Path,
    timestamp: str,
    excludes: Optional[Sequence[str]] = None,
) -> Snapshot:
    """Create a deterministic snapshot for non-git folders using a file manifest."""
    exclude_set = set(DEFAULT_EXCLUDES)
    if excludes:
        exclude_set.update(excludes)

    manifest: list[ManifestEntry] = []

    for root, dirs, files in os.walk(root_path):
        # Modify dirs in-place to skip excluded directories
        dirs[:] = [
            d for d in dirs
            if d not in exclude_set
            and not any((Path(root) / d).resolve().match(ex) for ex in exclude_set)
        ]

        for file in files:
            if file in exclude_set or file.endswith(".pyc"):
                continue
            full_path = Path(root) / file
            try:
                rel_path = full_path.relative_to(root_path).as_posix()
            except ValueError:
                rel_path = str(full_path)

            if any(rel_path.startswith(ex) or f"/{ex}/" in f"/{rel_path}/" for ex in exclude_set):
                continue

            try:
                size = full_path.stat().st_size
                sha256_hash = _hash_file(full_path)
                manifest.append(ManifestEntry(path=rel_path, size=size, sha256=sha256_hash))
            except (OSError, PermissionError):
                continue

    # Sort deterministically by relative path
    manifest.sort(key=lambda m: m.path)

    # Compute deterministic snapshot hash from sorted manifest
    manifest_payload = "".join(f"{m.path}:{m.size}:{m.sha256}\n" for m in manifest)
    snap_hash = hashlib.sha256(manifest_payload.encode("utf-8")).hexdigest()

    return Snapshot(
        snapshot_type="NON_GIT",
        root_path=str(root_path.resolve()),
        timestamp=timestamp,
        snapshot_hash=snap_hash,
        manifest=manifest,
    )


def take_snapshot(
    target_path: Optional[Path | str] = None,
    force_non_git: bool = False,
    excludes: Optional[Sequence[str]] = None,
) -> Snapshot:
    """Take a snapshot, automatically selecting Git or deterministic Non-Git mode."""
    root = Path(target_path).resolve() if target_path else Path.cwd().resolve()
    ts = datetime.now(timezone.utc).isoformat()

    if not force_non_git and _is_git_repository(root):
        return create_git_snapshot(root, ts)
    else:
        return create_non_git_snapshot(root, ts, excludes=excludes)
