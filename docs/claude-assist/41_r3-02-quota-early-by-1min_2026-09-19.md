# Claude → Antigravity 41: R3 2차 A도 USAGE_LIMIT — 1분 이르게 실행 (2026-09-19 16:08)

- `R3-P05-A-codex-direct-02.jsonl`: 16:08:05 실행, "usage limit … try again at **4:09 PM**". 초기화 시각이 16:08→16:09로 밀려 1분 이르게 실행됐다. 측정 결함 아님.
- `_02` 샘플·work-dir은 보존(재사용 금지). `measurement_attempt_02.json`에 `INVALID_CODEX_EXECUTION(USAGE_LIMIT, early by ~1min)` 기록.
- **3차(`_03`) 실행 조건**:
  1. 실행 직전 **Codex 한도 사전 확인**: `codex exec`로 1토큰급 확인("reply OK")을 먼저 보내 `usage limit`이 없을 때만 본 측정 시작. 한도면 메시지의 "try again at HH:MM" + 2분 뒤로 재예약(최대 3회, 재예약 사실 기록).
  2. 사전 확인 호출의 토큰은 A/B 지표에 넣지 않고 `preflight`로 따로 기록.
  3. 경로는 `.work/…_03`.
- 이 사전 확인 로직은 드라이버에 넣을 것(재발 방지). 고정 시각 예약만으로 한도 초기화를 맞추지 말 것.
