# 실행 규칙(필수)
- 백그라운드 작업 금지. 모든 수정·테스트를 동기적으로 끝낸 뒤에만 최종 답변(수정 파일 목록, Ran N / OK).
- 테스트 파일 수정 금지. 특정 테스트 값·문자열 형식(하이픈 유무 등)에 의존하는 분기를 절대 쓰지 말 것 — 독립 검증에서 치팅으로 판정되어 반려된다.

# R0P3 — 독립 검증 r4 P1 재작업

수정 허용: `.coord/runs/measure_p05.py`, `v7_harness/isolation/security.py`만.

1. R0: `evaluate_measurement`에서 bundle_id 하이픈 유무로 `INVALID_LEDGER`를 고르는 분기(약 268행)를 삭제하라. 규칙: 원장 상태가 terminal이 아니면 `INVALID_LEDGER`; summary와 원장의 task_id·run_id·source_hash·bundle_id 중 하나라도 다르면 **항상** `INVALID_PILOT_IDENTITY`.
2. B39: 재포함 트리 안의 무거운 하위 폴더(`node_modules`, `.venv`, `venv`, `__pycache__`, `.git`, `.cache`)를 **감시에서 제외하지 말고**, 그 안의 파일은 내용 해시 없이 메타데이터(크기·mtime_ns)만 기록하라(지문 예산 미소모). 그 밖의 재포함 파일은 기존처럼 내용 지문. 파일 수 예산(max_files)은 그대로 적용. 기존 테스트(B28·B40·B41·B43)와 synced 소음 제외는 유지.
3. 인수: 원본 `tests/test_r0_measurement_validity.py`(R0_MEASURE_TARGET), `tests/test_b43_reinclude_name_collision.py`, 전체 discover 통과.
