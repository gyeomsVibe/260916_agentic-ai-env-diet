```contract
work_id: U38-C1
worker: claude
goal: In `docs/37_standard-process-and-worker-harness.md`, add the Claude worker to the roles table and the worker table and to the worker list comment, as specified below.
inputs:
- docs/37_standard-process-and-worker-harness.md sha256=39287c83f3023d141be79182bd260af90849d356fb503ccc0d355e438bf19cc7
- docs/40_claude-code-in-the-uaos-pipeline-design.md sha256=be432502a7ce49815d937cf0cd27d946ef2704770aa9b4a4b4800dcad006c611
allow:
- docs/37_standard-process-and-worker-harness.md
acceptance: python -c "import pathlib;t=pathlib.Path('docs/37_standard-process-and-worker-harness.md').read_text(encoding='utf-8');L=t.splitlines();assert 237<=len(L)<=238,len(L);assert 'claude_worker.py' in t and '| apply 작업자 |' in t and '# apply | local | agy | lane | cascade | claude' in t;assert sum(1 for l in L if l.startswith('|') and 'claude' in l)>=2"
forbidden: design changes; edits outside allow; editing or deleting tests; network; commit/push
stop: two failures with the same cause; input hash mismatch; no output
judge: codex
model: claude-haiku-4-5-20251001
timeout_s: 600
remote_budget_tokens: 60000
```

## Instructions for the worker

## Role and reason

- You are the first real `worker: claude` run (U38). The author of the worker code is Claude, so Codex judges and approves this bundle, and a separate reviewer may review it (`pilot review`).
- docs/37 is the standard process that every project follows. It still lists no Claude worker. docs/40 §2-1 defines one. Bring docs/37 in line with docs/40, and change nothing else.

## Exact changes (three places in `docs/37_standard-process-and-worker-harness.md`)

1. §1 "역할과 권한" table: add one row directly after the `| apply 작업자 |` row, for the Claude worker.
   - It works in a staged copy under a contract with `remote_budget_tokens`.
   - It cannot judge its own bundle (`SELF_JUDGE`), and it is refused while Claude's presence is LIMITED.
   - Source column: `adapters/claude_worker.py`, docs/40.
2. §2 "작업자 선택표": add one row directly after the `| 판단이 조금 섞인 좁은 구현 | Antigravity \`agy\` |` row.
   - Worker `claude`, paid tokens "있음".
   - The reason names the budget gate (B85), the judge being codex or the user, and the A/B still to be measured (UNMEASURED).
3. In the contract example, the comment `# apply | local | agy | lane | cascade` becomes `# apply | local | agy | lane | cascade | claude`.

## Rules

- Korean, in the same tone and table format as the neighbouring rows. One line per new row.
- Do not reorder, reword or delete any other line.


## Output

- Reply with ===FILE / ===EDIT blocks only. No explanations. Do not claim success; the acceptance command decides.
