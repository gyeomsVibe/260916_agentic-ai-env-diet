# U30 Antigravity implementation contract — one-file recovery

Work ID: U30_AGY_EVIDENCE_GATE. The preceding local pilot U30_OLLA_EVIDENCE_GATE failed with `no file written`, zero changed files, then was reconciled as ABANDONED. Do not reuse its output or assert it passed.

Goal: implement exactly one new file `v7_harness/olla_evidence.py`. Do not edit tests, existing code, settings, docs, or Git metadata. Do not commit, push, deploy, or call other paid agents. Review only the needed portions of `v7_harness/adapters/ollama_worker.py` and the fixed test.

Input contract: fixed `tests/test_u30_olla_evidence.py` SHA-256 `B62010417F96644B24D8F35E50179AB765F352A74A0CA84CF5929B62F9FA6EE2`; `v7_harness/adapters/ollama_worker.py` SHA-256 `01A20B3BF679ECD64CB40BE03E86BFB807D70DF1362577D0A9BCF2F2B615D7F3`. These bytes must remain unchanged. Acceptance starts RED because module is absent.

Implement `validate_response(raw, evidence, keys)` as strict single-object JSON: reject markdown fences, duplicate/missing/extra keys, empty/non-string values, and values not exact contiguous substrings of evidence. Return a dict ordered as keys; raise ValueError on rejection.

Implement `main(argv=None)` with flags `--manual`, `--evidence`, `--sha256`, `--keys`, `--prompt`, optional `--model` (default worker.DEFAULT_MODEL), `--timeout` (default 60, valid 1..120). Require nonempty UTF-8 regular files, not symlinks; verify evidence SHA-256 before and after one `worker._generate` call. Transmit **contents** of manual and evidence in the prompt. Emit no unvalidated model text: on success stdout is validated compact JSON and stderr a non-secret usage/outcome receipt. On failure stdout is empty; return 2 for bad preflight, 1 for provider/network, 5 for bad output or post-call hash. Avoid broad exception handling that hides bugs. Include `if __name__ == '__main__': raise SystemExit(main())`. Standard library plus existing worker only.

Gate: `python -m unittest tests.test_u30_olla_evidence -q` and `python -m compileall -q v7_harness/olla_evidence.py`, both exit 0; exact changed-file set `{v7_harness/olla_evidence.py}`; fixed test SHA unchanged. Codex alone decides approval from diff and tests. Stop with a concrete error rather than inventing a pass if implementation fails. Time budget: one read-only-to-source SQLite pilot, `--print-timeout 180`; avoid further retries without Codex review.
