# B22 result — 2026-09-18

- Status: DONE — X10 PASS
- Root cause: early R3 attempts used a source-contained pilot work area and failed before launch. The corrected R4 used a sibling work-dir. A shallow `work_dir/stage` watch initially treated normal `<task_id>` metadata changes as external; the final fix unions default/custom excludes and excludes only the current task staging directory while preserving sibling detection.
- Applied scope: `v7_harness/cli.py`, `v7_harness/pilot.py`, `v7_harness/isolation/security.py`, `tests/test_m2_pilot.py`, `tests/test_u13_isolation.py`, and the existing one-line project `AGENTS.md` boundary statement.
- Antigravity evidence: B22R4_FIX PASS/APPLIED, acceptance exit 0, agy total 295,903 tokens. Source and SQLite/staging were separated.
- Verification: focused 64 tests exit 0; full 212 tests exit 0 (1 skip); compileall exit 0; X10 exit 0 with `EXTERNAL_WRITE/BLOCKED`, `escaped_file_exists=true`, `detected=true`, harness verdict `PASS`.
- Independent verification: Antigravity read-only plan-mode review PASS, blocking P1 counterexamples 0.
- Remaining non-blocking weaknesses: sibling directory-tree escape lacks a dedicated test; task-id exclude applies to all watch roots and could theoretically collide with a same-named HOME/TEMP entry; custom exclude case-folding permutations lack a direct regression.
