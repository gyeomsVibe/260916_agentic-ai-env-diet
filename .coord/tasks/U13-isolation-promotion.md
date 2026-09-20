# [U13] isolation·promotion

- Status: REVIEW
- Owner: Codex
- Conversation: [U13] isolation·promotion
- Depends on: U12
- Started at: 2026-09-17T13:32:10+09:00
- Scope: `v7_harness/isolation/**`, `tests/test_u13_isolation.py`, strictly necessary U13 integration changes under `v7_harness/execution/**`, this card, and `.coord/PLAN.md` U13 status; all mutation tests use temporary fixtures only
- Excludes: live promotion, actual project worktree/staging mutation, delete/overwrite, auto-promotion, real AI worker, external network/effect, service/install, global rules/settings, push/deploy, permissions/credentials, U14 creation/start
- Outcome: Git fixture worktree adapter, non-Git staging copy, deterministic content-addressed patch bundle, and fail-closed promotion dry-run with zero source mutation
- Acceptance: canonical paths remain inside leased roots; symlink/junction/reparse, UNC/ADS, case alias, and `..` escape are rejected; base manifest/hash, current fence, PASS receipt, and effect reconciliation must all match; divergence, stale fence/receipt, UNKNOWN/INTENDED/FAILED effect, untracked overwrite, delete/rename, scope expansion, patch hash mismatch, source mutation during copy, and concurrent ownership fail closed; Git/non-Git outputs are deterministic; dry-run records changes, hashes, conflicts, and approval-required actions while mutating no source
- Verification: `python -m unittest tests.test_u13_isolation`, `python -m unittest tests.test_u12_execution`, `python -m unittest tests.test_u11_broker`, `python -m unittest tests.test_u10_contracts`, `python -m unittest discover -s tests -p "test_*.py"`, `python -m compileall -q v7_harness tests`; exact counts and exit codes recorded

## Decisions

- User source paths are read-only inputs in U13. All worktree/staging/promotion checks run only under temporary fixture directories.
- Promotion is dry-run only and must never apply, delete, rename, overwrite, commit, merge, or push.
- Artifact manifests and bundles are canonical JSON hashed with SHA-256; raw task payloads are not persisted.
- Event-driven wake-up remains a candidate. Realtime SLO is `UNKNOWN` until U16; cost/token savings remain `UNMEASURED`.

## Work log

- 2026-09-17: U12-R1 late writer reverted the authoritative gate and continued touching partial isolation files after U12 had passed. No matching Antigravity/U12 worker process remained when inspected. The coordinator restored U12 `DONE`, released U13 to `READY`, and fixed U13 to one owner: Codex. Existing isolation files are untrusted carryover until this owner reviews them; no second writer or delegation may modify U13 concurrently.

- 2026-09-17T13:32:10+09:00: Confirmed authoritative U09 v9, PLAN, and U10–U12 dependencies. PLAN had U12 `DONE` and only U13 `READY`.
- 2026-09-17T13:32:10+09:00: `git status --short` returned exit 128 because the user workspace is not a Git repository. No Git or source mutation was attempted.
- 2026-09-17T13:32:10+09:00: Card created and U13 claimed `ACTIVE` before implementation.
- 2026-09-17T13:32:59+09:00: Started the required single bounded Antigravity draft as job `mu51ah26_x3myuk` with `sandbox=true`, `auto_approve=false`, and writes restricted to `v7_harness/isolation/**` plus `tests/test_u13_isolation.py`.
- 2026-09-17T13:35:57+09:00: Coordinator changed the gate after confirming U12 P1 defects (timeout classified as NONE/retryable, Windows process tree not terminated, stale/expired late result missing UNKNOWN effect evidence, lease renewal not connected). U13 stopped immediately. Antigravity job `mu51ah26_x3myuk` was cancelled before completion; its output was not integrated, reviewed, or tested. Partial allowed-path files are preserved unchanged. Status returned to `READY (HOLD: U12 rework)` until U12 is `DONE` again.

## Handoff

