# 실행 규칙(필수)
- 백그라운드 작업 금지, 프로젝트 밖(TEMP 포함) 쓰기 금지. 모든 수정·테스트를 동기적으로 끝낸 뒤에만 최종 답변(수정 파일, Ran N / OK).
- 테스트 파일 수정 금지. 특정 테스트 값에 맞춘 분기 금지.

# B46 잔여 + B47

수정 허용: `v7_harness/pilot.py`만.

1. B46: `run_pilot`의 실행 전 `snapshot_watch_roots(...)` 호출이 `WatchScanUnavailableError`를 내면 1초 쉬고 **한 번만** 재시도한다. 두 번째도 실패하면 예외를 던지지 말고 구조화 summary를 반환: `state="FAILED"`, `error_class="WATCH_SCAN_UNAVAILABLE"`, `promotion="BLOCKED"`, `verdict_hint="BLOCKED"`, `error_detail`(메시지 앞 300자), 원장 attempt는 남기지 않거나 정리 가능한 상태로. agy는 실행하지 않는다.
2. B47: `_record_checkpoint_and_identity`에서 `INSERT OR IGNORE INTO plans`·`INSERT OR IGNORE INTO attempts`를 제거한다. attempt가 원장에 없으면 체크포인트를 기록하지 말고 예외(또는 실패 반환)로 드러낸다. 정상 흐름(attempt 존재)은 그대로.
3. 인수: `tests/test_b46_b47_hardening.py`, `tests/test_b44_live_identity.py`, 전체 discover 통과.
