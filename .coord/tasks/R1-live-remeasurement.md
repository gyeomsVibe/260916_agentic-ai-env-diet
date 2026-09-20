# [R1] 기존 SQLite pilot 정상 재측정

- Status: BLOCKED
- Owner: Codex (coordinator/reviewer), Antigravity (single SQLite pilot executor)
- Conversation: [R1] 기존 SQLite pilot 정상 재측정
- Depends on: R0 `DONE` (`R0CLOSE4` PASS/APPLIED); R0V1 is `SUPERSEDED_SOURCE_DIVERGENCE` and must never be approved
- Scope: `.coord/tasks/R1-live-remeasurement.md`, `.coord/PLAN.md`, `.coord/runs/R1/**`, fresh sibling P05 A/B sample directories, one fresh sibling pilot work-dir
- Excludes: harness implementation, R2 control-layer implementation, `.coord/runs/P05/ab.json` mutation, existing pilot ledgers/work-dirs, HOME/TEMP watch weakening, Antigravity Bridge, deletion, push, deployment, payment, account/permission/credential changes
- Outcome: one valid fresh identical-baseline pair compares A (Codex direct) with B (Codex one-turn SQLite pilot), or records the first failed validity gate without converting it into a performance result.
- Verification: fixed R0 12/12; B46 3/3; focused R1 evidence validation; full unittest discovery; compileall; original P05 `ab.json` SHA256 unchanged.

## Fixed measurement contract

- Logical task: P05, using the exact preserved `.coord/runs/P05/prompt.md` task text.
- A label: `R1-P05-A-codex-direct-20260919-01`.
- B pilot task ID: `P05-R1-B-20260919-01`; the generated attempt/run ID must be absent from `pre_run_attempt_ids` captured immediately before B.
- Fresh A source: sibling `260916_pilot_sample_R1_P05_A_20260919_01`.
- Fresh B source: sibling `260916_pilot_sample_R1_P05_B_20260919_01`.
- B work-dir: sibling `260916_pilot_work_R1_P05_B_20260919_01` (must not exist before setup and must not reuse `.coord/pilot`).
- Baseline: both sources are byte-identical copies of the preserved six-test P05 baseline; deterministic manifest hashes must match before either timed run.
- Allowed changed files in each sample: `calc.py`, `test_calc.py` only. No create/delete/rename.
- Acceptance for both: `python -m unittest -q`, direct exit 0, exactly 12 discovered tests, required `power`/`reciprocal` behavior including reciprocal zero error.
- Codex model: the same explicit model for A and the B one-turn controller.
- Antigravity model: fixed explicitly for the B pilot and recorded in evidence.
- Measurement window: wall time of each spawned Codex process, from process start through its final response after acceptance; setup and final independent review are excluded for both.
- B lifecycle: one blocking pilot run, read `summary.json` once, approve only the exact same bundle when `verdict_hint=PASS` and changed files are allowed, then post-apply acceptance exit 0.
- Safety watches: preserve the configured HOME/TEMP fail-closed watch behavior; no excludes or watch roots may be weakened for R1.
- Metrics: record Codex total/cached/noncached input and output/reasoning tokens, wall time, tool events, B `agy_usage`, tests, and lifecycle identity. Cross-provider monetary/total-token savings remain `UNMEASURED` unless a common cost basis exists.

## Pre-run red-team gates

- Stale ledger: reject if B terminal `run_id` existed in the immediate pre-run snapshot.
- Start-state mismatch: reject unless A and B pre-run manifest hashes equal the fixed baseline hash.
- Measurement pollution: reject existing R1 sample/work/output paths rather than overwrite or reuse them.
- Cache distortion: report cached and noncached tokens separately; do not infer monetary savings from raw mixed-provider totals.
- Test mismatch: reject unequal discovery counts or counts other than 12 even if both commands exit 0.
- Execution failure: Codex/Antigravity/quota/helper/timeout/ledger/promotion failures are validity failures, never performance values.
- Identity: summary and independent SQLite ledger must match on task, run, source, and bundle; summary must be PASS/APPLIED and post-apply acceptance must be 0.

## Preserved historical judgment

- Existing P05 B: `INVALID_SETUP`.
- Existing P05 comparison: `INVALID_MEASUREMENT`.
- Existing savings: `UNMEASURED`.
- Original `.coord/runs/P05/ab.json` is immutable historical evidence.

## Work log

- 2026-09-19: R0 evidence independently cross-checked against the R0 card, PLAN closeout, original P05 artifact, and R6 independent verification.
- 2026-09-19: Card created and claimed `ACTIVE`; dangling PLAN reference resolved.
- 2026-09-19: Pre-run red-team found the legacy runner unsuitable for R1 because it reuses historical IDs/artifacts and derives the baseline after A; R1 uses fresh pre-run manifests and unique resources instead.
- 2026-09-19: Fresh A completed validly: 44.882s, Codex input 69,456 (cached 40,960), 12 tests, direct behavior PASS, only `calc.py` and `test_calc.py` modified.
- 2026-09-19: Fresh B controller failed before pilot startup. Two `exec_command` attempts were rejected by `helper_unknown_error: setup refresh had errors`; no external work-dir, SQLite ledger, summary, identity, worker run, bundle, approval, or source change exists.
- 2026-09-19: Raw B controller exit 0, 53.671s, and token values are explicitly excluded from performance comparison. R1 comparison=`INVALID_INFRASTRUCTURE`; savings=`UNMEASURED`.
- 2026-09-19: Final verification passed: corrected raw-event parser detects `helper_unknown_error`; focused R0+B44+B46 17/17 OK; full discovery 279 OK (1 skipped); compileall exit 0; historical `ab.json` SHA256 remains `F844872FFA0DAC9AEC39430C288603C374763038EA8B3D52F2F03914CEA940AF`.

## Handoff

- Result: BLOCKED — no valid A/B pair; B failed before SQLite pilot startup.
- Changed: this card, PLAN, `.coord/runs/R1/**`, fresh A/B samples; B sample remains at the baseline and the B work-dir was never created.
- Checks and exit codes: preflight/final focused 17/17 OK; A acceptance/behavior/discovery exit 0 with 12 tests; B controller process exit 0 but raw event has two helper failures and no pilot evidence; full 279 OK (1 skipped), compileall 0, historical hash unchanged.
- Remaining risks: nested Codex helper startup can fail and can retry despite a one-call prompt; cache asymmetry still limits any future single-pair interpretation.
- Next action: R2 minimum deterministic control layer is the next READY candidate; do not implement it in R1.