- Result: HOLD. No U13 result accepted; partial Antigravity draft preserved without integration.
- Changed: Card and PLAN state only by Codex. Cancelled Antigravity left unreviewed partial files under `v7_harness/isolation/**`: `__init__.py`, `errors.py`, `git_worktree.py`, `manifest.py`, `promotion.py`, `security.py`, `staging.py`. No U13 test file was present at stop time.
- Checks and exit codes: `git status --short` -> exit 128 (workspace is not a Git repository); `antigravity_health` -> ok (`agy 1.2.4`, defaults sandbox=true/auto_approve=false); `antigravity_cancel(mu51ah26_x3myuk)` -> `cancelled`. Per coordinator instruction, no U13 tests or content review were run after the hold.
- Failure history: Antigravity job was intentionally cancelled due to the upstream U12 gate regression, not treated as a U13 implementation failure.
- Remaining risks: Partial draft is unreviewed and must not be used. U12's newly identified P1 defects invalidate U13's promotion prerequisites until U12 is reworked and independently returned to `DONE`. Realtime latency SLO is `UNKNOWN`; cost/token savings are `UNMEASURED`.
- Next action: Keep U13 on HOLD. After U12 is independently `DONE` again, resume in this same U13 conversation, inspect the preserved partial draft, and decide whether to correct or replace it. Do not open U14.

## Resumed implementation handoff (2026-09-17)

- Result: U13 implementation is returned for independent review. Deterministic exclusion-aware non-Git staging, fixture-only Git worktrees, canonical path confinement, watch-root external-write detection, structured patch bundles, directory scope/shared-spec gating, zero-write promotion dry-run, base divergence, delete approval, and stale-fence reconciliation are implemented.
- Failure-first evidence: initial `python -m unittest tests.test_u13_isolation` exited 1 at import because external-write APIs were absent. After the draft, new rename-source/delete-approval and explicit UNKNOWN-record regressions reproduced one failure and two errors before correction.
- Antigravity: health passed (`agy 1.2.4`, sandbox=true, auto_approve=false). Required single draft job `mu54683m_t3me1n` completed. Its prose and claimed checks were not accepted; Codex inspected files and independently reran checks.
- Changed: `v7_harness/isolation/{__init__,errors,security,manifest,staging,git_worktree,promotion}.py`, `tests/test_u13_isolation.py`, this card, and `.coord/PLAN.md`.
- Checks: `python -m unittest tests.test_u13_isolation` -> exit 0, 12 tests; `python -m unittest tests.test_u12_execution` -> exit 0, 29 tests; `python -m unittest discover -s tests -p "test_*.py"` -> exit 0, 128 tests; `python -m compileall -q v7_harness tests` -> exit 0.
- Counterexamples passed: junction/symlink escape; `..`, UNC, drive/ADS, case/8.3 aliases; home/TEMP-style external write with UNKNOWN evidence; concurrent source mutation; scope/shared-spec escape; delete and rename approval; stale fence reconciliation; large binary; empty change; fixture worktree isolation.
- Remaining risks: orchestration callers must supply the source, user-home, and TEMP watch roots; full host-filesystem write prevention still depends on OS sandbox/ACL controls. Real provider workers and live promotion were intentionally untested. Realtime latency is `UNKNOWN`; cost/token savings are `UNMEASURED`.
- Next action: U13 coordinator independently reviews this snapshot and sets U13 to `DONE` or returns this same stage to `READY`. Do not open U14.

## Watch-root P1 rework (2026-09-17)

- Verdict before rework: REJECT. Memo 05 measured HOME at 289,749+ files and 39.3GB+, with stat-only traversal still incomplete after 50 seconds. The implementation hashed every file before and after execution and treated transient read failures as content changes, making normal Codex/AppData/browser writes false-positive UNKNOWN effects.
- Root cause: external-write detection was coupled to unbounded recursive content hashing. Fixture tests proved correctness on small trees but not operational feasibility.
- Accepted design: `Path` watch roots are shallow by default (HOME/TEMP top-level escape coverage); selected roots such as Desktop/Documents/Downloads/project parent can explicitly opt into recursion. Each root has a 50,000-file default hard bound. AppData, .codex, caches, browser state, Antigravity brain, and node_modules are excluded by auditable names.
- Detection: snapshots store `(size, mtime_ns, ctime_ns)` only. The post-check compares metadata and hashes only changed/new files for evidence. Read/hash failure is `UNAVAILABLE`, not a synthetic content value. A before/after snapshot inherently bounds changes to the execution window; no second mtime filter can hide preserved-timestamp copies.
- Added counterexamples: `test_watch_roots_ignores_noise_dirs`, `test_watch_roots_stat_first_only_hashes_changed`, `test_watch_home_top_level_write_detected`, and `test_watch_roots_budget` with 50,000 synthetic files.
- Verification: `python -m unittest tests.test_u13_isolation` -> exit 0, 16 tests in 4.624s; `python -m unittest tests.test_u12_execution` -> exit 0, 29 tests; full discovery -> exit 0, 132 tests; compileall -> exit 0.
- Residual risk: recursive selected user folders may still contain legitimate concurrent writes; those correctly fail closed unless explicitly excluded. `ReadDirectoryChangesW` remains an optional later optimization, not required for U13 correctness. Real provider execution and live promotion remain untested; cost/token savings are `UNMEASURED`.
- Next action: coordinator independently judges U13. Do not open U14 before U13 is `DONE`.

