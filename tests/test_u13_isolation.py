from __future__ import annotations

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from v7_harness.isolation import (
    ExternalWriteDetectedError,
    GitWorktreeAdapter,
    NonGitStagingAdapter,
    ScopeExpansionError,
    SourceDivergenceError,
    StaleFenceOrReceiptError,
    WatchScanUnavailableError,
    build_manifest,
    create_patch_bundle,
    dry_run_promotion,
    snapshot_watch_roots,
    validate_safe_relative_path,
)
from v7_harness.isolation.security import WatchRootsSnapshot, WatchScanResult


class U13IsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.stage = self.root / "stage"
        self.source.mkdir()
        (self.source / "backend").mkdir()
        (self.source / "frontend").mkdir()
        (self.source / "backend" / "api.py").write_text("x = 1\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _workspace(self):
        return NonGitStagingAdapter(excludes=["ignored"]).create_staging(self.source, self.stage)

    def test_non_git_manifest_excludes_and_worker_stage_only(self) -> None:
        (self.source / "ignored").mkdir()
        (self.source / "ignored" / "secret.txt").write_text("no", encoding="utf-8")
        ws = self._workspace()
        self.assertEqual(["backend/api.py"], [e.path for e in ws.base_manifest.entries])
        (ws.staging_dir / "backend" / "api.py").write_text("x = 2\n", encoding="utf-8")
        self.assertEqual("x = 1\n", (self.source / "backend" / "api.py").read_text())

    def test_junction_or_symlink_escape_is_rejected(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        link = self.source / "backend" / "escape"
        try:
            if os.name == "nt":
                subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], check=True, capture_output=True)
            else:
                link.symlink_to(outside, target_is_directory=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("junction/symlink creation unavailable")
        with self.assertRaises(Exception):
            build_manifest(self.source)

    def test_watch_recursive_junction_or_symlink_escape_is_rejected(self) -> None:
        watched = self.root / "watch-junction"
        outside = self.root / "watch-outside"
        watched.mkdir()
        outside.mkdir()
        (outside / "secret.txt").write_text("outside", encoding="utf-8")
        link = watched / "escape"
        try:
            if os.name == "nt":
                subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], check=True, capture_output=True)
            else:
                link.symlink_to(outside, target_is_directory=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("junction/symlink creation unavailable")
        effects: list[dict[str, object]] = []
        with self.assertRaises(WatchScanUnavailableError):
            snapshot_watch_roots([watched], recursive_roots=[watched], effect_recorder=effects)
        self.assertEqual("WATCH_SCAN_UNAVAILABLE", effects[0]["reason"])

    def test_watch_root_substitution_with_junction_or_symlink_is_rejected(self) -> None:
        watched = self.root / "watch-root-swap"
        displaced = self.root / "watch-root-original"
        outside = self.root / "watch-root-outside"
        watched.mkdir()
        outside.mkdir()
        (watched / "inside.txt").write_text("inside", encoding="utf-8")
        (outside / "secret.txt").write_text("outside", encoding="utf-8")
        before = snapshot_watch_roots([watched])
        watched.rename(displaced)
        try:
            if os.name == "nt":
                subprocess.run(["cmd", "/c", "mklink", "/J", str(watched), str(outside)], check=True, capture_output=True)
            else:
                watched.symlink_to(outside, target_is_directory=True)
        except (OSError, subprocess.CalledProcessError):
            displaced.rename(watched)
            self.skipTest("junction/symlink creation unavailable")
        effects: list[dict[str, object]] = []
        with self.assertRaises(WatchScanUnavailableError):
            before.assert_unchanged(effect_recorder=effects)
        self.assertEqual("WATCH_SCAN_UNAVAILABLE", effects[0]["reason"])

    def test_windows_alias_forms_are_rejected(self) -> None:
        for value in ("../x", "C:/x", "C:x", "\\\\server\\share\\x", "PROGRA~1/x"):
            with self.subTest(value=value), self.assertRaises(Exception):
                validate_safe_relative_path(value)

    def test_home_or_temp_external_write_marks_unknown(self) -> None:
        home = self.root / "home"
        home.mkdir()
        before = snapshot_watch_roots([home], recursive_roots=[home])
        (home / "escaped.txt").write_text("side effect", encoding="utf-8")
        with self.assertRaises(ExternalWriteDetectedError) as caught:
            effects: list[dict[str, object]] = []
            before.assert_unchanged(effect_recorder=effects)
        self.assertEqual("UNKNOWN", caught.exception.effect_state)
        self.assertEqual("UNKNOWN", effects[0]["state"])

    def test_watch_roots_ignores_noise_dirs(self) -> None:
        home = self.root / "home"
        (home / "AppData").mkdir(parents=True)
        (home / ".codex").mkdir()
        before = snapshot_watch_roots([home], recursive_roots=[home])
        (home / "AppData" / "browser.lock").write_text("noise", encoding="utf-8")
        (home / ".codex" / "session.jsonl").write_text("noise", encoding="utf-8")
        effects: list[dict[str, object]] = []
        before.assert_unchanged(effect_recorder=effects)
        self.assertEqual([], effects)

    def test_temp_watch_ignores_observed_agy_runtime_noise(self) -> None:
        watched = self.root / "temp"
        watched.mkdir()
        schema = watched / "unleash-repo-schema-v1-codeium-language-server.json"
        schema.write_text("stable", encoding="utf-8")
        before = snapshot_watch_roots([watched])
        (watched / "cddf1043-830f-4278-9f36-4af0faeef143.tmp").write_bytes(b"")
        os.utime(schema, None)
        before.assert_unchanged()

    def test_watch_root_enumeration_unavailable_is_not_false_delete(self) -> None:
        watched = self.root / "unavailable-root"
        watched.mkdir()
        (watched / "existing.txt").write_text("keep", encoding="utf-8")
        before = snapshot_watch_roots([watched])
        effects: list[dict[str, object]] = []
        with mock.patch("v7_harness.isolation.security.os.scandir", side_effect=PermissionError("locked")):
            with self.assertRaises(WatchScanUnavailableError) as caught:
                before.assert_unchanged(effect_recorder=effects)
        self.assertEqual("WATCH_SCAN_UNAVAILABLE", caught.exception.error_class)
        self.assertEqual("WATCH_SCAN_UNAVAILABLE", effects[0]["reason"])
        self.assertNotIn("EXTERNAL_WRITE", [item["effect"] for item in effects])

    def test_initial_watch_scan_unavailable_records_unknown(self) -> None:
        watched = self.root / "initial-unavailable"
        watched.mkdir()
        effects: list[dict[str, object]] = []
        with mock.patch("v7_harness.isolation.security.os.scandir", side_effect=PermissionError("locked")):
            with self.assertRaises(WatchScanUnavailableError):
                snapshot_watch_roots([watched], effect_recorder=effects)
        self.assertEqual("WATCH_SCAN_UNAVAILABLE", effects[0]["reason"])
        self.assertEqual("UNKNOWN", effects[0]["state"])

    def test_watch_file_stat_unavailable_is_not_false_delete(self) -> None:
        watched = self.root / "unavailable-file"
        watched.mkdir()
        target = (watched / "existing.txt").resolve()
        target.write_text("keep", encoding="utf-8")
        before = snapshot_watch_roots([watched])
        original_stat = Path.stat

        def selective_stat(path: Path, *args, **kwargs):
            # realpath, not Path.resolve: on POSIX resolve() calls stat() and would recurse into this mock.
            if Path(os.path.realpath(path)) == target:
                raise PermissionError("locked")
            return original_stat(path, *args, **kwargs)

        with mock.patch("v7_harness.isolation.security.Path.stat", autospec=True, side_effect=selective_stat):
            with self.assertRaises(WatchScanUnavailableError) as caught:
                before.assert_unchanged()
        self.assertEqual("WATCH_SCAN_UNAVAILABLE", caught.exception.error_class)

    def test_watch_roots_fingerprint_unchanged_files_within_budget(self) -> None:
        watched = self.root / "watched"
        watched.mkdir()
        (watched / "large.bin").write_bytes(b"x" * (2 * 1024 * 1024))
        from v7_harness.isolation import security

        with mock.patch(
            "v7_harness.isolation.security._bounded_content_fingerprint",
            wraps=security._bounded_content_fingerprint,
        ) as fingerprinter:
            before = snapshot_watch_roots([watched])
            before.assert_unchanged()
        self.assertEqual(2, fingerprinter.call_count)

    def test_watch_detects_same_size_content_with_restored_mtime(self) -> None:
        watched = self.root / "restored-metadata"
        watched.mkdir()
        target = watched / "same.txt"
        target.write_bytes(b"AAAA")
        original = target.stat()
        before = snapshot_watch_roots([watched])
        target.write_bytes(b"BBBB")
        os.utime(target, ns=(original.st_atime_ns, original.st_mtime_ns))
        with self.assertRaises(ExternalWriteDetectedError):
            before.assert_unchanged()

    def test_recursive_excludes_are_root_relative_not_global_basenames(self) -> None:
        watched = self.root / "relative-excludes"
        legitimate = watched / "product" / "browser"
        legitimate.mkdir(parents=True)
        target = legitimate / "logic.py"
        target.write_text("before", encoding="utf-8")
        before = snapshot_watch_roots([watched], recursive_roots=[watched])
        target.write_text("after", encoding="utf-8")
        with self.assertRaises(ExternalWriteDetectedError):
            before.assert_unchanged()

    def test_recursive_literal_exclude_name_is_not_global_file_filter(self) -> None:
        watched = self.root / "relative-file-excludes"
        nested = watched / "product" / "feature"
        nested.mkdir(parents=True)
        target = nested / "appdata"
        target.write_text("before", encoding="utf-8")
        before = snapshot_watch_roots([watched], recursive_roots=[watched])
        target.write_text("after", encoding="utf-8")
        with self.assertRaises(ExternalWriteDetectedError):
            before.assert_unchanged()

    def test_watch_home_top_level_write_detected(self) -> None:
        home = self.root / "home"
        home.mkdir()
        before = snapshot_watch_roots([home])
        (home / "shell.txt").write_text("escaped", encoding="utf-8")
        effects: list[dict[str, object]] = []
        with self.assertRaises(ExternalWriteDetectedError):
            before.assert_unchanged(effect_recorder=effects)
        self.assertEqual("shell.txt", effects[0]["changes"][0]["path"])

    def test_watch_roots_budget(self) -> None:
        watched = self.root / "budget"
        watched.mkdir()
        resolved = watched.resolve()
        files = {f"f{index:05d}": (0, 1, 1, "empty") for index in range(50_000)}
        scan = WatchScanResult(root_exists=True, files=files)
        before = WatchRootsSnapshot(
            roots=(resolved,),
            initial_state={resolved: scan},
            started_ns=time.time_ns(),
            excludes=frozenset(),
            recursive_roots=frozenset(),
            max_files_per_root=50_001,
            max_fingerprint_bytes_per_root=1,
        )
        started = time.perf_counter()
        with mock.patch("v7_harness.isolation.security._scan_watch_root", return_value=scan):
            before.assert_unchanged()
        self.assertLess(time.perf_counter() - started, 5.0)

    def test_watch_fingerprint_byte_budget_fails_closed(self) -> None:
        watched = self.root / "fingerprint-budget"
        watched.mkdir()
        (watched / "large.bin").write_bytes(b"x" * 1025)
        effects: list[dict[str, object]] = []
        with self.assertRaises(Exception) as caught:
            snapshot_watch_roots(
                [watched], max_fingerprint_bytes_per_root=1024, effect_recorder=effects
            )
        self.assertEqual("WATCH_FINGERPRINT_BUDGET_EXCEEDED", caught.exception.error_class)
        self.assertEqual("WATCH_FINGERPRINT_BUDGET_EXCEEDED", effects[0]["reason"])
        self.assertEqual("UNKNOWN", effects[0]["state"])

    def _make_dir_link(self, link: Path, target: Path) -> None:
        try:
            if os.name == "nt":
                subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
            else:
                link.symlink_to(target, target_is_directory=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("junction/symlink creation unavailable")

    def test_shallow_home_with_directory_junctions_snapshots(self) -> None:
        home = self.root / "home-links"
        home.mkdir()
        (home / "note.txt").write_text("n", encoding="utf-8")
        for index in range(3):
            target = self.root / f"relocated-{index}"
            target.mkdir()
            (target / "big.bin").write_bytes(b"x" * 2048)
            self._make_dir_link(home / f".tool-{index}", target)
        before = snapshot_watch_roots([home], max_fingerprint_bytes_per_root=1024)
        files = before.initial_state[home.resolve()].files
        self.assertTrue(files[".tool-0"][3].startswith("LINK:"))
        before.assert_unchanged()

    def test_excluded_reparse_entry_is_skipped_before_reparse_check(self) -> None:
        home = self.root / "home-excluded-link"
        home.mkdir()
        target = self.root / "excluded-target"
        target.mkdir()
        self._make_dir_link(home / "appdata", target)
        before = snapshot_watch_roots([home])
        self.assertNotIn("appdata", before.initial_state[home.resolve()].files)

    def test_top_level_junction_retarget_detected(self) -> None:
        home = self.root / "home-retarget"
        home.mkdir()
        first = self.root / "retarget-a"
        second = self.root / "retarget-b"
        first.mkdir()
        second.mkdir()
        link = home / ".tool"
        self._make_dir_link(link, first)
        before = snapshot_watch_roots([home])
        # removes only the link, never the target directory
        if os.name == "nt":
            os.rmdir(link)
        else:
            link.unlink()
        self._make_dir_link(link, second)
        with self.assertRaises(ExternalWriteDetectedError):
            before.assert_unchanged()
        self.assertTrue(first.exists())

    @unittest.skipUnless(os.name == "nt", "Windows sharing-violation lock")
    def test_locked_file_recorded_as_metadata_not_root_failure(self) -> None:
        import ctypes
        from ctypes import wintypes

        home = self.root / "home-locked"
        home.mkdir()
        locked = home / "ntuser.dat"
        locked.write_bytes(b"registry-hive")
        (home / "plain.txt").write_text("p", encoding="utf-8")
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.restype = wintypes.HANDLE
        handle = kernel32.CreateFileW(str(locked), 0x80000000, 0, None, 3, 0x80, None)  # GENERIC_READ, no sharing
        if handle in (None, wintypes.HANDLE(-1).value):
            self.skipTest("exclusive lock unavailable")
        try:
            before = snapshot_watch_roots([home])
            self.assertEqual("LOCKED", before.initial_state[home.resolve()].files["ntuser.dat"][3])
            before.assert_unchanged()
            (home / "plain.txt").write_text("changed", encoding="utf-8")
            with self.assertRaises(ExternalWriteDetectedError):
                before.assert_unchanged()
        finally:
            kernel32.CloseHandle(handle)

    def test_real_scan_budget_5k_files(self) -> None:
        watched = self.root / "real-budget"
        watched.mkdir()
        for index in range(5_000):
            (watched / f"f{index:05d}.txt").write_bytes(b"payload")
        # U46-T1: CPU time of this process, not wall time. Wall time failed under a loaded machine (43 s, 51 s) while
        # passing alone; the budget is about the scan's own cost, which other processes cannot inflate.
        started = time.process_time()
        before = snapshot_watch_roots([watched])
        before.assert_unchanged()
        self.assertLess(time.process_time() - started, 30.0)

    def test_patch_bundle_classifies_rename_binary_newline_and_encoding(self) -> None:
        (self.source / "backend" / "old.txt").write_text("same\n", encoding="utf-8")
        (self.source / "backend" / "binary.bin").write_bytes(b"\x00\xff")
        (self.source / "backend" / "newline.txt").write_bytes(b"a\r\n")
        (self.source / "backend" / "encoding.txt").write_bytes("café".encode("latin-1"))
        ws = self._workspace()
        (self.stage / "backend" / "old.txt").rename(self.stage / "backend" / "new.txt")
        (self.stage / "backend" / "binary.bin").write_bytes(b"\x00\xfe")
        (self.stage / "backend" / "newline.txt").write_bytes(b"a\n")
        (self.stage / "backend" / "encoding.txt").write_bytes("café".encode("utf-8"))
        bundle = ws.create_patch_bundle()
        kinds = {(i.change_type, i.content_kind, i.delta_kind) for i in bundle.items}
        self.assertIn(("RENAMED", "text", "content"), kinds)
        renamed = next(i for i in bundle.items if i.change_type == "RENAMED")
        self.assertEqual("backend/old.txt", renamed.rename_from)
        self.assertTrue(any(k[1] == "binary" for k in kinds))
        self.assertTrue(any(k[2] == "newline" for k in kinds))
        self.assertTrue(any(k[2] == "encoding" for k in kinds))

    def test_scope_and_shared_spec_are_fail_closed(self) -> None:
        ws = self._workspace()
        (self.stage / "frontend" / "ui.ts").write_text("x", encoding="utf-8")
        bundle = ws.create_patch_bundle(metadata={"owner": "codex", "spec_change_requests": []})
        with self.assertRaises(ScopeExpansionError):
            dry_run_promotion(source_dir=self.source, patch_bundle=bundle, allowed_scopes=["backend"])
        (self.stage / "frontend" / "ui.ts").unlink()
        (self.stage / "AGENTS-CONSENSUS.md").write_text("changed", encoding="utf-8")
        bundle = ws.create_patch_bundle(metadata={"owner": "antigravity", "spec_change_requests": []})
        with self.assertRaises(ScopeExpansionError):
            dry_run_promotion(source_dir=self.source, patch_bundle=bundle, allowed_scopes=["frontend"])

    def test_source_concurrent_change_rejected_and_source_never_written(self) -> None:
        ws = self._workspace()
        (self.stage / "backend" / "api.py").write_text("x = 2\n", encoding="utf-8")
        bundle = ws.create_patch_bundle()
        (self.source / "backend" / "api.py").write_text("user edit\n", encoding="utf-8")
        with self.assertRaises(SourceDivergenceError):
            dry_run_promotion(source_dir=self.source, patch_bundle=bundle, allowed_scopes=["backend"])
        self.assertEqual("user edit\n", (self.source / "backend" / "api.py").read_text())

    def test_delete_requires_separate_approval_and_empty_bundle_passes(self) -> None:
        ws = self._workspace()
        empty = ws.create_patch_bundle()
        result = dry_run_promotion(source_dir=self.source, patch_bundle=empty, allowed_scopes=["backend"])
        self.assertEqual("DRY_RUN_PASSED", result.status)
        (self.stage / "backend" / "api.py").unlink()
        deletion = ws.create_patch_bundle()
        result = dry_run_promotion(source_dir=self.source, patch_bundle=deletion, allowed_scopes=["backend"])
        self.assertEqual("APPROVAL_REQUIRED", result.status)
        self.assertEqual(["DELETE_FILE"], [a["action"] for a in result.approval_required_actions])

    def test_rename_carries_delete_approval_for_old_path(self) -> None:
        (self.source / "backend" / "old.txt").write_text("same\n", encoding="utf-8")
        ws = self._workspace()
        (self.stage / "backend" / "old.txt").rename(self.stage / "backend" / "new.txt")
        result = dry_run_promotion(
            source_dir=self.source,
            patch_bundle=ws.create_patch_bundle(),
            allowed_scopes=["backend"],
        )
        actions = {(a["action"], a["path"]) for a in result.approval_required_actions}
        self.assertIn(("DELETE_FILE", "backend/old.txt"), actions)
        self.assertIn(("ADD_FILE", "backend/new.txt"), actions)

    def test_stale_fence_records_reconciliation(self) -> None:
        ws = self._workspace()
        bundle = ws.create_patch_bundle(metadata={"attempt_id": "a1", "fencing_token": 4})
        log: list[dict[str, str]] = []
        with self.assertRaises(StaleFenceOrReceiptError):
            dry_run_promotion(
                source_dir=self.source,
                patch_bundle=bundle,
                attempt_id="a1",
                fencing_token=3,
                current_fence=4,
                reconciliation_log=log,
            )
        self.assertEqual("STALE_FENCE", log[0]["reason"])

    def test_large_binary_bundle_keeps_hashes_without_embedding_payload(self) -> None:
        payload = b"\x00" + os.urandom(2 * 1024 * 1024)
        (self.source / "backend" / "large.bin").write_bytes(payload)
        ws = self._workspace()
        (self.stage / "backend" / "large.bin").write_bytes(payload[:-1] + b"x")
        item = ws.create_patch_bundle().items[0]
        self.assertEqual("binary", item.content_kind)
        self.assertLess(len(item.patch_data), 1024)
        self.assertIsNotNone(item.base_sha256)
        self.assertIsNotNone(item.target_sha256)

    def test_git_fixture_worktree_isolated(self) -> None:
        repo = self.root / "repo"
        wt = self.root / "worktree"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Fixture"], cwd=repo, check=True)
        (repo / "a.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
        ctx = GitWorktreeAdapter.create_worktree(repo, wt, "u13-fixture")
        try:
            (wt / "a.txt").write_text("stage\n", encoding="utf-8")
            self.assertEqual("base\n", (repo / "a.txt").read_text())
            self.assertEqual("MODIFIED", ctx.create_patch_bundle().items[0].change_type)
        finally:
            ctx.cleanup()

    def test_snapshot_watch_roots_custom_excludes_union_with_defaults(self) -> None:
        watched = self.root / "exclude-union"
        watched.mkdir()
        (watched / "AppData").mkdir()
        (watched / "AppData" / "noise.txt").write_text("noise", encoding="utf-8")
        (watched / "custom_dir").mkdir()
        (watched / "custom_dir" / "worker.txt").write_text("worker", encoding="utf-8")
        (watched / "regular.txt").write_text("regular", encoding="utf-8")

        before = snapshot_watch_roots(
            [watched],
            excludes=["custom_dir", "custom_dir/**"],
        )

        # Both AppData (from DEFAULT_WATCH_EXCLUDES) and custom_dir (from custom excludes) are excluded
        (watched / "AppData" / "noise.txt").write_text("noise modified", encoding="utf-8")
        (watched / "custom_dir" / "worker.txt").write_text("worker modified", encoding="utf-8")
        before.assert_unchanged()

        # Modifying regular unexcluded file is detected
        (watched / "regular.txt").write_text("tampered", encoding="utf-8")
        with self.assertRaises(ExternalWriteDetectedError):
            before.assert_unchanged()


if __name__ == "__main__":
    unittest.main()

