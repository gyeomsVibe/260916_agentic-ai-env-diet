B22 R2 only. The first implementation passed focused tests but X10 still reproduced the P1 gap because an explicit --watch-root replaced all safety defaults.

Allowed edits:
- v7_harness/cli.py
- tests/test_m2_pilot.py

Required failing regression first:
- With an explicit custom --watch-root, PilotConfig.watch_roots must still contain the resolved mandatory safety roots HOME, TEMP, work_dir.parent, and source_dir.parent, plus the explicit root.
- Deduplicate resolved paths deterministically.

Implement the smallest correction: explicit --watch-root values augment, never replace, mandatory safety roots. Keep the existing AGENTS.md sentence unchanged. Do not edit any other file; do not delete, rename, commit, push, deploy, or change global settings.

Run: python -m unittest tests.test_m2_pilot tests.test_m4_efficiency -q
Return a one-line summary only.
