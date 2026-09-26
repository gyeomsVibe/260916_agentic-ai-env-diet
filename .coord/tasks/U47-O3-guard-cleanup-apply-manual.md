```contract
work_id: U47-O3
worker: apply
goal: Test ledger guard removes its temp file at exit so paid pilot runs stop failing EXTERNAL_WRITE
inputs:
- tests/_env_guard.py sha256=09f725ddbfb99df11db68850bfcd9affc9f1b9d11f4d3ce23d928eb5eef9b78a
allow:
- tests/_env_guard.py
- tests/test_u47_o3_guard_cleanup.py
acceptance: python -m unittest tests.test_u47_o3_guard_cleanup tests.test_000_env_guard tests.test_u47_olla_record && python -m unittest discover -s tests -p "test_*.py"
forbidden: design changes; edits outside allow; editing or deleting tests; network; commit/push
stop: two failures with the same cause; input hash mismatch; no output
judge: antigravity
timeout_s: 1800
remote_budget_tokens: 0
```

## Instructions for the worker

## Instructions for the worker

Apply U47-O3 exactly: tests/_env_guard.py removes its per-process temp ledger at interpreter exit; new test proves no leftover. Red-first: the new test fails against the current guard.

===FILE: tests/_env_guard.py===
"""U47-O1: keep the test suite out of this machine's real ledgers.

`python -m unittest discover -s tests` imports test modules as top-level modules, so `tests/__init__.py` never runs
under it (checked 2026-09-26: a marker set there was None inside a test). The U33 stream guard in `__init__` was
therefore off for the usual command, and fake local-model runs (1 input / 1 output token) reached the real
~/.cache/olla/usage.jsonl: 64 of 193 `pilot_local` rows on 2026-09-26. `test_000_env_guard.py` sorts first in
discovery and imports this module before any test module imports `v7_harness`; `__init__` imports it for dotted runs.
"""

import atexit
import os
import sys
import tempfile
from pathlib import Path

# One file per test process, in the system temp folder; a test that needs its own log still patches USAGE_LOG.
SAFE_OLLA_USAGE = Path(tempfile.gettempdir()) / f"uaos_test_olla_usage_{os.getpid()}.jsonl"


def _remove_safe_log() -> None:
    # U47-O3: a file left in %TEMP% after the suite made every paid pilot run that ran the tests fail its watch-root
    # check as EXTERNAL_WRITE (U47-R2, 2026-09-26; 9 leftovers found). Worker subprocesses finish before this runs.
    try:
        SAFE_OLLA_USAGE.unlink(missing_ok=True)
    except OSError:
        pass


def install() -> None:
    os.environ["UAOS_STREAM_AUTOLOG"] = "0"
    os.environ["OLLA_USAGE"] = str(SAFE_OLLA_USAGE)  # inherited by the worker subprocesses tests start
    olla = sys.modules.get("v7_harness.olla")
    if olla is not None:  # already imported by an earlier module: its path was fixed at import time
        olla.USAGE_LOG = SAFE_OLLA_USAGE


install()
atexit.register(_remove_safe_log)
===END===

===FILE: tests/test_u47_o3_guard_cleanup.py===
"""U47-O3: the test ledger guard leaves nothing in the system temp folder once the test process exits."""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCRIPT = (
    "import tests._env_guard as g\n"
    "g.SAFE_OLLA_USAGE.write_text('{}\\n', encoding='utf-8')\n"
    "import os\n"
    "assert os.environ['OLLA_USAGE'] == str(g.SAFE_OLLA_USAGE)\n"
    "print(g.SAFE_OLLA_USAGE)\n"
)


class GuardCleanupTest(unittest.TestCase):
    def test_safe_ledger_is_removed_at_exit(self):
        done = subprocess.run([sys.executable, "-c", SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(0, done.returncode, done.stderr)
        path = Path(done.stdout.strip())
        self.assertTrue(path.name.startswith("uaos_test_olla_usage_"), path)
        self.assertFalse(path.exists(), f"left behind: {path}")


if __name__ == "__main__":
    unittest.main()
===END===


## Output

- Reply with ===FILE / ===EDIT blocks only. No explanations. Do not claim success; the acceptance command decides.
