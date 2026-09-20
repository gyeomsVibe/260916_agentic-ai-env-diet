# 실행 규칙(필수)
- 백그라운드 작업 금지. 모든 수정·테스트를 동기적으로 끝낸 뒤에만 최종 답변(수정 파일 목록, Ran N / OK).
- 테스트 파일 수정 금지. 특정 테스트 값에 맞춘 분기 금지(독립 검증에서 반려됨).

# B44 — 라이브 측정 신원을 원장에서 독립적으로 읽기

수정 허용: `v7_harness/pilot.py`, `.coord/runs/measure_p05.py`.

현재 결함:
- `measure_p05.py`의 `read_terminal_ledger`는 `deliveries`·`leases`에 없는 `task_id` 열로 조회해 예외가 나고, 예외를 삼켜 항상 None을 반환한다.
- source_hash를 `"UNKNOWN"`으로 고정하고, bundle_id를 summary.json에서 읽어 원장 검증이 순환한다.
- pilot은 `checkpoints` 테이블에 아무것도 기록하지 않는다.

요구:
1. `pilot.py`: bundle이 만들어지면 원장 `checkpoints`에 (checkpoint_id, attempt_id, resource_id, base_manifest_hash=원본 manifest 해시, artifact_set_hash=bundle_id, fence) 한 행을 기록한다(같은 attempt 재실행·approve 재생 시 중복 없이). 또 `runs/<task>/identity.json`에 {task_id, run_id(attempt_id), source_hash("sha256:"+base manifest hash), bundle_id}를 쓴다. summary.json 키 구성은 바꾸지 않는다.
2. `measure_p05.py`:
   - `read_terminal_ledger(work_dir, task_id)`: attempts(task_id로 최신 attempt) + checkpoints(attempt_id) + leases(attempt_id)·deliveries(가능한 키로)에서 읽어 {task_id, run_id, source_hash("sha256:"+base_manifest_hash), bundle_id(artifact_set_hash), attempt_state, delivery_state, lease_state} 반환. **summary.json을 읽지 않는다.** 예외를 삼키지 말고 원인이 드러나게 한다(없으면 None).
   - `read_pilot_identity(work_dir, task_id)`: identity.json을 읽어 반환.
   - 라이브 러너는 evidence의 pilot_summary에 summary.json + identity.json을 합쳐 넣는다.
3. 인수: `tests/test_b44_live_identity.py`, 원본 `tests/test_r0_measurement_validity.py`(R0_MEASURE_TARGET), 전체 discover 통과.
