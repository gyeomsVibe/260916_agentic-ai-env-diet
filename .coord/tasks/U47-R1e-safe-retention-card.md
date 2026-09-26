# U47-R1e safe retention card

- State: ACTIVE. Single owner: Codex deterministic `worker: apply` path.
- Historical rejection: U47-R1c bundle `9988bfc769312faa2e8fc279ef9384a409f1c73eba243ee0ebce37a8bf5fc8a5` is REJECTED because its frozen test requires a successful real deletion based on a local `approver=user` JSON label. That violates B83 and the fresh delete-approval boundary.
- Legacy evidence preserved: `tests/u47_r1_check.py` stays byte-identical at SHA-256 `35b12965bd1147abd64bf2ec5f52b8310b591a69e72dbc8c3ba8a7802c37b35d`; it is an immutable record of the rejected gate, not an active acceptance criterion.
- New fixed acceptance: `tests/u47_r1e_check.py` SHA-256 `32cb4508c8e9abebe99f657a63bf0aa34cc91eb5280b24b2270b16e2437c69c5`.
- Frozen LF-normalized test hashes: stages `0b265b60848d6d8201b226e5f45b6de740dbff1e8049c0ad93e899d6d8bdc3f6`; safety `9e3c8bb12d02d2812a5f452369db056ad49ce6abbffc967381474190c9c00573`; no-delete `4d4291f0904d3a2883831bccf5512d198040f818108093288f02e0504cd73897`.
- Red-first evidence: `python tests/u47_r1e_check.py` exited 1 with `FROZEN_TEST_MISSING tests/test_u47_retention_stages.py` before implementation.
- Acceptance: `python tests/u47_r1e_check.py && python -m unittest discover -s tests -p "test_*.py"`.
- Forbidden: deletion, paid or local model calls, network, commit, push, deploy, edits outside the contract allow list.
