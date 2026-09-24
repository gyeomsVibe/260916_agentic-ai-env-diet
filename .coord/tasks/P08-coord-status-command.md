# P08 — coord status subcommand implementation

## 1. Goal
Add `coord status` subcommand to `v7_harness/cli.py` that inspects and reports system health:
- `lock`: "CLEAN" if no `.work/QUIET_LOCK`, else lock details
- `mailbox_pending`: integer count of files in `.coord/mailbox/inbox/`
- `stream_events`: integer count of events in `.coord/stream/events.jsonl`
- `ledger_entries`: integer count of lines in `.coord/usage/runs.jsonl`
- `reconcile_tasks`: list of task IDs needing reconciliation in `.coord/pilot`
Prints JSON to stdout and returns exit code 0.

## 2. Target Files
- `v7_harness/cli.py`: implement `cmd_coord_status(args)` and register `p_coord_status = p_coord_subs.add_parser("status")`
- `tests/test_cli.py`: add `test_cli_coord_status` verifying exit code 0 and JSON fields

## 3. Acceptance Gate
`python -m unittest tests.test_cli.TestCLI.test_cli_coord_status`

## 4. Work Constraints
- Edits allowed only in `v7_harness/cli.py` and `tests/test_cli.py`.
- No modification outside target files.
- Exit code must be 0.
