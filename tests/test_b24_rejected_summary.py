"""B24 regression test: IsolationError during promotion converts to REJECTED summary cleanly."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from v7_harness.isolation.errors import IsolationError
from v7_harness.isolation.manifest import PatchBundle, PatchItem
from v7_harness.pilot import PilotConfig, run_pilot


class B24RejectedSummaryTests(unittest.TestCase):
    def test_promotion_isolation_error_converts_to_rejected_summary(self) -> None:
        """Verify IsolationError during apply_promotion results in REJECTED promotion status without traceback."""
        dummy_bundle = PatchBundle(
            bundle_id="bnd_test_rejected",
            base_manifest_hash="dummy_base",
            target_manifest_hash="dummy_target",
            items=[
                PatchItem(
                    path="deleted.py",
                    change_type="DELETED",
                    base_sha256="abc",
                    target_sha256="",
                    patch_data="dummy_patch",
                    patch_hash="dummy_hash",
                )
            ],
        )

        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir) / "work"
            config = PilotConfig(
                task_id="B24_TEST",
                title="Deletion test",
                prompt="delete a file",
                source_dir=Path("."),
                work_dir=work_dir,
                agy_command=["dummy_agy"],
                watch_roots=[],
                approve_bundle_id="bnd_test_rejected",
                accept_cmd=None,
            )

            class DummyWatch:
                def assert_unchanged(self) -> None:
                    pass

            staging_dir = work_dir / "stage" / "B24_TEST"
            staging_dir.mkdir(parents=True, exist_ok=True)
            from v7_harness.isolation.staging import StagingWorkspace
            dummy_ws = StagingWorkspace(
                source_dir=Path(".").resolve(),
                staging_dir=staging_dir.resolve(),
                base_manifest=None,
                base_manifest_hash="abc",
            )

            # Mock workspace & promotion to simulate IsolationError
            with mock.patch("v7_harness.pilot.NonGitStagingAdapter") as mock_adapter_cls:
                mock_adapter_cls.return_value.create_staging.return_value = dummy_ws
                with mock.patch("v7_harness.pilot.snapshot_watch_roots", return_value=DummyWatch()):
                    from v7_harness.adapters.agy import AgyOutcome
                    launcher_inst = mock.MagicMock()
                    launcher_inst.last_outcome = AgyOutcome(
                        successful=True,
                        status="SUCCESS",
                        error_class="NONE",
                        effect_state="CONFIRMED",
                        retryable=False,
                        conversation_id="conv_b24",
                        usage={"input_tokens": 100},
                    )
                    launcher_inst.raw_paths = (Path("stdout.json"), Path("stderr.err"))
                    with mock.patch("v7_harness.pilot.DurableExecutionEngine.execute", return_value=None):
                        with mock.patch("v7_harness.pilot.AgyProcessLauncher", return_value=launcher_inst):
                            with mock.patch("v7_harness.pilot.dry_run_promotion") as mock_dry:
                                mock_dry.return_value = mock.Mock(success=True, status="DRY_RUN_PASSED")
                                with mock.patch("v7_harness.pilot.apply_promotion", side_effect=IsolationError("Live mutation does not support DELETED")):
                                    with mock.patch("v7_harness.pilot._write_summary"):
                                        with mock.patch("v7_harness.isolation.staging.StagingWorkspace.create_patch_bundle", return_value=dummy_bundle):
                                            summary = run_pilot(config)

            self.assertEqual(summary["state"], "FAILED")
            self.assertEqual(summary["promotion"], "REJECTED")
            self.assertEqual(summary["verdict_hint"], "BLOCKED")
            self.assertEqual(summary["error_class"], "ISOLATION_ERROR")
            # B35 contract: 14 base keys plus up to 4 optional diagnostics.
        self.assertGreaterEqual(len(summary), 14)
        self.assertLessEqual(len(summary), 18)


if __name__ == "__main__":
    unittest.main()
