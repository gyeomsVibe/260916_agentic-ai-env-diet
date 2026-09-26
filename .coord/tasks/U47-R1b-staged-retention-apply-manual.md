```contract
work_id: U47-R1b
worker: apply
goal: Apply Antigravity's U47-R1 staged retention (rollup, archive, user-approved purge, .work report, CLI flags) with two judge fixes: purge never deletes outside the project; rollup keeps exact bytes.
inputs:
- v7_harness/retention.py sha256=3b8cefeb54bb39fbb90db0bb93713115e230020d77c9049419e91349cf146f74
- v7_harness/cli.py sha256=8f93694f510131a0d84e1c8b85521f4f5a05f6502fd6b34e93dffc1cd1b1e6af
- tests/u47_r1_check.py sha256=2f1e384504892d0a1239fb063607c49ba103926f27925a1fe4c122bbfe2d3795
allow:
- v7_harness/retention.py
- v7_harness/cli.py
- tests/test_u47_retention_stages.py
- tests/test_u47_retention_safety.py
acceptance: python tests/u47_r1_check.py && python -m unittest discover -s tests
forbidden: design changes; edits outside allow; editing or deleting tests; network; commit/push
stop: two failures with the same cause; input hash mismatch; no output
judge: antigravity
timeout_s: 900
remote_budget_tokens: 0
```

## Instructions for the worker

Apply the U47-R1 bundle: Antigravity's implementation (run U47-R1 a001, stage passed the frozen acceptance) plus two judge fixes (purge path escape, rollup byte preservation).

===FILE: v7_harness/retention.py===
"""U42-R1 / U47-R1: deletion-free retention planning, staged reversible archiving and user-approved purge.

A retention plan is only ever a dry-run manifest: which files are old or excess for their zone,
which are protected (failure/P1/approval evidence), and which are excluded because their run is
still active or locked. Nothing in this module deletes a file by default. Archiving/restoring and real
deletion are separate, explicitly-approved steps; `apply_retention` with `execute_delete=True` always refuses.
Stage 1 rolls up oversized JSONL ledgers into verified .gz archives and summaries.
Stage 2 archives old files into verified zip bundles.
Stage 3 purges originals only with explicit user approval bound to the archive manifest hash.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import time
import zipfile
from pathlib import Path
from typing import Any, Optional


class RetentionRefused(Exception):
    """Raised when a retention plan or apply call would violate a safety invariant."""


def default_policy() -> dict[str, Any]:
    """Deterministic default retention zones covering the harness's own runtime state."""
    return {
        "zones": [
            {"path": ".coord/usage", "retention_days": 180, "max_count": 5000,
             "max_bytes": 50_000_000, "kind": "generic"},
            {"path": ".coord/stream", "retention_days": 90, "max_count": 5000,
             "max_bytes": 20_000_000, "kind": "generic"},
            {"path": ".coord/pilot/runs", "retention_days": 30, "max_count": 500,
             "max_bytes": 200_000_000, "kind": "runs"},
            {"path": ".coord/runs", "retention_days": 30,  # 30 days retention window for coord runs
             "max_count": 2000,  # 2,000 maximum run records cap
             "max_bytes": 200_000_000,  # 200MB max total bytes cap
             "kind": "runs"},
            {"path": ".coord/mailbox/ack", "retention_days": 30,  # 30 days retention for acknowledged messages
             "max_count": 5000,  # 5,000 maximum acknowledged messages cap
             "max_bytes": 50_000_000,  # 50MB max total bytes cap
             "kind": "generic"},
            {"path": ".coord/mailbox/claimed", "retention_days": 30,  # 30 days retention for claimed messages
             "max_count": 5000,  # 5,000 maximum claimed messages cap
             "max_bytes": 50_000_000,  # 50MB max total bytes cap
             "kind": "generic"},
            {"path": ".work/logs", "retention_days": 30, "max_count": 200,
             "max_bytes": 100_000_000, "kind": "generic"},
            {"path": ".coord/approvals", "retention_days": 3650, "max_count": 100000,
             "max_bytes": 50_000_000, "kind": "approvals"},
            {"path": ".coord/rsi", "retention_days": 365, "max_count": 2000,
             "max_bytes": 50_000_000, "kind": "generic"},
            {"path": ".coord/sentinel/receipts", "retention_days": 90, "max_count": 5000,
             "max_bytes": 50_000_000, "kind": "generic"},
        ],
    }


