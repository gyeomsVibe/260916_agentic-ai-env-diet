# [R0] 비용절감 측정 유효성 재설계

- Status: DONE
- Owner: Codex (coordinator/reviewer), Antigravity (single pilot executor)
- Conversation: [R0] 비용절감 측정 유효성 재설계
- Depends on: M4 historical record (preserved)
- Scope: `.coord/runs/measure_p05.py`, `tests/test_r0_measurement_validity.py`, `v7_harness/isolation/security.py`, `tests/test_b46_temp_noise.py`, `.coord/runs/R0/**`, this card, `.coord/PLAN.md`
- Excludes: `.coord/runs/P05/ab.json` mutation, global settings, deletion, push, deployment, payment, account/permission/credential changes
- Outcome: invalid P05 B is corrected without rewriting raw history; savings are emitted only after identity, ledger freshness, apply, and post-apply gates pass.
- Verification: fixed original-source R0 acceptance (12/12 OK); B46 narrowed temp noise tests (3/3 OK); full test suite discovery (279 OK, 1 skipped); compileall exit 0; original `.coord/runs/P05/ab.json` SHA256 (`F844872FFA0DAC9AEC39430C288603C374763038EA8B3D52F2F03914CEA940AF`) unchanged.

## Root-cause evidence

- `.coord/runs/codex-measure/P05-B-one-turn.jsonl`: three `helper_unknown_error`, final `UNKNOWN, NOT_APPROVED`, zero tool calls.
- `.coord/runs/P05/ab.json`: `pilot_summary=null`, B=6 tests versus A=12, but `quality_gate=PASS` and `MEASURED_AND_VERIFIED` were recorded. Raw file SHA256 (`F844872FFA0DAC9AEC39430C288603C374763038EA8B3D52F2F03914CEA940AF`) is preserved intact.
- Judgment: B=`INVALID_SETUP`; comparison=`INVALID_MEASUREMENT`; savings=`UNMEASURED`.
- Claude read-only input: `docs/claude-assist/25_p05-measurement-invalid_2026-09-18.md` agrees the B worker never ran. Memo 26 is only a request; locked empty `ask26.log` is not evidence.

## Fixed acceptance & Freshness gate

- `tests/test_r0_measurement_validity.py` is created in the original source before the pilot and executed by absolute path against the candidate via `R0_MEASURE_TARGET`.
- It rejects missing summary, Codex failure, forbidden infrastructure errors, baseline mismatch, missing direct behavior, summary identity mismatch, nonterminal/mismatched ledger, stale pre-run attempt IDs (`INVALID_STALE_RUN`), missing pre-run snapshot (`INVALID_STALE_RUN`), PASS without APPLIED, and failed post-apply acceptance.
- `tool_call_events > 0` and raw test counts are never sufficient.

## Pilot Run History

- **R0V1**: Bundle `f9fc991730c250a3655573e35f4329c9fe381f0a0e7a4cbc63eb6d619cb3f8ba`
  - Status: `SUPERSEDED_SOURCE_DIVERGENCE`
  - Verdict hint: `PASS`, promotion: `DRY_RUN_PASSED`, never approved.
- **R6FIX3**: Bundle `db31d25d9554433023a4d4dd077f2f4c551d0f9d3b13abfd214d935ca7da3fc9`
  - Status: `SUCCEEDED`, verdict hint: `PASS`, promotion: `APPLIED`, acceptance exit 0.
  - Changes: `.coord/runs/measure_p05.py`, `v7_harness/isolation/security.py`.
  - Enforced `pre_run_attempt_ids` snapshot and `INVALID_STALE_RUN` counterexample tests (`test_stale_ledger_from_before_the_b_run_is_rejected`, `test_missing_pre_run_snapshot_is_rejected`).

## Work log

- 2026-09-18: `systematic-debugging` Phase 1-3 complete; root cause and immutable evidence recorded. Fixed acceptance is expected RED before implementation.
- 2026-09-18: Implemented `evaluate_measurement(evidence: dict) -> dict` in `.coord/runs/measure_p05.py` and connected live runner to same validator. Emitted `.coord/runs/R0/p05-correction.json` preserving raw `.coord/runs/P05/ab.json` path while classifying historical B as `INVALID_SETUP`, comparison as `INVALID_MEASUREMENT`, and savings as `UNMEASURED`.
- 2026-09-19: Resolved freshness gate P1 via R6FIX3: added `pre_run_attempt_ids` snapshot validation and `INVALID_STALE_RUN` classification in `measure_p05.py`, narrowed TEMP exclusion patterns in `security.py`. All 12/12 R0 tests and 3/3 B46 tests pass. Full test suite (279 OK, 1 skipped) and compileall exit 0.

## Handoff & Closeout

- Result: DONE
- Preserved: M4 historical record preserved; `.coord/runs/P05/ab.json` hash `F844872FFA0DAC9AEC39430C288603C374763038EA8B3D52F2F03914CEA940AF` unchanged.
- Classifications: B=`INVALID_SETUP`, comparison=`INVALID_MEASUREMENT`, savings=`UNMEASURED`.
- Verification summary:
  - Codex R0 acceptance: 12/12 OK
  - B46 TEMP noise: 3/3 OK
  - Full unittest suite: 279 OK (1 skipped), exit 0
  - Byte compilation (compileall): exit 0
- Next stage: R1 is READY only for fresh identical-baseline measurement. Current savings remain UNMEASURED.
