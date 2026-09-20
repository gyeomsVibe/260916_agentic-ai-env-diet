# [U14] Antigravity·Codex adapters

- Status: DONE (M1)
- Owner: Codex (coordinator). Preparation by Claude under user instruction during coordinator outage.
- Conversation: [U14] Antigravity·Codex adapters
- Depends on: U13 (`DONE`, proxy gate recorded; Codex re-validation pending)
- Prepared at: 2026-09-17 (Asia/Seoul)
- Scope: `v7_harness/adapters/**` (new), `tests/test_u14_adapters.py`, strictly necessary bounded integration with `v7_harness/execution/launcher.py` and `v7_harness/contracts/**`, this card, `.coord/PLAN.md` U14 status
- Excludes: real delegation to Antigravity/Codex in default test runs, live promotion, MCP adapter, global rules/settings, service install, delete/overwrite of user sources, push/deploy, account/credential/permission mutation, U15 creation/start
- Outcome: pure, testable command builders and result parsers for `agy` headless JSON and `codex exec`, a conversation registry binding one conversation per task and tool, and a recursion guard for Antigravity↔Codex calls
- Requirements covered: R05 (Codex coordinator, Antigravity leased executor), R11 (conversation per stage), R12 (`[U##]` prefix), R13 (managed Antigravity as Codex project executor), R14 (managed auto-connect; standalone/imported separation; ask-codex guard), R26 (CLI adapter over broker, MCP optional)

## Acceptance (fixed by failing tests)

`tests/test_u14_adapters.py` — 21 tests + 1 opt-in live canary.

