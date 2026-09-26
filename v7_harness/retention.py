"""U42-R1 / U47-R1: deletion-free retention planning, staged reversible archiving and a fail-closed purge boundary.

A retention plan is only ever a dry-run manifest: which files are old or excess for their zone,
which are protected (failure/P1/approval evidence), and which are excluded because their run is
still active or locked. Nothing in this module deletes a file. Archiving/restoring remain available, while real
deletion requires an authenticated fresh user action outside this process; every purge entry point refuses.
Stage 1 rolls up oversized JSONL ledgers into verified .gz archives and summaries.
Stage 2 archives old files into verified zip bundles.
Stage 3 validates an archive without deleting and then reports the missing authenticated approval boundary.
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


def _resolve_project_relative(root: Path, candidate: str | Path, *, label: str) -> tuple[Path, str]:
    """Resolve an archive-controlled path under root or reject it before any file operation."""
    raw = Path(candidate)
    if raw.is_absolute():
        raise RetentionRefused(f"PATH_ESCAPE: {label} must be project-relative: {candidate}")
    target = (root / raw).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise RetentionRefused(f"PATH_ESCAPE: {label} escapes the retention root: {candidate}")
    return target, raw.as_posix()


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

    resolved_candidates: list[tuple[dict[str, Any], Path, str]] = []
    for candidate in candidates:
        raw_path = candidate.get("path")
        expected_sha = candidate.get("sha256")
        if not isinstance(raw_path, str) or not isinstance(expected_sha, str):
            raise RetentionRefused("ARCHIVE_INVALID_CANDIDATE")
        source, archive_name = _resolve_project_relative(root, raw_path, label="archive candidate")
        if not source.is_file():
            raise RetentionRefused(f"ARCHIVE_SOURCE_MISSING: {archive_name}")
        if _file_sha256(source) != expected_sha:
            raise RetentionRefused(f"ARCHIVE_SOURCE_CHANGED: {archive_name}")
        resolved_candidates.append((candidate, source, archive_name))

    manifest_sha256 = plan.get("manifest_sha256", "")
    date_str = time.strftime("%Y%m%d", time.gmtime(now))
    zip_rel = f".coord/retention_archive/{date_str}_{manifest_sha256[:8]}.zip"
    archive_dir = _resolve_zone_path(root, ".coord/retention_archive")
    zip_path = archive_dir / f"{date_str}_{manifest_sha256[:8]}.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    manifest_data = {
        "manifest_sha256": manifest_sha256,
        "items": [{"path": archive_name, "sha256": candidate["sha256"]}
                  for candidate, _, archive_name in resolved_candidates],
    }

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for _, source, archive_name in resolved_candidates:
            bundle.write(source, arcname=archive_name)
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
    """Validate the archive read-only, then refuse because a file label is not authentication.

    ``approval_path`` remains in the signature for compatibility, but is deliberately never read. B83 forbids
    treating ``{"approver": "user"}`` or any other local JSON label as an authenticated human action.
    """
    root = Path(root).resolve()
    archive_path = Path(zip_path)
    if archive_path.is_absolute():
        try:
            archive_path = archive_path.resolve()
            archive_path.relative_to(root)
        except ValueError:
            raise RetentionRefused(f"PATH_ESCAPE: archive zip escapes the retention root: {zip_path}")
    else:
        archive_path, _ = _resolve_project_relative(root, archive_path, label="archive zip")

    if not archive_path.is_file():
        raise RetentionRefused(f"ZIP_MISSING: archive zip not found: {archive_path}")

    try:
        with zipfile.ZipFile(archive_path, "r") as bundle:
            if "manifest.json" not in bundle.namelist():
                raise RetentionRefused("ZIP_INVALID: manifest.json missing from archive zip")
            manifest = json.loads(bundle.read("manifest.json").decode("utf-8"))
            if not isinstance(manifest, dict) or not isinstance(manifest.get("items"), list):
                raise RetentionRefused("ZIP_INVALID: manifest must contain an items list")
            names = set(bundle.namelist())
            for item in manifest["items"]:
                if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                    raise RetentionRefused("ZIP_INVALID: manifest item path is missing")
                _, archive_name = _resolve_project_relative(root, item["path"], label="zip manifest path")
                if archive_name not in names:
                    raise RetentionRefused(f"ZIP_INVALID: manifest entry missing from zip: {archive_name}")
                expected_sha = item.get("sha256")
                if not isinstance(expected_sha, str) or hashlib.sha256(bundle.read(archive_name)).hexdigest() != expected_sha:
                    raise RetentionRefused(f"ZIP_INVALID: archived bytes do not match manifest: {archive_name}")
    except Exception as exc:
        if isinstance(exc, RetentionRefused):
            raise
        raise RetentionRefused(f"ZIP_INVALID: error reading zip manifest: {exc}")

    _ = approval_path
    raise RetentionRefused(
        "UNAUTHENTICATED_ACTOR: local approval files and actor names are not authenticated user actions; "
        "FRESH_DELETE_APPROVAL_REQUIRED: purge is disabled and this call performed no deletion"
    )


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
