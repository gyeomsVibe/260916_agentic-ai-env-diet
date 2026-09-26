```contract
work_id: U47-R2
worker: agy
goal: Stat-only retention alert line in the session hook (brief), once per change, under 200 ms on 5k files; never reads, writes (except its fingerprint) or deletes
inputs:
- tests/u47_r2_check.py sha256=39c18cc13e7d2da2ac6b5ecd4fbe6391aad9d1bac54969ad78512e0f8e9ce7b5
- v7_harness/coord/hook_context.py sha256=b05748074339b5648880f2084c7727bf68c75257cfeff6f4f8c9923678af7d18
- v7_harness/cli.py sha256=d5d8fac322b0a2e7b1b7e2c5b0c72a0d26908f97cd87ed75902723fa7fa7a9cf
- v7_harness/retention.py sha256=05ecb6b7113a53c44bda1be03f09bab772c372ecc80cb374357d5f5578ee0001
allow:
- v7_harness/coord/hook_context.py
- v7_harness/cli.py
- tests/test_u47_r2_retention_alert.py
acceptance: python tests/u47_r2_check.py && python -m unittest discover -s tests -p "test_*.py"
forbidden: design changes; edits outside allow; editing or deleting tests; network; commit/push
stop: two failures with the same cause; input hash mismatch; no output
judge: claude
timeout_s: 2400
remote_budget_tokens: 400000
```

## Instructions for the worker

## Instructions for the worker (Antigravity)

Implement U47-R2: a stat-only retention alert in the session hook line. Judge: Claude. Design is fixed; do not redesign.

1. In `v7_harness/coord/hook_context.py` add:
   - `retention_alert(project, policy=None) -> str`. `policy` defaults to `v7_harness.retention.default_policy()` (import inside the function so hook start-up stays cheap). For each zone, walk `project/<zone path>` recursively with `os.scandir` and `DirEntry.stat()` only: count files and sum bytes. A missing zone is skipped. Never open, read, write, move or delete a file.
   - Return "" when every zone has count <= max_count and bytes <= max_bytes. Otherwise return one line, no newline, under 300 characters: `UAOS retention: <zone> <count>/<max_count> files, <MB>/<max MB> MB; ... - run `rsi retention` (dry run), then `--archive``. List over-cap zones only, in policy order; truncate so the line stays under 300.
   - `retention_alert_is_new(project, line) -> bool`: "" -> False. Otherwise compare sha256(line) with `project/.coord/presence/retention_seen.txt` (git-ignored runtime state, like `P1_SEEN`); if different, write the new fingerprint (create the folder) and return True; if equal return False. Mirror `p1_is_new`.
2. In `v7_harness/cli.py` `cmd_coord_presence`, in the `--from-hook` branch only when `say == "brief"`: after `line = brief_line(...)`, compute `alert = retention_alert(project)`; if `retention_alert_is_new(project, alert)`, set `line = line + " " + alert`. Keep the existing try/except so a hook never fails. Do not change `p1`, `json` or non-hook paths.
3. Create `tests/test_u47_r2_retention_alert.py` byte-for-byte as below (it is frozen; `tests/u47_r2_check.py` checks its LF-normalized sha256 cd29595c...). Do not edit any other test.
4. Performance: the 5,000-file test must finish under 200 ms best of 3; use `os.scandir` recursion, not `Path.rglob` + `Path.stat`.

Forbidden: importing or calling `purge_archived`, any deletion, network, model calls, edits outside the allow list, writing outside the staging folder (no %TEMP% or home writes), commit, push.

===FILE: tests/test_u47_r2_retention_alert.py===
"""U47-R2 frozen acceptance (written by the judge, Claude): a session hook says one stat-only retention line.

`retention_alert(project, policy=None)` walks the retention zones with stat only (no file contents, no writes, no
deletes) and returns "" when every zone is within its count and byte caps, else one line under 300 characters that
starts "UAOS retention:", names each over-cap zone and points to the dry-run command. `retention_alert_is_new` makes
the line speak once per change, like the U46-P1 hook line. `coord presence --from-hook --say brief` adds the line.
"""

import builtins
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from v7_harness.coord import hook_context


def _policy(max_count=1000, max_bytes=10**9):
    return {"zones": [{"path": ".coord/runs", "retention_days": 30, "max_count": max_count,
                       "max_bytes": max_bytes, "kind": "runs"}]}


