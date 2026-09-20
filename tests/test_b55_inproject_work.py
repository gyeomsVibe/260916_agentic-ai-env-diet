"""B55: all runtime artifacts live under <project>/.work; manifests and staging must ignore .work and .coord/pilot."""

import tempfile
import unittest
from pathlib import Path

from v7_harness.isolation.manifest import build_manifest
from v7_harness.isolation.staging import NonGitStagingAdapter


class InProjectWorkDirTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "proj"
        (self.root / "src").mkdir(parents=True)
        (self.root / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_manifest_ignores_runtime_sections(self) -> None:
        before = build_manifest(self.root).manifest_hash
        (self.root / ".work" / "pilot" / "stage" / "T1").mkdir(parents=True)
        (self.root / ".work" / "pilot" / "stage" / "T1" / "copy.py").write_text("y = 2\n", encoding="utf-8")
        (self.root / ".coord" / "pilot").mkdir(parents=True)
        (self.root / ".coord" / "pilot" / "coord.sqlite3").write_bytes(b"db")
        self.assertEqual(before, build_manifest(self.root).manifest_hash)

    def test_staging_copy_does_not_include_work_section(self) -> None:
        (self.root / ".work" / "big").mkdir(parents=True)
        (self.root / ".work" / "big" / "blob.bin").write_bytes(b"z" * 1024)
        stage = Path(self.temp.name) / "stage"
        workspace = NonGitStagingAdapter().create_staging(self.root, stage)
        self.assertTrue((workspace.staging_dir / "src" / "a.py").is_file())
        self.assertFalse((workspace.staging_dir / ".work").exists())

    def test_work_dir_inside_source_is_safe_for_self_hosting(self) -> None:
        # A pilot whose work_dir is <source>/.work/pilot must not see its own staging in the source manifest.
        work = self.root / ".work" / "pilot"
        (work / "stage" / "T2").mkdir(parents=True)
        (work / "stage" / "T2" / "src").mkdir()
        (work / "stage" / "T2" / "src" / "a.py").write_text("changed\n", encoding="utf-8")
        self.assertNotIn(".work", {e.path.split("/")[0] for e in build_manifest(self.root).entries})


if __name__ == "__main__":
    unittest.main()
