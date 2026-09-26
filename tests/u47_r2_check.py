"""U47-R2 fixed acceptance gate (judge: Claude). The worker must create the frozen test verbatim and make it pass."""

import hashlib
import subprocess
import sys
from pathlib import Path

FROZEN = "cd29595c743a296eabcd96a7d4ad8937836a51b5ecb51507e720c7a71b2973e5"  # LF-normalized sha256 of the test

test = Path("tests/test_u47_r2_retention_alert.py")
if not test.is_file():
    sys.exit("FROZEN_TEST_MISSING")
digest = hashlib.sha256(test.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
if digest != FROZEN:
    sys.exit(f"FROZEN_TEST_CHANGED {digest}")
sys.exit(subprocess.call([sys.executable, "-m", "unittest", "tests.test_000_env_guard", "tests.test_u47_r2_retention_alert",
                          "tests.test_u47_retention_no_delete", "tests.test_cli"]))
