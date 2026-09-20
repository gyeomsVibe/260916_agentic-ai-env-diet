B22 R3, final minimal hypothesis test.

Evidence: R2 still leaves X10 GAP because watch scans are shallow. work_dir.parent does not observe a file created at work_dir/stage/ESCAPED_FROM_STAGING.txt. Normal worker writes are under work_dir/stage/<task>/.

Allowed edits:
- v7_harness/cli.py
- tests/test_m2_pilot.py

Add a failing regression first, then minimally include (work_dir.resolve() / "stage") in mandatory watch roots. Preserve HOME, TEMP, work_dir.parent, source_dir.parent, explicit-root augmentation, resolved deterministic deduplication, and every existing contract. This stage root is intentionally shallow: it must catch direct staging-parent escapes without treating normal nested task staging writes as external.

Do not edit any other file. Run: python -m unittest tests.test_m2_pilot tests.test_m4_efficiency -q
Return a one-line summary only.
