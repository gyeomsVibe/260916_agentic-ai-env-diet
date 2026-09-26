"""U47-R1 frozen acceptance: staged, reversible-first cleanup of accumulating records (written by the judge, Claude).

Stages: 0 plan (existing, dry run) -> 1 roll up an oversized JSONL ledger (old rows kept verbatim in a verified .gz,
summary kept forever) -> 2 archive old files into a verified zip (originals untouched) -> 3 purge originals only with
a user approval bound to the archive's manifest hash. `.work/` is only reported, never touched.
"""

import gzip
import hashlib
import json
import os
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

from v7_harness import retention


def _rows(n, start=0):
    return [{"ts": f"2026-09-{1 + (i % 28):02d}T00:00:00", "event": "pilot_local", "status": "GENERATED",
             "input_tokens": 1 if i % 3 == 0 else 100, "output_tokens": 1 if i % 3 == 0 else 20, "elapsed_s": 2.0}
            for i in range(start, start + n)]


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Bytes, not text: Windows text mode writes CRLF, and the rollup keeps a ledger's exact bytes (judge fix).
    path.write_bytes("".join(json.dumps(r) + "\n" for r in rows).encode("utf-8"))


class DefaultZonesTest(unittest.TestCase):
    def test_runs_and_mailbox_history_are_zones(self):
        paths = {zone["path"]: zone for zone in retention.default_policy()["zones"]}
        self.assertEqual("runs", paths[".coord/runs"]["kind"])
        self.assertIn(".coord/mailbox/ack", paths)
        self.assertIn(".coord/mailbox/claimed", paths)
        self.assertNotIn(".work", paths)  # .work is reported, never a zone


class RollupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ledger = self.root / "usage.jsonl"
        self.archive = self.root / "archive"

    def tearDown(self):
        self.tmp.cleanup()

    def test_under_limit_changes_nothing(self):
        _write_jsonl(self.ledger, _rows(10))
        before = self.ledger.read_bytes()
        result = retention.rollup_jsonl(self.ledger, self.archive, max_rows=20, max_bytes=10**9, keep_rows=5)
        self.assertEqual("UNDER_LIMIT", result["status"])
        self.assertEqual(before, self.ledger.read_bytes())
        self.assertFalse(self.archive.exists())

    def test_over_limit_keeps_newest_rows_and_archives_the_rest_verbatim(self):
        rows = _rows(30)
        _write_jsonl(self.ledger, rows)
        original = self.ledger.read_text(encoding="utf-8").splitlines(keepends=True)
        result = retention.rollup_jsonl(self.ledger, self.archive, max_rows=20, max_bytes=10**9, keep_rows=5)
        self.assertEqual("ROLLED_UP", result["status"])
        self.assertEqual(25, result["archived_rows"])
        self.assertEqual(5, result["kept_rows"])
        self.assertEqual("".join(original[25:]), self.ledger.read_text(encoding="utf-8"))
        gz = Path(result["archive"])
        self.assertTrue(gz.is_file())
        archived = gzip.decompress(gz.read_bytes())
        self.assertEqual("".join(original[:25]).encode("utf-8"), archived)
        self.assertEqual(hashlib.sha256(archived).hexdigest(), result["sha256"])

    def test_rollup_summary_accumulates_and_counts_fake_rows(self):
        _write_jsonl(self.ledger, _rows(30))
        retention.rollup_jsonl(self.ledger, self.archive, max_rows=20, max_bytes=10**9, keep_rows=5)
        _write_jsonl(self.ledger, _rows(30, start=30))
        retention.rollup_jsonl(self.ledger, self.archive, max_rows=20, max_bytes=10**9, keep_rows=5)
        summary = json.loads((self.archive / "usage.rollup.json").read_text(encoding="utf-8"))
        self.assertEqual(50, summary["rows"])
        self.assertEqual(50, summary["by_kind"]["pilot_local/GENERATED"])
        fake = sum(1 for i in list(range(25)) + list(range(30, 55)) if i % 3 == 0)
        self.assertEqual(fake, summary["fake_rows"])
        self.assertEqual(sum(100 for i in list(range(25)) + list(range(30, 55)) if i % 3), summary["tokens_in_real"])
        self.assertEqual(2, len(list(self.archive.glob("usage_*.jsonl.gz"))))

    def test_byte_limit_also_triggers(self):
        _write_jsonl(self.ledger, _rows(10))
        result = retention.rollup_jsonl(self.ledger, self.archive, max_rows=10**6, max_bytes=100, keep_rows=2)
        self.assertEqual("ROLLED_UP", result["status"])
        self.assertEqual(2, len(self.ledger.read_text(encoding="utf-8").splitlines()))


class ArchivePurgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        runs = self.root / ".coord" / "runs" / "T1"
        runs.mkdir(parents=True)
        self.old = runs / "old.json"
        self.old.write_text(json.dumps({"status": "SUCCEEDED"}), encoding="utf-8")
        self.failed = runs / "failed.json"
        self.failed.write_text(json.dumps({"status": "FAILED"}), encoding="utf-8")
        self.new = runs / "new.json"
        self.new.write_text(json.dumps({"status": "SUCCEEDED"}), encoding="utf-8")
        self.now = time.time()
        past = self.now - 40 * 86400
        for path in (self.old, self.failed):
            os.utime(path, (past, past))
        self.plan = retention.plan_retention(self.root, retention.default_policy(), now=self.now)

    def tearDown(self):
        self.tmp.cleanup()

    def _approve(self, manifest_sha256, approver="user", action="purge"):
        path = self.root / "approval.json"
        path.write_text(json.dumps({"approver": approver, "action": action, "manifest_sha256": manifest_sha256}),
                        encoding="utf-8")
        return path

    def test_archive_copies_only_candidates_and_leaves_originals(self):
        result = retention.archive_candidates(self.root, self.plan, now=self.now)
        self.assertEqual("ARCHIVED", result["status"])
        self.assertEqual(1, result["files"])
        with zipfile.ZipFile(self.root / result["zip"]) as bundle:
            names = set(bundle.namelist())
            self.assertIn(".coord/runs/T1/old.json", names)
            self.assertIn("manifest.json", names)
            self.assertNotIn(".coord/runs/T1/failed.json", names)  # failure evidence is protected
            self.assertNotIn(".coord/runs/T1/new.json", names)
        self.assertTrue(self.old.is_file())
        self.assertTrue(result["zip"].startswith(".coord/retention_archive/"))

    def test_nothing_to_archive(self):
        plan = retention.plan_retention(self.root, retention.default_policy(), now=self.now - 30 * 86400)
        self.assertEqual("NOTHING_TO_ARCHIVE", retention.archive_candidates(self.root, plan, now=self.now)["status"])

    def test_purge_always_refuses_file_labels_as_authentication(self):
        result = retention.archive_candidates(self.root, self.plan, now=self.now)
        zip_path = self.root / result["zip"]
        for approval in (self.root / "missing.json", self._approve("0" * 64), self._approve(result["manifest_sha256"],
                                                                                           approver="claude"),
                         self._approve(result["manifest_sha256"], action="archive"),
                         self._approve(result["manifest_sha256"])):
            with self.assertRaisesRegex(
                retention.RetentionRefused,
                r"UNAUTHENTICATED_ACTOR.*FRESH_DELETE_APPROVAL_REQUIRED",
            ):
                retention.purge_archived(self.root, zip_path, approval)
        self.assertTrue(self.old.is_file())

    def test_purge_never_deletes_a_verified_unchanged_original(self):
        result = retention.archive_candidates(self.root, self.plan, now=self.now)
        approval = self._approve(result["manifest_sha256"])
        with self.assertRaisesRegex(retention.RetentionRefused, "UNAUTHENTICATED_ACTOR"):
            retention.purge_archived(self.root, self.root / result["zip"], approval)
        self.assertTrue(self.old.is_file())
        self.assertTrue(self.failed.is_file())
        self.assertTrue(self.new.is_file())

    def test_purge_never_deletes_a_file_changed_after_archiving(self):
        result = retention.archive_candidates(self.root, self.plan, now=self.now)
        self.old.write_text(json.dumps({"status": "SUCCEEDED", "edited": True}), encoding="utf-8")
        with self.assertRaisesRegex(retention.RetentionRefused, "UNAUTHENTICATED_ACTOR"):
            retention.purge_archived(
                self.root,
                self.root / result["zip"],
                self._approve(result["manifest_sha256"]),
            )
        self.assertTrue(self.old.is_file())

    def test_apply_retention_still_refuses_delete(self):
        with self.assertRaisesRegex(retention.RetentionRefused, "FRESH_DELETE_APPROVAL_REQUIRED"):
            retention.apply_retention(self.root, self.plan, execute_delete=True)


class WorkReportTest(unittest.TestCase):
    def test_work_folders_are_reported_by_age_and_never_touched(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            old = root / ".work" / "old_run"
            fresh = root / ".work" / "fresh_run"
            old.mkdir(parents=True)
            fresh.mkdir()
            (old / "f.txt").write_text("x", encoding="utf-8")
            now = time.time()
            os.utime(old, (now - 20 * 86400, now - 20 * 86400))
            report = retention.work_dir_report(root, now=now, older_than_days=14)
            self.assertEqual(["old_run"], [item["name"] for item in report["stale"]])
            self.assertEqual(2, report["total"])
            self.assertTrue((old / "f.txt").is_file())


if __name__ == "__main__":
    unittest.main()
