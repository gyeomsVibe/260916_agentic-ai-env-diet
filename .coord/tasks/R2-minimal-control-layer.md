# [R2] 최소 제어층 후보

- Status: DONE (R2FIX15 APPLIED; Codex independent re-review passed)
- Owner: Codex (design/review), Antigravity (implementation only after activation)
- Conversation: [R2] 최소 결정적 제어층 (`01a0b792-c54c-76d1-b6a2-607fd1ce8d8e`)
- Depends on: R1 `BLOCKED` evidence
- Started at: 2026-09-19T12:00:00+09:00
- Scope: `v7_harness/control.py` (new minimal controller only), `tests/test_r2_minimal_control.py` (new fixed counterexamples), `.coord/runs/R2/**`, this card, and `.coord/PLAN.md`
- Excludes: existing pilot/CLI/broker/isolation implementation changes, harness-wide redesign, watch-root weakening, Antigravity Bridge, historical P05 or R1 artifact mutation, deployment/push/global settings, and R3 measurement
- Outcome: remove the nested Codex `exec_command` helper from the B critical path while preserving a measurable, explicit controller-cost boundary.
- Acceptance: a local-process controller accepts a predeclared fresh task/source/work-dir and launches exactly one blocking `pilot run`; reads the resulting summary exactly once; independently opens the fresh SQLite ledger and binds task/run/source/bundle identities; only the exact `PASS` bundle is replayed once with `--approve`; requires `promotion=APPLIED` and an independent post-apply acceptance exit 0; rejects an existing work-dir and duplicate execution; returns a fail-closed structured nonzero result for launch failure, timeout/UNKNOWN effect, missing or non-JSON summary, stale ledger, any task/run/source/bundle mismatch, PASS without APPLIED, approval mismatch, post-apply failure, or raw helper error even when a wrapped process reports exit 0; preserves CLI HOME/TEMP watch defaults.
- Verification: fixed R2 counterexamples for pilot-not-started, missing/non-JSON summary, stale ledger, task/run/source/bundle mismatch, PASS-without-APPLIED, approval mismatch, post-apply failure, raw-helper-error-plus-exit-0, duplicate/existing work-dir, and timeout/UNKNOWN effect; focused R2; R0 validity; B46; full discovery; compileall; immutable historical hash.

## Trigger evidence

- R1 B controller event `.coord/runs/R1/P05-R1-B-20260919-01-controller.jsonl` contains two `helper_unknown_error: setup refresh had errors` failures before any pilot process or SQLite ledger was created.
- The nested controller returned exit 0 with `BLOCKED, NOT_APPROVED`, so process exit alone hid the infrastructure failure.
- This reproduces the historical P05 helper failure class and is a concrete control-path defect, not a SQLite pilot performance result.

## Constraint

- No R2 implementation was performed in R1. R2 is now claimed in this dedicated conversation with WIP=1.

## Decisions

- `/CRITIC`: process exit 0 is never sufficient; success requires the complete pilot/ledger/bundle/apply/post-acceptance evidence chain.
- `/STEPBYSTEP`: preflight freshness -> one run -> one summary read -> independent ledger identity -> exact-bundle approval replay -> APPLIED -> independent acceptance -> structured terminal receipt.
- `/REDTEAM`: every named counterexample above is fixed before implementation and must fail closed without source mutation.

## Work log

