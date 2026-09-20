# [U12] durable execution

- Status: DONE
- Owner: Codex (implementation draft: Antigravity via antigravity-bridge)
- Conversation: [U12] durable execution
- Depends on: U11
- Started at: 2026-09-17
- Scope: `v7_harness/execution/**`, `tests/test_u12_execution.py`, U12-required forward migration and migration tests in `v7_harness/contracts/database.py` and `tests/test_u10_contracts.py`, strictly necessary bounded integration changes under `v7_harness/broker/**`, this card, and `.coord/PLAN.md` U12 status
- Excludes: real Antigravity/Claude execution, auto-promotion, MCP adapter, global rules/settings, service install, external network/effects, delete/overwrite, push/deploy, system/account/credential/permission mutation, U13 creation/start
- Outcome: durable deliveries, claim/ack lifecycle, lease/fencing, retry budgets/circuits, bounded single-writer dispatcher, and mock worker launcher with recoverable at-least-once/idempotent behavior
- Acceptance: conditional delivery transitions; lease expiry/revoke/fence bump; stale worker checkpoint/receipt/effect/promotion rejection; retry budget and same-root-cause third-failure circuit open; quota `UNKNOWN` fail-closed; timeout/crash/partial-result handling; commit-before-response replay; graceful drain; subprocess waits outside DB transactions; no external effect/network/real AI worker
- Verification: `python -m unittest tests.test_u12_execution`, `python -m unittest tests.test_u11_broker`, `python -m unittest tests.test_u10_contracts`, `python -m unittest discover -s tests -p "test_*.py"`, `python -m compileall -q v7_harness tests`; exact counts and exit codes recorded

## Decisions

- Only the broker owner thread may touch the writable SQLite connection. Concurrent clients submit bounded commands through a bounded in-memory dispatcher queue.
- Queue saturation fails quickly and retryably; it must not wait without a bound or expose a DB bypass.
- Worker subprocess waiting occurs outside every SQLite transaction.
- Unknown external-effect outcome is non-retryable and fail-closed. Quota `UNKNOWN` does not launch work.
- Circuit half-open permits only a bounded canary; ordinary work remains blocked until the canary succeeds.
- Cost/token savings remain `UNMEASURED`.

## Work log

- 2026-09-17: U11 `DONE`, PLAN U12 `READY`, authoritative U09 design and U10/U11 dependencies confirmed. The workspace is not a Git repository; `git status --short` returned exit 128, so no Git mutation was attempted.
- 2026-09-17: Card created and U12 claimed `ACTIVE` before implementation.
- 2026-09-17: `antigravity-bridge` health passed (`agy 1.2.4`, sandbox=true, auto_approve=false). One job `mu504hw8_6qpz8p` produced an allowed-path draft after 432091 ms. Its prose and exit claims were not trusted; Codex inspected the files and reran tests.
- 2026-09-17: Codex review found that the draft could roll back failure-state updates when raising inside a SQLite transaction, kept circuit counts only in memory, omitted bounded attempt/elapsed/turn/token/tool retry accounting, and did not wire the dispatcher into the real IPC boundary. These were corrected with commit-then-raise failure handling, SQLite-backed consecutive-failure/reset events, durable multidimensional reservations, exclusive half-open canary reservation, bounded drain/stop, and concurrent IPC connection handling through the single owner-thread dispatcher.
- 2026-09-17: Added commit-before-response-loss replay, durable budget/circuit restart, consecutive-failure reset, single half-open canary, and real IPC silent-peer/concurrent-client counterexamples. Worker waits remain outside DB transactions; no real AI worker, network, or external effect was used.
- 2026-09-17: Claude Code 2.1.270 preflight passed. One read-only `--tools Read --permission-mode plan` CRITIC/REDTEAM process was started and bounded; it exited without recoverable stdout, so the review result is `UNAVAILABLE` and the call was not repeated. No Claude prose or exit status was used as acceptance evidence.
- 2026-09-17: Final independent verification passed U12 15 tests, U11 11 tests, U10 19 tests, all 100 tests, and compileall; every command exited 0. U12 returns to `REVIEW`; U13 was not created or started.
- 2026-09-17: Independent review rejected U12 after reproducing false success when an observable effect callback raised after ACK/SUCCEEDED/PASS/CONFIRMED had already committed. U12 was returned to `READY` and immediately re-claimed `ACTIVE` in the same dedicated stage. Rework scope explicitly includes checksum-pinned migration v2 and U10 migration regressions; U13 remains unopened.
- 2026-09-17: Systematic root-cause reproduction failed exactly at `engine.py`'s post-commit `effect_callback()` call: the callback raised raw `RuntimeError` after success state was already durable. A failing regression was added before implementation.
- 2026-09-17: Observable effects now use durable `INTENDED` before the callback, run outside every DB transaction, then conditionally transition to `CONFIRMED` only before PASS/SUCCEEDED/ACK in one Phase 3 transaction. Callback exception defaults to `UNKNOWN` + `NEEDS_RECONCILIATION`, non-retryable, with zero PASS/CONFIRMED/ACK/SUCCEEDED. Only explicit `not_applied` mode is retryable and can safely reuse the same idempotency key/fenced effect row.
- 2026-09-17: Removed hot-path DDL. Checksum-pinned migration v2 now owns `execution_budget_usage` and payload-free `execution_stage_events`. New DB, v1→v2 upgrade, reapply idempotency, v2 checksum mismatch, and newer-schema refusal are covered. Stage evidence records wall time plus monotonic submit/claim/worker-finish/ack ticks; no latency SLO is claimed before benchmark measurement.
- 2026-09-17: Final rework verification passed the direct effect counterexamples, U12 23 tests, U11 11 tests, U10 21 tests, all 110 tests, and compileall; every final command exited 0. U12 returns to `REVIEW`; U13 remains unopened.

