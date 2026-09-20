# [R4] 중간 크기 과제(P06, P07) 추가 라이브 A/B 측정

- Status: READY (FINAL JUDGMENT; B58 gate complete)
- Owner: Claude Code (조율·인수 설계), Antigravity (드라이버 구현·실행·검증)
- Conversation: [R4] 중간 크기 과제 추가 실측
- Depends on: R3 `DONE` (MEASURED_AND_VERIFIED, n=1)
- Started at: 2026-09-19T16:38:00+09:00
- Finished at: 2026-09-19T16:51:55+09:00
- Scope: `.coord/tasks/R4-additional-measurements.md`, `.coord/runs/R4/**`, `.work/260916_pilot_sample_R4_*`, `.work/260916_pilot_work_R4_*`
- Excludes: 기존 P05/R1/R3 결과 변조, 전역 설정 변경, 삭제, 배포, 결제, Bridge 사용
- Outcome: 중간 크기 과제 P06(통계 7함수) 및 P07(인벤토리 클래스·CSV)에서 A(Codex 직접) vs B(로컬 제어층 + Antigravity + Codex 1턴 조율)를 실측하여 **양쪽 모두 `MEASURED_AND_VERIFIED`** 판정 및 **Codex 입력 토큰 평균 78.3% 절감, 시간 평균 8.3% 단축** 검증 완료.

## Post-R2 consistency decision

- R3와 같은 기준을 적용한다. P06·P07 드라이버가 반영 전후 source manifest의 기대 추가 파일 집합을 독립 확인하고 숨은 인수를 재실행했으므로 R4 수치와 판정은 유지한다. control receipt 단독 신뢰 결함으로 현재 R2 구현은 계속 `BLOCKED`지만, 이미 확보된 독립 측정 증거를 소급 폐기하지 않는다.
- 2026-09-19: R2는 이후 DONE이 됐고 B58도 relay 로그 manifest 격리·보호 경로 회귀 검증을 통과해 DONE이다. 최신 사용자 지시에 따라 기존 측정 결과를 바꾸지 않고 R4 최종 판정 단계만 `READY`로 연다.

## Measurement History & Verification

1. **P06 (통계 7함수)**:
   - Gate Status: **`MEASURED_AND_VERIFIED`**
   - Quality Gate: **PASS** (A 31 tests, B 37 tests, `P06_ACCEPT_OK`)
   - Codex Input Tokens: A 94,018 → B 18,623 (**−80.2%**)
   - Noncached Input Tokens: A 9,538 → B 6,975 (**−26.9%**)
   - Codex Output Tokens: A 2,601 → B 45 (**−98.3%**)
   - Wall-clock Seconds: A 91.8s → B 82.7s (**−9.9%**)
   - Tool Calls: A 6회 → B 0회
   - B Worker (`gemini-3.7-flash-high`): 72.8s, 80,984 tokens, bundle `216872d4...` (`APPLIED`)

2. **P07 (인벤토리 클래스·CSV)**:
   - Gate Status: **`MEASURED_AND_VERIFIED`**
   - Quality Gate: **PASS** (A 38 tests, B 44 tests, `P07_ACCEPT_OK`)
   - Codex Input Tokens: A 78,437 → B 18,626 (**−76.3%**)
   - Noncached Input Tokens: A 10,725 → B 11,458 (+6.8%)
   - Codex Output Tokens: A 4,248 → B 52 (**−98.8%**)
   - Wall-clock Seconds: A 113.8s → B 106.3s (**−6.6%**)
   - Tool Calls: A 4회 → B 0회
   - B Worker (`gemini-3.7-flash-high`): 97.0s, 108,115 tokens, bundle `17b2e13a...` (`APPLIED`)

3. **Combined n=3 Statistics (P05, P06, P07)**:
   - **Codex Input Token Reduction**: **76.7%** (평균)
   - **Codex Output Token Reduction**: **97.0%** (평균)
   - **Wall-clock Time Reduction**: **7.6%** (평균)
   - **Quality Gate**: 전 과제 100% PASS
   - 산출물: `.coord/runs/R4/measurement_P06.json`, `.coord/runs/R4/measurement_P07.json`
