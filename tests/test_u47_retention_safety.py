"""U47-R1 judge findings: a purge never leaves the project, and a rollup keeps the ledger's exact bytes."""

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from v7_harness import retention


class PurgeEscapeTest(unittest.TestCase):
    def test_a_manifest_path_outside_the_project_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            root = base / "proj"
            root.mkdir()
            victim = base / "outside.txt"
            victim.write_text("keep me", encoding="utf-8")
            sha = hashlib.sha256(victim.read_bytes()).hexdigest()
            manifest = {"manifest_sha256": "m" * 64, "items": [{"path": "../outside.txt", "sha256": sha}]}
            zip_path = root / "a.zip"
            with zipfile.ZipFile(zip_path, "w") as bundle:
                bundle.writestr("../outside.txt", victim.read_bytes())
                bundle.writestr("manifest.json", json.dumps(manifest))
            approval = root / "approval.json"
            approval.write_text(json.dumps({"approver": "user", "action": "purge", "manifest_sha256": "m" * 64}),
                                encoding="utf-8")
            with self.assertRaisesRegex(retention.RetentionRefused, "PATH_ESCAPE"):
                retention.purge_archived(root, zip_path, approval)
            self.assertTrue(victim.is_file())

    def test_user_label_is_not_authenticated_and_never_deletes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            victim = root / "old.txt"
            victim.write_text("keep me", encoding="utf-8")
            sha = hashlib.sha256(victim.read_bytes()).hexdigest()
            manifest = {"manifest_sha256": "m" * 64, "items": [{"path": "old.txt", "sha256": sha}]}
            zip_path = root / "a.zip"
            with zipfile.ZipFile(zip_path, "w") as bundle:
                bundle.writestr("old.txt", victim.read_bytes())
                bundle.writestr("manifest.json", json.dumps(manifest))
            approval = root / "approval.json"
            approval.write_text(json.dumps({"approver": "user", "action": "purge",
                                            "manifest_sha256": "m" * 64}), encoding="utf-8")
            with self.assertRaisesRegex(
                retention.RetentionRefused,
                r"UNAUTHENTICATED_ACTOR.*FRESH_DELETE_APPROVAL_REQUIRED",
            ):
                retention.purge_archived(root, zip_path, approval)
            self.assertTrue(victim.is_file())


class RollupBytesTest(unittest.TestCase):
    def test_kept_rows_keep_their_exact_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "usage.jsonl"
            lines = [json.dumps({"ts": str(i), "event": "e", "status": "s"}) + "\n" for i in range(10)]
            ledger.write_bytes("".join(lines).encode("utf-8"))
            retention.rollup_jsonl(ledger, Path(d) / "archive", max_rows=5, max_bytes=10**9, keep_rows=3)
            self.assertEqual("".join(lines[7:]).encode("utf-8"), ledger.read_bytes())
            self.assertNotIn(b"\r\n", ledger.read_bytes())


if __name__ == "__main__":
    unittest.main()
