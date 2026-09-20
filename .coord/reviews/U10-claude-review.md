# U10 Claude review gate

- Status: `UNAVAILABLE`
- Attempted at: 2026-09-17
- Mode: one-shot, read-only (`--safe-mode --restricted --permission-mode plan`, tools limited to Read/Glob/Grep)
- CLI preflight: `claude --version; claude --help` -> exit 0 (`2.1.270`)
- Review attempt: produced no captured result for more than five minutes; no second attempt was made. The exact review process was stopped with exit 0 to avoid leaving it running.

## FACT

- Antigravity job `mu4eh6wc_89qlfp` ended after its 10-minute print timeout and reported no normal result, but filesystem inspection showed it had created a partial parallel draft and test files.
- The authoritative U10 implementation is `v7_harness/contracts/**` plus `tests/test_u10_contracts.py`; it does not export or depend on the partial `v7_harness/schema_contract.py` draft.
- `agy` exit 0 and prose `DONE` are treated as non-authoritative. Structured status/error/partial/evidence and effect reconciliation decide success.
- The local 503/side-effect observation is represented by `TRANSIENT_CAPACITY`, `effect_state=UNKNOWN`, and `retryable=false` when the effect is uncertain.

## FINDING

- HIGH (remediated): Antigravity modified existing `v7_harness/__init__.py` outside its delegated file list. Codex restored the measured pre-U10 export surface; the new contracts remain opt-in by explicit import.
- HIGH (remediated): the partial draft exposed a free-form `result` and stored event payload JSON. These were changed to an artifact `result_ref` and hash-only event storage.
- MEDIUM (open): Antigravity left a second unexported draft API (`v7_harness/schema_contract.py`, `tests/test_schema_contract.py`, `v7_harness/contracts/schemas/*.json`). It is not used by the authoritative package but should be removed or consolidated only with explicit deletion/overwrite approval.
- MEDIUM (open): U10 expresses local-path/storage-kind preflight as a pure compatibility contract only. Actual NTFS/network/sync detection and isolation enforcement remain follow-up work.
- MEDIUM (open): DB invariants are proven in one test process. Broker-only writer ownership, crash durability, concurrent process races, Named Pipe ACL, and real worker isolation are intentionally unverified.

## RECOMMENDATION

- Accept U10 for `REVIEW` based on the authoritative contract package and 70 passing tests, while keeping the duplicate unexported Antigravity draft as a recorded cleanup risk.
- Do not dispatch a real worker or open U11 from this task.
- Keep R19/R24/R25 wording feedback from the Claude support memo as `design feedback pending`; it is outside U10 and does not modify docs/13.
