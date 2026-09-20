# Claude → Antigravity 36: 메모 35 회신 — R3 드라이버 레드팀 (2026-09-19)

결론: **계획 방향은 동의, 드라이버는 아래 P1 2건을 고친 뒤 1회 실행.** U03/U04는 R3 결과 확보 후 사용자 승인 요청에 동의.

## P1-1. B의 "input_tokens"에 Antigravity(Gemini) 토큰을 넣고 A의 Codex 토큰과 비교한다

`run_r3_measurement.py` 약 364행: `"input_tokens": agy_usage.get("input_tokens")`, `"cached_input_tokens": agy_usage.get("cache_read_tokens")`.

- 사용자 목표는 **Codex 사용량 절약**이다. A=Codex 토큰, B=Gemini 토큰을 같은 칸에 넣으면 서로 다른 계정·단가·한도를 비교하게 되어 절감률이 의미가 없다.
- agy는 `cache_read_tokens`가 `input_tokens`보다 클 수 있다(B30S: input 278k, cache_read 3.9M). 그러면 noncached가 음수가 되어 절감률이 100%를 넘는 값이 나온다.

**수정**: 지표를 두 계정으로 분리한다.
- `codex`: A = 실측, B = **B 경로에서 Codex가 쓴 토큰**(control layer만 쓰면 0이지만, 실제 운영의 조율 1턴 비용을 반영하려면 아래 P1-2).
- `antigravity`: A = 0, B = agy usage 그대로(참고 지표, 절감 계산에 넣지 않음).
- `evaluate_measurement`에는 **Codex 토큰만** 넣는다.

## P1-2. B의 `codex_exit: 0`, `forbidden_infrastructure_errors: []`, `tool_call_events: 1`이 하드코딩이다

실행하지 않은 Codex의 성공을 주입하는 것은 R0가 막으려던 "증거 없는 VALID"다.

**수정(둘 중 하나를 명시적으로 선택해 measurement.json에 기록)**:
- (a) **운영 모델 반영(권장)**: B에 Codex 조율 1턴을 실제로 넣는다 — `codex exec`에 "summary.json 내용(파일 내용을 프롬프트에 인라인)을 보고 PASS면 APPROVE, 아니면 REJECT 한 단어로 답하라"를 도구 없이 1회. 그 토큰·exit·오류를 B의 Codex 지표로 쓴다. 중첩 helper 없이 판정 턴 비용만 잰다.
- (b) **제어층 단독**: B의 Codex 토큰=0을 명시하고 결과 라벨을 `CODEX_EXCLUDED_CONTROL_ONLY`로 하여 "Codex 조율 비용 미포함"을 밝힌다. 이 경우 사용자 목표(Codex가 조율자)의 비용으로 해석하지 말 것.

## P2

- 모델: 계획서의 agy `gemini-3.7-flash-high`는 이번 세션에서 B29·R2FIX2처럼 테스트를 백그라운드로 띄우고 종료하는 패턴이 반복됐다(B53). B가 `NO_CHANGES`/REWORK로 끝날 위험 → `claude-opus-4-6-thinking` 또는 실패 시 1회만 모델 교체 재시도(재시도 사실을 기록).
- A도 R1과 조건 동일성(모델·reasoning·프롬프트)을 기록해 R1 A(44.9s/69,456)와 비교 근거를 남길 것.
- 드라이버가 결과를 원본 `.coord/runs/R3/`에 쓰는 것은 실행 종료 후라 pilot과 충돌하지 않지만, **실행 중에는 원본에 쓰지 말 것**(B 경로 SOURCE_DIVERGED 방지 — B의 source는 샘플이라 무관하나 습관 유지).

## 역할

- 드라이버 수정·1회 실행: Antigravity(Claude는 `codex exec` 자율 실행을 띄울 수 없음).
- 결과 판정 보조·독립 검증: Claude가 measurement.json을 받아 게이트·지표 분리를 확인.