- 2026-09-19: Claimed `ACTIVE`. Workspace is intentionally non-Git (`git status` exit 128); existing changes are preserved by a strict allowlist and historical artifact hashes.
- 2026-09-19: Context-recovery takeover. Previous conversation `[R2] 최소 결정적 제어층` (`01a0b792-c54c-76d1-b6a2-607fd1ce8d8e`) remained an `active` ghost for more than seven minutes after a usage-limit stop and two resume requests, with zero items/tool activity and zero related pilot processes. This replacement conversation `[R2-R1] 최소 결정적 제어층 복구` (`01a0b8db-de11-7ea3-9f6a-239de0d18a44`) is the sole R2 owner and reclaims `ACTIVE`; if another R2 executor appears, this owner must stop immediately.
- 2026-09-19: Handoff evidence received: R2FIX3 bundle `1608333f5c90a48e1169d7435e0a4a40096bb145294634eef6e1dde5efef30a6` was `PASS/APPLIED`, but its acceptance is superseded by two later fixed source tests. Independent coordinator evidence reported focused discovery at 39 tests with two substantive counterexamples failing (six duplicated discovery failures, one skipped), full discovery at 331 tests with the same failures, `compileall` exit 0, and unchanged historical P05 `ab` hash. Claude Code 2.1.270 read-only critique produced no output for four minutes and is recorded as `UNAVAILABLE`, never as success evidence.
- 2026-09-19: `systematic-debugging` Phase 1-3 evidence fixed before implementation. Phase 1: the reproducible failures are `test_applied_without_observed_source_change_fails_closed` and `test_applied_with_undeclared_source_change_fails_closed`; both show a receipt with `ok=True` when an approval summary claims `APPLIED` despite either no observed source-manifest change or a change outside declared `changed_files`. Phase 2: the existing identity/ledger/promotion checks validate reported metadata but do not bind promotion to an independently observed before/after source manifest. Phase 3 single hypothesis: `v7_harness/control.py` omits comparison of the actual pre/post approval source-manifest diff with the bundle's declared `changed_files`. The minimal test is to require every non-empty bundle to produce a non-empty observed diff exactly equal to declared `changed_files`, with any empty or mismatched diff returning a structured fail-closed error. The two fixed tests must not be modified.
- 2026-09-19T17:49:26+09:00: Ownership-conflict stop condition triggered. The previous conversation `01a0b792-c54c-76d1-b6a2-607fd1ce8d8e` resumed its in-progress turn and launched an unrequested-by-this-owner `R2FIX4` chain: PowerShell PID 20024, Python pilot PID 3472, and `agy.exe` PID 20032 using `.work/pilot_R2FIX4` and `.coord/runs/R2/delegation-03-prompt.md`. `read_thread` confirms the previous conversation is still `active` with an in-progress empty-item turn. Per the takeover contract, this replacement executor stopped immediately without editing `v7_harness/control.py`, running tests, reading pilot result/summary, approving a bundle, or starting R3. Coordinator action is required to select one owner and reconcile the surviving pilot before R2 can continue.
- 2026-09-19: The surviving official `R2FIX4` pilot completed once in `.work/pilot_R2FIX4`. Worker output was limited to `v7_harness/control.py`, bundle `627b12c0a18cccf5c95b50dc6d19b01bc81a52de0659a159b2381510b483cec4`, but final summary was `FAILED/SOURCE_DIVERGED/REJECTED/BLOCKED`, `acceptance_exit=null`. No approval replay was executed.
- 2026-09-19: Root cause of `SOURCE_DIVERGED` is independently observed concurrent source mutation: this card was rewritten at 17:51:44 while R2FIX4 was active. The replacement executor and original executor overlapped despite WIP=1. Current source still fails the two substantive apply-observation tests (39 run, 6 duplicated failures); historical P05 hash remains `F844872FFA0DAC9AEC39430C288603C374763038EA8B3D52F2F03914CEA940AF`.
- 2026-09-19: Coordinator selected this conversation as the sole owner after all R2FIX4 processes ended. R2FIX4 staging independently passes the two new apply-observation counterexamples (2/2, exit 0), but its rejected bundle remains permanently unapproved. One fresh recovery task `R2FIX5` in `.work/pilot_R2FIX5` is authorized; no card/PLAN writes are permitted while it runs.
- 2026-09-19: Official recovery `R2FIX5` ran once in `.work/pilot_R2FIX5` with no card/PLAN writes by the owner during execution. It produced only `v7_harness/control.py`, bundle `72136a81d05efecd8717793c8ec85d16bd47b0ddac103b36566afe61bfabd6ea`, but ended `FAILED/SOURCE_DIVERGED/REJECTED/BLOCKED`, `acceptance_exit=null`; no approval was executed. Read-only timestamp evidence identifies the external source mutation as `.claude/codex-relay/sent.log` at 18:00:35 during the pilot. Related pilot processes are now 0.
- 2026-09-19: Final recovery `R2FIX6` authorized. Preflight found 0 related pilot/agy/R2 processes, and `.claude/codex-relay/sent.log` length/mtime/SHA256 (`0644C94CB62F2493F0D5C7738FACE14974F0875BF7FE780EF8DDDEA8D9E07497`) remained identical across a 10-second interval. All source writers and commentary are quiesced for the run.
- 2026-09-19: R2FIX6 ended `FAILED/SOURCE_DIVERGED/REJECTED/BLOCKED`, bundle `d92c5c3b9d4a8f64051374a290d89e5c2e6eab67fd51f31b87083bffe1889a89`, `changed_files=[]`, `acceptance_exit=null`; no approval was executed. During the run, external writers modified `v7_harness/control.py`, Claude advisory documents, `.coord/BACKLOG.md`, `.claude/codex-relay/codex_relay.sh`, this R2 card, `AGENTS.md`, and `.coord/PLAN.md`. Related pilot/agy processes are now 0.
- 2026-09-19: This is the third same-family `SOURCE_DIVERGED` promotion failure (R2FIX4, R2FIX5, R2FIX6). Retry limit reached; no further pilot may run in this stage. Current focused suite remains failing: 39 tests, six duplicated failures representing the two substantive apply-observation counterexamples. Historical P05 hash remains `F844872FFA0DAC9AEC39430C288603C374763038EA8B3D52F2F03914CEA940AF`.

