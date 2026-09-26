```contract
work_id: U45-O1
worker: local
goal: Tag each Claude global rule line as HISTORY, PROJECT or GENERAL
inputs:
- claude_rules.tsv sha256=2e5f3432dda300bca661f1e804c4c7ea871a01cc4640b421814259178ed02fcd
- check_tags.py sha256=924acf9d1a7055114ba0fe10dde481babe125674cc8b1b59c4ccb6df7cea2fff
allow:
- tags.tsv
acceptance: python check_tags.py
forbidden: design changes; edits outside allow; editing or deleting tests; network; commit/push
stop: two failures with the same cause; input hash mismatch; no output
judge: claude
timeout_s: 300
remote_budget_tokens: 0
```

## Instructions for the worker

## Task (one mechanical operation)

Input file `claude_rules.tsv`: 38 lines, each `ID<TAB>rule text` (Korean). Write a new file `tags.tsv` with exactly one
line per ID, in the same order: `ID<TAB>TAG`. Nothing else in the file.

TAG is exactly one of:
- HISTORY: the rule text contains a date (like 2026-09-21), an incident count (like "5회"), or a paper/incident citation in parentheses.
- PROJECT: the rule names a specific machine path, a specific PC setup, or one named project, and has no date.
- GENERAL: every other line.

Reply with one ===FILE: tags.tsv=== block only.


## Output

- Reply with ===FILE / ===EDIT blocks only. No explanations. Do not claim success; the acceptance command decides.
