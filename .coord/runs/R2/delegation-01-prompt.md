# [R2] Minimal deterministic local control layer

Implement exactly one new production file: `v7_harness/control.py`.

Do not modify tests, existing harness modules, cards, plans, evidence, or any other file. The fixed acceptance is `python -m unittest -v tests.test_r2_minimal_control`.

## Public contract

- Export a `ControlConfig` dataclass and `run_control(config, *, runner=subprocess.run) -> dict`.
- `ControlConfig` must support the fields used by the fixed test: `task_id`, `title`, `source_dir`, `prompt_file`, `work_dir`, `agy_command`, `accept_cmd`, `watch_roots`, and `timeout_s`; an optional model is allowed.
- The returned dict is a structured terminal receipt. It always includes at least `ok`, `exit_code`, `error_class`, `task_id`, `run_id`, `source_hash`, `bundle_id`, `promotion`, `post_acceptance_exit`, `pilot_invocations`, and `approval_invocations`.

## Required deterministic lifecycle

1. Fail before spawning if task/source/prompt inputs are invalid or `work_dir` already exists. Never delete or reuse a work-dir.
2. Record a start boundary, compute the original source manifest, and directly spawn one local process for `python -m v7_harness.cli pilot run` with the configured task, source, prompt, title, accept command, work-dir, agy command, watch roots, timeout, and optional model. Do not use Codex, `exec_command`, a shell, or Bridge.
3. Treat launch errors, timeout, nonzero exit, and helper/quota/infrastructure error markers in raw stdout/stderr as failure even if the wrapped process exits 0.
4. Read `<work_dir>/runs/<task>/summary.json` from disk exactly once. Missing or invalid JSON fails closed. Require SUCCEEDED, PASS, non-UNKNOWN effect, DRY_RUN_PASSED, acceptance 0, and a 64-hex bundle.
5. Read `identity.json` and `coord.sqlite3` independently. Require exact agreement across configured task, identity run, current source manifest, summary bundle, exactly one terminal SUCCEEDED attempt for the task, and that run's checkpoint source/bundle hashes. Reject a database older than the controller start boundary and reject extra task attempts.
6. Spawn approval replay once using the exact original argv plus `--approve <the same bundle>`. Parse the approval JSON from stdout; do not reread summary.json. Require process exit 0, no raw infrastructure marker, exact bundle, PASS, SUCCEEDED, non-UNKNOWN effect, and `promotion=APPLIED`. Approval mismatch or PASS without APPLIED is failure.
7. Run the configured acceptance command independently against the applied source with `shell=False`; require exit 0.
8. Any exception or incomplete evidence returns a nonzero structured receipt. A raw process exit 0 alone can never produce success.

## Fixed error classes

At minimum produce the exact classes asserted by the test: `WORK_DIR_NOT_FRESH`, `PILOT_NOT_STARTED`, `PILOT_TIMEOUT`, `HELPER_FAILURE`, `SUMMARY_MISSING`, `SUMMARY_INVALID`, `STALE_LEDGER`, `TASK_ID_MISMATCH`, `RUN_ID_MISMATCH`, `SOURCE_ID_MISMATCH`, `BUNDLE_ID_MISMATCH`, `UNKNOWN_EFFECT`, `PASS_WITHOUT_APPLIED`, `APPROVAL_MISMATCH`, and `POST_APPLY_ACCEPTANCE_FAILED`.

Keep the implementation narrow and dependency-free. Return deterministic failure details without secrets or raw environment data.
