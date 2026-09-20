"""B28 regression test: Protected Configuration Guard for agent config files."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from v7_harness.isolation.errors import ExternalWriteDetectedError
from v7_harness.isolation.security import (
    DEFAULT_WATCH_EXCLUDES,
    PROTECTED_WATCH_FILES,
    _watch_path_excluded,
    is_protected_watch_path,
    snapshot_watch_roots,
)


class B28WatchHoleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_protected_watch_files_are_not_excluded(self) -> None:
        """Ensure all protected configuration files return False from _watch_path_excluded."""
        for path in PROTECTED_WATCH_FILES:
            self.assertTrue(
                is_protected_watch_path(path),
                f"Expected '{path}' to be recognized as a protected watch path",
            )
            self.assertFalse(
                _watch_path_excluded(path, DEFAULT_WATCH_EXCLUDES),
                f"Expected '{path}' to NOT be excluded by DEFAULT_WATCH_EXCLUDES",
            )

    def test_noise_files_remain_excluded(self) -> None:
        """Ensure runtime noise files are safely excluded."""
        noise_files = [
            ".claude.json",
            ".claude/cache/model_cache.bin",
            ".claude/projects/history.json",
            ".codex/session.jsonl",
            ".codex/cache/tokens.bin",
            "claude/temp_session.tmp",
        ]
        for path in noise_files:
            self.assertTrue(
                _watch_path_excluded(path, DEFAULT_WATCH_EXCLUDES),
                f"Expected noise path '{path}' to be excluded",
            )

    def test_shallow_watch_root_detects_claude_settings_mutation(self) -> None:
        """Verify shallow home root (typical pilot setup) detects modification of ~/.claude/settings.json."""
        claude_dir = self.home / ".claude"
        claude_dir.mkdir()
        settings_file = claude_dir / "settings.json"
        settings_file.write_text('{"auto_compact": false}', encoding="utf-8")

        # Snapshot home shallowly (recursive_roots=None)
        snapshot = snapshot_watch_roots([self.home])

        # Mutate settings.json
        settings_file.write_text('{"auto_compact": true}', encoding="utf-8")

        with self.assertRaises(ExternalWriteDetectedError):
            snapshot.assert_unchanged()

    def test_shallow_watch_root_detects_codex_config_mutation(self) -> None:
        """Verify shallow home root detects modification of ~/.codex/config.toml."""
        codex_dir = self.home / ".codex"
        codex_dir.mkdir()
        config_file = codex_dir / "config.toml"
        config_file.write_text('model = "default"\n', encoding="utf-8")

        snapshot = snapshot_watch_roots([self.home])

        # Mutate config.toml
        config_file.write_text('model = "compromised"\n', encoding="utf-8")

        with self.assertRaises(ExternalWriteDetectedError):
            snapshot.assert_unchanged()

    def test_shallow_watch_root_ignores_runtime_noise(self) -> None:
        """Verify shallow home root ignores session.jsonl and .claude.json writes."""
        claude_dir = self.home / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text("{}", encoding="utf-8")
        codex_dir = self.home / ".codex"
        codex_dir.mkdir()
        (codex_dir / "config.toml").write_text("{}", encoding="utf-8")

        snapshot = snapshot_watch_roots([self.home])

        # Write noise to session files and root claude.json
        (codex_dir / "session.jsonl").write_text('{"turn": 1}\n', encoding="utf-8")
        (self.home / ".claude.json").write_text('{"active": true}\n', encoding="utf-8")

        # Should not raise
        effects: list[dict[str, object]] = []
        snapshot.assert_unchanged(effect_recorder=effects)
        self.assertEqual([], effects)

    def test_recursive_watch_root_detects_rules_mutation(self) -> None:
        """Verify recursive watch root detects creation/modification of rules files."""
        rules_dir = self.home / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        rule_file = rules_dir / "security.md"
        rule_file.write_text("# Original Rule\n", encoding="utf-8")

        snapshot = snapshot_watch_roots([self.home], recursive_roots=[self.home])

        # Modify rule file
        rule_file.write_text("# Malicious Rule Bypass\n", encoding="utf-8")

        with self.assertRaises(ExternalWriteDetectedError):
            snapshot.assert_unchanged()
