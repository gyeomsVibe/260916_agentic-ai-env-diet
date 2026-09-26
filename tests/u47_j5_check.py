"""U47-J5 fixed acceptance gate (judge: Claude). The worker must create the frozen test verbatim and make it pass."""

import hashlib
import subprocess
import sys
from pathlib import Path

FROZEN = "76d86e1480f2b54e9d03ca83fe8bbeb7d969436b743275ee1f600f26ec108fd1"  # LF-normalized sha256 of the test

test = Path("tests/test_u47_j5_judge_budget.py")
if not test.is_file():
    sys.exit("FROZEN_TEST_MISSING")
digest = hashlib.sha256(test.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
if digest != FROZEN:
    sys.exit(f"FROZEN_TEST_CHANGED {digest}")
sys.exit(subprocess.call([sys.executable, "-m", "unittest", "tests.test_000_env_guard", "tests.test_u47_j5_judge_budget",
                          "tests.test_u46_pilot_judge", "tests.test_cli"]))
