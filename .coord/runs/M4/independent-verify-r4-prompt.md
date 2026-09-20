Read-only independent verification. Do not edit, create, delete, rename, commit, push, deploy, or change settings. Do not use Claude Code.

Review only:
- v7_harness/cli.py
- v7_harness/pilot.py
- v7_harness/isolation/security.py
- tests/test_m2_pilot.py
- tests/test_u13_isolation.py
- .coord/runs/B22/result.md

Verify by code reading and the recorded evidence:
1. Mandatory watch roots include HOME, TEMP, work_dir.parent, source_dir.parent, work_dir/stage, plus explicit roots with deterministic resolved deduplication.
2. snapshot_watch_roots custom excludes augment DEFAULT_WATCH_EXCLUDES.
3. run_pilot excludes only the current task staging directory while a direct sibling escape under work_dir/stage remains detectable.
4. X10 now returns EXTERNAL_WRITE/BLOCKED/detected=true and focused 64, full 212 (skip 1), compileall all exited 0.
5. Identify any blocking P1 counterexample. Treat the B23 Antigravity runtime HOME/TEMP external-write block as a separate execution-environment issue, not a B22 regression.

Return JSON only with keys: verdict (PASS or REWORK), counterexamples (array), test_weaknesses (array), notes (string).
