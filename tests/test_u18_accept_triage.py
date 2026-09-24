"""U18: 인수 실패 원인 분류(CODE/INFRA/UNKNOWN)와 인수 실행 실패 BLOCKED.

반례는 양방향으로 둔다. INFRA 로 잘못 보면 cascade 가 고칠 기회를 잃고, CODE 로 잘못 보면 lane 1회를 낭비한다.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from v7_harness.accept_triage import classify
from v7_harness.pilot import PilotConfig, run_pilot

FAKE_AGY = [sys.executable, str(Path(__file__).parent / "fixtures" / "fake_agy.py")]
PY = f'"{sys.executable}"'

# U17 e2e 실제 로그에서 가져온 꼬리(경로만 줄임)
REAL_FENCE = 'File "stage\\E2E-rename_across-142417\\store.py", line 1\n    ```python\n    ^\nSyntaxError: invalid syntax\n'
REAL_NAME = ("  File \"net.py\", line 12, in retry\n    time.sleep(1)\n    ^^^^\n"
             "NameError: name 'time' is not defined. Did you forget to import 'time'?\n")
# 260912 R2 반례: 코드 실패 로그에 재시도 로그가 섞여 있다
MIXED = ("Retry 3 failed: Connection refused\nTraceback (most recent call last):\n"
         "  File \"t.py\", line 3, in <module>\n    assert fetch() == 'ok'\nAssertionError\n")
UNITTEST_IMPORT = ("ERROR: t (unittest.loader._FailedTest.t)\nImportError: Failed to import test module: t\n"
                   "ModuleNotFoundError: No module named 'mathlib'\n\nFAILED (errors=1)\n")


class ClassifyTests(unittest.TestCase):
    # --- CODE 쪽 반례: 환경 어휘가 섞여도 코드 결함이다 ---
    def test_assertion_beats_connection_refused(self):
        self.assertEqual("CODE", classify(MIXED, 1)[0])

    def test_real_fence_and_name_errors_are_code(self):
        self.assertEqual("CODE", classify(REAL_FENCE, 1)[0])
        self.assertEqual("CODE", classify(REAL_NAME, 1)[0])

    def test_worker_added_missing_import_is_code(self):
        out = "ModuleNotFoundError: No module named 'requests'\n"
        self.assertEqual("CODE", classify(out, 1, ["net.py"], ["import requests\n"])[0])

    def test_worker_removed_module_is_code(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual("CODE", classify(UNITTEST_IMPORT, 1, ["mathlib.py"], [""], Path(d))[0])

    def test_pytest_failed_banner_is_code(self):
        self.assertEqual("CODE", classify("E   assert 1 == 2\n==== 1 failed in 0.02s ====\n", 1)[0])

    # --- INFRA 쪽 반례: 코드와 무관한 환경 실패다 ---
    def test_module_present_but_not_importable_is_infra(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "mathlib.py").write_text("X = 1\n", encoding="utf-8")
            self.assertEqual("INFRA", classify(UNITTEST_IMPORT, 1, ["mathlib.py"], ["X = 1\n"], Path(d))[0])

    def test_missing_env_package_not_touched_by_worker_is_infra(self):
        out = "ModuleNotFoundError: No module named 'pytest'\n"
        self.assertEqual("INFRA", classify(out, 1, ["calc.py"], ["def add(a, b):\n    return a + b\n"])[0])

    def test_missing_command_is_infra(self):
        out = "'pytestx' is not recognized as an internal or external command,\noperable program or batch file.\n"
        self.assertEqual("INFRA", classify(out, 1)[0])

    # --- 판단 불가: 지금처럼 승격시킨다 ---
    def test_timeout_and_bare_exit_are_unknown(self):
        self.assertEqual("UNKNOWN", classify("", 124)[0])
        self.assertEqual("UNKNOWN", classify("", 3)[0])
        self.assertEqual("UNKNOWN", classify("timed out waiting\n", 1)[0])


class PilotAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.source = root / "sample"
        self.source.mkdir()
        (self.source / "calc.py").write_text("def mul(a, b):\n    return a * b\n", encoding="utf-8")
        self.home = root / "home"
        self.home.mkdir()
        self.work = root / "work"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _run(self, task: str, accept_cmd: str) -> dict:
        config = PilotConfig(task_id=task, title="u18", prompt="Add add().", source_dir=self.source,
                             work_dir=self.work, agy_command=FAKE_AGY, watch_roots=[self.home],
                             print_timeout_s=60, approve_bundle_id=None, accept_cmd=accept_cmd)
        with mock.patch.dict(os.environ, {"FAKE_AGY_MODE": "success", "FAKE_AGY_OUTSIDE_DIR": str(self.home)}):
            return run_pilot(config)

    def test_missing_accept_executable_is_blocked_not_rework(self):
        s = self._run("U18NR", "u18_definitely_missing_cmd --x")
        self.assertEqual("BLOCKED", s["verdict_hint"])
        self.assertEqual("ACCEPT_NOT_RUN", s["error_class"])
        self.assertIsNone(s["acceptance_exit"])
        self.assertIn("FileNotFoundError", s.get("error_detail", ""))

    def test_infra_failure_is_blocked(self):
        s = self._run("U18INF", f'{PY} -c "import u18_absent_pkg"')
        self.assertEqual("BLOCKED", s["verdict_hint"])
        self.assertEqual("ACCEPT_INFRA", s["error_class"])
        self.assertEqual("INFRA", s["rework_class"])

    def test_path_problem_on_present_module_is_blocked(self):
        # -I 는 cwd 를 sys.path 에서 뺀다: calc.py 는 있는데 import 가 안 되는 U17 PYTHONPATH 상황
        s = self._run("U18PATH", f'{PY} -I -c "import calc"')
        self.assertEqual("BLOCKED", s["verdict_hint"])
        self.assertEqual("INFRA", s["rework_class"])

    def test_code_failure_stays_rework(self):
        s = self._run("U18CODE", f'{PY} -c "import calc; assert calc.add(2, 2) == 5"')
        self.assertEqual("REWORK", s["verdict_hint"])
        self.assertEqual("CODE", s["rework_class"])

    def test_unexplained_failure_stays_rework(self):
        s = self._run("U18UNK", f'{PY} -c "import sys; sys.exit(3)"')
        self.assertEqual("REWORK", s["verdict_hint"])
        self.assertEqual("UNKNOWN", s["rework_class"])

    def test_pass_has_no_rework_class(self):
        s = self._run("U18OK", f'{PY} -c "import calc; assert calc.add(2, 3) == 5"')
        self.assertEqual("PASS", s["verdict_hint"])
        self.assertNotIn("rework_class", s)


class U20AcceptTriageTests(unittest.TestCase):
    def test_database_is_locked_falls_to_unknown(self):
        out = "sqlite3.OperationalError: database is locked\n"
        self.assertEqual("UNKNOWN", classify(out, 1)[0])

    def test_winerror_32_falls_to_unknown(self):
        out = "PermissionError: [WinError 32] The process cannot access the file because it is being used by another process: 'coord.sqlite3'\n"
        self.assertEqual("UNKNOWN", classify(out, 1)[0])

    def test_cant_open_file_inside_staging_is_code(self):
        with tempfile.TemporaryDirectory() as d:
            staging = Path(d)
            out = "python: can't open file 'missing.py': [Errno 2] No such file or directory\n"
            self.assertEqual("CODE", classify(out, 2, staging=staging)[0])

    def test_cant_open_file_subdir_inside_staging_is_code(self):
        with tempfile.TemporaryDirectory() as d:
            staging = Path(d)
            out = "python: can't open file 'subdir/missing.py': [Errno 2] No such file or directory\n"
            self.assertEqual("CODE", classify(out, 2, staging=staging)[0])

    def test_cant_open_file_absolute_inside_staging_is_code(self):
        with tempfile.TemporaryDirectory() as d:
            staging = Path(d)
            target = (staging / "missing.py").resolve()
            out = f"python: can't open file '{target}': [Errno 2] No such file or directory\n"
            self.assertEqual("CODE", classify(out, 2, staging=staging)[0])

    def test_cant_open_file_relative_outside_staging_is_infra(self):
        with tempfile.TemporaryDirectory() as d:
            staging = Path(d)
            out = "python: can't open file '../outside.py': [Errno 2] No such file or directory\n"
            self.assertEqual("INFRA", classify(out, 2, staging=staging)[0])

    def test_cant_open_file_absolute_outside_staging_is_infra(self):
        with tempfile.TemporaryDirectory() as d:
            staging = Path(d)
            external = "C:/some/external/tool.py" if os.name == "nt" else "/some/external/tool.py"
            out = f"python: can't open file '{external}': [Errno 2] No such file or directory\n"
            self.assertEqual("INFRA", classify(out, 2, staging=staging)[0])

    def test_cant_open_file_without_staging_uses_changed_files(self):
        out = "python: can't open file 'moved.py': [Errno 2] No such file or directory\n"
        self.assertEqual("CODE", classify(out, 2, changed_files=["src/moved.py"], staging=None)[0])
        self.assertEqual("INFRA", classify(out, 2, changed_files=["other.py"], staging=None)[0])


if __name__ == "__main__":
    unittest.main()
