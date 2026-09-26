```contract
work_id: U47-R1
worker: agy
goal: Staged, reversible-first cleanup of accumulating records in v7_harness/retention.py: JSONL rollup with verified gz, verified zip archive, user-approved purge, .work age report, rsi retention flags.
inputs:
- v7_harness/retention.py sha256=3b8cefeb54bb39fbb90db0bb93713115e230020d77c9049419e91349cf146f74
- v7_harness/cli.py sha256=8f93694f510131a0d84e1c8b85521f4f5a05f6502fd6b34e93dffc1cd1b1e6af
- tests/u47_r1_check.py sha256=2f1e384504892d0a1239fb063607c49ba103926f27925a1fe4c122bbfe2d3795
allow:
- v7_harness/retention.py
- v7_harness/cli.py
- tests/test_u47_retention_stages.py
acceptance: python tests/u47_r1_check.py
forbidden: design changes; edits outside allow; editing or deleting tests; network; commit/push
stop: two failures with the same cause; input hash mismatch; no output
judge: claude
timeout_s: 1500
remote_budget_tokens: 250000
```

## Instructions for the worker

## Why (context for the worker)

Records keep piling up: the project `.work/` is 1,019 MB (measured 2026-09-26), `.coord/` 201 MB, and the local-model
ledger `~/.cache/olla/usage.jsonl` gains about 144 rows a day. `v7_harness/retention.py` (U42-R1) already builds a
dry-run manifest but never archives or cleans anything. Add a staged, reversible-first cleanup. Deleting data is on
the human list, so the only deleting function requires a user approval file bound to the archive's manifest hash.

## Step 1 — create the frozen acceptance test verbatim

Create `tests/test_u47_retention_stages.py` with EXACTLY the content of the block below (the gate checks its
sha256). Do not change it; make the code satisfy it.

===FILE: tests/test_u47_retention_stages.py===
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
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


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

    def test_purge_refuses_without_a_matching_user_approval(self):
        result = retention.archive_candidates(self.root, self.plan, now=self.now)
        zip_path = self.root / result["zip"]
        for approval in (self.root / "missing.json", self._approve("0" * 64), self._approve(result["manifest_sha256"],
                                                                                           approver="claude"),
                         self._approve(result["manifest_sha256"], action="archive")):
            with self.assertRaises(retention.RetentionRefused):
                retention.purge_archived(self.root, zip_path, approval)
        self.assertTrue(self.old.is_file())

    def test_purge_deletes_only_verified_unchanged_originals(self):
        result = retention.archive_candidates(self.root, self.plan, now=self.now)
        approval = self._approve(result["manifest_sha256"])
        purged = retention.purge_archived(self.root, self.root / result["zip"], approval)
        self.assertEqual("PURGED", purged["status"])
        self.assertEqual(1, purged["deleted"])
        self.assertFalse(self.old.exists())
        self.assertTrue(self.failed.is_file())
        self.assertTrue(self.new.is_file())

    def test_purge_skips_a_file_changed_after_archiving(self):
        result = retention.archive_candidates(self.root, self.plan, now=self.now)
        self.old.write_text(json.dumps({"status": "SUCCEEDED", "edited": True}), encoding="utf-8")
        purged = retention.purge_archived(self.root, self.root / result["zip"], self._approve(result["manifest_sha256"]))
        self.assertEqual(0, purged["deleted"])
        self.assertEqual([".coord/runs/T1/old.json"], purged["skipped_changed"])
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
===END===

## Step 2 — implement in `v7_harness/retention.py` (keep every existing function and behavior)

1. `default_policy()`: add zones `{"path": ".coord/runs", "retention_days": 30, "max_count": 2000, "max_bytes":
   200_000_000, "kind": "runs"}`, `.coord/mailbox/ack` and `.coord/mailbox/claimed` (both generic, 30 days,
   max_count 5000, max_bytes 50_000_000). Never add `.work` as a zone. Put a short comment on each new number.
