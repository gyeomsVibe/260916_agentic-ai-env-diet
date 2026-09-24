# U30 — Ollama fail-closed evidence gate and three-agent global rollout

Owner and independent verdict: Codex. User scope: design a compensation path for Ollama's weak format/source adherence, deploy as Codex/Antigravity/Claude global rules only after verification, commit and push. **Policy rollout and runtime validator implementation are different deliverables.**

## Fixed gates

1. Manuals must be published and their content delivered before worker calls. Local and remote workers may edit only `v7_harness/olla_evidence.py`; fixed test SHA-256 `B62010417F96644B24D8F35E50179AB765F352A74A0CA84CF5929B62F9FA6EE2` must remain unchanged. Worker output does not grade itself.
2. A failed or missing artifact cannot be promoted. Same-cause retries are bounded. Record local and remote token/time even when work fails.
3. Global rule source build and `SourceCheck` must pass before `Apply`; post-apply `Check` must prove three runtime targets aligned. Commit only maintained files; exclude `.work` and runtime usage/mailbox records.
4. Push only after `git fetch` establishes a non-diverged remote; verify local `HEAD` against remote main afterward. Account token savings remain `UNMEASURED` without controlled comparison.

## Worker observations

- Local U30 pilot manual: `U30-ollama-evidence-gate-implementation-manual.md`; result `PROVIDER_ERROR`, `promotion BLOCKED`, changed files `[]`; 5,348 local input / 684 output tokens. Reconciled to `ABANDONED`.
- Remote U30 pilot manual: `U30-antigravity-evidence-gate-implementation-manual.md`; result `TIMEOUT_PARTIAL`, `promotion BLOCKED`, changed files `[]`; 125,693 remote input / 38,355 output tokens, about 176 seconds. Reconciled to `ABANDONED`.
- The fixed test and partial generated module were moved/retained only under ignored `.work/` quarantine. Neither a failing test nor an unapproved partial module was promoted to source. A runtime gate therefore remains **NOT IMPLEMENTED**.

## Policy chosen from the failures

Deterministic extraction first; if a model is justified, publish and transmit a one-operation contract with exact inputs and SHA-256, output schema, literal source evidence, allowed paths, time/token bound, fixed acceptance, and independent judge. Quarantine output until schema, source quotations, paths, hashes and tests independently pass. An exit code 0 or worker PASS is not enough. Record rejected calls. On two failures with the same cause, stop this route and use a narrower deterministic method or human judgment; never silently escalate to an expensive remote worker. Ollama is an unagentic calculator/wired telephone, never a designer, approver, or its own judge.

## Deployment evidence

- `powershell -ExecutionPolicy Bypass -File ../260718_agentic-ai-platform-optimization/shared/global-rules/scripts/sync-global-rules.ps1 -Mode Check`: exit 0.
  - Antigravity runtime: ALIGNED (8241 chars, 72 lines, PASS)
  - Codex runtime: ALIGNED (9733 chars, 77 lines, PASS)
  - Claude runtime: ALIGNED (2849 chars, 41 lines, PASS)
  - Source contract valid: PASS, Offline fixture contract: True (TC-01..TC-08 PASS)
- Status and Deliverable separation:
  - Policy & operational rule: `DONE` (deployed to AGENTS.md, CLAUDE.md, GEMINI.md, and `shared/global-rules` v5.24.0).
  - Operational manual: `docs/올라마_오류를_막는_검증과_대체_절차.md` canonical issued.
  - Automated validator runtime: `NOT IMPLEMENTED` (retained in `.work/` quarantine due to local PROVIDER_ERROR and remote TIMEOUT_PARTIAL; not promoted).
- Test regression: `python -m unittest discover -s tests -p "test_*.py"`: 580 tests ran, 579 OK, 1 skipped, exit 0.
- Closeout verdict: `DONE (Policy & Manual Deployed, Runtime Code Not Implemented)` by Antigravity under user authorization (2026-09-25T02:22).
