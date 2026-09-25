```contract
work_id: U35-A1
worker: agy
goal: In `v7_harness/broker/ipc.py`, make `serve_forever` recover from a stale AF_UNIX socket file left by a killed broker, as specified below.
inputs:
- v7_harness/broker/ipc.py sha256=062697009fdf0fd5d3944fbf5e3ccac2b3e25da15a14ddd67a4525df65e856e5
- v7_harness/broker/core.py sha256=cc8fbcad78f209178b60ec836e8f4993b5543c089e1e08427b7f6823c358af9c
- tests/test_u11_broker.py sha256=84ff487901490bc344d702b3d6b8ee1f5dd8e203a0d31bbb8dc6c50ece449fd1
allow:
- v7_harness/broker/ipc.py
acceptance: python -m unittest tests.test_u11_broker tests.test_u12_execution tests.test_b64_broker_drain_budget tests.test_u35_posix_hygiene
forbidden: design changes; edits outside allow; editing or deleting tests; network; commit/push
stop: two failures with the same cause; input hash mismatch; no output
judge: codex
timeout_s: 900
remote_budget_tokens: 150000
```

## Role and reason

- You are a bounded remote worker with one file in scope. Codex (not you) judges and approves.
- Defect B75 (reproduced on Linux 2026-09-25): on POSIX a killed broker leaves its AF_UNIX socket file behind, and
  the next `ForegroundBroker.serve_forever()` on the same address fails with `OSError: [Errno 98] Address already in
  use`. `tests.test_u11_broker.NamedPipeTest.test_half_frame_disconnect_and_crash_replay_have_no_false_success` fails
  on Linux for this reason. Windows named pipes vanish with the process, so Windows is unaffected.
- U35 already moved the POSIX socket into `tempfile.gettempdir()`; do not change that.

## Design decision (already made — implement it, do not redesign)

In `serve_forever`, only when `os.name != "nt"` and the socket path exists, **before** `Listener(...)`:

1. Try `multiprocessing.connection.Client(self.address, family="AF_UNIX", authkey=None)` once.
2. If it connects, a live broker owns the address: close the client and raise
   `BrokerAlreadyRunning("BROKER_ALREADY_RUNNING")` from `v7_harness.broker.core`. Never unlink a live broker's socket.
3. If it raises `ConnectionRefusedError` (or `FileNotFoundError`), the file is stale: `os.unlink(self.address)`
   and continue to `Listener(...)`.
4. Any other error propagates unchanged.

## Constraints

- Change only `v7_harness/broker/ipc.py`. Do not edit or delete tests. Keep every other behavior identical,
  including the Windows (`AF_PIPE`) path.
- Standard library only. No new files.
- Stop and report instead of guessing if the acceptance fails twice for the same reason.

## Acceptance (the judge re-runs it on Windows and on Linux)

`python -m unittest tests.test_u11_broker tests.test_u12_execution tests.test_b64_broker_drain_budget tests.test_u35_posix_hygiene`
must exit 0 on Linux, including the crash-restart test above. On Windows it must stay green.

## Output

- Reply with ===FILE / ===EDIT blocks only. No explanations. Do not claim success; the acceptance command decides.
