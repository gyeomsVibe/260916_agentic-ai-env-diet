"""U47-O1: sorts first in discovery, so the ledger guard is on before any module imports v7_harness."""

import os
import unittest
from pathlib import Path

from tests import _env_guard  # noqa: F401  (installs the guard on import)


class EnvGuardTest(unittest.TestCase):
    def test_tests_never_write_the_real_local_model_ledger(self):
        from v7_harness import olla

        real = Path.home() / ".cache" / "olla" / "usage.jsonl"
        self.assertEqual(_env_guard.SAFE_OLLA_USAGE, olla.USAGE_LOG)
        self.assertNotEqual(real.resolve(), Path(os.environ["OLLA_USAGE"]).resolve())
        self.assertEqual("0", os.environ["UAOS_STREAM_AUTOLOG"])


if __name__ == "__main__":
    unittest.main()
