```contract
work_id: U38-O1
worker: local
goal: Copy five values exactly as written in `v7_harness/adapters/claude_worker.py` into a JSON object with the keys listed below; each value must be a contiguous substring of that file.
inputs:
- v7_harness/adapters/claude_worker.py sha256=ecaa09b1a22987c42016a1974fcfffcc1146554df027a3eb3ac8edd604337996
allow:
- .work/u38/o1.json
acceptance: python -m v7_harness.olla_evidence --manual .coord/tasks/U38-O1-ollama-claude-worker-facts-manual.md --evidence v7_harness/adapters/claude_worker.py --sha256 ecaa09b1a22987c42016a1974fcfffcc1146554df027a3eb3ac8edd604337996 --keys worker_tools,review_tools,default_model,max_turns_line,worker_marker --prompt "Copy the five values exactly as they appear."
forbidden: design changes; edits outside allow; editing or deleting tests; network; commit/push
stop: two failures with the same cause; input hash mismatch; no output
judge: codex
timeout_s: 120
remote_budget_tokens: 0
```

## Instructions for the worker

## Role and reason

- You are a calculator doing extraction: a large input, a small exact output. No summary, no judgement.
- Why this exists: docs/40 describes how the Claude worker is fenced. A value copied from the code by a second tool is an independent check that the documentation and the code say the same thing.
- The caller runs `v7_harness.olla_evidence`. It checks the evidence SHA-256 before and after your call, forces a JSON object with exactly these five string keys, and rejects any value that is not copied verbatim from the evidence.
- The judge (Codex) compares your values with expected values kept outside this manual (memo 76).

## Where each value is (copy the exact characters)

1. `worker_tools`: the value inside the quotes on the line that starts with `TOOLS =`.
2. `review_tools`: the value inside the quotes on the line that starts with `REVIEW_TOOLS =`.
3. `default_model`: the second quoted value on the line that starts with `DEFAULT_MODEL =`.
4. `max_turns_line`: the whole line that starts with `MAX_TURNS =`.
5. `worker_marker`: the whole line (without leading spaces) that sets `env["UAOS_WORKER"]`.

## Output

- One JSON object with the five keys. No markdown fences, no extra keys, no explanation. Save the caller's stdout to `.work/u38/o1.json`.


## Output

- Reply with ===FILE / ===EDIT blocks only. No explanations. Do not claim success; the acceptance command decides.
