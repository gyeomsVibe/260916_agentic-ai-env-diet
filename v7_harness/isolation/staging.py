"""Non-Git staging copy adapter with deterministic manifest and zero source mutation verification."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from v7_harness.isolation.errors import (
    ReparsePointError,
    SourceMutationError,
)
from v7_harness.isolation.manifest import (
    DEFAULT_EXCLUDES,
    DeterministicManifest,
    PatchBundle,
    build_manifest,
    create_patch_bundle,
)
from v7_harness.isolation.security import (
    assert_no_reparse_or_symlink,
    is_symlink_or_reparse,
    validate_safe_relative_path,
)


@dataclass(frozen=True)
class StagingWorkspace:
    source_dir: Path
    staging_dir: Path
    base_manifest: DeterministicManifest
    base_manifest_hash: str
    excludes: Sequence[str] | None = None

    def create_patch_bundle(self, metadata: dict[str, Any] | None = None) -> PatchBundle:
        """Create content-addressed patch bundle between base and current staging state."""
        target_manifest = build_manifest(self.staging_dir, excludes=self.excludes)
        return create_patch_bundle(
            base_manifest=self.base_manifest,
            target_manifest=target_manifest,
            base_dir=self.source_dir,
            target_dir=self.staging_dir,
            metadata=metadata,
        )

    def cleanup(self) -> None:
        """Remove temporary staging directory safely."""
        if self.staging_dir.exists():
            shutil.rmtree(self.staging_dir, ignore_errors=True)


class NonGitStagingAdapter:
    """Creates an isolated staging copy from a non-Git source directory."""

    def __init__(self, excludes: Sequence[str] | None = None) -> None:
        self.excludes = excludes

    def create_staging(
        self,
        source_dir: Path,
        staging_dir: Path,
    ) -> StagingWorkspace:
        """
        Copy source_dir to staging_dir deterministically.
        Fail closed if:
        - source_dir contains symlinks or reparse points
        - source_dir mutates during the copy process
        - staging copy does not match base manifest
        """
        canonical_source = source_dir.resolve()
        assert_no_reparse_or_symlink(canonical_source)

        # 1. Pre-copy base manifest
        base_manifest = build_manifest(canonical_source, excludes=self.excludes)

        # Ensure staging dir is empty and clean
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)
        canonical_staging = staging_dir.resolve()
        assert_no_reparse_or_symlink(canonical_staging)

        # 2. Replicate directory hierarchy (excluding excluded directories)
        exclude_set = set(DEFAULT_EXCLUDES)
        if self.excludes:
            exclude_set.update(self.excludes)
        for root, dirs, _ in os.walk(canonical_source):
            root_path = Path(root)
            surviving = []
            for d in dirs:
                dir_full = root_path / d
                if is_symlink_or_reparse(dir_full):
                    raise ReparsePointError(f"Symlink/reparse directory detected during copy: {dir_full}")
                rel_d = str(dir_full.relative_to(canonical_source)).replace("\\", "/")
                if d in exclude_set or rel_d in exclude_set:
                    continue
                surviving.append(d)
                (canonical_staging / rel_d).mkdir(parents=True, exist_ok=True)
            dirs[:] = surviving

        # 3. Copy files recorded in base manifest
        for entry in base_manifest.entries:
            safe_rel = validate_safe_relative_path(entry.path)
            src_file = canonical_source / safe_rel
            dst_file = canonical_staging / safe_rel

            # Safety assertion on source file
            if is_symlink_or_reparse(src_file):
                raise ReparsePointError(f"Symlink/reparse point detected during copy: {src_file}")

            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)

        # 3. Post-copy verification: ensure source was NOT mutated during copy
        post_source_manifest = build_manifest(canonical_source, excludes=self.excludes)
        if post_source_manifest.manifest_hash != base_manifest.manifest_hash:
            # Clean up staging before raising
            shutil.rmtree(canonical_staging, ignore_errors=True)
            raise SourceMutationError(
                f"CRITICAL: Source directory mutated during staging copy: "
                f"before={base_manifest.manifest_hash} after={post_source_manifest.manifest_hash}"
            )

        # 4. Verify staging copy matches base manifest
        staging_manifest = build_manifest(canonical_staging, excludes=self.excludes)
        if staging_manifest.manifest_hash != base_manifest.manifest_hash:
            shutil.rmtree(canonical_staging, ignore_errors=True)
            raise SourceMutationError(
                f"Staging copy manifest mismatch: expected={base_manifest.manifest_hash} "
                f"actual={staging_manifest.manifest_hash}"
            )

        return StagingWorkspace(
            source_dir=canonical_source,
            staging_dir=canonical_staging,
            base_manifest=base_manifest,
            base_manifest_hash=base_manifest.manifest_hash,
            excludes=self.excludes,
        )
