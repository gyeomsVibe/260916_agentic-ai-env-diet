"""U47-R1e fixed acceptance: safe retention never authenticates deletion from a local file label."""

import hashlib
import subprocess
import sys
from pathlib import Path


FROZEN = {
    "tests/test_u47_retention_stages.py": "0b265b60848d6d8201b226e5f45b6de740dbff1e8049c0ad93e899d6d8bdc3f6",
    "tests/test_u47_retention_safety.py": "9e3c8bb12d02d2812a5f452369db056ad49ce6abbffc967381474190c9c00573",
    "tests/test_u47_retention_no_delete.py": "4d4291f0904d3a2883831bccf5512d198040f818108093288f02e0504cd73897",
}


for name, expected in FROZEN.items():
    path = Path(name)
    if not path.is_file():
        sys.exit(f"FROZEN_TEST_MISSING {name}")
    digest = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    if digest != expected:
        sys.exit(f"FROZEN_TEST_CHANGED {name} {digest}")

sys.exit(
    subprocess.call(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_000_env_guard",
            "tests.test_u47_retention_stages",
            "tests.test_u47_retention_safety",
            "tests.test_u47_retention_no_delete",
            "tests.test_u42_r1_hardening",
            "tests.test_cli",
        ]
    )
)
