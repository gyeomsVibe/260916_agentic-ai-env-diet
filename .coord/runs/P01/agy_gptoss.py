"""P01-only launcher shim selecting an available Antigravity model."""

from __future__ import annotations

import subprocess
import sys


raise SystemExit(
    subprocess.call(["agy", "--model", "gpt-oss-120b-medium", *sys.argv[1:]])
)