## Watch availability rework (2026-09-17)

- Independent rejection reproduced: root enumeration failure returned an empty map and file stat failure silently omitted a path, so either could be misclassified as mass/single-file deletion.
- Fix: `WatchScanResult` preserves root existence separately from file metadata. Root enumeration, recursive walk, and individual stat failures raise `WATCH_SCAN_UNAVAILABLE` with effect state `UNKNOWN`; they never emit `EXTERNAL_WRITE` deletion evidence. A genuinely removed root remains distinguishable and fail-closed.
- Noise test now opts into recursive traversal, proving AppData/.codex pruning rather than passing only because shallow mode skipped every directory. Non-recursive scandir iterators are closed deterministically.
- New counterexamples: transient root enumeration failure and transient file stat failure. Both assert `WATCH_SCAN_UNAVAILABLE`, no false `EXTERNAL_WRITE` classification.
- Verification: `python -W error::ResourceWarning -m unittest tests.test_u13_isolation` -> exit 0, 18 tests; U12 -> exit 0, 29 tests; full discovery -> exit 0, 134 tests; compileall -> exit 0.
- Next action: coordinator independently judges U13. U14 remains unopened.

## Final bounded-fingerprint and Claude review (2026-09-17)

- Replaced the disproved changed-only hash design with complete SHA-256 fingerprints bounded to 64 MiB per root and 50,000 files. Budget overflow records UNKNOWN evidence and fails closed.
- Exclusions use one root-relative glob matcher for shallow and recursive paths. Removed residual basename filtering and the dead `_hash_file_quick` test; the replacement test verifies that unchanged included files are fingerprinted under the explicit byte budget.
- Initial/post scan failures, file/root budgets, and fingerprint budgets record structured UNKNOWN evidence. Evidence reuses the scan fingerprint rather than rereading a potentially changed file.
- Every scan rejects file, directory, supplied-root, and post-snapshot root-substitution symlink/junction/reparse points. Added a Windows junction root-swap regression.
- Final independent checks: U13 25 tests with ResourceWarning-as-error -> exit 0; U12 29 -> exit 0; full discovery 141 -> exit 0; compileall -> exit 0.
- Claude Code 2.1.270 final read-only review -> exit 0, `VERDICT: PASS`, `P1: NONE`. It retained one P2 residual: a local attacker with write access may race between reparse inspection and file open. OS sandbox/ACL containment remains required defense in depth.
- Next action: coordinator independently judges U13. U14 remains unopened.

## Coordinator review: live watch-root feasibility (2026-09-17)

- Verdict: REJECT; return the same U13 stage to `READY (REWORK)`. U14 remains unopened.
- Verified defect: `snapshot_watch_roots()` and `assert_unchanged()` recursively walk every supplied root and hash every readable file; read failures become the unstable sentinel `ERROR`. On the measured host, even stat-only HOME traversal exceeded 50 seconds across more than 289,749 files/39.3 GB, while normal `.codex`, AppData, browser, and TEMP writes make full-root equality produce routine false positives.
- Historical rejected proposal: stat-first changed-only hashing. It was later disproved by restored-metadata content replacement and is not the final design.
- Required regressions: ignore declared noise directories, hash zero unchanged large files, detect a HOME top-level write as UNKNOWN, and meet a declared synthetic 50k-file snapshot budget. `ReadDirectoryChangesW` is optional evidence-driven optimization, not required for this rework.
- Existing 128 passing tests remain regression evidence only; they do not satisfy live-operability acceptance.

## Coordinator review: P1 rework snapshot (2026-09-17)

- Verdict: REJECT; keep U13 in `READY (REWORK)` and U14 unopened.
- Historical intermediate evidence only: the four memo-05 selectors passed, but changed-only hashing was later rejected because it could not detect restored-metadata content replacement without an event journal.
- Blocking counterexample: `_scan_watch_root()` returns an empty map when root enumeration fails and silently drops individual files whose `stat()` fails. `assert_unchanged()` then compares that absence with the prior snapshot and raises `ExternalWriteDetectedError`, misreporting transient unavailability/lock state as an external deletion. A direct unavailable-scan probe reproduced this (`UNAVAILABLE_SCAN_FALSE_DELETE=True`, exit 1).
- Test weakness: `test_watch_roots_ignores_noise_dirs` uses shallow default scanning, so it passes without traversing AppData/.codex and does not prove recursive exclusion behavior.
- Required rework: preserve scan/file availability metadata; distinguish `WATCH_SCAN_UNAVAILABLE` from a verified external write and fail closed without fabricating a deletion; add a transient root/file-unavailable regression. Run the noise test with `recursive_roots=[home]` so the exclusion path is actually exercised.
- Existing 132 passing tests are regression evidence but cannot override the reproduced blocking counterexample.

