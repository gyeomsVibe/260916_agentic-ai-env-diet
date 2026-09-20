# [U11] broker·IPC core

- Status: DONE
- Owner: Codex
- Conversation: [U11] broker·IPC core
- Depends on: U10
- Started at: 2026-09-17
- Scope: foreground broker lifecycle/startup preflight, Windows current-user local Named Pipe IPC, SQLite single-writer ownership, bounded versioned request/response framing, authentication, replay/dedupe rejection, graceful stop, crash/restart durable delivery, mock client and temporary local DB tests, this card and PLAN U11 status
- Excludes: real Antigravity/Claude worker execution, auto-promotion, MCP adapter, global rule changes, service installation, external network, push/deploy, deletion/overwrite, system/account/credential/persistent permission changes, U12 creation/start
- Outcome: U10 authoritative contracts/DDL을 소비하는 최소 broker·IPC core와 재현 가능한 crash/replay/authentication tests
- Acceptance: concurrent second broker start denied; unauthorized/bad auth/oversize/malformed schema denied; replay/dedupe harmless; disconnect/half-frame/crash produces zero false ACK and zero durable success; broker-only DB writer is demonstrated by API/tests; U10 19 tests, full regression, and compileall pass
- Verification: `python -m unittest tests.test_u11_broker`, `python -m unittest tests.test_u10_contracts`, `python -m unittest discover -s tests -p "test_*.py"`, `python -m compileall -q v7_harness tests`; exact counts and exit codes recorded

## Decisions

- `docs/01 + .coord/PLAN.md + task card` remain planning authority; SQLite remains a durable execution projection.
- Only the foreground broker owns a writable SQLite connection. Clients receive no DB handle or path-based mutation API.
- Subprocess/model/network calls are forbidden inside DB transactions.
- Tests use temporary local DBs and mock clients only. Cost/token savings remain `UNMEASURED`.

## Work log

- 2026-09-17: authoritative U09 design, PLAN, U10 card, and `v7_harness/contracts/**` inventory reviewed. The working directory is not a Git repository, so `git status --short` returned exit 128; Git was not initialized.
- 2026-09-17: U11 card created and PLAN U11 claimed as `ACTIVE` before implementation.
- 2026-09-17: `antigravity-bridge` health succeeded (`agy 1.2.4`, sandbox default true, auto-approve false) and job `mu4fgafk_uw1op6` was dispatched once with the allowed U11 paths. After the interrupted wait, result lookup returned `not_found`; filesystem inspection found no Antigravity-authored allowed-path draft at that point, so no prose/status was treated as success and Codex implemented the authoritative snapshot directly.
- 2026-09-17: Added `v7_harness/broker/**` with a broker-owned SQLite writer lock/connection, local endpoint naming, authenticated `AF_PIPE` transport on Windows, 16 KiB JSON frame limit, protocol/schema validation, atomic enqueue/event commit, replay/dedupe handling, graceful stop, and crash-after-commit fault injection. No subprocess/model/network call exists inside a DB transaction.
- 2026-09-17: Initial bad-auth test exposed that `multiprocessing.AuthenticationError` escaped `Listener.accept()` and killed the broker. Root-cause reproduction was fixed by containing authentication failure at the accept boundary; U11 tests then passed.
- 2026-09-17: Claude Code 2.1.270 preflight succeeded. One restricted/read-only CRITIC/REDTEAM completed within five minutes and identified a reproducible same-command-id/different-dedupe-key PK exception. Codex reproduced it with a failing test, added explicit atomic `COMMAND_ID_CONFLICT` rejection, and added a real second-process writer-lock test. The broad catch-all suggestion was not adopted because unexpected DB faults must remain visible/fail-closed; POSIX auth coverage is outside this Windows Named Pipe stage.
- 2026-09-17: Final independent runs passed U11 8 tests, U10 19 tests, all 82 tests, and compileall. U11 was returned to `REVIEW`; U12 was not created or started.
- 2026-09-17: Resume audit found the card header had remained `ACTIVE` while PLAN was `REVIEW`; the card header was corrected. Windows endpoints now fail closed unless they use the local `\\.\pipe\coordd-<current-user>-*` namespace, and clients also enforce the 16-byte minimum auth key. This narrows accidental endpoint exposure but is explicitly not claimed as an OS DACL guarantee.
- 2026-09-17: Post-resume verification passed U11 9 tests, U10 19 tests, all 83 tests, and compileall; all commands exited 0.
- 2026-09-17: Runtime-recovery audit re-inspected the authoritative U11 source/test snapshot and found no new source outside `v7_harness/broker/**`, `tests/test_u11_broker.py`, this card, and PLAN; generated `__pycache__` files are compile/test artifacts only. The existing bounded Claude read-only review was not repeated. Fresh runs again passed U11 9 tests, U10 19 tests, all 83 tests, and compileall, each exit 0. PLAN and card both remain `REVIEW`; U12 remains unopened.
- 2026-09-17: Independent review rejected U11 after reproducing an authenticated silent-client hang: built-in `Listener.accept()` authentication and subsequent `recv_bytes()` had no deadline, while the client response read was also unbounded. The same U11 was treated as rework; no U12 work began.
- 2026-09-17: Added bounded server request polling (`REQUEST_READ_TIMEOUT`) and bounded client response polling (`BROKER_RESPONSE_TIMEOUT`). Success/error responses now have strict protocol fields; errors carry stable `error_code` and `retryable`. Transport authentication moved to a nonce-bound HMAC-SHA256 frame inside the bounded read, avoiding the un-deadline-bounded stdlib challenge; however, any underlying `multiprocessing.Listener.accept()` authentication-handshake stall and Windows pipe ACL/current-user guarantee cannot be proven within stdlib/U11 scope and remain explicitly `UNKNOWN`.
- 2026-09-17: Added regression tests proving a connected silent peer is evicted, a normal client proceeds, graceful stop still completes, an unresponsive broker yields a bounded retryable client timeout, and malformed success responses are rejected. The focused hang suite passed 2 tests, U11 passed 11, U10 passed 19, full discovery passed 85, and compileall passed; every command exited 0. U11 returns to `REVIEW` and U12 remains unopened.

