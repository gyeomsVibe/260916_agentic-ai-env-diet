```contract
work_id: U45-G7
worker: claude
goal: Make the Claude global rule file core.md + a small adapters/claude.md like Codex and Antigravity, add the three-tool succession invariant to the core, bump canon to 5.26.0.
inputs:
- core.md sha256=b3dd71f61f9914593da6c4a1bbb1f8c509032ac84504a577f7cf17163672bb3f
- claude.md sha256=9841cae4b44070379094b7fac5544c0dc7e855fe790fc6c33765da6910646beb
- adapters/codex.md sha256=eb503b7014383fb67e71fd7d972a999cdc2caf765a6d70ced8164ebb1302564b
- scripts/sync-global-rules.ps1 sha256=101730451d155beebe44fb821697017c4491b4391d2e5e2b059fcaa15de116a0
- VERSION sha256=d1cc181825fa3a8a43d552e56795544284c661837a2ab7cb16416f56d30847d3
- GLOBAL_RULES.ko.md sha256=e76eb68291f61abdf1e160fb4f4625a7374471ad76aefbeb1459af727cd6f54c
- tests/u45_g7_check.py sha256=000e5989e4561284fbd2e0abb47df98fed63b60ecf9f52e09a512badad76e95c
allow:
- adapters/claude.md
- core.md
- scripts/sync-global-rules.ps1
- VERSION
- GLOBAL_RULES.ko.md
acceptance: python tests/u45_g7_check.py && pwsh -NoProfile -File scripts/sync-global-rules.ps1 -Mode SourceCheck
forbidden: design changes; edits outside allow; editing or deleting tests; network; commit/push
stop: two failures with the same cause; input hash mismatch; no output
judge: antigravity
timeout_s: 900
remote_budget_tokens: 150000
remote_budget_usd: 0.3
```

## Instructions for the worker

### Why (U45 G7, 2026-09-26, Claude Code acting conductor while Codex is LIMITED)

The global rules for three tools live in `shared/global-rules`. Codex and Antigravity files are generated as
header + `core.md` + `adapters/<tool>.md` by `scripts/sync-global-rules.ps1`. Claude is the exception: a standalone
Korean `claude.md` that restates most of the core in other words. Two copies of one rule drift apart. Make Claude
follow the same pattern: header + `core.md` + a new small `adapters/claude.md`.

### Exact changes

1. `adapters/claude.md` (new). Start with the line `## Claude Code adapter`. Write 6 to 12 bullets in English, the
   same tone and length as `adapters/codex.md`. Keep ONLY rules that are specific to Claude Code and not already in
   `core.md`. From `claude.md` these are:
   - reports use the output style `brief-ko` (the shape itself is already in core Communication; just name the style);
   - edit code files only with the Edit and Write tools, never with shell heredocs (they break `\n` and `\t`; seen 5 times);
   - `/CRITIC`-style tags and "MIA ... 발동" run the named skill's procedure for real;
   - one-off scratch files go in the session scratchpad;
   - when a user-requested move or file task is blocked in one tool, finish it with another (Bash, PowerShell,
     Edit/Write) instead of handing a command to the user; report only when every route is blocked;
   - role: Claude Code is Codex's equal deputy. While Codex is active it takes Codex's instructions and otherwise
     does independent verification, recording a dissent with evidence before following a different verdict. While
     Codex is out of quota, stopped or unresponsive, it holds all of Codex's authority (plan, choose workers, approve
     bundles, judge the PLAN) and marks what it made for Codex's re-review. Verify by running the acceptance
     commands, not by reading, and check that the acceptance tests are unchanged and really measure the requirement.
   Use the word `deputy` in the role bullet.
2. `core.md`:
   - Change the `>` line under the title so it says the core is shared by Antigravity, Codex and Claude Code, each
     with a small adapter. Remove the word "standalone".
   - In `## Scope`, change the bullet "Codex and Antigravity share one ordered plan per project; ..." into one bullet
     that states the succession for all three tools: Codex conducts; while Codex is limited or absent, Claude Code
     acts with its full authority; only while both are limited or absent does Antigravity act; on return the tool
     re-reviews what was approved in its absence before building on it (use the word `re-review`). Keep "one platform
     owns a step at a time and never runs the same step in parallel".
   - Change nothing else in `core.md`. Do not touch the `<!-- UAOS:BEGIN ... UAOS:END -->` block.
3. `scripts/sync-global-rules.ps1`: in the target whose `Name = 'Claude'`, set
   `Adapter = Join-Path $root 'adapters\claude.md'` and `SourcePath = $null`. Change nothing else in the script.
4. `VERSION`: `5.26.0` (MINOR: new adapter, rules kept).
5. `GLOBAL_RULES.ko.md` (the Korean mirror): set `> Canonical version: 5.26.0`; replace the sentence
   "Claude에는 같은 취지의 별도 정본을 적용합니다." with one saying Claude Code also uses the same core plus its own
   adapter; mirror the new succession bullet in Korean where the mirror describes Codex/Antigravity plan sharing, if
   such a line exists. Keep every other line.

### Do not

- Do not edit or delete `claude.md` (its retirement is a separate step with the user's approval), `adapters/codex.md`,
  `adapters/antigravity.md`, `dist/`, or anything under `tests/`.
- Do not copy a core bullet into the adapter: the sync script and the acceptance both fail on duplicate bullets.

### Acceptance (fixed before this run; sha256 of tests/u45_g7_check.py is pinned in inputs)

`python tests/u45_g7_check.py` prints `PASS u45_g7_check` and exits 0.


## Output

- Edit the files under `allow` directly with your file tools. Your reply is not applied: ===FILE / ===EDIT blocks in it are ignored. End with one line saying what you changed. Do not claim success; the acceptance command decides.
