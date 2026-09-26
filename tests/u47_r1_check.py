"""U47-R1 fixed acceptance gate (judge: Claude). The worker must create the frozen test verbatim and make it pass."""

import hashlib
import subprocess
import sys
from pathlib import Path

FROZEN = "f3bc413a7a7909bc054e4b35ddb4dcabd4dd8bdd5d8131d545f0e5c3b3e5d866"  # LF-normalized sha256 of the test

test = Path("tests/test_u47_retention_stages.py")
if not test.is_file():
    sys.exit("FROZEN_TEST_MISSING")
digest = hashlib.sha256(test.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
if digest != FROZEN:
    sys.exit(f"FROZEN_TEST_CHANGED {digest}")
sys.exit(subprocess.call([sys.executable, "-m", "unittest", "tests.test_000_env_guard", "tests.test_u47_retention_stages",
                          "tests.test_u42_r1_hardening", "tests.test_cli"]))
