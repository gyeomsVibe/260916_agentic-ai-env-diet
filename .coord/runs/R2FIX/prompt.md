# 실행 규칙(필수)
- 백그라운드 작업 금지, TEMP 등 프로젝트 밖에 파일 쓰기 금지. 모든 수정·테스트를 동기적으로 끝낸 뒤에만 최종 답변(수정 파일, Ran N / OK).
- 테스트 파일 수정 금지. 특정 테스트 값·문자열에 맞춘 분기 금지(독립 검증에서 반려).

# R2FIX — 독립 검증 r8 P1 2건

수정 허용: `v7_harness/control.py`만. 계약: `.coord/runs/R2/delegation-01-prompt.md`.

1. 4단계(summary.json): `state=="SUCCEEDED"`, `verdict_hint=="PASS"`, `promotion=="DRY_RUN_PASSED"`, `acceptance_exit==0`(정수 0), `effect_state!="UNKNOWN"`, 64-hex bundle을 **모두** 요구. `effect_state=="UNKNOWN"`은 기존대로 `UNKNOWN_EFFECT`, 그 외 필드 위반은 `SUMMARY_INVALID`.
2. 6단계(approval replay): stdout/stderr에 인프라 오류 표시(helper_unknown_error 등 1단계와 같은 목록)가 있으면 `HELPER_FAILURE`. 응답 JSON의 `state=="SUCCEEDED"`, `verdict_hint=="PASS"`, `effect_state!="UNKNOWN"`, bundle 일치 위반은 `APPROVAL_MISMATCH`. `promotion`이 APPLIED가 아니면 기존대로(`PASS_WITHOUT_APPLIED`/`APPROVAL_MISMATCH`).
3. 인수: `tests/test_r2_minimal_control.py`, `tests/test_r2_contract_gaps.py`, 전체 discover 통과.
