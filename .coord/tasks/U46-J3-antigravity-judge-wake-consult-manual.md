```contract
work_id: U46-J3
worker: agy
goal: Write a read-only design consult at .coord/notes/U46_J3_agy_consult.md on how Claude (acting conductor) can get a binding Antigravity verdict with zero human relay; change nothing else.
inputs:
- docs/47_claude-code-uaos-intake-audit-and-no-approval-process.md sha256=1722f3f8ea40c974dca73f8bbcd918c1125c2d72e91462d48ca8ff417d3f6d37
- v7_harness/adapters/agy.py sha256=dd8dcf48569acf0614e6b013cce3200b54c3cab8329354779b5f8fcd31b4604c
- v7_harness/review.py sha256=7d9996360a68b23419e7d3287d521178b69f6244ebf70dd8e720c15260fefe54
allow:
- .coord/notes/U46_J3_agy_consult.md
acceptance: python -c "import pathlib;t=pathlib.Path('.coord/notes/U46_J3_agy_consult.md').read_text(encoding='utf-8');assert all(s in t for s in ('## Recommendation','## Options','## Facts about agy','## Risks','## Daemon claim'))"
forbidden: design changes to code; edits outside allow; editing or deleting tests; network; commit/push; starting any daemon or scheduled task; changing agy settings or permissions
stop: two failures with the same cause; input hash mismatch; no output
judge: claude
timeout_s: 900
remote_budget_tokens: 120000
```

## Instructions for the worker

## Role and reason

You are Antigravity, consulted by Claude Code (acting conductor while Codex is LIMITED until 18:50 KST, 2026-09-26). The user asked Claude to "consult the Antigravity CLI and improve the process" because today the user had to paste every Claude JUDGE_REQUEST into the Antigravity IDE by hand. Read-only: write one markdown file, nothing else. Keep it under 150 lines. Budget 120,000 tokens: do not read files beyond the three inputs unless one specific fact needs it.

## The problem, measured today

- Claude writes `.coord/mailbox/inbox/claude_<id>_judge_<ts>.json` (full contract manual inside, `approve_if_pass` command with `--coord-actor antigravity`). Antigravity acted on G2b, G1a, G7b, G1b only after the user relayed the letter in the IDE.
- New today (U46-J1, not yet approved): `pilot review --reviewer agy` runs `agy -p <short prompt> --output-format json --print-timeout 600s --add-dir <run folder>` with the review request in a file, no `--dangerously-skip-permissions`. Live run 15:50: 68 s, conversation c03ad2cb, 0 file writes, 71,299 tokens (budget 60,000, so UNUSABLE). It is advisory evidence only (B83: on one OS account an actor name is not authentication).
- Windows Task Scheduler (15:55) shows no Antigravity recurring task; only `Antigravity Daily Update`, `UAOS Sentinel 30m` (0-token), `UAOS Claude Monitor 30m`, `UAOS_RSI_Watch_39b238e0`. Your process map claimed an autonomous `*/10 * * * *` daemon.
- `agy --help` (1.x on this PC) flags: --add-dir, --agent, --continue, --conversation, --dangerously-skip-permissions, --disable-slash-commands, --effort, --input-format, --json-schema, --log-file, --mode (accept-edits, plan), --model, --new-project, --output-format, -p/--print, --print-timeout, --project, --prompt-interactive, --remote-control, --sandbox. Subcommands include `remote-control start|status|stop` (background daemon), `mcp`, `plugin`, `agents`.

## Hard limits any option must keep

- The judge is a different tool from the author, and the approval is attributable to a real Antigravity call (conversation id, verdict JSON hash in the ledger).
- The existing `pilot run --approve` gate is unchanged (bundle digest, cost gate, scope). Evaluator code is not an improvement target.
- No Bridge MCP. `--dangerously-skip-permissions` only inside an isolated staging copy. No paid polling; waiting belongs to the 0-token sentinel/mailbox. Every paid call is budget-gated (B85) and one call per request, no retry loop.
- Deletion, push, deploy, payment, account/permission/system-setting changes stay with the user.

## Options to evaluate

- A. `pilot judge --judge agy`: the pilot runs the acceptance itself, calls agy once with `--json-schema` for `{"verdict":"APPROVE|REJECT","bundle_id":"...","evidence":[...]}` (plan mode, read-only), and only on APPROVE with a matching bundle id runs the unchanged approve gate, recording coord_actor=antigravity plus judge_conversation_id and verdict hash.
- B. agy headless runs the approve command itself (needs shell permission in print mode without skip-permissions: is there a per-command allow list, `--sandbox`, or `--mode` that permits exactly one command?).
- C. `agy remote-control` daemon or your IDE agent watching the mailbox.
- D. The 0-token sentinel (`UAOS Sentinel 30m`) detects a new JUDGE_REQUEST and launches option A once.

## Required output file format

`## Recommendation` (one option or a combination, why, first smallest step), `## Options` (A-D: feasibility with the agy facts above, token cost estimate with its basis, failure modes), `## Facts about agy` (only what you can state about your own CLI, label UNKNOWN otherwise), `## Risks` (forgery, runaway cost, scope), `## Daemon claim` (does a `*/10` Antigravity daemon exist, where, how to verify; say NOT_FOUND if you cannot show it).
