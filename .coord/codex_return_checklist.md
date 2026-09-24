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
11. **Antigravity hooks & usage** — confirm caller=antigravity rows in usage log (`paid_tokens_saved` observed) — `~/.cache/olla/usage.jsonl`
12. **U21 Calculator Principle** — auto routing (`--worker auto`), commit gate (`v7_harness/calculator_gate.py`), `.githooks/commit-msg` — `python -m unittest tests.test_u21_calculator`
13. **U22 Worker Limits & Closeout** — `num_predict=4096`, `PROMPT_TOO_LARGE` fail-fast, `--install` flag — `python -m unittest tests.test_u22_worker_limits`
14. **Zero-Token File IPC & Ollama Sentinel Architecture (`docs/23`)** — User mandate: eliminate polling token bleed, establish disk-file async mailbox & 24/7 Ollama sentinel as permanent standard across 3 tools, backed by arXiv (`tap`, `FrugalGPT`, `RouteLLM`, `LbMAS`) & open-source (`AMQ`, `ai-night-shift`, `claude-mpm`) research dossier — `docs/23`
15. **Fine-grained Ollama Calculator Protocol** — User & Antigravity specification: Ollama has zero reasoning power and is strictly an electronic calculator; commands must 100% fix (1) target file paths, (2) exact SEARCH/REPLACE text blocks, and (3) deterministic acceptance commands (exit code 0). Specificity gate >= 60 enforced — `v7_harness/adapters/worker_advice.py`, `v7_harness/adapters/ollama_worker.py`, `docs/01` §16–17
16. **Codex 부재 중 대화창 큐 발송 원천 차단 (`CODEX_ABSENT`)** — 사용자 스크린샷(`docs/25_codex_absent_no_message.png`) 근거: 한도 초과 상태인 Codex 대화창에 메시지 인입으로 인한 에러 화면 유발을 방지하기 위해 `notify()` 최상단에서 `NotifyRefused("CODEX_ABSENT")`로 전면 거부. 회귀 17 OK — `tests/test_u15_notify_codex.py`
17. **올라마 유선 전화기 모델 및 작업명령서 매뉴얼 정본화 (`docs/24`)** — 사용자 지정: 올라마는 3대 도구의 비용 0원 유선 전화기(원할 때만 다이얼, 0원 즉답, 우편함=음성사서함, 교환원=Sentinel)이자 생각 없는 단순 계산기. 구체성 80점 이상 세밀한 작업명령서 템플릿 제정 및 3대 도구 불변식 고정 — `docs/24`, `AGENTS.md`, `docs/01` §18–19
18. **U23 전건 완료 (S1–S4 ALL DONE)** — S1 우편함 원시요소, S2 전달 어댑터, S3 상주 감시관, S4 감시 CLI/루프(`coord sentinel`) 전건을 로컬 올라마(`qwen2.5-coder:7b`)로 PASS/APPLIED 완료. 유료 토큰 0, 38/38 단위 테스트 OK, 실측 `wall_time 0.838s, paid_api_calls 0` — `tests/test_u23_mailbox.py`, `.coord/tasks/U23-mailbox-foundation.md`
19. **U23 2대 반례 해결 및 최종 DONE 마감** — (1) `mailbox.py` stale recovery 밑줄 ID 손실 결함 해결(JSON 본문 message_id 직접 추출, bundle `70481ad0…` APPLIED), (2) 회귀 테스트 `test_stale_claim_recovery_preserves_underscored_message_id_and_payload` 추가(bundle `4458884a…` APPLIED, 39/39 OK), (3) `sentinel.py` 동일 초 다중 감시 충돌 나노초 타임스탬프 부여(bundle `81866152…` APPLIED, 5회 연속 사이클 exit 0 통과). 유료 API 0토큰 완결 — `tests/test_u23_mailbox.py`, `.coord/tasks/U23-mailbox-foundation.md`
20. **U26 증거 관문형 RSI 운영 정본화 (DONE)** — `docs/31_evidence-gated-rsi-for-uaos.md` 제정, `.coord/usage/runs.jsonl` 장부 개시, 4도구 권한 경계 및 동일 작업 ID 사용량 필드 연결 검증 통과 — `.coord/tasks/U26-rsi-research-and-policy.md`
21. **U27 최종 재검토 (DONE, Codex 2026-09-25)** — 초기 완료 판정에서 잠금·스키마·자동기록 반례를 발견해 `60246863…`, `e25fb43d…`, `c7fb6e25…`로 수리. Windows 다중 프로세스·잠금 timeout·실제 v2 append와 전체 580 OK 확인 — `.coord/tasks/U27-usage-ledger-automation.md`
22. **올라마 RSI·Windows 호환성 (DONE, 비용 주장 정정)** — `FIX_OLLA_SQUEEZE_WIN5`는 유지하되 이후 Antigravity 원격 토큰 사용이 확인되어 유료 0원·100% 절감 주장은 철회. 실제 계정 절감은 `UNMEASURED` — `docs/32_ollama_process_improvement_manual.md`