| Group | Contract |
|---|---|
| agy command | headless `-p` + `--output-format json` + `--print-timeout`; exactly one `--add-dir` equal to the leased workspace; never `--continue`/`-c`; resume only via `--conversation <id>`; prompt first line starts with `[U##] <title>`; `--dangerously-skip-permissions` allowed **only** when `isolation_mode == "staging"`, otherwise `AdapterPolicyError`; `--json-schema` forwarded |
| agy result | success requires parsed envelope `status=SUCCESS`, non-empty response, no partial-timeout warning; captures `conversation_id` and `usage`; exit 0 + `status=ERROR` + 503 + "DONE" claim → not successful, `TRANSIENT_CAPACITY`, effect `UNKNOWN`, non-retryable (local E1/E2 evidence); stderr partial-timeout warning → `TIMEOUT_PARTIAL`, effect `UNKNOWN` (agy #1012); empty/invalid JSON/empty response → `VALIDATION`; 429/quota → `QUOTA`; OAuth/login → `AUTH`, non-retryable |
| agy capability | `detect_agy_capabilities(help_text)` exposes `headless_json`; `require_headless_json()` raises `AdapterPolicyError` if `--output-format`, `--json-schema`, `--conversation`, `--add-dir`, `--print-timeout` are missing |
| codex command | resume by explicit session id, never `--last`; always `--skip-git-repo-check`; `advice`/`review` run with `--sandbox read-only`; `execution` from `standalone` mode → `AdapterPolicyError` |
| recursion guard (v9 §12) | allow single advice hop; reject `call_depth > max_hops`; reject same-tool reentry; reject cycle on `(root_task_id, caller, callee, intent_hash)`; reject managed Antigravity → Codex `execution` hand-back; reject standalone call with `mutates_plan=True` |
| conversation registry | `bind(task, tool, id)` idempotent for same id, `ConversationConflictError` for a different id; lookup never crosses tasks |
| live canary (opt-in) | `U14_LIVE_CANARY=1`: installed `agy --help` satisfies `require_headless_json()`; read-only, no quota use |

## Verification

- `python -m unittest tests.test_u14_adapters` → currently **exit 1** (`ModuleNotFoundError: No module named 'v7_harness.adapters'`), expected red.
- `python -m unittest discover -s tests -p "test_u1[0-3]*.py"` → exit 0, 91 tests (prior stages unaffected).
- `python -m unittest discover -s tests -p "test_*.py"` → **exit 1** (147 run, 1 import error from U14 only). Until U14 is implemented, gates for other stages must use the stage-specific commands above, not full discovery.
- After implementation: U14 tests, U10–U13 suites, full discovery, `python -m compileall -q v7_harness tests`; exact counts and exit codes; optional `U14_LIVE_CANARY=1` run recorded separately.

## Decisions

- Adapters are pure (build argv / parse bytes). Process spawning stays in the U12 launcher (Job Object containment, timeout → UNKNOWN effect).
- The exact partial-timeout stderr wording is based on agy #1012 (1.2.2). Implementation must match it case-insensitively on `timeout` + `partial` and record the raw stderr hash.
- (Superseded 2026-09-17) Preparation-time note "Claude did not implement adapters" is historical: implementation was later done by Claude on user instruction (see Implementation handoff). `DONE` judgment still belongs to an independent verifier/coordinator.

## Carried risks

- U13 residuals R1–R5 (locked-file metadata-only detection, whole-root budget failure, reparse TOCTOU, no Antigravity live smoke re-run, no live provider/promotion) still apply before any real delegation.
- Live agy/Codex behaviour may differ by version; only the opt-in canary checks the installed CLI.
- Cost/token savings `UNMEASURED`.

## Work log

- 2026-09-17: Claude prepared this card and `tests/test_u14_adapters.py` (option 2 approved by user). Red state confirmed as above. No production code added.

## Handoff

- Result: PREPARED. Contract fixed by failing tests.
- Next action: coordinator Codex (after usage reset) re-validates U13 proxy gate, reviews this contract, claims U14 `ACTIVE`, and delegates the implementation draft.

## Implementation handoff — Claude proxy for coordinator (2026-09-17)

- Authority: coordinator Codex unavailable (usage limit). User instructed Claude to carry on Codex's work per Claude's recommendation.
- Changed: `v7_harness/adapters/{__init__,errors,agy,codex,guard}.py` (new), `tests/test_u14_adapters.py` (canary fix + 2 hardening tests), this card, PLAN U14 row. No existing module modified.
- Live canary finding: installed `agy` 1.2.4 prints `--help` usage to **stderr**, not stdout. The opt-in canary originally read stdout only and failed with a false `CAPABILITY` error; fixed to read both streams. Integration code that probes CLI capabilities must do the same.
- Hardening beyond the prepared contract (self-REDTEAM): multi-line `task_id`/`title` rejected so the `[U##]` first line cannot be forged; `status=SUCCESS` with non-zero exit → `VALIDATION` (contradictory evidence never accepted); every non-success outcome is `effect_state=UNKNOWN`, `retryable=False` (effects must be reconciled first); envelope success yields `effect_state=PENDING_VERIFICATION`, not `CONFIRMED`, so U13 diff/scope checks remain mandatory; `codex exec resume` (0.154.0) has no `--sandbox`/`-C`, so resume sets `-c sandbox_mode=...`.
- Checks: `python -m unittest tests.test_u14_adapters` with `U14_LIVE_CANARY=1` and `-W error::ResourceWarning` -> exit 0, 24 tests (canary executed); `python -m unittest discover -s tests -p "test_*.py"` -> exit 0, 170 tests (1 skipped: canary without env); `python -m compileall -q v7_harness tests` -> exit 0.
- Separation of duties gap: Claude wrote both the failing tests and the implementation. Acceptance requires an independent verifier (Codex on return, or Antigravity) to review tests for weakness, not only rerun them.
- Residual risks: (A1) `isolation_mode="staging"` is a caller-supplied label; the launcher integration must derive it from the U13 `NonGitStagingAdapter`/worktree object rather than trust a string before allowing `--dangerously-skip-permissions`; (A2) partial-timeout detection relies on stderr wording from agy #1012 (1.2.2) and is unverified on 1.2.4 live timeouts; (A3) provider error classification is substring-based; unknown wording becomes `PROVIDER_ERROR` (fail-closed, non-retryable); (A4) adapters are not yet wired into the U12 launcher or broker; no real delegation executed; (A5) U13 residuals R1–R3, R5 still apply; cost/token savings `UNMEASURED`.
- Next action: independent verification and coordinator `DONE`/rework judgment. Do not open U15.

## Independent verification V1 — Antigravity (2026-09-17)

- Delegation: Claude (coordinator proxy) → `agy -p ... --output-format json --json-schema .claude/codex-relay/u14_verify_schema.json --mode plan --add-dir <project>`; read-only prompt. Raw envelope `.coord/runs/U14-V1-agy.json` (status SUCCESS, input 161,289 / output 36,861 tokens). No project file changed (mtime check after run: none newer).
- Verdict: **REWORK** (7 P1, 4 P2, 1 P3).
- P1 (Antigravity, confirmed by code reading):
  1. Recursion guard case bypass: `caller='Antigravity', callee='Codex', intent='execution'` passes the managed hand-back rule.
  2. Same-tool reentry bypass: `caller='Codex', callee='codex'` passes.
  3. Partial-timeout wording variant `print timed out ... returning partial output` → false SUCCESS (`timeout` substring absent).
  4. Conversation cross-binding: same conversation id bindable to U14 and U15.
  5. Codex argv injection: `session_id='--last'` (or any leading `-`) is emitted as a flag.
  6. `task_id` containing `\r` forges the `[U##]` first line in agy prompt.
  7. `usage` with NaN/Infinity/bool crashes or miscounts (`int(nan)` ValueError).
  8. (counted with 6) `build_codex_command` has no task_id single-line validation.
- P1 (Claude parallel probe, same snapshot): `session_id='--dangerously-bypass-approvals-and-sandbox'` is emitted as a Codex flag (sandbox bypass); agy `conversation_id`/`model` beginning with `-` are emitted after `--conversation`/`--model` (flag-value confusion); `mode='Managed'` bypasses the managed hand-back rule.
- P2: `--flag=<value>` help syntax not detected; cycle set never scoped (independent same-intent sibling calls blocked); `call_depth=0` root call rejected with a misleading message; A1 staging label still caller-trusted. P3: `/login` substring over-classifies AUTH.
- Test weaknesses: no injection, casing, cross-binding, CR, NaN/bool, wording-variant, or `--flag=` tests — consistent with same-author bias.
- Required rework: enum-normalize and validate `caller/callee/mode/intent/purpose`; strict id patterns (UUID-like, no leading `-`) for session/conversation/model and `--` separators where supported; reject any control characters in task_id/title; timeout detection on normalized tokens (`time(d)? ?out` + `partial`); reverse-map uniqueness in registry; finite non-negative int usage only (bool excluded, else VALIDATION); `--flag=` capability parsing; guard scoped by call chain; add a regression test for every item above.

## Antigravity independent verification V2 — direct probe (2026-09-17T17:20 KST)

- Authority: Antigravity direct code reading + live probes. No code modified.
- Tests: `python -W error::ResourceWarning -m unittest discover -s tests -p "test_u1[0-4]*.py"` → exit 0, 115/115 (1 skipped: canary), 24.268s. `python -m compileall -q v7_harness tests` → exit 0.
- Direct probes confirming V1 REWORK findings:
  - P1-1 (caller casing): `guard.py:34` hardcodes `caller == "antigravity"` — `caller="Antigravity"` bypasses managed hand-back rule. **Reproduced.**
  - P1-2 (callee casing): `caller == callee` case-sensitive — `caller="codex", callee="Codex"` passes same-tool reentry. **Reproduced.**
  - P1-3 (timed-out wording): `b"timed out; partial result"` → `detected=False` (false SUCCESS). **Reproduced.**
  - P1-5 (session_id injection): `codex.py:36-40` inserts session_id after `resume` with no leading-dash guard — `"--last"` becomes a flag. **Code-confirmed.**
  - P1-6 + A3 (CR forge): `agy.py:68` rejects `"\n"` but not `"\r"` — CR in title passes single-line guard. **Code-confirmed.**
  - A1 (staging label): `isolation_mode="staging"` is caller-supplied string; `skip_permissions=True` accepted. **Probe: flag_present=True.**
  - A2 (timeout variants): `"timed out"` phrasing correctly returns `detected=False` per known-acceptable miss (timeout+partial policy).
- Verdict: **REWORK confirmed.** All V1 P1-1 through P1-6 independently reproduced by code reading and live probes. Required rework in line 82 is not yet implemented. U15 remains unopened.


## M1 rework (docs/14 §5) and final independent gate V2 (2026-09-17)

- Authority: user instructed Claude to perform M1 on Codex's behalf. Scope limited to the six P1 items in docs/14 §5 M1; P2/P3 moved to `.coord/BACKLOG.md` (B04–B08).
- Failure-first: added `M1ReworkRegressionTests` (8 tests, 25 failing subcases) before code changes; confirmed red (`FAILED failures=23, errors=2`).
- Changes: new `v7_harness/adapters/validation.py` (casefold enum allow-list, identifier `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`, control chars `[\x00-\x1f\x7f]`, timeout `time[d]?[\s_-]*out`+`partial`, usage finite non-negative integers only); `agy.py`, `codex.py`, `guard.py` use it; `ConversationRegistry` enforces reverse uniqueness.
- Checks: U14 (`U14_LIVE_CANARY=1`, `-W error::ResourceWarning`) exit 0, 32 tests; `test_u1[0-4]*.py` strict run exit 0, 123 tests (1 skipped) on rerun — first run hit an intermittent U12 heartbeat timing failure unrelated to changed code (standalone 5/5 pass, recorded as B08); full discovery exit 0, 178 tests (1 skipped); compileall exit 0.
- Independent verification V2 (Antigravity, read-only `--mode plan`, scoped to the six items; `.coord/runs/M1-V2-agy.json`, input 91,325 tokens): **PASS**, all six FIXED, no new normal-path P1.
- V2 non-blocking notes → BACKLOG: Unicode line/paragraph separators `\u2028`/`\u2029` not covered by the control-character pattern (B14); usage test lacks a mixed valid/invalid dict case (code rejects any invalid value) (B15).
- Verdict: U14 = M1 `DONE`. M2 card created as `READY`; M2 not started.
