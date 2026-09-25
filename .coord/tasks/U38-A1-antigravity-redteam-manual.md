```contract
work_id: U38-A1
worker: agy
goal: Write a red-team report at `.coord/runs/U38/agy_redteam_u38.md` on the U38 Claude worker and reviewer, in the format below; change no code.
inputs:
- v7_harness/adapters/claude_worker.py sha256=2bb37e1ee2c7e99804721fd0a376b26b32c2bcef72feb645d54a942cf1c9f4a2
- v7_harness/review.py sha256=1bd89af9acfc0152c3a63a64629d2dab9c63545b8acae076573f8d1b5246eaca
- tests/test_u38_cost_gate_and_claude_worker.py sha256=40a96a9d13be6941a1233563014f8dc6591e260b2854b5dfdeaa7230e23b8c9f
allow:
- .coord/runs/U38/agy_redteam_u38.md
acceptance: python -c "import pathlib;t=pathlib.Path('.coord/runs/U38/agy_redteam_u38.md').read_text(encoding='utf-8');assert '## Findings' in t and '## Reproduction' in t and '## Not found' in t"
forbidden: design changes; edits outside allow; editing or deleting tests; network; commit/push
stop: two failures with the same cause; input hash mismatch; no output
judge: codex
timeout_s: 900
remote_budget_tokens: 80000
```

## Instructions for the worker

## Role and reason

- You are an independent red-team verifier for U38 (Claude Code joining the pipeline as a worker and a reviewer). The author is Claude, so Claude cannot be the verifier. You write a report. You do not change code. Codex judges.
- Your spend is gated. This run is the first real test of B85: if it spends more than `remote_budget_tokens` (input + output + cache), the pilot marks it BLOCKED and it cannot be approved. Keep the report short and stop when it is written.

## What to attack (read the pinned inputs)

1. `v7_harness/adapters/claude_worker.py`. Can the worker escape its fence?
   - Look at: Bash, writes to `tests/`, `.coord/` or `.claude/`, hooks running inside the staged copy, and the parent-session markers leaking.
   - Can a worker run report usage that makes the cost gate read WITHIN when it spent more?
2. `v7_harness/review.py`. Can the reviewer edit what it judges? Can it review its own worker's bundle? Can a missing or forged `runs/<task>/worker` file pass the author check? Can an unparsable answer become a PASS?
3. `tests/test_u38_cost_gate_and_claude_worker.py`. Name one important case the tests do not cover.

## Report format (write exactly this file: `.coord/runs/U38/agy_redteam_u38.md`)

```
# U38 red-team (Antigravity)
## Findings
- F1 [severity high|medium|low] <one sentence> — evidence: <path>:<line> "<quote>"
## Reproduction
- F1: <steps or a short Python snippet, or "not reproducible from reading">
## Not found
- <what you checked and found sound>
```

- Every finding needs a quote copied exactly from a pinned input. "No findings" is a valid answer if the Not found section lists what you checked.


## Output

- Reply with ===FILE / ===EDIT blocks only. No explanations. Do not claim success; the acceptance command decides.