## Prior blocked handoff (superseded by authorized R2FIX5 recovery)

- Result: BLOCKED — promotion rejected; no approved R2FIX4 implementation exists.
- Changed by this stage: fixed tests for no observed apply and undeclared apply, R2 prompts/review evidence, card/PLAN only. Production `v7_harness/control.py` was not changed by R2FIX4.
- Checks and exit codes: focused R2 39 tests => 6 failures (two substantive cases duplicated by inheritance), exit 1; R2FIX4 pilot exit 1 with `SOURCE_DIVERGED`; historical hash unchanged. R0/B46/full/compile completion suite was not rerun after the focused blocking failure and is `UNKNOWN` for this closeout.
- Remaining risk: `promotion=APPLIED` can still be accepted without an independently observed exact source diff.
- Next action: do not run R3 or accept existing R3 measurements as dependent evidence. A coordinator must establish a single R2 owner, quiesce source writers, then run a new explicitly authorized fresh pilot; the rejected R2FIX4 bundle must never be approved.
- R2FIX5 addendum: bundle `72136a81d05efecd8717793c8ec85d16bd47b0ddac103b36566afe61bfabd6ea` is also permanently unapproved. Before any future explicitly authorized run, the Codex↔Claude relay writer must be quiesced or moved outside the source manifest by a separately reviewed design change; watch-root safety must not be weakened.
- Final addendum: R2FIX6 bundle `d92c5c3b9d4a8f64051374a290d89e5c2e6eab67fd51f31b87083bffe1889a89` is permanently unapproved. R2 remains BLOCKED and R3 remains dependency-blocked. Full/R0/B46/compile completion verification is not applicable because focused acceptance fails.

## R2FIX7 recovery authorization

- 2026-09-19: After the three failures were stopped and reported, the user accepted the quiet-window mitigation for one exceptional recovery. R2FIX7 is `READY`, not running: Codex is the sole owner; it must create `.work/QUIET_LOCK`, verify its recorded PID, keep every other writer under `.work/notes/`, and use a fresh `.work/pilot_R2FIX7` exactly once. Rejected R2FIX4/5/6 bundles remain permanently unapprovable. Only `PASS` plus exact observed source diff may be approved, followed by focused and full regression. B58 remains a separate post-R2 task and must not be folded into R2FIX7.
- 2026-09-19: R2FIX7 claimed `ACTIVE` by the Codex coordinator after preflight confirmed no lock, no related process, and no existing `.work/pilot_R2FIX7`. No source/card/PLAN write is permitted after the quiet lock is created and until it is released.
- 2026-09-19: R2FIX7 stopped before Antigravity launch while `build_manifest` hashed the source: opening `.coord/PLAN.md` raised `PermissionError [Errno 13]`. The file is not read-only, no related process exists, no summary or bundle was created, protected hashes were captured unchanged, and `pilot reconcile` returned `NOTHING_TO_RECONCILE` (exit 0). The quiet lock was moved to `.work/notes/` as a release record. Do not repeat this execution until the runtime can read `.coord/PLAN.md`; this is an environment/access blocker, not a worker or implementation result.

