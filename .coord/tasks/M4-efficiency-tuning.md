# [M4] 효율 튜닝

- Status: DONE
- Owner: Codex (coordinator, final judgment) — **Codex usage limit until 2026-09-18 00:15; Claude proxy-coordinates on user instruction, Antigravity executes and verifies**
- Executor / independent verifier: Antigravity
- Conversation: [M4] 효율 튜닝
- Depends on: M2, M3 (`DONE`)
- Directive: `docs/claude-assist/12_next-M4-efficiency-and-closeout_2026-09-17.md`
- Scope: `v7_harness/pilot.py`, `v7_harness/cli.py`(pilot 부분), `tests/test_m4_efficiency.py`, `tests/test_m2_pilot.py`(summary 키 수 상한만), project `AGENTS.md`(2줄), `.coord/BACKLOG.md`, `.coord/runs/M4/**`, `.coord/pilot/**` reconcile, sample `260916_pilot_sample*`, this card, PLAN M4 row
- Excludes: global rules, delete of user files, push/deploy, this project's source promotion

## Acceptance (fixed by `tests/test_m4_efficiency.py`, 11 tests)

1. `--accept-cmd`: after a successful agy run with no external write, run the command inside staging. Summary adds `acceptance_exit` and `verdict_hint` (PASS / REWORK / BLOCKED / NEEDS_ACCEPTANCE), max 14 keys.
2. `--approve` is BLOCKED when acceptance failed.
3. Leases are not left ACTIVE after a finished run (found: P01 lease still ACTIVE in `.coord/pilot`).
4. `reconcile_pilot` / `pilot reconcile`: an interrupted attempt (RUNNING/CLAIMED) → attempt FAILED, delivery DEAD, lease REVOKED, event recorded, summary ABANDONED. A rerun then executes fresh with a new attempt. SUCCEEDED runs and source files are never touched.
5. A rerun while an unreconciled attempt exists → `NEEDS_RECONCILIATION` / BLOCKED, agy not run.
6. Codex one-turn rule in project `AGENTS.md`: read `summary.json` once and decide from `verdict_hint`.

## Work log

- 2026-09-17 20:5x: Claude (proxy) created card and failing tests (red confirmed: import error `reconcile_pilot`).
- 2026-09-17 21:0x: Codex cost breakdown recorded (`.coord/runs/M4/codex-cost-breakdown.md`).
- 2026-09-17 21:0x–21:28: Antigravity delegation — default, gemini-3.1-pro-high, claude-sonnet-4-6 hit individual quota; gemini-3.7-flash-high implemented pilot.py/cli.py (+ M2 test key limit 12→14). Scope diff: only allowed files.
- Checks: M4+M2 28 OK; full discovery 207 OK (1 skipped); compileall exit 0.
- Real ledger: `pilot reconcile --task P02 --work-dir .coord/pilot` → ABANDONED, attempt FAILED, delivery DEAD, lease REVOKED.
- AGENTS.md: accept-cmd, blocking single call/no polling, verdict_hint one-turn decision, reconcile rule.
- P03 B live: 37s, agy input 55,972, acceptance exit 0, PASS, approve replay APPLIED (no agy re-run), sample 18 tests OK, external write 0 (`.coord/runs/P03/ab.json`). A pending Codex.
- Independent verification (Antigravity, read-only): PASS, no normal-path P1 (`.coord/runs/M4/independent-verify.json`).

## Handoff

- Result: REVIEW. Codex to judge DONE, run P03 A, and run P04 B itself under the one-turn rule to re-measure Codex cost vs P01 baseline.
- Report for Codex: `docs/claude-assist/14_M4-proxy-report-for-codex-return_2026-09-17.md`.

## Final gate (2026-09-17 21:4x)

- Verdict: PASS; M4 `DONE`.
- Authority: user instruction "빠른 진행을 위해 개입해서 마무리해" during Codex usage limit, with Antigravity independent verification PASS (`.coord/runs/M4/independent-verify.json`) and full regression 207 OK. Codex re-validates on return (read-only, no defect re-hunt).
- Remaining measurement (non-blocking): P03 A (Codex-only) and P04 B (Codex one-turn rule) Codex-cost measurement after Codex usage reset (2026-09-18 00:15), recorded in `.coord/runs/P03/ab.json` and `.coord/runs/P04/`.

## Codex return follow-up (2026-09-18)

- P02 ledger remained reconciled (`FAILED/DEAD`). Stale P04_TEST/P04_DEBUG runs were reconciled to `ABANDONED`; no manual SQL mutation was used.
- P03 A: 139.3s, Codex input 390,550, acceptance exit 0. P04 B: 25.4s, Codex input 60,108, agy total 48,325, acceptance exit 0, `PASS/APPLIED`. Prompts and model conditions differ, so savings remain `UNMEASURED`.
- B22 R4 moved SQLite/staging to a sibling work-dir, then added shallow `work_dir/stage` monitoring with current-task exclusion. B22R4_FIX was PASS/APPLIED; focused 64, full 212 (skip 1), compileall exit 0, and X10 changed from GAP to PASS (`EXTERNAL_WRITE/BLOCKED`, detected=true).
- Antigravity read-only independent verification returned PASS with blocking P1 0. B23 implementation was blocked by genuine HOME/TEMP runtime writes (`.claude.json`, `%TEMP%\\claude`) under the existing fail-closed watch contract; no bundle was applied. B24/B25 remained unopened by WIP=1.

## Final Codex adjudication (2026-09-18)

- Lifecycle status: `DONE` — implementation verification and the required same-task A/B measurement are complete.
- Safety/quality gate: PASS. Antigravity read-only r2 verified B20·B21·B23~B26·B28·B31~B34·B08 as 12/12 PASS with blocking P1 0. The B08 evidence description overstates the production default change, but this does not change the verifier's verdict.
- Efficiency goal: FAIL. On identical P05 task and identical starting state, both paths passed acceptance, but B used 367,347 Codex input tokens versus A 97,270 (`+277.7%`) and took 915.7s versus 81.6s (`+1022.2%`).
- Final decision: `STOP`. Do not adopt the current pilot path as a Codex-saving default and do not continue incremental tuning under M4. Any future attempt requires a separately approved redesign with a new architecture hypothesis and a predeclared same-task measurement gate.
- Residual P2s: accept-command CWD binary hijacking, re-included large-directory watch budget exhaustion, and mandatory `--allow-no-changes` for read-only tasks.