## Coordinator final gate (2026-09-17)

- Verdict: PASS; U13 `DONE`. U14 remains unopened.
- Code review confirmed that transient root enumeration and individual file-stat failures now raise `WATCH_SCAN_UNAVAILABLE` with UNKNOWN evidence and cannot be emitted as fabricated `EXTERNAL_WRITE` deletion evidence. Root existence remains a separate field in `WatchScanResult`; recursive noise exclusions are exercised by an actual recursive test.
- Independent focused verification: recursive noise exclusion, root enumeration unavailable, and file stat unavailable passed 3/3 under `-W error::ResourceWarning`.
- Independent regression verification: U13 18/18 under strict ResourceWarning, U12 29/29, full discovery 134/134, and compileall all exited 0. A first combined run was not used for the final full-suite assertion because its still-running session identifier was not preserved; full discovery and compileall were rerun separately and exited 0.
- Residuals: real provider execution/live promotion remain untested; explicitly recursive user folders may fail closed on legitimate concurrent writes; realtime and cost/token savings remain `UNKNOWN`/`UNMEASURED`.

## Coordinator reopened gate: Claude Windows counterexamples (2026-09-17)

- Verdict: prior `DONE` withdrawn; U13 returns to `READY (REWORK)`. U14 remains unopened.
- P1 reproduced on this Windows host: a watched file changed from `AAAA` to same-size `BBBB`, then its mtime was restored. `(size, mtime_ns, ctime_ns)` was identical before/after and `assert_unchanged()` returned success without hashing; direct probe exited 1 with `detected=False`.
- P1 reproduced: under an explicitly recursive root, changing the legitimate project path `product/browser/logic.py` was not detected because directory basename `browser` is globally excluded. Direct probe exited 1 with `detected=False`.
- Required rework: content identity must not depend solely on restorable metadata. Use bounded content fingerprints for included files or an audited filesystem event/journal mechanism with overflow/unavailability fail-closed; keep the performance budget explicit. Exclusions must be auditable root-relative paths/globs, not global directory basenames; shallow and recursive policies must share one matcher.
- Add exact regressions for same-size content replacement with restored mtime and a legitimate nested `browser`/`brain` path. Also attach structured UNKNOWN evidence when the initial snapshot itself is unavailable.
- The earlier 134 passing tests remain regression evidence only and cannot override these two reproduced misses.

## Claude coordinator-proxy gate and host-shape rework (2026-09-17)

- Context: coordinator Codex session stopped at 06:49 UTC with `You've hit your usage limit` during the final gate. User instructed Claude Code to take over.
- Gate verdict on the "Final bounded-fingerprint" snapshot: REJECT. Details: `.coord/reviews/U13-claude-coordinator-gate.md`.
- Blocking host evidence (read-only live probe, default settings): `snapshot_watch_roots([Path.home()])` failed immediately with `WATCH_SCAN_UNAVAILABLE: reparse or symlink C:\Users\Kimyoongyeom\.antigravity-ide` (HOME top level has 17 symlinks/junctions); adding the name to `excludes` did not help because the shallow branch checked reparse before exclusion; `%TEMP%` failed with `Permission denied` on an exclusively locked `.tmp`. Every real delegation would fail closed before execution.
- Rework (Claude): shallow scans apply root-relative exclusion before reparse checks; untraversed top-level links are recorded by link identity `(0, lstat mtime, lstat ctime, "LINK:<target>")` so creation/removal/retarget is detected; recursive traversal still rejects links; watched-root substitution still rejects; exclusively locked files are recorded as metadata-only `"LOCKED"` evidence instead of failing the whole root. Fingerprint/file budgets unchanged (still fail closed).
- Added regressions: `test_shallow_home_with_directory_junctions_snapshots`, `test_excluded_reparse_entry_is_skipped_before_reparse_check`, `test_top_level_junction_retarget_detected`, `test_locked_file_recorded_as_metadata_not_root_failure`, `test_real_scan_budget_5k_files` (no mock).
- Checks: `python -W error::ResourceWarning -m unittest tests.test_u13_isolation` -> exit 0, 30 tests; `python -m unittest tests.test_u12_execution` -> exit 0, 29 tests; full discovery -> exit 0, 146 tests; `python -m compileall -q v7_harness tests` -> exit 0.
- Live read-only smoke (default settings): HOME snapshot OK, 121 entries (16 LINK, 3 LOCKED), 0.36s, unchanged after 10s; TEMP snapshot OK, 36 entries (7 LOCKED), 0.15s, unchanged after 10s.
- Residuals: LOCKED files are metadata-only (same-size content change with restored metadata on a locked file is undetectable without NTFS ChangeTime/USN; see docs/claude-assist/06); budget overflow still fails the whole root; real provider/live promotion untested; cost/token savings `UNMEASURED`.
- Status: `REVIEW`. Claude implemented this rework, so Claude does not self-approve `DONE`. Next action: independent coordinator judgment (Codex after usage reset). U14 remains unopened.