## Handoff

- Result: Implemented durable conditional claim/ack execution, monotonic lease/fence enforcement, stale write/promotion rejection, SQLite-backed multidimensional retry budgets and consecutive-failure circuits, quota UNKNOWN fail-closed, mock subprocess fault handling, commit-before-response replay, and bounded graceful drain. Observable effects are now prepared as `INTENDED`, executed outside transactions, and committed as success only after confirmed callback return; ambiguous callback failure becomes durable non-retryable reconciliation with no false success. IPC connections execute concurrently while all SQLite work passes through one bounded owner-thread dispatcher.
- Changed: `v7_harness/contracts/database.py` (checksum-pinned migration v2), `v7_harness/execution/__init__.py`, `v7_harness/execution/errors.py`, `v7_harness/execution/dispatcher.py`, `v7_harness/execution/lease.py`, `v7_harness/execution/circuit.py`, `v7_harness/execution/launcher.py`, `v7_harness/execution/engine.py`, `v7_harness/broker/core.py`, `v7_harness/broker/ipc.py`, `tests/test_u10_contracts.py`, `tests/test_u12_execution.py`, this card, and `.coord/PLAN.md` U12 status.
- Checks and exit codes:
  - `git status --short` -> exit 128 (workspace is not a Git repository; no Git mutation attempted)
  - `antigravity_health` -> ok, `agy 1.2.4`, sandbox=true, auto_approve=false
  - Antigravity job `mu504hw8_6qpz8p` -> status done after 432091 ms; filesystem and tests independently reviewed
  - `claude --version` -> exit 0 (`2.1.270`); one read-only CRITIC/REDTEAM -> process exited, stdout/result unavailable, not used as evidence
  - Direct effect regression trio -> exit 0, 3 tests: callback UNKNOWN path, safe not-applied retry, commit-before-response replay
  - Direct migration regression trio -> exit 0, 3 tests: new v2 schema, v1→v2/idempotency/checksum, newer-schema refusal
  - `python -m unittest tests.test_u12_execution` -> exit 0, 23 tests
  - `python -m unittest tests.test_u11_broker` -> exit 0, 11 tests
  - `python -m unittest tests.test_u10_contracts` -> exit 0, 21 tests
  - `python -m unittest discover -s tests -p "test_*.py"` -> exit 0, 110 tests
  - `python -m compileall -q v7_harness tests` -> exit 0
- Failure history:
  - Antigravity draft initially passed 10 U12 tests, but Codex review rejected its transaction rollback, in-memory circuit, missing retry-budget dimensions, and unwired IPC dispatcher gaps before final acceptance.
  - First U11 run after IPC dispatcher integration -> exit 1 (11 tests, 2 failures): missing `time` import plus STOP could not unblock `Listener.accept()`. Import added and a bounded local wake connection implemented.
  - Focused U11 graceful-stop tests after import-only fix -> exit 1 (2 tests, 2 failures); local wake fix then -> exit 0 (2 tests).
  - First focused U12 IPC concurrency test -> exit 1 (1 test): test sent U12-only metadata through the strict U10 command schema. Fixture was narrowed to the authoritative command fields; rerun -> exit 0 (1 test).
  - Independent-review direct callback counterexample before fix -> exit 1 (1 test, 1 error): raw callback `RuntimeError` escaped after DB already held ACK/SUCCEEDED/PASS/CONFIRMED. After lifecycle reorder the focused test and full suite pass.
