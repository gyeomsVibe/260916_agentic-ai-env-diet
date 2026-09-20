# [R2] Rework: close fail-open summary and approval gates

Modify only `v7_harness/control.py`. Do not edit tests, existing harness modules, cards, plans, or evidence.

The current implementation passes `tests.test_r2_minimal_control` but independent counterexamples in `tests.test_r2_contract_gaps` expose nine fail-open cases.

Required changes:

1. Before reading identity/ledger or invoking approval, require the first summary to have exactly the success semantics needed by the contract: `state == "SUCCEEDED"`, `verdict_hint == "PASS"`, `promotion == "DRY_RUN_PASSED"`, `acceptance_exit == 0`, and `effect_state != "UNKNOWN"`. Any other summary value must return nonzero `SUMMARY_INVALID`, except the existing explicit `UNKNOWN_EFFECT` behavior may remain for an UNKNOWN effect.
2. After the approval process returns, scan both stdout and stderr for the same raw infrastructure/helper failure markers used for the first process. A marker must return nonzero `HELPER_FAILURE` even when exit code is 0.
3. Parse approval stdout once and require `state == "SUCCEEDED"`, `verdict_hint == "PASS"`, `effect_state != "UNKNOWN"`, exact bundle equality, and `promotion == "APPLIED"`. The field mismatches exercised by the fixed gap tests must return nonzero `APPROVAL_MISMATCH`; a non-APPLIED promotion without an explicit mismatch may retain `PASS_WITHOUT_APPLIED` where the original fixed test requires it.
4. Preserve all existing behavior and keep the file dependency-free and narrow.

Acceptance:

`python -m unittest -v tests.test_r2_minimal_control tests.test_r2_contract_gaps`

No other file may change.