## Final gate under coordinator outage (2026-09-17)

- Verdict: PASS; U13 `DONE`. U14 remains unopened.
- Authority: coordinator Codex unavailable (usage limit since 06:49 UTC). User approved proceeding with Claude's recommendation ("추천안대로 진행", 2026-09-17).
- Separation of duties: implementation of the host-shape rework by Claude; independent verification by Antigravity (U13 30/30 under strict ResourceWarning, full 146/146, compileall exit 0, code review of `security.py`/`errors.py`/tests). Claude did not self-approve; Claude only re-ran full discovery before recording (146 tests, exit 0).
- Correction to Antigravity report: the earlier "Claude Code read-only review PASS/P1 NONE" applied to the pre-rework snapshot, which Claude later rejected on live-host evidence; it is not evidence for this snapshot.
- Carried residual risks (must be addressed or accepted before live promotion, U14+): (R1) locked files are metadata-only, so same-size content change with restored metadata on a locked file is undetectable (candidate fix: NTFS ChangeTime/USN, docs/claude-assist/06); (R2) budget overflow fails the whole root instead of per-file UNVERIFIED evidence; (R3) reparse inspection→open TOCTOU requires OS sandbox/ACL containment; (R4) ~~Antigravity did not re-run the live HOME/TEMP smoke~~ — **RESOLVED** by Antigravity re-run below; (R5) real provider execution and live promotion untested; cost/token savings `UNMEASURED`.
- Next action: Codex coordinator re-validates this proxy gate on return, then opens U14 (Antigravity/Codex adapters).

## Antigravity independent verification — host-shape rework (2026-09-17T17:04 KST)

- Authority: Antigravity performed independent read-only verification of Claude's host-shape rework. No code was modified.
- Focused host-shape regressions (7 tests, `-W error::ResourceWarning`): `test_watch_detects_same_size_content_with_restored_mtime`, `test_recursive_excludes_are_root_relative_not_global_basenames`, `test_shallow_home_with_directory_junctions_snapshots`, `test_excluded_reparse_entry_is_skipped_before_reparse_check`, `test_top_level_junction_retarget_detected`, `test_locked_file_recorded_as_metadata_not_root_failure`, `test_real_scan_budget_5k_files` → exit 0, 7/7, 9.599s.
- Live HOME smoke (read-only, actual `Path.home()`): snapshot OK, 121 entries (16 LINK, 3 LOCKED), 0.21s; unchanged after 3s, 0 false positives. (R4 resolved.)
- Live TEMP smoke (read-only, actual `%TEMP%`): snapshot OK, 43 entries (0 LINK, 9 LOCKED), 0.07s; unchanged after 3s, 0 false positives. (R4 resolved.)
- Full regression: U13 30/30 (`-W error::ResourceWarning`), full discovery 146/146, compileall exit 0.
- Code review: `security.py` (483 lines) — exclude-before-reparse order, LINK identity recording, LOCKED metadata fallback, fingerprint budget, root-relative glob exclusion all match the Claude rework design. `errors.py` taxonomy clean. 30-test suite covers all critical scenarios.
- Verdict: **PASS**. All P1 blocking defects from the coordinator gate are resolved. Residuals R1-R3, R5 remain (see prior entry). U14 remains unopened.
- Correction (Claude Code, 2026-09-17T17:07 KST): the "146/146" full-discovery count above was correct at that moment; Claude subsequently prepared `tests/test_u14_adapters.py` (intentionally failing), making the total 147 with 1 import error. Full discovery now exits 1 until U14 is implemented. Use `python -m unittest discover -s tests -p "test_u1[0-3]*.py"` (91 tests, exit 0, verified by Antigravity) for multi-stage regression gates until then.
