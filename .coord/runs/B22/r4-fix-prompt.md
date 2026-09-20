B22 R4 focused rework. Use test-first development.

Evidence from the prior R4 run:
- Adding work_dir/stage as a shallow mandatory watch root catches the intended sibling escape.
- It also caused EXTERNAL_WRITE on normal writes inside work_dir/stage/<task_id> because the task directory metadata changed.
- The prior run was not promoted; source still has the R2 implementation.

Allowed edits only:
- v7_harness/cli.py
- v7_harness/pilot.py
- v7_harness/isolation/security.py
- tests/test_m2_pilot.py
- tests/test_u13_isolation.py only if needed for the exclude-union contract

Required behavior and failing regressions first:
1. Keep HOME, TEMP, work_dir.parent, source_dir.parent, explicit-root augmentation, resolved deterministic deduplication.
2. Add work_dir/stage as a shallow mandatory root; do not make the whole source recursive.
3. When snapshotting watch roots for a pilot, exclude exactly the current task_id directory in addition to all existing DEFAULT_WATCH_EXCLUDES. Custom excludes must augment, not replace, the defaults.
4. Prove a normal worker edit under work_dir/stage/<task_id> is not classified EXTERNAL_WRITE.
5. Prove a direct sibling file work_dir/stage/ESCAPED_FROM_STAGING.txt is classified EXTERNAL_WRITE/BLOCKED and source remains unchanged.
6. Preserve fail-closed behavior for every other watch path.

Do not edit unrelated files; do not delete, rename, commit, push, deploy, or change global settings.
Run: python -m unittest tests.test_m2_pilot tests.test_m4_efficiency tests.test_u13_isolation -q
Return a one-line summary only.