- Remaining risks: Windows Named Pipe current-user DACL and stdlib accept-level guarantees remain `UNKNOWN` from U11. Power-loss/fsync hardware semantics, real worker process-tree containment, real quota-provider reset behavior, and provider-specific external-effect reconciliation remain untested. Stage events make queue/worker/end-to-end latency measurable, but real-time guarantees and high-load latency remain `UNKNOWN` until a later benchmark. Cost/token savings are `UNMEASURED`.
- Next action: Coordinator independently reviews the U12 evidence and sets U12 to `DONE` or returns this same U12 to `READY` for rework. Do not create or start U13.

## Independent review

- Verdict: PASS after one rejected review; U12 `DONE`.
- Reproduced rejection case: an observable effect callback raised after the original implementation had already committed `ACKED/SUCCEEDED/CONFIRMED/PASS`.
- Accepted rework: `INTENDED` is committed first, the callback runs outside SQLite transactions, success is committed only after callback return, and ambiguous failure becomes one non-retryable `UNKNOWN` plus `NEEDS_RECONCILIATION` with no PASS/ACK/SUCCEEDED.
- Direct probe after rework: ACK 0, SUCCEEDED 0, PASS 0, CONFIRMED 0, UNKNOWN 1; the second execution was rejected and the callback count remained one.
- Runtime DDL was removed. Migrations v1/v2 are checksum-pinned and fresh, upgrade, idempotency, tamper, newer-schema, and unmigrated hot-path cases are covered.
- Independent checks: U12 23 tests, U11 11 tests, U10 21 tests, full discovery 110 tests, direct probe, and compileall all exited 0.
- Timing evidence records stage/state/timestamps only. Realtime latency, cross-reboot monotonic comparability, high-load fairness, and cost/token savings remain `UNKNOWN`/`UNMEASURED` until U16.

## Rework gate from Claude memo 04

- U12 was reopened after static review matched the current code: timeout was classified as effect `NONE` and retryable; Windows killed only the direct process; stale/expired late results left no durable UNKNOWN effect; renewal existed as a helper but was not connected to running workers.
- U13 is held and its partial isolation draft is not integrated until these gates pass.
- Required evidence: effectful timeout UNKNOWN/non-retryable; child-process survivors 0; expired lease state persists; late stale result records UNKNOWN/reconciliation; conditional renew permits current fence and rejects stale renew.

## U12-R1 handoff (2026-09-17)

- Result: effectful or unspecified timeout is durable `UNKNOWN` + `NEEDS_RECONCILIATION` and non-retryable; only explicit `read_only` timeout is `NONE` and retryable. Windows timeout uses a kill-on-close Job Object with a process-tree fallback. Expired lease rejection survives caller rollback. Stale/expired late results record one non-retryable UNKNOWN effect, reconciliation stage/event, zero ACK/PASS/SUCCEEDED, and reject automatic retry. Heartbeat renewal is wired through the engine and succeeds only for matching owner+attempt+resource+fence.
- Privacy: execution stage/events persist hashes, references, state, and timestamps only; prompt/output source text is not stored in U12 DB/event/log paths.
- Antigravity: existing job `mu51j3go_x4iqap` was polled without duplicate delegation. The result endpoint remained stale at `running`, while the cancel/status probe returned `not_running`; its prose and claimed test state were not used as evidence. Codex reviewed the current files and ran every check below independently.
- Checks and exit codes:
  - `git status --short` -> exit 128 (workspace is not a Git repository)
  - five named direct counterexamples -> exit 0, 5 tests
  - `python -m unittest tests.test_u12_execution` -> exit 0, 28 tests
  - `python -m unittest tests.test_u11_broker` -> exit 0, 11 tests
  - `python -m unittest tests.test_u10_contracts` -> exit 0, 21 tests
  - `python -m unittest discover -s tests -p "test_*.py"` -> exit 0, 115 tests
  - `python -m compileall -q v7_harness tests` -> exit 0
