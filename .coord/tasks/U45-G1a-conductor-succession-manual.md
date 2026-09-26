```contract
work_id: U45-G1a
worker: apply
goal: Add presence.conductor(desk): the Codex -> Claude -> Antigravity succession from desk states only, UNKNOWN stops it.
inputs:
- v7_harness/coord/presence.py sha256=8b8026964f0676d19befbc4ba8fcc4478d263decac69fce9961fab0147464af1
- tests/test_u45_conductor_succession.py sha256=d723f742f20c934174fda4bf1b59b14bf9cb25f7894f3fe92da946f007196d0d
allow:
- v7_harness/coord/presence.py
acceptance: python -m unittest tests.test_u45_conductor_succession.ConductorSuccessionTest.test_succession_table tests.test_u45_conductor_succession.ConductorSuccessionTest.test_decision_takes_only_desk_states
forbidden: design changes; edits outside allow; editing or deleting tests; network; commit/push
stop: two failures with the same cause; input hash mismatch; no output
judge: antigravity
timeout_s: 180
remote_budget_tokens: 0
```

## Instructions for the worker

U45 G1a (2026-09-26, Claude acting conductor): who conducts is decided from the desk states only. docs/27 §1 forbids
turning a remaining-quota figure into tokens, and §4 fixes the order Codex -> Claude -> Antigravity. An expired heartbeat
(UNKNOWN) is not absence (docs/27 §4.3), so it stops the succession. The CLI field comes in G1b, after the pending
U45-G2b bundle on cli.py is judged, so the two bundles never overwrite each other.

===EDIT: v7_harness/coord/presence.py===
<<<<<<< SEARCH
def read_all(project: Path, *, now: float | None = None) -> dict[str, dict[str, Any]]:
    return {tool: read(project, tool, now=now) for tool in TOOLS}
=======
def read_all(project: Path, *, now: float | None = None) -> dict[str, dict[str, Any]]:
    return {tool: read(project, tool, now=now) for tool in TOOLS}


# U45 G1/G3: the succession order of docs/27 §4. Codex conducts; Claude acts while Codex is LIMITED or ABSENT;
# Antigravity acts only while both are. Only desk states count: a quota figure beside a state is ignored on purpose.
SUCCESSION = ("codex", "claude", "antigravity")
AWAY = ("LIMITED", "ABSENT")


def conductor(desk: dict[str, dict[str, Any]]) -> dict[str, Any]:
    for position, tool in enumerate(SUCCESSION):
        state = (desk.get(tool) or {}).get("state", "UNKNOWN")
        if state == "ACTIVE":
            acting = position > 0
            reason = f"{tool} ACTIVE" + (f"; {', '.join(SUCCESSION[:position])} away" if acting else "")
            return {"conductor": tool, "acting": acting, "reason": reason}
        if state not in AWAY:
            # An expired heartbeat is not absence: stop here instead of handing authority to the next tool.
            return {"conductor": "UNKNOWN", "acting": False, "reason": f"{tool} {state}: heartbeat not current"}
    return {"conductor": "none", "acting": False, "reason": "all three tools LIMITED or ABSENT"}
>>>>>>> REPLACE


## Output

- Reply with ===FILE / ===EDIT blocks only. No explanations. Do not claim success; the acceptance command decides.
