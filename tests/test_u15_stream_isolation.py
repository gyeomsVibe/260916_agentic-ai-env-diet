"""U15 S1: 조율 스트림과 브리핑은 원본 매니페스트에서 제외돼야 한다.

파일럿 실행 도중 세 도구가 사건을 기록해도 `SOURCE_DIVERGED`가 나지 않아야 하고,
그 대가로 감시해야 할 조율 산출물(PLAN, 카드, 메모)까지 놓치면 안 된다.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from v7_harness.isolation.manifest import DEFAULT_EXCLUDES, build_manifest


class U15StreamIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.files = {
            "src/app.py": "value = 1\n",
            ".coord/PLAN.md": "# plan\n",
            ".coord/tasks/U15-coordination-stream.md": "# card\n",
            ".coord/stream/2026-09-20.jsonl": '{"id":"a","kind":"NOTE"}\n',
            ".coord/stream/archive/2026-09-19.jsonl": '{"id":"b","kind":"NOTE"}\n',
            ".coord/codex_brief.md": "# brief\n",
            "docs/claude-assist/70_memo.md": "# memo\n",
        }
        for rel, text in self.files.items():
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _paths(self) -> set[str]:
        return {entry.path for entry in build_manifest(self.root).entries}

    def test_stream_and_brief_are_excluded(self) -> None:
        paths = self._paths()
        self.assertNotIn(".coord/stream/2026-09-20.jsonl", paths)
        self.assertNotIn(".coord/stream/archive/2026-09-19.jsonl", paths)
        self.assertNotIn(".coord/codex_brief.md", paths)

    def test_coordination_records_stay_monitored(self) -> None:
        paths = self._paths()
        for rel in (".coord/PLAN.md", ".coord/tasks/U15-coordination-stream.md", "docs/claude-assist/70_memo.md", "src/app.py"):
            self.assertIn(rel, paths)

    def test_stream_writes_during_a_run_do_not_change_the_hash(self) -> None:
        before = build_manifest(self.root).manifest_hash
        stream = self.root / ".coord" / "stream" / "2026-09-20.jsonl"
        for index in range(10):
            with stream.open("a", encoding="utf-8") as handle:
                handle.write('{"id":"e%d","kind":"RUN"}\n' % index)
        (self.root / ".coord" / "codex_brief.md").write_text("# brief v2\n", encoding="utf-8")
        self.assertEqual(before, build_manifest(self.root).manifest_hash)

    def test_source_edit_still_changes_the_hash(self) -> None:
        before = build_manifest(self.root).manifest_hash
        (self.root / "src" / "app.py").write_text("value = 2\n", encoding="utf-8")
        self.assertNotEqual(before, build_manifest(self.root).manifest_hash)

    def test_exclusions_are_declared_not_incidental(self) -> None:
        self.assertIn(".coord/stream", DEFAULT_EXCLUDES)
        self.assertIn(".coord/codex_brief.md", DEFAULT_EXCLUDES)


if __name__ == "__main__":
    unittest.main()