- Independent review notes: direct Windows child PID probe observed zero survivor; timeout classification, EXPIRED persistence, late-result fail-closed state, and conditional renewal all passed their named counterexamples. No U13 file was opened, modified, integrated, or tested.
- Remaining risks: Job Object assignment and `taskkill` fallback are verified only by the local Windows mock; real provider worker trees, power-loss/fsync hardware semantics, real quota reset behavior, and provider-specific reconciliation remain untested. Realtime/100% delivery, latency SLO, and cross-reboot monotonic comparison remain `UNKNOWN`; cost/token savings remain `UNMEASURED`.
- Next action: coordinator reviews this evidence and sets U12 to `DONE` or returns U12 to `READY`. U13 remains `READY (HOLD: U12 rework)` and U14 remains unopened.

## U12-R1 coordinator gate (2026-09-17)

- Verdict: PASS; U12 `DONE` and only U13 HOLD released.
- Independent counterexamples: the five named timeout/process-tree/expiry/late-result/renewal tests passed 5/5, exit 0. An earlier selector run used the wrong plural class name and produced five loader errors; it was explicitly excluded rather than hidden by later chained-command exit 0.
- Independent regressions: U12 28, U11 11, U10 21, full discovery 115, and compileall each passed. The Antigravity claim of premature U13 verification was excluded from U12 evidence because it violated the held-stage boundary.
- Residuals remain unchanged: realtime/100% delivery and latency are `UNKNOWN`; cost/token savings are `UNMEASURED`; real provider trees and reconciliation remain untested.
- Next action: open U13 as the sole active dedicated stage. Keep U14 unopened.

## U12-R2 final handoff (2026-09-17)

- Result: Claude memo 04 cases 1~5 are implemented and independently reproduced. Effectful/unknown timeout is `UNKNOWN + NEEDS_RECONCILIATION + non-retryable`; only explicit `read_only` is `NONE + retryable`. Windows mock timeout terminates the launcher-owned process tree with child PID survivor 0. Expired lease uses local commit-then-reject and persists `EXPIRED`. Stale/expired late results durably record one UNKNOWN effect, reconciliation event/stage, and `NEEDS_RECONCILIATION`, with ACK/PASS/SUCCEEDED 0 and retry blocked. Conditional renewal requires owner+attempt+resource+fence and is called repeatedly while the worker runs.
- Antigravity: exactly one sandboxed/auto-approve-disabled U12 draft job was used: `mu51i79h_it4xjc`. Its prose/test claims were not accepted directly. Codex rejected operation-based read-only inference, one-shot heartbeat, global SQLite rollback interception, incomplete Win32 handle typing, and unsafe POSIX process-group assumptions, then independently reworked and tested the files.
- Privacy/timing: stage/event records contain process/lease/effect state, hashes/references, wall time, and monotonic timing only; no raw prompt/output is stored. Realtime and latency SLO remain `UNKNOWN` until U16.
- Checks and exit codes:
  - Initial five P1 counterexamples before implementation -> exit 1 (5 tests: 1 failure, 4 errors)
  - Final five named P1 counterexamples -> exit 0 (5 tests)
  - `python -m unittest tests.test_u12_execution` -> exit 0 (29 tests)
  - `python -m unittest tests.test_u11_broker` -> exit 0 (11 tests)
  - `python -m unittest tests.test_u10_contracts` -> exit 0 (21 tests)
  - `python -m unittest discover -s tests -p "test_*.py"` -> exit 0 (116 tests)
  - `python -m compileall -q v7_harness tests` -> exit 0
- Failure history: after replacing the Antigravity draft's one-shot heartbeat and capability inference, the first full U12 run failed 1/28 because the older timeout test still expected `FAILED`; it was corrected to the new fail-closed `NEEDS_RECONCILIATION` contract. A later full U12 run failed 1/29 because a 1-second SQLite circuit cooldown test crossed second-granularity time; the deterministic fixture cooldown was raised to 60 seconds, after which all final runs passed.
- Remaining risks: Job Object plus fallback is verified only against launcher-owned Windows mock processes; real provider trees and POSIX multi-generation tree termination are untested. Power-loss/fsync behavior, provider-specific effect reconciliation, real quota reset, high-load fairness, realtime latency, and cross-reboot monotonic comparison remain `UNKNOWN`; cost/token savings remain `UNMEASURED`.
- Next action: coordinator independently reviews this R2 evidence and sets U12 to `DONE` or returns the same U12 to `READY`. U13 remains on HOLD and U14 remains unopened.
