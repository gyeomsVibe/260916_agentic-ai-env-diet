"""B28/B31-B34 re-include tests: agent config files inside excluded dirs are detected."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from v7_harness.isolation.errors import ExternalWriteDetectedError
from v7_harness.isolation.security import (
    DEFAULT_WATCH_EXCLUDES,
    DEFAULT_WATCH_REINCLUDES,
    _watch_path_excluded,
    is_protected_watch_path,
    snapshot_watch_roots,
)


class ReincludeDetectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    # --- req 4a: .claude/settings.json write → detected ---
    def test_claude_settings_json_detected(self) -> None:
        claude_dir = self.home / ".claude"
        claude_dir.mkdir()
        sf = claude_dir / "settings.json"
        sf.write_text('{"a":1}', encoding="utf-8")

        snap = snapshot_watch_roots([self.home])
        sf.write_text('{"a":2}', encoding="utf-8")

        with self.assertRaises(ExternalWriteDetectedError):
            snap.assert_unchanged()

    # --- req 4b: .codex/config.toml write → detected ---
    def test_codex_config_toml_detected(self) -> None:
        codex_dir = self.home / ".codex"
        codex_dir.mkdir()
        cf = codex_dir / "config.toml"
        cf.write_text('model = "a"\n', encoding="utf-8")

        snap = snapshot_watch_roots([self.home])
        cf.write_text('model = "b"\n', encoding="utf-8")

        with self.assertRaises(ExternalWriteDetectedError):
            snap.assert_unchanged()

    # --- req 4c: .claude/hooks/x.ps1 creation → detected ---
    def test_claude_hooks_file_detected(self) -> None:
        hooks_dir = self.home / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)

        snap = snapshot_watch_roots([self.home])
        (hooks_dir / "x.ps1").write_text("echo hi", encoding="utf-8")

        with self.assertRaises(ExternalWriteDetectedError):
            snap.assert_unchanged()

    # --- req 4d: noise files not detected ---
    def test_noise_files_not_detected(self) -> None:
        claude_dir = self.home / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text("{}", encoding="utf-8")
        codex_dir = self.home / ".codex"
        codex_dir.mkdir()
        (codex_dir / "config.toml").write_text("{}", encoding="utf-8")

        snap = snapshot_watch_roots([self.home])

        # Noise writes
        projects_dir = claude_dir / "projects" / "a"
        projects_dir.mkdir(parents=True, exist_ok=True)
        (projects_dir / "b.jsonl").write_text("{}", encoding="utf-8")
        (self.home / ".claude.json").write_text("{}", encoding="utf-8")
        sessions_dir = codex_dir / "sessions"
        sessions_dir.mkdir(exist_ok=True)
        (sessions_dir / "x.jsonl").write_text("{}", encoding="utf-8")

        effects: list[dict] = []
        snap.assert_unchanged(effect_recorder=effects)
        self.assertEqual([], effects)

    # --- req 4e: case variation detected ---
    def test_case_insensitive_detection(self) -> None:
        claude_dir = self.home / ".CLAUDE"
        claude_dir.mkdir()
        sf = claude_dir / "Settings.json"
        sf.write_text('{"v":1}', encoding="utf-8")

        snap = snapshot_watch_roots([self.home])
        sf.write_text('{"v":2}', encoding="utf-8")

        with self.assertRaises(ExternalWriteDetectedError):
            snap.assert_unchanged()

    # --- Additional: agents, skills, commands, CLAUDE.md, AGENTS.md ---
    def test_claude_agents_dir_detected(self) -> None:
        agents_dir = self.home / ".claude" / "agents"
        agents_dir.mkdir(parents=True)
        af = agents_dir / "helper.md"
        af.write_text("# Agent", encoding="utf-8")

        snap = snapshot_watch_roots([self.home])
        af.write_text("# Malicious Agent", encoding="utf-8")

        with self.assertRaises(ExternalWriteDetectedError):
            snap.assert_unchanged()

    def test_claude_skills_dir_detected(self) -> None:
        skills_dir = self.home / ".claude" / "skills"
        skills_dir.mkdir(parents=True)

        snap = snapshot_watch_roots([self.home])
        (skills_dir / "inject.md").write_text("# Skill", encoding="utf-8")

        with self.assertRaises(ExternalWriteDetectedError):
            snap.assert_unchanged()

    def test_claude_commands_dir_detected(self) -> None:
        cmds_dir = self.home / ".claude" / "commands"
        cmds_dir.mkdir(parents=True)

        snap = snapshot_watch_roots([self.home])
        (cmds_dir / "deploy.md").write_text("# Deploy", encoding="utf-8")

        with self.assertRaises(ExternalWriteDetectedError):
            snap.assert_unchanged()

    def test_claude_md_detected(self) -> None:
        claude_dir = self.home / ".claude"
        claude_dir.mkdir()
        md = claude_dir / "CLAUDE.md"
        md.write_text("# Original", encoding="utf-8")

        snap = snapshot_watch_roots([self.home])
        md.write_text("# Tampered", encoding="utf-8")

        with self.assertRaises(ExternalWriteDetectedError):
            snap.assert_unchanged()

    def test_codex_agents_md_detected(self) -> None:
        codex_dir = self.home / ".codex"
        codex_dir.mkdir()
        md = codex_dir / "AGENTS.md"
        md.write_text("# Agents", encoding="utf-8")

        snap = snapshot_watch_roots([self.home])
        md.write_text("# Injected", encoding="utf-8")

        with self.assertRaises(ExternalWriteDetectedError):
            snap.assert_unchanged()

    def test_codex_skills_dir_detected(self) -> None:
        skills_dir = self.home / ".codex" / "skills"
        skills_dir.mkdir(parents=True)

        snap = snapshot_watch_roots([self.home])
        (skills_dir / "skill.md").write_text("# Skill", encoding="utf-8")

        with self.assertRaises(ExternalWriteDetectedError):
            snap.assert_unchanged()

    def test_codex_rules_dir_detected(self) -> None:
        rules_dir = self.home / ".codex" / "rules"
        rules_dir.mkdir(parents=True)
        rf = rules_dir / "rule.md"
        rf.write_text("# Rule", encoding="utf-8")

        snap = snapshot_watch_roots([self.home])
        rf.write_text("# Bad Rule", encoding="utf-8")

        with self.assertRaises(ExternalWriteDetectedError):
            snap.assert_unchanged()

    # --- Verify exclude/re-include logic at the function level ---
    def test_reinclude_paths_not_excluded(self) -> None:
        for path in DEFAULT_WATCH_REINCLUDES:
            self.assertTrue(is_protected_watch_path(path), f"Expected '{path}' in re-include")
            self.assertFalse(
                _watch_path_excluded(path, DEFAULT_WATCH_EXCLUDES),
                f"Expected '{path}' NOT to be excluded",
            )

    def test_reinclude_sub_paths_not_excluded(self) -> None:
        sub_paths = [
            ".claude/hooks/pre-commit.sh",
            ".claude/agents/helper.md",
            ".claude/skills/coding.md",
            ".claude/commands/deploy.md",
            ".claude/rules/security.md",
            ".codex/rules/policy.md",
            ".codex/skills/python.md",
        ]
        for path in sub_paths:
            self.assertFalse(
                _watch_path_excluded(path, DEFAULT_WATCH_EXCLUDES),
                f"Expected sub-path '{path}' NOT to be excluded",
            )


if __name__ == "__main__":
    unittest.main()
