import tempfile
import unittest
from pathlib import Path

from v7_harness.isolation.errors import IsolationError
from v7_harness.isolation.security import snapshot_watch_roots


class ReincludeNameCollisionTest(unittest.TestCase):
    """r3 counterexample: heavy-dir names inside re-included trees must not hide sensitive files."""

    def _detected(self, rel: str) -> bool:
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

    def test_skill_named_like_heavy_dir_is_detected(self) -> None:
        self.assertTrue(self._detected(".claude/skills/venv/SKILL.md"))

    def test_hook_under_dot_git_named_dir_is_detected(self) -> None:
        self.assertTrue(self._detected(".claude/hooks/.git/x.ps1"))

    def test_dependency_tree_below_a_skill_is_watched_by_metadata(self) -> None:
        # r4: excluding it hid executable code; watch size/mtime without content hashing instead.
        self.assertTrue(self._detected(".claude/skills/myskill/node_modules/pkg/index.js"))
        self.assertTrue(self._detected(".claude/skills/myskill/.venv/lib/x.py"))

    def test_heavy_tree_does_not_consume_fingerprint_budget(self) -> None:
        import tempfile
        from v7_harness.isolation.security import snapshot_watch_roots
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            big = root / ".claude/skills/s/node_modules/pkg/blob.bin"
            big.parent.mkdir(parents=True)
            big.write_bytes(b"x" * (2 * 1024 * 1024))
            snapshot_watch_roots([root], max_fingerprint_bytes_per_root=1024 * 1024)


if __name__ == "__main__":
    unittest.main()
