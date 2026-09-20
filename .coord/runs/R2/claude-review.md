# R2 Claude Code review record — 2026-09-19

- Mode: `claude -p`, `permission-mode=plan`, tools limited to `Read,Grep,Glob`; no file edits or command execution.
- Acceptance availability: **UNAVAILABLE; never used as success evidence.** The coordinator's authoritative read-only call produced no stdout/stderr for more than four minutes and was stopped. A separate diagnostic call emitted the analysis below, but its claims are retained only as hypotheses; the blocking P1 was established independently by Codex reproduction and fixed RED tests.
- Scope: `v7_harness/control.py`, `tests/test_r2_minimal_control.py`, `tests/test_r2_contract_gaps.py`.

## Verdict

- Existing nine fail-open cases are closed in the current code: five initial-summary gates and four approval-response/raw-helper gates.
- The nested Codex `exec_command` helper is absent from the controller critical path; the controller directly starts `python -m v7_harness.cli pilot run`.
- **P1 found; R3 not READY until reproduced and closed:** the controller trusts approval stdout `promotion=APPLIED` plus a post-acceptance exit 0 but does not independently observe that the source tree changed. The existing `FakePilotRunner` never mutates source, yet the happy path can return `ok=True`, `promotion=APPLIED`.
- Proposed P1 gate: compute a post-approval source manifest and require observed source change consistent with the declared changed-file set; otherwise fail closed (`APPLY_NOT_OBSERVED` / `APPLY_MISMATCH`).

## Non-blocking findings

- P2: non-dict approval JSON can escape as an exception instead of a structured receipt.
- P2: effect state validation is a denylist of literal `UNKNOWN`, not a positive enum allowlist.
- P2: checkpoint-only source/bundle mismatch branches lack direct tests.
- P2: raw helper detection recognizes only narrow marker strings.
- P2: pilot and post-apply acceptance parse shell operators differently.
- P2: PYTHONPATH injection also reaches the independent post-apply acceptance process.
- P3: PYTHONPATH membership uses substring comparison; real-run env propagation lacks a direct test; `acceptance_exit=false` equals integer zero in Python; broad GC/warning suppression and ledger mtime slack deserve cleanup.

## PYTHONPATH follow-up assessment

- Moving PYTHONPATH propagation from global `os.environ` mutation into per-subprocess `env` is directionally safe and does not weaken the fixed R2 gates.
- It is not byte-identical to the R2FIX3 stage: current source is a later B54 follow-up, while R2FIX3 summary/identity/SQLite remain mutually consistent for bundle `1608333f5c90a48e1169d7435e0a4a40096bb145294634eef6e1dde5efef30a6`.

## Evidence boundary

Claude did not run the proposed reproduction. Codex independently reproduced the P1: a no-op fake approval returned `ok=True/APPLIED` while the source manifest remained unchanged. The review remains excluded from completion evidence.
