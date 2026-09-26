"""U47-O1: keep the test suite out of this machine's real ledgers.

`python -m unittest discover -s tests` imports test modules as top-level modules, so `tests/__init__.py` never runs
under it (checked 2026-09-26: a marker set there was None inside a test). The U33 stream guard in `__init__` was
therefore off for the usual command, and fake local-model runs (1 input / 1 output token) reached the real
~/.cache/olla/usage.jsonl: 64 of 193 `pilot_local` rows on 2026-09-26. `test_000_env_guard.py` sorts first in
discovery and imports this module before any test module imports `v7_harness`; `__init__` imports it for dotted runs.
"""

import os
import sys
import tempfile
from pathlib import Path

# One file per test process, in the system temp folder; a test that needs its own log still patches USAGE_LOG.
SAFE_OLLA_USAGE = Path(tempfile.gettempdir()) / f"uaos_test_olla_usage_{os.getpid()}.jsonl"


def install() -> None:
    os.environ["UAOS_STREAM_AUTOLOG"] = "0"
    os.environ["OLLA_USAGE"] = str(SAFE_OLLA_USAGE)  # inherited by the worker subprocesses tests start
    olla = sys.modules.get("v7_harness.olla")
    if olla is not None:  # already imported by an earlier module: its path was fixed at import time
        olla.USAGE_LOG = SAFE_OLLA_USAGE


install()