## Claude proxy runs R2FIX8–11 (Codex usage limit until 21:09, user-directed proxy)

- R2FIX8 (claude-opus-4-6-thinking): QUOTA, no changes, reconciled. R2FIX9 (gemini-3.1-pro-high) bundle `0a776b1f7008510e8837f222f9881a49e2ec56c90659029ea959f39727c39b96`: REWORK (unrelated flaky U13 → B59). R2FIX10 bundle `95a4cc97ff535e2e62bf77bd78b0421d1b417fa909da2e0ca2670d9d81538865`: SOURCE_DIVERGED (IDE memo 56 written during lock) and the stage emptied `tests/test_r2_contract_gaps.py`. R2FIX11 bundle `ce371d86cf15fcc64d7f3633404b623996bc1ccfce43e7007a715af4896b7b43`: PASS with fixed-test hash guard, but control.py contains an explicit test-fitting branch (`getattr(runner, "defect", None) == "post_acceptance_failure"` forces observed == declared). **All four bundles are permanently unapprovable.** Original source and fixed-test hashes unchanged; lock released 19:0x.
- Root cause (B60, Codex decision needed): fixed test `test_post_apply_acceptance_failure_is_not_success` uses `_run()` → `FakePilotRunner`, which never writes source on `--approve`, yet expects `POST_APPLY_ACCEPTANCE_FAILED` with 3 calls. Under the new contract (APPLY_NOT_OBSERVED before post-apply acceptance) that expectation is unreachable honestly. Proposed acceptance fix (Codex only): run that case with `ApplyingFakePilotRunner` carrying `defect="post_acceptance_failure"` (its `__init__` needs a `defect` passthrough). Then one fresh control.py-only pilot.

## R2FIX12–15 (user-directed proxy, 2026-09-19)

- B60 fixed-test correction applied by Antigravity IDE on user instruction (memo 59); Claude verified it equals the memo-57 minimal diff (memo 60). Needs Codex re-approval as an acceptance-criteria change.
- R2FIX12 (gemini pro) and R2FIX13 (opus) QUOTA, reconciled. R2FIX14 LATE_RESULT (heartbeat lost), reconciled, no bundle.
- **R2FIX15 bundle `fec3bdede4dafd831192603dd6d86373454a0163ea8f8061322499b6de7c1f14` APPLIED** after Claude diff review (no runner/test introspection). Post-apply: control.py identical to stage, focused 39 OK, full 331 OK (1 skip), compileall OK, fixed-test hashes unchanged. Status REVIEW pending Codex.
- P3 note: declared `changed_files` are compared without `\` → `/` normalization; a backslash declaration fails closed as APPLY_MISMATCH (safe direction).

## Codex final decision (2026-09-19)

- Status: **DONE**. R2FIX15 identity/summary and exact `control.py` stage-source hash were rechecked; no runner/test introspection pattern was found.
- Independent checks: R2 focused 39/39 OK, R0·B46 15/15 OK, full 331 OK (1 skipped), compileall exit 0, historical P05 SHA256 `F844872FFA0DAC9AEC39430C288603C374763038EA8B3D52F2F03914CEA940AF` unchanged.
- B60 acceptance correction is re-approved as the minimal semantic repair verified in memos 57/59/60. The production contract now fails closed with `APPLY_NOT_OBSERVED` or `APPLY_MISMATCH` before post-apply acceptance.
- Remaining P3 path-normalization note is non-blocking. B58 stays a separate next stage.
