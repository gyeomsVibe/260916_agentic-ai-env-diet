# [U18] Acceptance failure triage

- Owner: Claude Code (deputy commander while Codex/agy on quota; direct edit, marked for Codex re-review)
- Status: REVIEW
- Scope: `v7_harness/accept_triage.py` (new), `v7_harness/pilot.py` acceptance block, `tests/test_u18_accept_triage.py` (new)

## Result
- Acceptance failure -> CODE / INFRA / UNKNOWN. INFRA -> verdict BLOCKED, error_class ACCEPT_INFRA. CODE/UNKNOWN -> REWORK (cascade still escalates).
- Acceptance spawn failure -> BLOCKED, ACCEPT_NOT_RUN, acceptance_exit null, error_detail = exception.
- `rework_class` added as optional summary key only when acceptance ran and failed.

## Design changes vs docs/20 A1 (self-refine / red-team)
- Asymmetric cost: CODE misread as INFRA loses a repair; INFRA misread as CODE wastes one lane run (today's behaviour). So INFRA needs a strong signal; UNKNOWN escalates.
- Dropped as INFRA signals: connection refused, PermissionError (code under test raises them), timeouts (worker may add an infinite loop), auth-expiry (worker-side, not acceptance).
- ModuleNotFoundError: INFRA if the module file exists in staging (path problem, the U17 PYTHONPATH case); CODE if the worker changed/removed that module or added the import; otherwise INFRA.
- unittest `FAILED (errors=N)` is not a code signal (test-module import errors count as errors).
- The "U17 cascade 9/10" gate was a stale premise: the last recorded e2e cascade run is 6/10 (lane BLOCKED VALIDATION). Replaced with an offline check: all 15 real failing acceptance logs from `.work/lane_ab_20260923` classify as non-INFRA (12 SyntaxError, 2 AssertionError, 1 NameError).

## Evidence
- `python -m unittest tests.test_u18_accept_triage` -> 15 OK (before pilot change: failures=3, errors=2).
- `python .coord/runs/run_regression.py` -> 518 OK, 79 s, log `.work/logs/regression-20260923T200707.log`.
- `.work/u18/tests_sha_before.txt` vs after: 56 existing test files unchanged, one file added.
- Live e2e cascade re-run: UNKNOWN (not run; lane/agy quota, PASS path untouched).

## Open risks
- Keyword triage is heuristic; unseen infra signatures fall to UNKNOWN (safe: escalates).
- 12/15 local failures are markdown fences written into files by `ollama_worker._apply` -> U19 candidate.

## Next
- Codex re-review on return (2026-09-24 13:41).
