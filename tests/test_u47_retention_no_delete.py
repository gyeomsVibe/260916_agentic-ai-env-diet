"""U47-R1d: file labels never authenticate destructive retention."""

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from v7_harness import retention


class DeleteBoundaryTest(unittest.TestCase):
    def _archive(self, root: Path, rel: str = ".coord/runs/T1/old.json") -> tuple[Path, Path]:
        original = root / rel
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_text("keep", encoding="utf-8")
        digest = hashlib.sha256(original.read_bytes()).hexdigest()
        manifest = {"manifest_sha256": "a" * 64, "items": [{"path": rel, "sha256": digest}]}
        archive = root / ".coord" / "retention_archive" / "safe.zip"
        archive.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr(rel, original.read_bytes())
            bundle.writestr("manifest.json", json.dumps(manifest))
        approval = root / "approval.json"
        approval.write_text(
            json.dumps({"approver": "user", "action": "purge", "manifest_sha256": "a" * 64}),
            encoding="utf-8",
        )
        return original, approval

    def test_user_name_in_json_never_authorizes_unlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original, approval = self._archive(root)
            archive = root / ".coord" / "retention_archive" / "safe.zip"
            with mock.patch.object(Path, "unlink", side_effect=AssertionError("unlink must not run")):
                with self.assertRaisesRegex(
                    retention.RetentionRefused,
                    r"UNAUTHENTICATED_ACTOR.*FRESH_DELETE_APPROVAL_REQUIRED",
                ):
                    retention.purge_archived(root, archive, approval)
            self.assertTrue(original.is_file())

    def test_archive_rejects_candidate_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            outside = root.parent / "outside.txt"
            outside.write_text("keep", encoding="utf-8")
            digest = hashlib.sha256(outside.read_bytes()).hexdigest()
            plan = {
                "manifest_sha256": "b" * 64,
                "items": [{"path": "../outside.txt", "sha256": digest, "action": "ARCHIVE_CANDIDATE"}],
            }
            with self.assertRaisesRegex(retention.RetentionRefused, "PATH_ESCAPE"):
                retention.archive_candidates(root, plan, now=0)
            self.assertTrue(outside.is_file())

    def test_purge_rejects_manifest_path_escape_without_unlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            outside = root.parent / "outside.txt"
            outside.write_text("keep", encoding="utf-8")
            digest = hashlib.sha256(outside.read_bytes()).hexdigest()
            archive = root / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("../outside.txt", outside.read_bytes())
                bundle.writestr(
                    "manifest.json",
                    json.dumps({"manifest_sha256": "c" * 64,
                                "items": [{"path": "../outside.txt", "sha256": digest}]}),
                )
            approval = root / "approval.json"
            approval.write_text("{}", encoding="utf-8")
            with mock.patch.object(Path, "unlink", side_effect=AssertionError("unlink must not run")):
                with self.assertRaisesRegex(retention.RetentionRefused, "PATH_ESCAPE"):
                    retention.purge_archived(root, archive, approval)
            self.assertTrue(outside.is_file())


if __name__ == "__main__":
    unittest.main()
