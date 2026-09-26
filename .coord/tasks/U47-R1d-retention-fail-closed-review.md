# U47-R1d review handoff

- State: REVIEW / REWORK. Do not approve either the old R1c bundle or this R1d bundle yet.
- Old bundle rejected: `9988bfc769312faa2e8fc279ef9384a409f1c73eba243ee0ebce37a8bf5fc8a5` allowed a local JSON `approver=user` label to reach `Path.unlink()`.
- New bundle: `8d2894c9b948c6120b62a941f963ad98ee898267f41d5610043b11692752463d` (`worker: apply`, input/output model tokens 0).
- Changed in the isolated stage only: `v7_harness/retention.py`, `v7_harness/cli.py`, `tests/test_u47_retention_stages.py`, `tests/test_u47_retention_safety.py`, and new `tests/test_u47_retention_delete_boundary.py`.
- Red-first evidence: the independent 3-test boundary suite failed 3/3 against the R1c stage. It observed a live `Path.unlink()` attempt, missing archive path-escape rejection, and approval checking before manifest path validation.
- Safe-stage evidence: targeted retention/CLI regression 36/36 passed; full discovery 857 passed with 4 skips in 101.095 seconds; direct CLI purge returned exit 2, `FRESH_DELETE_APPROVAL_REQUIRED`, `deleted=0`, and preserved the original.
- Fixed-gate conflict: source and stage `tests/u47_r1_check.py` both retain SHA-256 `35b12965bd1147abd64bf2ec5f52b8310b591a69e72dbc8c3ba8a7802c37b35d`. That unchanged checker freezes the old deletion-expecting stage test, so the prescribed command exits 1 with `FROZEN_TEST_CHANGED 0b265b60848d6d8201b226e5f45b6de740dbff1e8049c0ad93e899d6d8bdc3f6` before the full suite runs.
- Test-fitting review: the implementation does not inspect test names, runners, fixtures, argv, or environment. `purge_archived()` contains no unlink/delete operation and always refuses a valid archive after read-only validation.
- Coordination note: three `coord ack` attempts were rejected with `MailboxRejected: root must exist and be a directory` because this isolated worktree has no `.coord/mailbox`; the route was stopped after the third identical failure and the main worktree was not written.
- Next binding decision: replace the stale frozen acceptance artifact under a separately authorized gate change, then rebuild the same safety change under the new immutable hash. Until then, keep R1 in REVIEW and do not start R2/D1/release/deploy.
