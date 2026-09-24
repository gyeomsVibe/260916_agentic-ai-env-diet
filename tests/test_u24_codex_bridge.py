"""Tests for U24 Codex session bridge (docs/24)."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from v7_harness.coord.codex_session_bridge import (
    create_or_update_rollout,
    format_thread_name,
    parse_transcript_to_turns,
    publish_codex_thread,
    register_thread_in_codex,
)


class TestCodexSessionBridge(unittest.TestCase):
    def test_format_thread_name(self):
        self.assertEqual(format_thread_name("agy", "MIA 전략 검토"), "[agy-MIA 전략 검토]")
        self.assertEqual(format_thread_name("antigravity", "[agy-작업 A]"), "[agy-작업 A]")
        self.assertEqual(format_thread_name("claude", "U15 조율 스트림"), "[claude-U15 조율 스트림]")
        self.assertEqual(format_thread_name("claude", "[claude-작업 B]"), "[claude-작업 B]")

    def test_create_rollout_structure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rollout_path = Path(tmpdir) / "rollout-test.jsonl"
            proj_dir = Path(tmpdir) / "project"
            proj_dir.mkdir()

            create_or_update_rollout(
                rollout_path,
                thread_id="test-uuid-1234",
                project_dir=proj_dir,
                actor="agy",
                turns=[("안녕하세요", "반갑습니다")],
            )

            lines = [json.loads(line) for line in rollout_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(lines), 7)
            self.assertEqual(lines[0]["type"], "session_meta")
            self.assertEqual(lines[0]["payload"]["session_id"], "test-uuid-1234")
            self.assertEqual(lines[1]["type"], "event_msg")
            self.assertEqual(lines[1]["payload"]["type"], "task_started")
            self.assertEqual(lines[2]["payload"]["role"], "user")
            self.assertEqual(lines[2]["payload"]["content"][0]["text"], "안녕하세요")
            self.assertEqual(lines[4]["payload"]["role"], "assistant")
            self.assertEqual(lines[4]["payload"]["content"][0]["text"], "반갑습니다")
            self.assertEqual(lines[6]["type"], "event_msg")
            self.assertEqual(lines[6]["payload"]["type"], "task_complete")


    def test_parse_transcript_to_turns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            transcript_p = Path(tmpdir) / "transcript.jsonl"
            lines = [
                {"type": "USER_INPUT", "content": "<USER_REQUEST>\n테스트 요청입니다.\n</USER_REQUEST>"},
                {"type": "PLANNER_RESPONSE", "content": None},
                {"type": "GENERIC", "content": "도구 실행 결과"},
                {"type": "PLANNER_RESPONSE", "content": "작업 결과 보고입니다."},
            ]
            transcript_p.write_text("\n".join(json.dumps(l) for l in lines) + "\n", encoding="utf-8")

            turns = parse_transcript_to_turns(transcript_p)
            self.assertEqual(len(turns), 1)
            self.assertEqual(turns[0][0], "테스트 요청입니다.")
            self.assertEqual(turns[0][1], "작업 결과 보고입니다.")


if __name__ == "__main__":
    unittest.main()
