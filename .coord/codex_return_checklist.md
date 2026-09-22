# Codex return checklist (2026-09-24)

Written by Claude (deputy) for Codex. Ordered by risk. Everything below was changed while Codex was out; the author must not be the only verifier (arXiv:2410.21819). Full context: `.coord/PLAN.md` "Codex 복귀 재검토 목록", `.coord/BACKLOG.md` B57–B70.

1. **Hooks trust** — open `/hooks`, trust `olla hook-plan`, `hook-shell`, `hook-bash`, `hook-stop`; nothing runs until trusted — `~/.codex/hooks.json`
2. **B64 broker stop budget** — DRAIN_FLOOR_S=2.0 changes Codex-owned U11/U12 shutdown; confirm it keeps a bounded stop — `python -m unittest tests.test_b64_broker_drain_budget tests.test_u11_broker`
3. **B63 stream lock** — PermissionError now treated as "busy" in `_exclusive` — `python -m unittest tests.test_u15_lock_contention`
4. **Agent-to-agent English** — brief header and queue header are English now; check the brief still parses — `python -m unittest tests.test_u15_codex_brief tests.test_u15_notify_codex`
5. **Global rules v5.6–v5.20** — no-approval clauses must not weaken the stop list (delete, push, payment, permissions) — `shared/global-rules/scripts/sync-global-rules.ps1 -Mode Check`
6. **olla hooks and sandbox** — read/plan/stop/bash hooks, Antigravity adapter, test sandbox guard — `python -m unittest tests.test_u17_olla`
7. **Local worker** — SEARCH/REPLACE edit mode and specificity advice — `python -m unittest discover -s tests -t . -p "test_u16_*"`
8. **Coordination stream** — U15 still REVIEW; effect UNMEASURED — `python -m unittest discover -s tests -t . -p "test_u15_*"`
9. **R4-FINAL verdict by proxy** — recompute −76.7% input / −97.0% output — `.coord/tasks/R4-additional-measurements.md`
10. **Full regression** — must end OK with no POLLUTED lines — `python .coord/runs/run_regression.py`
11. **Antigravity hooks** — after its quota resets, look for caller=antigravity rows — `~/.cache/olla/usage.jsonl`