def _files(folder, n, size=1):
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        (folder / f"f{i:05d}.json").write_bytes(b"x" * size)


class AlertLineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".coord").mkdir()
        (self.root / ".coord" / "PLAN.md").write_text("# plan\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_or_small_zones_say_nothing(self):
        self.assertEqual("", hook_context.retention_alert(self.root))
        _files(self.root / ".coord" / "runs", 2)
        self.assertEqual("", hook_context.retention_alert(self.root, _policy(max_count=2)))

    def test_count_over_cap_names_the_zone_and_the_dry_run(self):
        _files(self.root / ".coord" / "runs" / "T1", 3)
        line = hook_context.retention_alert(self.root, _policy(max_count=2))
        self.assertTrue(line.startswith("UAOS retention:"), line)
        self.assertIn(".coord/runs", line)
        self.assertIn("3/2", line)
        self.assertIn("rsi retention", line)
        self.assertLess(len(line), 300)
        self.assertNotIn("\n", line)

    def test_bytes_over_cap_also_speak(self):
        _files(self.root / ".coord" / "runs", 2, size=600)
        line = hook_context.retention_alert(self.root, _policy(max_bytes=1000))
        self.assertIn(".coord/runs", line)

    def test_default_policy_is_used_when_none_is_given(self):
        _files(self.root / ".coord" / "runs", 3)
        self.assertEqual("", hook_context.retention_alert(self.root))

    def test_stat_only_no_reads_writes_or_deletes(self):
        _files(self.root / ".coord" / "runs", 3)
        before = sorted(p.name for p in (self.root / ".coord" / "runs").iterdir())
        guard = AssertionError("retention_alert must only stat")
        with mock.patch.object(builtins, "open", side_effect=guard), \
                mock.patch.object(Path, "unlink", side_effect=guard), \
                mock.patch.object(os, "remove", side_effect=guard), \
                mock.patch.object(shutil, "rmtree", side_effect=guard):
            line = hook_context.retention_alert(self.root, _policy(max_count=2))
        self.assertIn(".coord/runs", line)
        self.assertEqual(before, sorted(p.name for p in (self.root / ".coord" / "runs").iterdir()))

    def test_five_thousand_files_under_200_ms(self):
        _files(self.root / ".coord" / "runs", 5000)
        best = min(self._timed() for _ in range(3))
        self.assertLess(best, 0.2, f"best of 3 took {best:.3f}s")

    def _timed(self):
        start = time.perf_counter()
        hook_context.retention_alert(self.root, _policy(max_count=10))
        return time.perf_counter() - start

    def test_speaks_once_per_change(self):
        self.assertFalse(hook_context.retention_alert_is_new(self.root, ""))
        self.assertTrue(hook_context.retention_alert_is_new(self.root, "UAOS retention: a"))
        self.assertFalse(hook_context.retention_alert_is_new(self.root, "UAOS retention: a"))
        self.assertTrue(hook_context.retention_alert_is_new(self.root, "UAOS retention: b"))


class HookIntegrationTest(unittest.TestCase):
    def test_brief_hook_line_carries_the_alert_once(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".coord").mkdir()
            (root / ".coord" / "PLAN.md").write_text("# plan\n", encoding="utf-8")
            _files(root / ".coord" / "runs", 2001)  # default cap for .coord/runs is 2,000 files
            env = {k: v for k, v in os.environ.items() if k != "UAOS_WORKER"}
            cmd = [sys.executable, "-m", "v7_harness.cli", "coord", "presence", "--from-hook", "--project", str(root),
                   "--say", "brief"]
            first = subprocess.run(cmd, capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL, timeout=60)
            second = subprocess.run(cmd, capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL, timeout=60)
            self.assertEqual(0, first.returncode, first.stderr)
            self.assertIn("UAOS project", first.stdout)
            self.assertIn("UAOS retention:", first.stdout)
            self.assertIn("UAOS project", second.stdout)
            self.assertNotIn("UAOS retention:", second.stdout)


if __name__ == "__main__":
    unittest.main()
===END FILE===


## Output

- Edit the files under `allow` directly with your file tools. Your reply is not applied: ===FILE / ===EDIT blocks in it are ignored. End with one line saying what you changed. Do not claim success; the acceptance command decides.
