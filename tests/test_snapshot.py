"""
Tests for Deterministic Snapshots (Acceptance #6).
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from v7_harness.snapshot import (
    create_non_git_snapshot,
    take_snapshot,
)


class TestSnapshot(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_deterministic_non_git_manifest(self):
        # Create directory hierarchy with files
        (self.root / "sub").mkdir()
        (self.root / "b.txt").write_text("file b content", encoding="utf-8")
        (self.root / "a.txt").write_text("file a content", encoding="utf-8")
        (self.root / "sub" / "c.txt").write_text("file c content", encoding="utf-8")

        snap1 = create_non_git_snapshot(self.root, timestamp="2026-09-17T00:00:00Z")
        snap2 = create_non_git_snapshot(self.root, timestamp="2026-09-17T00:00:00Z")

        # Manifest order must be deterministic (sorted)
        paths = [m.path for m in snap1.manifest]
        self.assertEqual(paths, ["a.txt", "b.txt", "sub/c.txt"])
        self.assertEqual(snap1.snapshot_hash, snap2.snapshot_hash)
        self.assertEqual(snap1.snapshot_type, "NON_GIT")

    def test_file_modification_changes_manifest_hash(self):
        (self.root / "file.txt").write_text("version 1", encoding="utf-8")
        snap1 = create_non_git_snapshot(self.root, timestamp="2026-09-17T00:00:00Z")

        (self.root / "file.txt").write_text("version 2", encoding="utf-8")
        snap2 = create_non_git_snapshot(self.root, timestamp="2026-09-17T00:00:00Z")

        self.assertNotEqual(snap1.snapshot_hash, snap2.snapshot_hash)

    def test_git_snapshot_in_git_repo(self):
        # Check if git is available
        git_path = shutil.which("git")
        if not git_path:
            self.skipTest("git not available in PATH")

        # Initialize temporary git repo
        repo_dir = self.root / "git_repo"
        repo_dir.mkdir()
        try:
            subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_dir), check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=str(repo_dir), check=True, capture_output=True)
            (repo_dir / "code.py").write_text("x = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo_dir), check=True, capture_output=True)

            snap = take_snapshot(repo_dir)
            self.assertEqual(snap.snapshot_type, "GIT")
            self.assertIsNotNone(snap.git_head)
            self.assertNotEqual(snap.git_head, "UNCOMMITTED_ROOT")
        except (subprocess.SubprocessError, PermissionError):
            self.skipTest("Git execution restricted in current environment")


if __name__ == "__main__":
    unittest.main()
