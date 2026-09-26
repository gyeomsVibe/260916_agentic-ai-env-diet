```contract
work_id: U45-G1b
worker: apply
goal: coord presence reports the current conductor from presence.conductor.
inputs:
- v7_harness/cli.py sha256=43d9e434addb66761956ad5c1b286dd5be11ce88c803b4b10bd3d1bb16a35bdf
- tests/test_u45_conductor_succession.py sha256=d723f742f20c934174fda4bf1b59b14bf9cb25f7894f3fe92da946f007196d0d
allow:
- v7_harness/cli.py
acceptance: python -m unittest tests.test_u45_conductor_succession tests.test_u45_coord_init_manual tests.test_u32_sentinel_bell tests.test_u37_install_everywhere tests.test_u38_cost_gate_and_claude_worker
forbidden: design changes; edits outside allow; editing or deleting tests; network; commit/push
stop: two failures with the same cause; input hash mismatch; no output
judge: antigravity
timeout_s: 240
remote_budget_tokens: 0
```

## Instructions for the worker

U45 G1b (2026-09-26, Claude acting conductor): `coord presence` reports who conducts now, from `presence.conductor`
(G1a, APPLIED by Antigravity). The session hook output shows it too, so a tool that starts up sees at once whether it
conducts or acts for an absent tool.

===EDIT: v7_harness/cli.py===
<<<<<<< SEARCH
    from .coord.presence import mark, read_all
=======
    from .coord.presence import conductor, mark, read_all
>>>>>>> REPLACE

===EDIT: v7_harness/cli.py===
<<<<<<< SEARCH
            _emit({"ok": True, "project": str(project), "presence": presence}, line)
=======
            _emit({"ok": True, "project": str(project), "presence": presence, "conductor": conductor(presence)}, line)
>>>>>>> REPLACE

===EDIT: v7_harness/cli.py===
<<<<<<< SEARCH
    _emit({"ok": True, "presence": read_all(project)})
=======
    presence = read_all(project)
    _emit({"ok": True, "presence": presence, "conductor": conductor(presence)})
>>>>>>> REPLACE


## Output

- Reply with ===FILE / ===EDIT blocks only. No explanations. Do not claim success; the acceptance command decides.
