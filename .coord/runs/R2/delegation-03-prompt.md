# [R2] P1 rework — independently observe applied source changes

Modify only `v7_harness/control.py`. Do not modify tests, cards, plans, evidence, or existing harness modules.

## Reproduced root cause

The approval subprocess can print `promotion=APPLIED` and exit 0 while making no source change. The current controller then runs a permissive post-acceptance command and returns `ok=True`. A second case can change the declared file plus an undeclared file and still return success.

The fixed RED acceptance in `tests/test_r2_minimal_control.py` now distinguishes:

- normal apply: declared `calc.py` changes and succeeds;
- `APPLIED` without any observed source change: fail closed as `APPLY_NOT_OBSERVED` before post-acceptance;
- source changes outside the declared `changed_files`: fail closed as `APPLY_MISMATCH` before post-acceptance.

## Required minimal fix

1. Preserve the validated initial summary's `changed_files` as a strict list of safe relative file paths. Missing, empty for this change-required controller, non-list, duplicate, absolute, traversal, or invalid entries must fail closed with a structured nonzero receipt.
2. Immediately after the exact-bundle approval response passes all existing gates, independently rebuild the source manifest before running post-apply acceptance.
3. Diff the pre-run and post-approval manifests by relative path and content/metadata identity.
4. If no source path changed, return `APPLY_NOT_OBSERVED` with nonzero exit and do not run post-apply acceptance.
5. If the observed changed-path set differs from the declared `changed_files` set, return `APPLY_MISMATCH` with nonzero exit and do not run post-apply acceptance.
6. Only after exact observed/declaration equality may post-apply acceptance run and success be returned.
7. Preserve the existing fail-closed summary, identity, SQLite, approval, helper-marker, subprocess-env, and receipt behavior. Do not redesign the harness.

## Fixed acceptance

`python -m unittest -v tests.test_r2_minimal_control tests.test_r2_contract_gaps`

The two new tests must change from RED to PASS and all existing focused cases must remain PASS. No other file may change.
