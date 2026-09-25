```contract
work_id: U41-A1
worker: agy
goal: Write a read-only verification report of the U41 rollout at .coord/runs/U41/agy_verify_u41.md in the required format; change nothing else.
inputs:
- .coord/runs/U41/deploy_receipt_20260925T222826.json sha256=6adf16c2f24780eedf069717f28681dcabe23036c24f21370e54517d720507de
- v7_harness/deploy_pc.py sha256=cdbc73b45d1218e69f12af4f034e15b881d442a966743eaae9280a256457e11b
- docs/43_one-command-pc-rollout-u41.md sha256=b06751d57381b8b1ccb98d23c314ef9f787b4273c70479a731ffc87aa52c103a
allow:
- .coord/runs/U41/agy_verify_u41.md
acceptance: python -c "import pathlib;t=pathlib.Path('.coord/runs/U41/agy_verify_u41.md').read_text(encoding='utf-8');assert '## Verdict' in t and '## Findings' in t and '## Checked and sound' in t"
forbidden: design changes; edits outside allow; editing or deleting tests; network; commit/push
stop: two failures with the same cause; input hash mismatch; no output
judge: codex
timeout_s: 900
remote_budget_tokens: 60000
```

## Instructions for the worker

## Role and reason

- You are the independent verifier of the U41 rollout on this PC. A deterministic script (`uaos_everywhere/deploy_to_this_pc.py`) made the changes. It was written by Claude and run by Codex, so neither of them can verify it. Codex judges your report. You change nothing.
- Your spend is capped by `remote_budget_tokens`, counting input + output + cache. Going over it makes the run BLOCKED and unapprovable (B85). Read only the pinned inputs, write the report, and stop.

## What to check (from the pinned inputs only)

1. The receipt `result` is `DONE`. Every step up to `installer_check` is `OK`, and none is `FAILED`. Name any `WARN` and quote its note.
2. The order of steps matches the documented order in `v7_harness/deploy_pc.py` (module docstring and `build_steps`). Was a push attempted before `installer_check` passed?
3. `canon_block` and `installer_check` both used `--portable`. Search the receipt's output tails for a `C:/Users/` path that would have gone into the shared canon.
4. The generator steps (Build, SourceCheck, Apply, Check) each exited 0, and `runtime_rules` reports that all rule files hold the block.
5. Anything in the receipt that contradicts `docs/43_one-command-pc-rollout-u41.md`.

## Report format (write exactly this file: `.coord/runs/U41/agy_verify_u41.md`)

```
# U41 rollout verification (Antigravity)
## Verdict
PASS or REWORK, one sentence
## Findings
- F1 [severity high|medium|low] <one sentence> — evidence: <path> "<quote>"
## Checked and sound
- <item>: <evidence quote>
```

- Every finding needs a quote copied exactly from a pinned input. No findings is a valid answer, as long as "Checked and sound" covers items 1-5.


## Output

- Reply with ===FILE / ===EDIT blocks only. No explanations. Do not claim success; the acceptance command decides.
