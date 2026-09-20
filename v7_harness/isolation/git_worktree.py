"""Git fixture worktree adapter for isolated workspace execution."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from v7_harness.isolation.errors import (
    GitWorktreeError,
    PathOutsideRootError,
)
from v7_harness.isolation.manifest import (
    DeterministicManifest,
    PatchBundle,
    build_manifest,
    create_patch_bundle,
)
from v7_harness.isolation.security import (
    assert_no_reparse_or_symlink,
)


@dataclass(frozen=True)
class GitWorktreeContext:
    repo_path: Path
    worktree_path: Path
    branch_name: str
    base_commit: str
    base_manifest: DeterministicManifest
    base_manifest_hash: str

    def create_patch_bundle(self, metadata: dict[str, Any] | None = None) -> PatchBundle:
        """Create content-addressed patch bundle between base worktree and current state."""
        target_manifest = build_manifest(self.worktree_path)
        return create_patch_bundle(
            base_manifest=self.base_manifest,
            target_manifest=target_manifest,
            base_dir=self.repo_path,
            target_dir=self.worktree_path,
            metadata=metadata,
        )

    def cleanup(self) -> None:
        """Remove worktree and clean up branch."""
        GitWorktreeAdapter.remove_worktree(
            repo_path=self.repo_path,
            worktree_path=self.worktree_path,
            branch_name=self.branch_name,
        )


class GitWorktreeAdapter:
    """Manages Git worktree lifecycle for test fixtures and isolated Git executions."""

    @staticmethod
    def _run_git(args: list[str], cwd: Path) -> str:
        try:
            res = subprocess.run(
                ["git"] + args,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                check=False,
                shell=False,
            )
            if res.returncode != 0:
                raise GitWorktreeError(
                    f"Git command failed: git {' '.join(args)} (exit {res.returncode}): {res.stderr.strip()}"
                )
            return res.stdout.strip()
        except OSError as exc:
            raise GitWorktreeError(f"Failed to execute git subprocess: {exc}")

    @classmethod
    def create_worktree(
        cls,
        repo_path: Path,
        worktree_path: Path,
        branch_name: str,
        base_commit: str = "HEAD",
        excludes: Sequence[str] | None = None,
    ) -> GitWorktreeContext:
        """
        Create a new Git worktree at worktree_path for branch_name at base_commit.
        Fails closed on reparse points, invalid repo, or git errors.
        """
        canonical_repo = repo_path.resolve()
        assert_no_reparse_or_symlink(canonical_repo)

        # Confirm git repository
        is_git = cls._run_git(["rev-parse", "--is-inside-work-tree"], cwd=canonical_repo)
        if is_git != "true":
            raise GitWorktreeError(f"Directory is not inside a git repository: {canonical_repo}")

        # Resolve base commit hash
        resolved_commit = cls._run_git(["rev-parse", base_commit], cwd=canonical_repo)

        # Worktree destination must not exist or be empty
        canonical_worktree = worktree_path.resolve()
        if canonical_worktree.exists():
            if any(canonical_worktree.iterdir()):
                raise GitWorktreeError(f"Worktree path already exists and is not empty: {canonical_worktree}")
            canonical_worktree.rmdir()

        # Add worktree
        cls._run_git(
            ["worktree", "add", "-b", branch_name, str(canonical_worktree), resolved_commit],
            cwd=canonical_repo,
        )
        assert_no_reparse_or_symlink(canonical_worktree)

        # Build base manifest of the worktree
        base_manifest = build_manifest(canonical_worktree, excludes=excludes)

        return GitWorktreeContext(
            repo_path=canonical_repo,
            worktree_path=canonical_worktree,
            branch_name=branch_name,
            base_commit=resolved_commit,
            base_manifest=base_manifest,
            base_manifest_hash=base_manifest.manifest_hash,
        )

    @classmethod
    def remove_worktree(cls, repo_path: Path, worktree_path: Path, branch_name: str | None = None) -> None:
        """Remove worktree and optionally delete the associated branch."""
        canonical_repo = repo_path.resolve()
        canonical_worktree = worktree_path.resolve()

        try:
            cls._run_git(["worktree", "remove", "--force", str(canonical_worktree)], cwd=canonical_repo)
        except GitWorktreeError:
            # Fallback if worktree directory was already deleted manually
            cls._run_git(["worktree", "prune"], cwd=canonical_repo)
            if canonical_worktree.exists():
                shutil.rmtree(canonical_worktree, ignore_errors=True)

        if branch_name:
            try:
                cls._run_git(["branch", "-D", branch_name], cwd=canonical_repo)
            except GitWorktreeError:
                pass
