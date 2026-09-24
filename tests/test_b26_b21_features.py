"""B26 & B21 regression tests: next_action hint on failure and shell operator support in accept_cmd."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from v7_harness.adapters.agy import AgyOutcome
from v7_harness.isolation.manifest import PatchBundle, PatchItem
from v7_harness.isolation.staging import StagingWorkspace
from v7_harness.pilot import PilotConfig, run_pilot


class B26NextActionHintTests(unittest.TestCase):
    def test_unreconciled_attempt_includes_next_action_reconcile(self) -> None:
        """Verify summary on unreconciled attempt provides explicit reconcile command in next_action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir) / "work"
            config = PilotConfig(
                task_id="B26_UNREC",
                title="Unrec task",
                prompt="dummy",
                source_dir=Path("."),
                work_dir=work_dir,
                agy_command=["dummy"],
                watch_roots=[],
            )

            # Insert an unreconciled attempt into sqlite
            db_path = work_dir / "coord.sqlite3"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            from v7_harness.broker.core import BrokerCore
            core = BrokerCore(db_path)
            core.start()
            h64 = "a" * 64
            core.connection.execute(
                "INSERT INTO plans(task_id, card_revision, status, depends_json, acceptance_hash) "
                f"VALUES('B26_UNREC', 1, 'ACTIVE', '[]', '{h64}')"
            )
            core.connection.execute(
                "INSERT INTO attempts(attempt_id, task_id, call_depth, max_hops, state, idempotency_key) "
                "VALUES('B26_UNREC-a001', 'B26_UNREC', 0, 3, 'RUNNING', 'idem_b26')"
            )
            core.connection.commit()
            core.close()

            summary = run_pilot(config)
            self.assertEqual(summary["state"], "FAILED")
            self.assertEqual(summary["error_class"], "NEEDS_RECONCILIATION")
            self.assertIn("next_action", summary)
            self.assertIn("pilot reconcile --task B26_UNREC", summary["next_action"])


class B21ShellAcceptCmdTests(unittest.TestCase):
    def test_accept_cmd_with_shell_operators_executes_successfully(self) -> None:
        """Verify accept_cmd with pipe/chaining shell operators succeeds with acceptance_exit 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir) / "work"
            staging_dir = work_dir / "stage" / "B21_SHELL"
            staging_dir.mkdir(parents=True, exist_ok=True)

            dummy_bundle = PatchBundle(
                bundle_id="bnd_b21",
                base_manifest_hash="base",
                target_manifest_hash="target",
                items=[
                    PatchItem(
                        path="calc.py",
                        change_type="MODIFIED",
                        base_sha256="abc",
                        target_sha256="def",
                        patch_data="dummy",
                        patch_hash="h1",
                    )
                ],
            )
            dummy_ws = StagingWorkspace(
                source_dir=Path(".").resolve(),
                staging_dir=staging_dir.resolve(),
                base_manifest=None,
                base_manifest_hash="abc",
            )

            class DummyWatch:
                def assert_unchanged(self) -> None:
                    pass

            launcher_inst = mock.MagicMock()
            launcher_inst.last_outcome = AgyOutcome(
                successful=True,
                status="SUCCESS",
                error_class="NONE",
                effect_state="CONFIRMED",
                retryable=False,
                conversation_id="conv_b21",
                usage={"input_tokens": 100},
            )
            launcher_inst.raw_paths = (Path("stdout.json"), Path("stderr.err"))

            config = PilotConfig(
                task_id="B21_SHELL",
                title="Shell operator test",
                prompt="test shell ops",
                source_dir=Path("."),
                work_dir=work_dir,
                agy_command=["dummy_agy"],
                watch_roots=[],
                accept_cmd='python -c "print(123)" | python -c "import sys; assert \'123\' in sys.stdin.read()"',
            )

            # source_dir is the real project, so keep the U27 auto-record out of its usage ledger.
            with mock.patch("v7_harness.coord.usage_ledger.record_usage"), \
                    mock.patch("v7_harness.pilot.NonGitStagingAdapter") as mock_adapter_cls:
                mock_adapter_cls.return_value.create_staging.return_value = dummy_ws
                with mock.patch("v7_harness.pilot.snapshot_watch_roots", return_value=DummyWatch()):
                    with mock.patch("v7_harness.pilot.DurableExecutionEngine.execute", return_value=None):
                        with mock.patch("v7_harness.pilot.AgyProcessLauncher", return_value=launcher_inst):
                            with mock.patch("v7_harness.pilot.dry_run_promotion") as mock_dry:
                                mock_dry.return_value = mock.Mock(success=True, status="DRY_RUN_PASSED")
                                with mock.patch("v7_harness.isolation.staging.StagingWorkspace.create_patch_bundle", return_value=dummy_bundle):
                                    with mock.patch("v7_harness.pilot._write_summary"):
                                        summary = run_pilot(config)

            self.assertEqual(summary["state"], "SUCCEEDED")
            self.assertEqual(summary["acceptance_exit"], 0)
            self.assertEqual(summary["verdict_hint"], "PASS")


if __name__ == "__main__":
    unittest.main()