def _resolve_zone_path(root: Path, zone_path: str) -> Path:
    root_resolved = Path(root).resolve()
    target = (root_resolved / zone_path).resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError:
        raise RetentionRefused(f"PATH_ESCAPE: zone path escapes the retention root: {zone_path}")
    return target


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_run_status(path: Path) -> tuple[Optional[str], bool]:
    """Best-effort read of a run/summary JSON file's status and P1-ness. Never raises."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None, False
    if not isinstance(data, dict):
        return None, False
    status = data.get("status")
    is_p1 = bool(data.get("p1")) or str(status).upper() == "P1"
    return status, is_p1


def plan_retention(root: Path, policy: dict[str, Any], now: float) -> dict[str, Any]:
    """Build a deterministic, deletion-free retention manifest.

    Enumeration is sorted (stable), path escape is rejected, ACTIVE/locked runs are excluded, and
    failure/P1/approval evidence is protected regardless of age. Everything else past its zone's
    retention window is classified ARCHIVE_CANDIDATE with a planned archive/restore path and its
    SHA-256, never deleted here.
    """
    # Normalize Windows short/long path spellings before relative comparisons.
    root = Path(root).resolve()
    items: list[dict[str, Any]] = []

    for zone in policy.get("zones", []):
        zone_path = zone["path"]
        target_dir = _resolve_zone_path(root, zone_path)
        if not target_dir.is_dir():
            continue

        kind = zone.get("kind", "generic")
        retention_days = zone.get("retention_days", 30)

        for path in sorted(p for p in target_dir.rglob("*") if p.is_file()):
            try:
                stat = path.stat()
            except OSError:
                continue
            rel = path.relative_to(root).as_posix()
            age_days = max(0.0, (now - stat.st_mtime) / 86400.0)

            action = "KEEP"
            if kind == "approvals":
                action = "PROTECT"
            elif kind == "runs":
                status, is_p1 = _read_run_status(path)
                if str(status).upper() == "ACTIVE":
                    action = "ACTIVE_EXCLUDE"
                elif str(status).upper() == "FAILED" or is_p1:
                    action = "PROTECT"
                elif age_days >= retention_days:
                    action = "ARCHIVE_CANDIDATE"
            elif age_days >= retention_days:
                action = "ARCHIVE_CANDIDATE"

            item: dict[str, Any] = {
                "path": rel,
                "zone": zone_path,
                "action": action,
                "age_days": round(age_days, 3),
                "size_bytes": stat.st_size,
                "sha256": _file_sha256(path),
            }
            if action == "ARCHIVE_CANDIDATE":
                item["archive_path"] = f".coord/retention_archive/{rel}"
                item["restore_path"] = rel
            items.append(item)

    items.sort(key=lambda entry: entry["path"])
    manifest_sha256 = hashlib.sha256(
        json.dumps(items, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return {"generated_at": now, "policy_zones": len(policy.get("zones", [])),
            "items": items, "manifest_sha256": manifest_sha256}


def apply_retention(root: Path, plan: dict[str, Any], *, execute_delete: bool = False) -> dict[str, Any]:
    """Print/return the plan. Defaults to DRY_RUN; a real delete needs a fresh, separate approval
    and is out of this task's scope, so `execute_delete=True` always refuses."""
    if execute_delete:
        raise RetentionRefused(
            "FRESH_DELETE_APPROVAL_REQUIRED: retention deletion needs a fresh, explicit approval "
            "receipt bound to this manifest hash; this call performs no deletion"
        )
    candidates = [item for item in plan.get("items", []) if item.get("action") == "ARCHIVE_CANDIDATE"]
    return {
        "status": "DRY_RUN",
        "manifest_sha256": plan.get("manifest_sha256"),
        "archive_candidates": len(candidates),
        "items": plan.get("items", []),
    }


