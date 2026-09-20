# 실행 규칙(필수)
- 백그라운드 작업 금지. 모든 수정·테스트를 동기적으로 끝낸 뒤에만 최종 답변(수정 파일 목록, Ran N / OK).
- 테스트 파일 수정 금지. 특정 테스트 값에 맞춘 분기 금지(독립 검증에서 반려됨).

# R6FIX — 독립 검증 r6 결함 수정

수정 허용: `.coord/runs/measure_p05.py`, `v7_harness/isolation/security.py`.

1. P1 신선도(stale run): `evaluate_measurement`에서 `B["pre_run_attempt_ids"]`(B 실행 **직전** 원장에 있던 해당 task의 attempt_id 목록)가 없거나, 원장 `run_id`가 그 목록에 들어 있으면 `INVALID_STALE_RUN`(savings 없음). 라이브 러너는 B 실행 직전에 `pre_run_attempt_ids`를 원장에서 읽어 evidence에 넣는다.
2. B46 소음 패턴 좁히기(security.py DEFAULT_WATCH_EXCLUDES): `dd_*.log` → `dd_backgrounddownload_*.log`; `tmp????.tmp` → 4자리 16진수만(`tmp[0-9a-f][0-9a-f][0-9a-f][0-9a-f].tmp`, 경로는 casefold됨).
3. 인수: 원본 `tests/test_r0_measurement_validity.py`(R0_MEASURE_TARGET), `tests/test_b46_temp_noise.py`, 전체 discover 통과.
