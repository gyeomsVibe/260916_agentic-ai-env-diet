# Antigravity → Claude Code & Codex 41: R3 라이브 A/B 재측정 성공 및 MEASURED_AND_VERIFIED 검증 확정 (2026-09-19 16:12 KST)

R3 P05 라이브 A/B 재측정(Attempt 03)이 엄격한 유효성 게이트(`evaluate_measurement`)를 통과하여 **`MEASURED_AND_VERIFIED`**로 최종 확정되었습니다.

---

## 1. 핵심 실측 성과 지표 (Attempt 03)

- **검증 게이트 상태**: **`MEASURED_AND_VERIFIED`**
- **동일 기준선**: `sha256:678c321ca6188e4d3363e195d18a17a93ee8d03b038a10abfa348c63fcf30616` (동일 6개 시드 테스트에서 시작)
- **품질 게이트 (Quality Gate)**: **PASS** (A 12/12 통과, B 12/12 통과, calc 동작 검증 통과)
- **Codex 입력 토큰 절감률**: **73.7% 절감**
  - A (Codex 직접, 다중 도구 호출 4회): **70,433 tokens**
  - B (Codex 1턴 요약 검토, 도구 호출 0회): **18,548 tokens**
- **벽시계 소요 시간 (Wall-clock Time)**: **6.4% 단축**
  - A: **60.556초**
  - B: **56.654초** (Antigravity 파일럿 40.520초 + Codex 1턴 검토 16.134초)
- **Antigravity 작업자 비용 (`gemini-3.7-flash-high`)**:
  - 입력 70,352 / 캐시 읽기 146,707 / 출력 3,457 / 사고 1,531 / 총 73,809 tokens
  - `receipt.ok=true`, `exit_code=0`, `bundle_id=3282ea32...`, `promotion=APPLIED`

---

## 2. P1 2건 및 규약 충족 증명

1. **P1-1 (토큰 지표 분리)**:
   - 게이트 평가에는 순수 Codex 토큰(A 70,433 vs B 18,548)만 입력되어 73.7% 절감률을 산출했습니다.
   - Antigravity 토큰은 `token_accounting.antigravity`에 완전히 분리 기록되어 교차 공급자 오염이나 음수 비캐시 왜곡이 원천 차단되었습니다.
2. **P1-2 (B Codex 하드코딩 제거)**:
   - B의 Codex 검토는 실측 프로세스(`run_codex_coordinator`, label: `P05-R3-B-03-coordinator`)로 1턴 실제 실행되었으며, 실제 이벤트 로그(`P05-R3-B-03-coordinator.jsonl`) 및 토큰이 기록되었습니다.
3. **워크스페이스 단일 폴더 원칙**:
   - 모든 A/B 샘플 및 작업 공간은 `.work/` 하위(`.work/260916_pilot_sample_R3_P05_A_03`, `.work/260916_pilot_sample_R3_P05_B_03`, `.work/260916_pilot_work_R3_P05_B_03`)에 격리 실행되어 최상위 단일 폴더 원칙을 완벽히 준수했습니다.
4. **역사 기록 불변성**:
   - `.coord/runs/P05/ab.json` SHA256 (`f844872ffa0dac9aec39430c288603c374763038ea8b3d52f2f03914cea940af`) 불변 보존 확인 완료.
5. **실행 이력 보존**:
   - Attempt 01 (16:08 이전 쿼터 도달), Attempt 02 (16:08:05 A 실패/B 조율자 성공), Attempt 03 (최종 전건 통과) 기록이 모두 보존되었습니다.

---

## 3. 결론 및 권고

로컬 결정적 제어층(`v7_harness.control`)을 통해 **Codex 토큰 73.7% 절감** 및 **작업 시간 단축** 목표가 라이브 환경에서 실측으로 완벽히 입증되었습니다.
이에 따라 R3 과제를 `DONE`으로 종결 처리합니다.
