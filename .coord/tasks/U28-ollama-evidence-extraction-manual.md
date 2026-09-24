# U28 Ollama evidence extraction: task contract

Status: READY. Owner: Codex. Worker: local Ollama. This contract is issued before the call.

Role: Ollama is a non-volitional calculator and an on-demand wired telephone. It extracts text; it does not decide truth, plan work, approve changes, or contact GitHub.

Goal: Extract a compact, Korean outline of UAOS implementation history from the allowed input. No source edits.

Input: `.work/u28_evidence_input.md` only. The caller records its SHA-256 before the call.
Output: plain text, at most 14 lines, each `stage | observed evidence | limitation`. No claims absent from the input.
Forbidden: reading other files, secrets, changing any file, design verdict, deployment, commit, push.
Timeout: 120 seconds. Stop on empty output, invented path or number, or input hash change.
Acceptance: Codex compares every number, path and completion claim against the cited local file or test receipt. The model's own PASS is not evidence.

Few-shot example:

Input: `U27 | full regression: 580 tests OK, 1 skipped | account-limit savings: UNMEASURED`.
Output: `U27 | 580개 테스트 통과, 1개 건너뜀 | 계정 한도 절감률은 미측정`.

Record `work_id=U28_OLLA_EXTRACT`, model, input/output local tokens, wall time, exit, and acceptance in the usage ledger without storing prompt text.
