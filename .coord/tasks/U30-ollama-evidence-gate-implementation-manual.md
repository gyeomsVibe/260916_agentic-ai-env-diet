# U30 local-worker implementation contract — evidence gate

Work ID: U30_OLLA_EVIDENCE_GATE. Implement exactly one new file: `v7_harness/olla_evidence.py`. Do not edit existing files, tests, settings, Git metadata, or docs. The caller is Codex; Ollama is a calculator/worker, never the judge.

Inputs: fixed `tests/test_u30_olla_evidence.py` SHA-256 `B62010417F96644B24D8F35E50179AB765F352A74A0CA84CF5929B62F9FA6EE2`; existing `v7_harness/adapters/ollama_worker.py` SHA-256 `01A20B3BF679ECD64CB40BE03E86BFB807D70DF1362577D0A9BCF2F2B615D7F3`. Read only their needed lines. These test bytes must not change.

Goal: add a strict source-anchored Ollama extraction entrypoint without changing the legacy `olla ask` behavior.

Required public functions:

1. `validate_response(raw: str, evidence: str, keys: list[str]) -> dict[str, str]`: parse exactly one JSON object, no markdown fences or extra prose. Reject duplicate keys via `object_pairs_hook`, missing/extra keys, empty or non-string values, and any value not an exact contiguous substring of `evidence`. Return a dict in the same key order as `keys`; raise `ValueError` on any rejection.
2. `main(argv: list[str] | None = None) -> int`: argparse flags `--manual PATH`, `--evidence PATH`, `--sha256 HEX`, `--keys comma,separated`, `--prompt TEXT`, `--model` default `worker.DEFAULT_MODEL`, `--timeout` default 60 and range 1..120. Require both files to exist, be nonempty UTF-8, and not be symlinks. Verify SHA-256 of evidence **before** calling `worker._generate(model, combined_prompt, timeout)` and again after the call. Include full manual content and evidence content in combined prompt. The expected hash is supplied by the caller, not invented by model.
3. On success, print only validated compact JSON to stdout. Print a non-secret usage/outcome JSON receipt to stderr with model, input/output local tokens, input SHA and `PASS`; do not log prompt or evidence contents. On preflight failure return 2, provider/network failure return 1, model output/after-call hash failure return 5. On failure stdout must remain empty. Never let model choose the verdict.
4. Include `if __name__ == '__main__': raise SystemExit(main())`. Reuse `v7_harness.adapters.ollama_worker` and standard library only.

Acceptance gate: `python -m unittest tests.test_u30_olla_evidence -q` exit 0 and `python -m compileall -q v7_harness/olla_evidence.py` exit 0. The fixed test is RED before implementation. Codex will review diff, rerun acceptance, and inspect source/test hashes before any pilot approval. Stop and report if you cannot implement within this one file; do not guess around a failing test by editing it.

Budget: one local `qwen2.5-coder:7b` pilot, 180-second print timeout. If local output fails, Codex may issue a narrower new task; do not self-escalate to a paid worker. Do not commit or push.
