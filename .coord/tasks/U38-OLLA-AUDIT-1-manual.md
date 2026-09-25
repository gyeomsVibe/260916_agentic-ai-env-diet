# U38-OLLA-AUDIT-1 — Claude pipeline design mechanical audit

```contract
work_id: U38-OLLA-AUDIT-1
worker: local
goal: Convert the fixed verified facts below into exactly one JSON object; do not make a design verdict.
inputs:
- docs/40_claude-code-in-the-uaos-pipeline-design.md sha256=E08353D0D3A62AAD4A5E0C850517B87530C3188AC7DB010BD04E664453B26C9B
- v7_harness/adapters/lane_worker.py sha256=D85A634F4CE11B28412F7980F346FD3A00316B141CB00A4AA2648FA387190997
allowed_output: stdout JSON only
forbidden: file edits; network; commands; secrets; approval; design verdict; invented facts
budget: 3000 local input tokens and 500 local output tokens; timeout 120 seconds
acceptance: JSON parses; keys are work_id, confirmed, conflicts, unknowns; every item is supported verbatim by FIXED FACTS; no extra keys
stop: malformed JSON once, unsupported claim, or timeout
independent_judge: codex
```

FIXED FACTS

1. Installed Claude Code version is `2.1.281`.
2. `claude auth status` reports `loggedIn: true`, `authMethod: claude.ai`, and `subscriptionType: pro`.
3. `claude --help` says `--bare` skips keychain reads and Anthropic auth is strictly `ANTHROPIC_API_KEY` or `apiKeyHelper`; OAuth and keychain are never read.
4. `claude --help` provides `--safe-mode`, which disables customizations while keeping authentication available.
5. `claude --help` provides `--restricted`, which ignores user, project, and local settings and confines file tools to working directories.
6. `claude --help` provides `--permission-prompts none`, so unanswered prompts can be denied automatically.
7. `claude --help` provides `--max-budget-usd`, a maximum dollar amount for print-mode API calls.
8. The U38 design currently proposes `claude -p --bare` for the paid subscription worker and says the existence of a budget option is UNKNOWN.
9. `lane_worker.py` already uses `--bare`, tool allowlists, test write denials, `--max-turns`, and JSON output for a local Ollama endpoint.
10. Whether `claude -p` can be nested inside the currently running Claude cloud session remains UNKNOWN; this Codex process is not that parent session.

OUTPUT SCHEMA

```json
{"work_id":"U38-OLLA-AUDIT-1","confirmed":["..."],"conflicts":["..."],"unknowns":["..."]}
```