2. `rollup_jsonl(path, archive_dir, *, max_rows=20_000, max_bytes=5_000_000, keep_rows=5_000) -> dict`
   - Under both limits: return `{"status": "UNDER_LIMIT", "rows": n}` and create nothing.
   - Otherwise, hold the same lock the writer uses (`from v7_harness.coord.stream import _exclusive`;
     `with _exclusive(path.with_suffix(".lock")):`). Split the lines (keepends) into old = all but the last
     `keep_rows`, and kept.
   - Write the old lines' exact bytes gzip-compressed to `archive_dir/<stem>_<first8 of sha256>.jsonl.gz`.
   - Read the file back and decompress it. If its sha256 differs from the old bytes' sha256, raise
     `RetentionRefused("ROLLUP_VERIFY_FAILED")` and leave the live file untouched.
   - Merge the summary into `archive_dir/<stem>.rollup.json`, where every value is a running total:
     - `rows`; `first_ts` and `last_ts`
     - `by_kind`: key `"<event or worker>/<status or outcome>"`, value a count
     - `fake_rows`: rows with `input_tokens == 1` and `output_tokens == 1`, which are test runs
     - `tokens_in_real`, `tokens_out_real` and `wall_s_real`: sums over the non-fake rows
   - Rewrite the live file atomically with the kept lines: write `<path>.tmp`, then `os.replace`.
   - Return `{"status": "ROLLED_UP", "archived_rows", "kept_rows", "archive": str(gz path), "sha256"}`.
3. `archive_candidates(root, plan, *, now) -> dict`
   - If no item has action `ARCHIVE_CANDIDATE`: return `{"status": "NOTHING_TO_ARCHIVE"}`.
   - Otherwise create `.coord/retention_archive/<YYYYmmdd of now>_<manifest_sha256[:8]>.zip`. It holds each candidate
     at its posix relative path, plus `manifest.json`: `{"manifest_sha256", "items": [{"path", "sha256"}]}`.
   - Re-open the zip and verify every entry's sha256; on a mismatch raise `RetentionRefused("ARCHIVE_VERIFY_FAILED")`.
   - Originals stay untouched.
   - Return `{"status": "ARCHIVED", "zip": <posix path relative to root>, "files": n, "manifest_sha256"}`.
4. `purge_archived(root, zip_path, approval_path) -> dict` (stage 3)
   - Refuse with `RetentionRefused` unless all of these hold:
     - The approval file exists and parses as JSON.
     - It has `approver == "user"`, `action == "purge"`, and `manifest_sha256` equal to the zip's manifest.
   - For each manifest item:
     - Original missing: skip it.
     - Current sha256 differs from the manifest: add the path to `skipped_changed` and keep the file.
     - Zip entry's sha256 differs from the manifest: skip it.
     - Otherwise delete the original.
   - Return `{"status": "PURGED", "deleted": n, "skipped_changed": [...]}`.
   - Docstring: agents never run this; B83, a name in a file, is not authentication.
5. `work_dir_report(root, *, now, older_than_days=14) -> dict`
   - Look only at the direct children of `<root>/.work`, using the directory's own mtime and no size walk.
   - Return `{"total": n, "stale": [{"name", "age_days"} ...]}`, oldest first.
   - Never modify anything.

## Step 3 — CLI in `v7_harness/cli.py`

`rsi retention` keeps its current default output. Add:

- `--archive`: runs `archive_candidates` and adds `"archive"` to the JSON.
- `--rollup-olla`: runs `rollup_jsonl(olla.USAGE_LOG, olla.USAGE_LOG.parent / "archive")` and adds `"rollup"`.
- `--purge ZIP --approval FILE`: runs `purge_archived` and prints a REFUSED JSON with exit 2 on `RetentionRefused`.
- It always adds `"work_report": work_dir_report(project, now=...)`.


## Output

- Edit the files under `allow` directly with your file tools. Your reply is not applied: ===FILE / ===EDIT blocks in it are ignored. End with one line saying what you changed. Do not claim success; the acceptance command decides.
