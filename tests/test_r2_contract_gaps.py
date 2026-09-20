"""r8 counterexamples: control.py must enforce every step-4 and step-6 contract field."""

import json
import subprocess
import unittest

from tests.test_r2_minimal_control import FakePilotRunner, MinimalControlLayerTests
from v7_harness.control import run_control
from v7_harness.isolation.promotion import build_manifest


class GapRunner(FakePilotRunner):
    def __init__(self, config, *, field=None, value=None, where="summary", marker=False):
        super().__init__(config)
        self.field, self.value, self.where, self.marker = field, value, where, marker

    def _write_first_run(self) -> None:
        super()._write_first_run()
        if self.where == "summary" and self.field:
            path = self.config.work_dir / "runs" / self.config.task_id / "summary.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data[self.field] = self.value
            path.write_text(json.dumps(data), encoding="utf-8")

    def __call__(self, argv, **kwargs):
        result = super().__call__(argv, **kwargs)
        if "--approve" in argv:
            data = json.loads(result.stdout)
            if self.where == "approval" and self.field:
                data[self.field] = self.value
            stderr = "helper_unknown_error: setup refresh had errors" if self.marker else ""
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(data), stderr=stderr)
        return result


class R2ContractGapTests(MinimalControlLayerTests):
    def _gap(self, expected, **kw):
        runner = GapRunner(self.config, **kw)
        receipt = run_control(self.config, runner=runner)
        self.assertFalse(receipt["ok"], kw)
        self.assertNotEqual(receipt["exit_code"], 0)
        self.assertEqual(receipt["error_class"], expected, kw)
        self.assertEqual(build_manifest(self.source).manifest_hash, self.before)

    def test_step4_summary_fields_are_all_enforced(self) -> None:
        cases = (
            ("state", "FAILED"),
            ("verdict_hint", "REWORK"),
            ("promotion", "BLOCKED"),
            ("acceptance_exit", 1),
            ("acceptance_exit", None),
        )
        for i, (field, value) in enumerate(cases):
            with self.subTest(field=field, value=value):
                self.config.work_dir = self.root / f"gap4-{i}"
                self._gap("SUMMARY_INVALID", field=field, value=value, where="summary")

    def test_step6_approval_fields_are_all_enforced(self) -> None:
        cases = (("state", "FAILED"), ("verdict_hint", "REWORK"), ("effect_state", "UNKNOWN"))
        for i, (field, value) in enumerate(cases):
            with self.subTest(field=field, value=value):
                self.config.work_dir = self.root / f"gap6-{i}"
                self._gap("APPROVAL_MISMATCH", field=field, value=value, where="approval")

    def test_step6_raw_infrastructure_marker_fails(self) -> None:
        self.config.work_dir = self.root / "gap6-marker"
        self._gap("HELPER_FAILURE", where="approval", marker=True)


if __name__ == "__main__":
    unittest.main()
