# U45 project manual (big picture) — UAOS as a general system for any project

- Written: 2026-09-26 15:00 KST by Claude Code, acting conductor while Codex is LIMITED. Codex re-reviews on return.
- Source: the U45 mission the user gave in the Claude chat on 2026-09-26 (same text as Codex's U45 assignment).
- Branch: `claude/u45-general-uaos` in worktree `.work/u45_claude`, based on 40caf37 (U44) merged with `origin/codex/u42-rsi-research-pr` (U42).
- Each worker call gets its own contract manual under `.coord/tasks/U45-*-manual.md`, and that text is the call input.
  Every action is logged with its time in `.coord/notes/U45_ACTING_LOG.md`.

## Goals

| # | Goal | Where it lands | Gate |
|---|---|---|---|
| G1 | Budget routing by tool state (ACTIVE/LIMITED/ABSENT), never by converting remaining quota into tokens | docs/27, routing | red-first test |
| G2 | Project manual before a project, contract manual before each delegation, passed as the call input | `coord init` template | red-first test |
| G3 | Codex ACTIVE -> Claude acting -> Antigravity acting when both are absent; handoff and return re-review | canon core + adapters | invariant in all three generated files |
| G4 | Ollama only for narrow mechanical work and record cleanup; UNMEASURED marking | canon core | invariant check |
| G5 | Records: archive candidate -> restore manifest -> separate fresh delete approval (age/count/bytes) | `retention.py` | U42 tests + red-first test if missing |
| G6 | SemVer bump on every UAOS change and a top-of-docs update section | `rsi_release` | idempotence test |
| G7 | Three global rule files = one minimal shared core + a small per-tool role adapter | `shared/global-rules` canon + installer | shared core identical across the three files |

## Workers

- Ollama: at least one mechanical dedupe/normalize classification of rule lines, with a ledger receipt.
- `worker: claude`: one run to refine the three-tool rules; author only, judged by another tool. Cap 150,000 tokens and $0.30
  (measured U44 review: 124,769 tokens, $0.13). Canary result recorded.
- Antigravity: U45-A1 read-only process map; one read-only red team at the end with a paid budget.

## Gates for the whole card

New red-first tests; U42/U44 regressions; full unittest; compileall; `git diff --check`; fixed test hashes unchanged;
0 test-name/runner branches in production code; installer fake-HOME apply/check and real apply/check drift 0; identical
core across the three global files; version and top-update idempotence; usage receipts; remote SHA check.

## Allowed and forbidden

- Allowed by the mission: global deploy, branch commit, fetch, push, PR create/update (no auto merge).
- Forbidden: real log deletion, auto merge, payment, credential changes, reading auth files.

## Return

PLAN row U45 -> REVIEW with changes, tests, usage, deploy, commit/push SHA and PR URL.
