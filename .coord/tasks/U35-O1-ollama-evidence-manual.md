```contract
work_id: U35-O1
worker: local
goal: Copy five values exactly as written in `docs/36_metaphor-realization-implementation-record_2026-09-25.md` into a JSON object with the keys listed below; each value must be a contiguous substring of that file.
inputs:
- docs/36_metaphor-realization-implementation-record_2026-09-25.md sha256=fde663da819118581a48e343ddf9fbaf89bf95399bf92e57517126ae2240726a
allow:
- .work/u35/o1.json
acceptance: python -m v7_harness.olla_evidence --manual .coord/tasks/U35-O1-ollama-evidence-manual.md --evidence docs/36_metaphor-realization-implementation-record_2026-09-25.md --sha256 fde663da819118581a48e343ddf9fbaf89bf95399bf92e57517126ae2240726a --keys mailbox_tests,sentinel_tests,harness_tests,full_suite,u35_bundle --prompt "Copy the five values exactly as they appear."
forbidden: design changes; edits outside allow; editing or deleting tests; network; commit/push
stop: two failures with the same cause; input hash mismatch; no output
judge: codex
timeout_s: 120
remote_budget_tokens: 0
```

## Role and reason

- You are a calculator doing extraction: a large input, a small exact output. No summary, no judgement.
- The caller runs `v7_harness.olla_evidence`: it verifies the evidence SHA-256 before and after your call, forces a
  JSON object with exactly these five string keys, and rejects any value that is not copied verbatim from the evidence.
- The judge (Codex) compares your five values with expected values kept outside this manual.

## Where each value is (copy the exact characters, including backticks and parentheses)

1. `mailbox_tests`: section "2-1", the line that starts with "검증:" — the backticked test file name, its count and the parenthesis right after it.
2. `sentinel_tests`: section "2-2", the line that starts with "검증:" — the backticked test file name and its count.
3. `harness_tests`: section "2-4", the line that starts with "검증:" — the backticked test file name, its count and the parenthesis right after it.
4. `full_suite`: section "3", the table row "전체 회귀" — the whole text of its result cell.
5. `u35_bundle`: section "4", the bundle id written with "…" in the approval row.

## Output

- One JSON object with the five keys. No markdown fences, no extra keys, no explanation. Save the caller's stdout to `.work/u35/o1.json`.
