```contract
work_id: U47-O1
worker: apply
goal: Keep the test suite out of the real local-model ledger (tests/_env_guard.py loaded first by test_000_env_guard.py) and record model and work_id on every pilot_local row.
inputs:
- tests/__init__.py sha256=8f6b341ae77737cc764ab91b81ae111c752424ae1d2cedc87720c1ec846767e8
- v7_harness/adapters/ollama_worker.py sha256=5354c6f9aaf224844b7e03c70eed7581b2ed6181aa01dc1e1c5c21e1388ac561
allow:
- tests/_env_guard.py
- tests/test_000_env_guard.py
- tests/test_u47_olla_record.py
- tests/__init__.py
- v7_harness/adapters/ollama_worker.py
acceptance: python -m unittest discover -s tests
forbidden: design changes; edits outside allow; editing or deleting tests; network; commit/push
stop: two failures with the same cause; input hash mismatch; no output
judge: antigravity
timeout_s: 900
remote_budget_tokens: 0
```

## Instructions for the worker

===FILE: tests/_env_guard.py===
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
===FILE: tests/test_000_env_guard.py===
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
===FILE: tests/test_u47_olla_record.py===
"""U47-O2: a local-model run row names its model and work, so the ledger can be joined to pilot outcomes."""

import unittest

from v7_harness.adapters.ollama_worker import contract_work_id


class OllaRecordTest(unittest.TestCase):
    def test_work_id_is_read_from_the_contract(self):
        prompt = "# Manual\n\n```contract\nwork_id: U47-X1\nworker: ollama\n```\nDo it."
        self.assertEqual("U47-X1", contract_work_id(prompt))

    def test_no_contract_gives_none(self):
        self.assertIsNone(contract_work_id("just a task"))


if __name__ == "__main__":
    unittest.main()

===EDIT: tests/__init__.py===
<<<<<<< SEARCH
os.environ["UAOS_STREAM_AUTOLOG"] = "0"
=======
os.environ["UAOS_STREAM_AUTOLOG"] = "0"

# U47-O1: this file runs only for dotted runs (`python -m unittest tests.test_x`); `discover -s tests` skips it, so
# the same guard also loads from test_000_env_guard.py, which sorts first.
from tests import _env_guard  # noqa: E402,F401
>>>>>>> REPLACE

===EDIT: v7_harness/adapters/ollama_worker.py===
<<<<<<< SEARCH
def _log(event: str, **fields) -> None:
=======
def contract_work_id(prompt: str) -> str | None:
    """U47-O2: the work id from the manual's contract block, so a `pilot_local` row can be joined to its pilot run."""
    found = re.search(r"^work_id:\s*(\S+)\s*$", prompt, re.M)
    return found.group(1) if found else None


def _log(event: str, **fields) -> None:
>>>>>>> REPLACE

===EDIT: v7_harness/adapters/ollama_worker.py===
<<<<<<< SEARCH
    if estimated > limit:
        return envelope("ERROR", "", {"input_tokens": 0, "output_tokens": 0}, f"PROMPT_TOO_LARGE: ~{estimated} tokens > {limit}")
    from v7_harness.adapters.gpu_priority import pilot_holds

    started = time.monotonic()
    try:
        with pilot_holds(timeout_s):  # 파일럿이 GPU 를 먼저 쓴다(B74). 보조 호출은 이 동안 양보한다
            text, usage = _generate(args.model, prompt, timeout_s)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        _log("pilot_local", status="ERROR", elapsed_s=round(time.monotonic() - started, 1))
        return envelope("ERROR", "", {"input_tokens": 0, "output_tokens": 0}, f"ollama unreachable: {exc}")
    _log("pilot_local", status="GENERATED", elapsed_s=round(time.monotonic() - started, 1), **usage)
=======
    # U47-O2: every row names the model and the work, so the ledger can be joined to pilot outcomes and distilled.
    run = {"model": args.model, "work_id": contract_work_id(args.prompt)}
    if estimated > limit:
        _log("pilot_local", status="PROMPT_TOO_LARGE", elapsed_s=0.0, estimated_tokens=estimated, **run)
        return envelope("ERROR", "", {"input_tokens": 0, "output_tokens": 0}, f"PROMPT_TOO_LARGE: ~{estimated} tokens > {limit}")
    from v7_harness.adapters.gpu_priority import pilot_holds

    started = time.monotonic()
    try:
        with pilot_holds(timeout_s):  # 파일럿이 GPU 를 먼저 쓴다(B74). 보조 호출은 이 동안 양보한다
            text, usage = _generate(args.model, prompt, timeout_s)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        _log("pilot_local", status="ERROR", elapsed_s=round(time.monotonic() - started, 1), **run)
        return envelope("ERROR", "", {"input_tokens": 0, "output_tokens": 0}, f"ollama unreachable: {exc}")
    _log("pilot_local", status="GENERATED", elapsed_s=round(time.monotonic() - started, 1), **run, **usage)
>>>>>>> REPLACE


## Output

- Reply with ===FILE / ===EDIT blocks only. No explanations. Do not claim success; the acceptance command decides.