def rollup_jsonl(
    path: Path | str,
    archive_dir: Path | str,
    *,
    max_rows: int = 20_000,
    max_bytes: int = 5_000_000,
    keep_rows: int = 5_000,
) -> dict[str, Any]:
    """Roll up an oversized JSONL ledger into a verified .gz archive and running summary."""
    path = Path(path)
    archive_dir = Path(archive_dir)

    if not path.is_file():
        return {"status": "UNDER_LIMIT", "rows": 0}

    content = path.read_bytes().decode("utf-8")  # bytes: text mode rewrites newlines on Windows
    lines = content.splitlines(keepends=True)
    size_bytes = path.stat().st_size
    if len(lines) <= max_rows and size_bytes <= max_bytes:
        return {"status": "UNDER_LIMIT", "rows": len(lines)}

    from v7_harness.coord.stream import _exclusive

    with _exclusive(path.with_suffix(".lock")):
        content = path.read_bytes().decode("utf-8")
        lines = content.splitlines(keepends=True)
        size_bytes = path.stat().st_size
        if len(lines) <= max_rows and size_bytes <= max_bytes:
            return {"status": "UNDER_LIMIT", "rows": len(lines)}

        if keep_rows > 0:
            if len(lines) > keep_rows:
                old_lines = lines[:-keep_rows]
                kept_lines = lines[-keep_rows:]
            else:
                old_lines = []
                kept_lines = lines
        else:
            old_lines = lines[:]
            kept_lines = []

        if not old_lines:
            return {"status": "UNDER_LIMIT", "rows": len(lines)}

        old_bytes = "".join(old_lines).encode("utf-8")
        old_sha256 = hashlib.sha256(old_bytes).hexdigest()

        archive_dir.mkdir(parents=True, exist_ok=True)
        gz_path = archive_dir / f"{path.stem}_{old_sha256[:8]}.jsonl.gz"

        with gzip.open(gz_path, "wb") as gz_file:
            gz_file.write(old_bytes)

        decompressed = gzip.decompress(gz_path.read_bytes())
        if hashlib.sha256(decompressed).hexdigest() != old_sha256:
            raise RetentionRefused("ROLLUP_VERIFY_FAILED")

        parsed_rows: list[dict[str, Any]] = []
        for line in old_lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                parsed_rows.append(json.loads(stripped))
            except json.JSONDecodeError:
                continue

        summary_file = archive_dir / f"{path.stem}.rollup.json"
        summary: dict[str, Any] = {
            "rows": 0,
            "first_ts": None,
            "last_ts": None,
            "by_kind": {},
            "fake_rows": 0,
            "tokens_in_real": 0,
            "tokens_out_real": 0,
            "wall_s_real": 0.0,
        }
        if summary_file.is_file():
            try:
                loaded = json.loads(summary_file.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    summary.update(loaded)
            except Exception:
                pass

        summary["rows"] = summary.get("rows", 0) + len(parsed_rows)

        by_kind = summary.setdefault("by_kind", {})
        fake_rows_add = 0
        tokens_in_add = 0
        tokens_out_add = 0
        wall_s_add = 0.0

        ts_list: list[str] = []
        for r in parsed_rows:
            if not isinstance(r, dict):
                continue
            ts = r.get("ts") or r.get("timestamp")
            if ts:
                ts_list.append(str(ts))

            ev = r.get("event") or r.get("worker") or "unknown"
            st = r.get("status") or r.get("outcome") or "unknown"
            kind_key = f"{ev}/{st}"
            by_kind[kind_key] = by_kind.get(kind_key, 0) + 1

            inp = r.get("input_tokens")
            out = r.get("output_tokens")
            if inp == 1 and out == 1:
                fake_rows_add += 1
            else:
                tokens_in_add += int(inp or 0)
                tokens_out_add += int(out or 0)
                elapsed = r.get("wall_s")
                if elapsed is None:
                    elapsed = r.get("elapsed_s", 0.0)
                wall_s_add += float(elapsed or 0.0)

        summary["fake_rows"] = summary.get("fake_rows", 0) + fake_rows_add
        summary["tokens_in_real"] = summary.get("tokens_in_real", 0) + tokens_in_add
        summary["tokens_out_real"] = summary.get("tokens_out_real", 0) + tokens_out_add
        summary["wall_s_real"] = round(summary.get("wall_s_real", 0.0) + wall_s_add, 3)

        if ts_list:
            min_ts = min(ts_list)
            max_ts = max(ts_list)
            if summary.get("first_ts") is None or min_ts < summary["first_ts"]:
                summary["first_ts"] = min_ts
            if summary.get("last_ts") is None or max_ts > summary["last_ts"]:
                summary["last_ts"] = max_ts

        summary_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

        tmp_path = path.with_name(f"{path.name}.tmp")
        tmp_path.write_bytes("".join(kept_lines).encode("utf-8"))  # exact bytes, no newline translation
        os.replace(tmp_path, path)

        return {
            "status": "ROLLED_UP",
            "archived_rows": len(old_lines),
            "kept_rows": len(kept_lines),
            "archive": str(gz_path),
            "sha256": old_sha256,
        }


def archive_candidates(root: Path | str, plan: dict[str, Any], *, now: float) -> dict[str, Any]:
    """Archive candidate files into a verified zip bundle (originals untouched)."""
    root = Path(root).resolve()
    candidates = [item for item in plan.get("items", []) if item.get("action") == "ARCHIVE_CANDIDATE"]
    if not candidates:
        return {"status": "NOTHING_TO_ARCHIVE"}

    manifest_sha256 = plan.get("manifest_sha256", "")
    date_str = time.strftime("%Y%m%d", time.gmtime(now))
    zip_rel = f".coord/retention_archive/{date_str}_{manifest_sha256[:8]}.zip"
    zip_path = root / zip_rel
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    manifest_data = {
        "manifest_sha256": manifest_sha256,
        "items": [{"path": c["path"], "sha256": c["sha256"]} for c in candidates],
    }

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for c in candidates:
            file_path = root / c["path"]
            bundle.write(file_path, arcname=c["path"])
        bundle.writestr("manifest.json", json.dumps(manifest_data, indent=2, ensure_ascii=False))

    with zipfile.ZipFile(zip_path, "r") as bundle:
        namelist = set(bundle.namelist())
        if "manifest.json" not in namelist:
            raise RetentionRefused("ARCHIVE_VERIFY_FAILED")
        read_manifest = json.loads(bundle.read("manifest.json").decode("utf-8"))
        if read_manifest.get("manifest_sha256") != manifest_sha256:
            raise RetentionRefused("ARCHIVE_VERIFY_FAILED")

        for item in manifest_data["items"]:
            path_str = item["path"]
            if path_str not in namelist:
                raise RetentionRefused("ARCHIVE_VERIFY_FAILED")
            entry_bytes = bundle.read(path_str)
            if hashlib.sha256(entry_bytes).hexdigest() != item["sha256"]:
                raise RetentionRefused("ARCHIVE_VERIFY_FAILED")

    return {
        "status": "ARCHIVED",
        "zip": zip_rel,
        "files": len(candidates),
        "manifest_sha256": manifest_sha256,
    }


def purge_archived(root: Path | str, zip_path: Path | str, approval_path: Path | str) -> dict[str, Any]:
    """Purge originals only with user approval bound to archive manifest hash.

    Agents never run this; B83, a name in a file, is not authentication.
    """
    root = Path(root).resolve()
    zip_path = Path(zip_path)
    if not zip_path.is_absolute():
        zip_path = root / zip_path

    approval_path = Path(approval_path)
    if not approval_path.is_absolute():
        approval_path = root / approval_path

    if not approval_path.is_file():
        raise RetentionRefused(f"APPROVAL_MISSING: approval file not found: {approval_path}")

    try:
        approval_data = json.loads(approval_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RetentionRefused(f"APPROVAL_INVALID: could not parse approval JSON: {exc}")

    if not isinstance(approval_data, dict):
        raise RetentionRefused("APPROVAL_INVALID: approval content is not a dict")

    if approval_data.get("approver") != "user":
        raise RetentionRefused(f"APPROVAL_REFUSED: approver must be 'user', got {approval_data.get('approver')!r}")

    if approval_data.get("action") != "purge":
        raise RetentionRefused(f"APPROVAL_REFUSED: action must be 'purge', got {approval_data.get('action')!r}")

    if not zip_path.is_file():
        raise RetentionRefused(f"ZIP_MISSING: archive zip not found: {zip_path}")

    try:
        with zipfile.ZipFile(zip_path, "r") as bundle:
            if "manifest.json" not in bundle.namelist():
                raise RetentionRefused("ZIP_INVALID: manifest.json missing from archive zip")
            manifest = json.loads(bundle.read("manifest.json").decode("utf-8"))
    except Exception as exc:
        if isinstance(exc, RetentionRefused):
            raise
        raise RetentionRefused(f"ZIP_INVALID: error reading zip manifest: {exc}")

    manifest_sha256 = manifest.get("manifest_sha256")
    if not manifest_sha256 or approval_data.get("manifest_sha256") != manifest_sha256:
        raise RetentionRefused("APPROVAL_MANIFEST_MISMATCH: approval manifest_sha256 does not match zip manifest")

    deleted = 0
    skipped_changed = []
    skipped_unsafe: list[str] = []

    with zipfile.ZipFile(zip_path, "r") as bundle:
        for item in manifest.get("items", []):
            rel_path = item.get("path")
            expected_sha = item.get("sha256")
            # The zip manifest is data: a path that leaves the project must never be deleted (U47-R1 judge).
            if not isinstance(rel_path, str) or Path(rel_path).is_absolute():
                skipped_unsafe.append(str(rel_path))
                continue
            target_file = (root / rel_path).resolve()
            try:
                target_file.relative_to(root)
            except ValueError:
                skipped_unsafe.append(rel_path)
                continue

            if not target_file.is_file():
                continue

            current_sha = _file_sha256(target_file)
            if current_sha != expected_sha:
                skipped_changed.append(rel_path)
                continue

            try:
                zip_entry_bytes = bundle.read(rel_path)
                if hashlib.sha256(zip_entry_bytes).hexdigest() != expected_sha:
                    continue
            except KeyError:
                continue

            try:
                target_file.unlink()
                deleted += 1
            except OSError:
                pass

    return {
        "status": "PURGED",
        "deleted": deleted,
        "skipped_changed": skipped_changed,
        "skipped_unsafe": skipped_unsafe,
    }


def work_dir_report(root: Path | str, *, now: float, older_than_days: float = 14) -> dict[str, Any]:
    """Look only at direct children of <root>/.work, using directory's own mtime and no size walk.
    Never modifies anything.
    """
    work_dir = Path(root) / ".work"
    if not work_dir.is_dir():
        return {"total": 0, "stale": []}

    stale: list[dict[str, Any]] = []
    children = [p for p in work_dir.iterdir() if p.is_dir()]
    total = len(children)

    for child in children:
        try:
            mtime = child.stat().st_mtime
        except OSError:
            continue
        age_days = max(0.0, (now - mtime) / 86400.0)
        if age_days >= older_than_days:
            stale.append({"name": child.name, "age_days": round(age_days, 1)})

    stale.sort(key=lambda item: (-item["age_days"], item["name"]))
    return {"total": total, "stale": stale}
===END===
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
===FILE: tests/test_u47_retention_safety.py===
"""U47-R1 judge findings: a purge never leaves the project, and a rollup keeps the ledger's exact bytes."""

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from v7_harness import retention


class PurgeEscapeTest(unittest.TestCase):
    def test_a_manifest_path_outside_the_project_is_never_deleted(self):
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
            result = retention.purge_archived(root, zip_path, approval)
            self.assertEqual(0, result["deleted"])
            self.assertEqual(["../outside.txt"], result["skipped_unsafe"])
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
===END===

===EDIT: v7_harness/cli.py===
<<<<<<< SEARCH
    p_rsi_retention.add_argument("--project", default=".")
    p_rsi_retention.set_defaults(func=cmd_rsi_retention)
=======
    p_rsi_retention.add_argument("--project", default=".")
    p_rsi_retention.add_argument("--archive", action="store_true", help="Archive candidate files into a verified zip")
    p_rsi_retention.add_argument("--rollup-olla", action="store_true", help="Roll up olla usage ledger")
    p_rsi_retention.add_argument("--purge", default=None, metavar="ZIP",
                                 help="Archive zip to purge (user only; agents never run it)")
    p_rsi_retention.add_argument("--approval", default=None, metavar="FILE", help="User approval file for purge")
    p_rsi_retention.set_defaults(func=cmd_rsi_retention)
>>>>>>> REPLACE

===EDIT: v7_harness/cli.py===
<<<<<<< SEARCH
def cmd_rsi_retention(args: argparse.Namespace) -> int:
    import time

    from .retention import apply_retention, default_policy, plan_retention

    project = Path(args.project)
    policy = default_policy()
    plan = plan_retention(project, policy, now=time.time())
    result = apply_retention(project, plan)
    _print_json({"ok": True, **result})
    return 0
=======
def cmd_rsi_retention(args: argparse.Namespace) -> int:
    import time

    from . import olla
    from .retention import (
        RetentionRefused,
        apply_retention,
        archive_candidates,
        default_policy,
        plan_retention,
        purge_archived,
        rollup_jsonl,
        work_dir_report,
    )

    now = time.time()
    project = Path(args.project)
    policy = default_policy()
    plan = plan_retention(project, policy, now=now)
    result = apply_retention(project, plan)
    out: dict = {"ok": True, **result}

    if getattr(args, "archive", False):
        out["archive"] = archive_candidates(project, plan, now=now)

    if getattr(args, "rollup_olla", False):
        out["rollup"] = rollup_jsonl(olla.USAGE_LOG, olla.USAGE_LOG.parent / "archive")

    if getattr(args, "purge", None):
        approval_path = Path(args.approval) if getattr(args, "approval", None) else project / "missing_approval.json"
        try:
            purge_res = purge_archived(project, Path(args.purge), approval_path)
            out["purge"] = purge_res
        except RetentionRefused as exc:
            _print_json({"ok": False, "status": "REFUSED", "error": str(exc)})
            return 2

    out["work_report"] = work_dir_report(project, now=now)
    _print_json(out)
    return 0
>>>>>>> REPLACE


## Output

- Reply with ===FILE / ===EDIT blocks only. No explanations. Do not claim success; the acceptance command decides.
