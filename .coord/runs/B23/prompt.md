Implement B23 only using test-first development.

Problem: concurrent pilot invocations can raise BrokerAlreadyRunning through the CLI and terminate with a traceback. This costs a coordinator turn and violates the structured-summary contract.

Allowed edits only:
- v7_harness/cli.py
- tests/test_m2_pilot.py or a new focused tests/test_b23_structured_errors.py

Acceptance:
1. Add a failing CLI-level regression that makes run_pilot raise BrokerAlreadyRunning.
2. `pilot run` must catch that specific exception and print one valid JSON summary to stdout with the normal compact keys (max 14): state FAILED, error_class BROKER_ALREADY_RUNNING, effect_state NONE, promotion BLOCKED, bundle_id null, changed_files [], conversation_id null, agy_usage {}, agy_workspace derived from work-dir/stage/task, raw paths null or stable paths, summary_path stable, acceptance_exit null, verdict_hint BLOCKED.
3. Return exit 1 and emit no traceback. Do not catch unrelated BaseException or hide programming errors.
4. Preserve all successful and existing failure paths.

Do not edit unrelated files; do not delete, rename, commit, push, deploy, or change global settings.
Run: python -m unittest tests.test_m2_pilot tests.test_m4_efficiency -q
Return a one-line summary only.
