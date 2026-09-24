# U29 — Cross-project global rule deployment

Owner/verdict: Codex. Worker review: Antigravity read-only; Ollama literal extraction only. Original U28 global rollout remained pending because source working tree had an uncommitted v5.22.0 -> v5.21.0 rollback and an uncommitted Codex title rule. User explicitly requested critical re-review and local global deployment on 2026-09-25.

## Pre-declared gates

- Preserve the title rule and the v5.22.0 `[올라마]` attribution rule. Never blindly apply the v5.21.0 working tree.
- Publish and transmit worker manuals before use. No worker edits original source or runtime files.
- Source generation: `sync-global-rules.ps1 -Mode SourceCheck` exit 0, offline fixtures 8/8; deployment: `-Mode Apply` then `-Mode Check` exit 0 and both runtime targets ALIGNED. Claude runtime gets an independent content check.
- Backups precede every overwrite. Do not delete unknown data, touch credentials, or weaken approval boundaries. Current Codex conversation does not prove fresh-session loading.

## Evidence and critical findings

- Baseline `SourceCheck` exit 1: Codex and Antigravity dist files did not match source; runtime still matched v5.22.0. Git HEAD `VERSION=5.22.0`, working VERSION was `5.21.0`.
- U29 Ollama: `qwen2.5-coder:7b`, 533 input/92 output local tokens, exit 0. Three source quotations matched, but output wrapped JSON in a Markdown fence; strict format gate failed. No verdict delegated.
- U29 Antigravity: `.work/pilot_U29_AGY_RULE_REVIEW/runs/U29_AGY_RULE_REVIEW/summary.json`; read-only `changed_files=[]`, raw review supplied six risks. 71,727 input/12,484 output paid-model tokens, ~59.36 s. Accepted rollback/marker/stale-session/Claude-divergence risks after independent file checks; no source mutation by worker.
- Resolution: restore v5.22.0 marker and history, preserve uncommitted Codex title rule, add compact-chat/full-guide and pre-call/manual plus Ollama validation rules, bump to `5.23.0`. Claude's separate home rule receives the same policy. Local inference is zero **paid API** tokens, not zero compute cost.
- Backups: source and three runtime rules copied to `260718_agentic-ai-platform-optimization/.work/backup_20260925/u29_global_deploy`; generator Apply made `C:/Users/Kimyoongyeom/.agent-global-rules-backups/20260925-015353` and, after the local-cost correction, `20260925-015659`.
- `Build` exit 0; `SourceCheck` exit 0, fixtures 8/8; `Apply` exit 0 with Codex/Antigravity aligned; final `Check` exit 0. Claude content markers present by direct file read. New Codex sessions inherit global AGENTS.md according to official OpenAI Docs; this already-running conversation cannot serve as independent fresh-session uptake evidence.

## Residuals

- Source repository has unrelated pre-existing uncommitted changes. This turn performed local deployment only; no source-repository commit or remote push was authorized by this specific request. Do not stage them wholesale.
- User-visible account token savings remain `UNMEASURED`. U29 remote review was expensive and should not be repeated for mechanical fact extraction. The failed Ollama format output remains in the RSI denominator.

## Superseded by U30 (2026-09-25)

The earlier two-target deployment and Claude manual check were valid for v5.23.0 only. U30 introduces `claude.md` as a tracked source, `dist/claude/CLAUDE.md` as a third generated target, and `sync-global-rules.ps1` as the three-runtime deployment/checker. See [U30](U30-ollama-evidence-gate-design.md) for v5.24.0 evidence and limits; do not infer U30 pass from this U29 card.