## Handoff

- Result: Implemented a foreground, authenticated Windows Named Pipe broker whose process owns the only writable SQLite connection exposed by the API. A process lock rejects concurrent broker writers; clients expose IPC only. Bounded/versioned frames and U10 command schema are validated before mutation. Enqueue plus audit event commit atomically, replay is idempotent, conflicting replay/command IDs are rejected, and neither disconnect, half-frame, nor crash-after-commit can create an ACK or `SUCCEEDED` attempt. Restart observes the one durable `PENDING` delivery and harmlessly dedupes replay.
- Changed: `v7_harness/broker/__init__.py`, `v7_harness/broker/core.py`, `v7_harness/broker/ipc.py`, `tests/test_u11_broker.py`, this card, and `.coord/PLAN.md` U11 status.
- Checks and exit codes:
  - `git status --short` -> exit 128 (expected non-Git project; Git init not performed)
  - `antigravity-bridge` health -> success (`agy 1.2.4`, sandbox=true, auto-approve=false); job `mu4fgafk_uw1op6` later -> `not_found`, no result trusted
  - Initial `python -m unittest tests.test_u11_broker` -> exit 1 (7 tests; bad auth killed listener); root cause fixed
  - Review counterexample `python -m unittest tests.test_u11_broker.CoreTest.test_schema_rejection_and_dedupe_are_atomic` -> exit 1 before fix (SQLite PK collision reproduced), exit 0 after fix
  - Claude read-only CRITIC/REDTEAM (`--restricted --tools Read --permission-mode plan`) -> exit 0; one HIGH command-id collision reproduced/fixed, bounded single call
  - `python -m unittest tests.test_u11_broker` -> exit 0 (9 tests after endpoint/auth preflight reinforcement)
  - `python -m unittest tests.test_u10_contracts` -> exit 0 (19 tests)
  - `python -m unittest discover -s tests -p "test_*.py"` -> exit 0 (83 tests)
  - `python -m compileall -q v7_harness tests` -> exit 0
- Rework checks and exit codes:
  - `python -m unittest tests.test_u11_broker.NamedPipeTest.test_silent_authenticated_client_is_evicted_and_broker_remains_usable tests.test_u11_broker.NamedPipeTest.test_client_response_timeout_and_strict_response_validation` -> exit 0 (2 tests)
  - `python -m unittest tests.test_u11_broker` -> exit 0 (11 tests)
  - `python -m unittest tests.test_u10_contracts` -> exit 0 (19 tests)
  - `python -m unittest discover -s tests -p "test_*.py"` -> exit 0 (85 tests)
  - `python -m compileall -q v7_harness tests` -> exit 0
- Remaining risks: the endpoint uses Windows local Named Pipe transport with nonce-bound HMAC authentication (16+ byte key) and a current-user-derived pipe name. `multiprocessing.Listener.accept()` authentication-handshake stall and Windows pipe ACL/current-user guarantee cannot be proven within stdlib/U11 scope and remain explicitly `UNKNOWN` rather than claimed as covered (the username namespace is defense in depth, not an OS DACL guarantee, and production auth-key provisioning remains `UNKNOWN`). Preflight rejects UNC paths but does not yet prove sync/removable-drive classification. Crash tests cover commit-before-response process death, not reboot/power-loss hardware semantics. No real worker, MCP adapter, service, or external effect was exercised. Cost/token savings remain `UNMEASURED`.
- Next action: coordinator independently reviews the acceptance evidence and sets U11 to `DONE` or returns the same U11 to `READY` for rework. Do not create or start U12 here.

## Independent review

- Verdict: PASS; U11 `DONE` after one rejected review and bounded rework.
- Reproduced defect before acceptance: an authenticated silent peer blocked a second request until the first connection closed. This was classified as a P1 operational error path because it produced indefinite silence and no recovery signal.
- Accepted fixes: bounded server read and client response deadlines, stable error code/retryability, strict response validation, and regression tests for silent peer eviction, later request success, timeout return, and graceful stop.
- Independent checks: focused timeout suite 2 tests, U11 11 tests, U10 19 tests, full discovery 85 tests, and compileall all exited 0.
- Claude memo 03 was compared after rework. Its timeout and stop cases are covered. A per-connection thread pool was deferred because preserving SQLite single-writer ownership requires a bounded dispatcher/queue design rather than ad-hoc concurrent DB access.
- Deferred gates: bounded serial head-of-line DoS, Windows Named Pipe DACL/current-user enforcement, production auth-key provisioning, sync/removable storage detection, and hardware power-loss durability remain `UNKNOWN`; savings remain `UNMEASURED`.
