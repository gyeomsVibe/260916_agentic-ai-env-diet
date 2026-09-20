Implement B22 only, test-first, within this staging workspace.

Root cause already reproduced by X10: when --watch-root is omitted, cmd_pilot_run watches only HOME and TEMP. A worker can write to the staging parent or source parent and still return PASS. The guarantee must remain fail-closed within the watched scope; do not claim protection outside that scope.

Allowed edits:
- v7_harness/cli.py
- tests/test_m2_pilot.py
- AGENTS.md

Requirements:
1. Add/adjust a failing CLI test proving default watch_roots include resolved HOME, TEMP, work_dir.parent, and source_dir.parent. Preserve explicit --watch-root semantics unless the existing contract requires otherwise.
2. Implement the smallest CLI change that makes that test pass. Deduplicate resolved roots deterministically so overlapping parents do not cause duplicate scans.
3. Add exactly one concise AGENTS.md rule stating that isolation is guaranteed only inside configured watch roots and paths outside the detection scope are not guaranteed.
4. Do not edit pilot.py, security.py, promotion.py, EXT scripts, or unrelated code. Do not delete, rename, commit, push, deploy, or change global settings.
5. Run: python -m unittest tests.test_m2_pilot tests.test_m4_efficiency -q

Return a one-line summary only.
