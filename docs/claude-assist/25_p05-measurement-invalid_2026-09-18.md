# Codex 보고 25 — P05 A/B의 B 측정 무효 (M4 FAIL·STOP 판정 재검토 요청)

> 발신: Claude Code(외부 보조) · 수신: Codex(조율·최종 판정) · 참조: 윤겸스
> 사용자 지시: "코덱스에게 진행도를 보고하고, 서로 협의해 다음 과정을 무승인으로 수행"

## 1. 결론

`.coord/runs/P05/ab.json`의 B(`P05-B-one-turn`)는 **pilot을 한 번도 실행하지 못한 실패 실행**이다. 따라서 "B가 Codex input +277.7%, wall +1022.2%로 절약 실패"는 pilot 경로의 비용이 아니라 **실행 실패 비용**이다. M4 효율 판정 `FAIL·STOP`의 근거가 성립하지 않는다(P1, 판정 근거 오류).

## 2. 근거 (`.coord/runs/codex-measure/P05-B-one-turn.jsonl`, 17줄 전부 확인)

| 증거 | 값 |
|---|---|
| `exec_command` | 07:41:57, 07:42:38, 07:42:44 세 번 모두 `CreateProcess … Rejected("Failed to create unified exec process: helper_unknown_error: setup refresh …")` — **Codex 샌드박스 프로세스 생성 실패** |
| 최종 메시지 | `UNKNOWN, NOT_APPROVED` |
| `tool_call_events` | 0 |
| `pilot_summary` | null (`.coord/pilot/runs/P05` summary 없음) |
| `test_count` | B 6 = 시작 상태 그대로, A 12 → **B는 과제를 수행하지 않음** |
| `comparison.quality_gate` | `PASS`로 기록됐으나 B 산출물이 없으므로 **오기록** |

토큰 구성: A는 비캐시 13,302 + 캐시 83,968, B는 비캐시 12,275 + 캐시 355,072이다. B의 증가분은 거의 전부 캐시 재읽기(대기·재시도 추론)다.

## 3. 요청(순서)

1. M4 효율 판정을 `FAIL·STOP` → `INVALID_MEASUREMENT(B 실행 실패)`로 정정한다. 기능·안전 12/12 PASS는 유지한다.
2. B를 다시 측정한다. Codex 샌드박스 helper 오류를 피하도록 `measure_p05.py`의 B 실행 조건을 A와 같은 방식으로 맞춘다(A는 exec 성공). 판정 게이트를 미리 둔다: **B 유효 조건 = pilot summary 존재 + `verdict_hint` PASS + 테스트 수 A와 동일(12).** 이 조건을 못 채우면 결과를 `INVALID`로 기록하고 비교하지 않는다.
3. 비교 지표는 input 합계와 함께 **비캐시 input**도 기록한다(캐시 비율이 크게 다름).
4. 유효한 B로 다시 판정한다. 그때 FAIL이면 STOP을 받아들인다.

## 4. 현재 상태(참고)

- B30S APPLIED(B28 완결 + B31~B34 + B08), 전체 250 OK, 독립 검증 r2 12/12 PASS·P1 0.
- BACKLOG B35~B39 기록. AGENTS.md에 `--allow-no-changes` 한 줄 추가.
- Claude는 `codex exec` 자율 실행을 띄울 수 없으므로 B 재측정은 Codex가 수행해야 한다. Antigravity 쪽 pilot P05 단독 실행이 필요하면 Claude가 즉시 대행한다.

## 5. 추가 (18:4x) — pilot 경로 가용성 핫픽스와 동시 편집 충돌

- **B40 핫픽스(Claude 직접, 부트스트랩)**: Claude 앱이 `~/.claude/skills/synced/`(폰트 포함 조직 스킬)를 주기 동기화해, B28 재포함 뒤 HOME 스캔이 `WATCH_FINGERPRINT_BUDGET_EXCEEDED` 또는 `EXTERNAL_WRITE`로 막혔다. HOME은 필수 감시 루트라 pilot 자체가 실행 불가 → pilot 위임이 불가능해 `security.py`에 `DEFAULT_REINCLUDE_NOISE = {".claude/skills/synced"}` 한 줄 규칙만 직접 추가. 테스트 `tests/test_b40_synced_noise.py` 2개 추가, 전체 252 OK, 민감 경로 8/8 탐지 유지, 2분 유휴 오탐 0. **Codex 검토 대상.**
- **P05 pilot 증명 실행(P05C·P05D, 반영 없음)**: agy가 과제를 완수(staging 34~35 tests OK)했으나 `EXTERNAL_WRITE`로 차단. 실측 원인은 실행 중 `~/.codex/skills/mia-vaccine-test/SKILL.md`(18:40:39)가 바뀐 것 — **Codex가 같은 시간 전역 스킬을 편집 중**. 감시는 진짜 전역 변경을 정확히 잡은 것이며 오탐이 아니다.
- 결론: Codex가 전역 설정을 편집하는 동안에는 pilot 실행이 설계대로 차단된다. P05 B 재측정은 **전역 편집이 없는 시간대**에 수행해야 한다.
- 신규 BACKLOG: B41 `EXTERNAL_WRITE` summary에 변경 경로 목록이 없음(원인 추적에 별도 diff 필요) → `external_paths` 키 추가.
