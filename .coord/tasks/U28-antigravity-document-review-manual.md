# U28 Antigravity independent review: task contract

Status: READY. Owner: Codex. Worker: Antigravity, read-only. This contract is issued before the call.

Goal: Critique the new beginner guide and global policy for unsupported claims, missing beginner steps, misleading cost language, and broken source links.

Allowed input: only the staged review packet `.work/u28_review_packet/`. Read-only pilot; `--allow-no-changes` is required.
Output: at most 8 findings, each `severity | exact quoted claim | counterevidence | suggested correction`. End with one line listing checked filenames. Empty output fails.
Forbidden: edits, commit, push, user message, final approval, new external browsing, reading secrets or unrelated files. The reviewer is not the author and cannot declare DONE.
Timeout: 180 seconds. Stop after one remote run or 3x the previous comparable token cost, whichever occurs first; record any overrun honestly.
Acceptance: Codex checks every finding against files and reruns link and evidence checks. The review is advisory, not a verdict.

Few-shot example:

Claim: `Ollama saved 200,133 paid tokens.` Evidence: `200,133 is local input+output only.`
Finding: `P1 | paid-token savings claim | local tokens do not measure account savings | mark account savings UNMEASURED`.

Record `work_id=U28_AGY_REVIEW`, actual input/output/cache tokens, wall time, exit and acceptance. If quota or capacity fails, do not retry automatically.
