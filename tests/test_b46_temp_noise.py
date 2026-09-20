import tempfile
import unittest
from pathlib import Path

from v7_harness.isolation.errors import IsolationError
from v7_harness.isolation.security import snapshot_watch_roots


class TempRootNoiseTest(unittest.TestCase):
    def _created_detected(self, name: str) -> bool:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snap = snapshot_watch_roots([root])
            (root / name).write_text("x")
            try:
                snap.assert_unchanged()
            except IsolationError:
                return True
            return False

    def test_visual_studio_download_logs_are_noise(self) -> None:
        self.assertFalse(self._created_detected("dd_BackgroundDownload_20260918214542_01_setup.log"))
        self.assertFalse(self._created_detected("tmpE7E0.tmp"))

    def test_other_temp_files_are_still_detected(self) -> None:
        self.assertTrue(self._created_detected("payload.ps1"))
        self.assertTrue(self._created_detected("tmp_escape.txt"))

    def test_noise_patterns_are_narrow(self) -> None:
        # r6: only VS BackgroundDownload logs and GetTempFileName-style hex names are noise.
        self.assertTrue(self._created_detected("dd_exploit.log"))
        self.assertTrue(self._created_detected("tmppayl.tmp"))
        self.assertTrue(self._created_detected("tmp_sh.tmp"))


if __name__ == "__main__":
    unittest.main()
