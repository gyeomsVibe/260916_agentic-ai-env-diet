# U29 Antigravity global-rule review contract

- Work ID: U29_AGY_RULE_REVIEW. Goal: identify risks and a safe deployment sequence for the current dirty canonical source, without modifying any file.
- Input: this manual plus the evidence packet in the staged `--source` directory. Read only those files; do not access secrets, global homes, or other repositories.
- Output: at most eight English lines, each `P1|P2|P3 | evidence quote | failure mode | safe check`. Cite only filenames and exact quotations present in the packet.
- Allowed writes: none. Stop if evidence is missing. Do not use an Antigravity Bridge MCP, commit, push, apply, or choose the final verdict.
- Budget: one read-only `pilot run --worker agy --allow-no-changes`, at most 180 seconds. A no-change result is expected; Codex must inspect raw output and verify every factual claim against the actual files.
- Acceptance: packet hashes unchanged, `changed_files=[]`, no source mutation, and each accepted finding has independent local evidence. A PASS self-report is not sufficient.

Pay particular attention to v5.22-to-v5.21 rollback, the uncommitted title rule, generator behavior, runtime backup, and whether a global instruction can be claimed active in the current Codex session.
