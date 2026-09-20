import tempfile
import unittest
from pathlib import Path

from v7_harness.isolation.errors import IsolationError
from v7_harness.isolation.security import snapshot_watch_roots


class SyncedSkillsNoiseTest(unittest.TestCase):
    def _changed_detected(self, rel: str) -> bool:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("a")
            snap = snapshot_watch_roots([root])
            target.write_text("changed-longer")
            try:
                snap.assert_unchanged()
            except IsolationError:
                return True
            return False

    def test_app_synced_skills_are_noise(self) -> None:
        self.assertFalse(self._changed_detected(".claude/skills/synced/org/skill/SKILL.md"))

    def test_user_skills_still_detected(self) -> None:
        self.assertTrue(self._changed_detected(".claude/skills/mine/SKILL.md"))
        self.assertTrue(self._changed_detected(".claude/hooks/pre.ps1"))


if __name__ == "__main__":
    unittest.main()
