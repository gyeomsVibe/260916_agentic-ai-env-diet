# Claude → Codex 지원 메모 04 — U12 read-only CRITIC/REDTEAM (UNAVAILABLE 대체)

U12 기록에서 Claude read-only 비평 호출이 stdout 회수 실패로 `UNAVAILABLE`이었다. 같은 목적의 정적 검토 결과다. 대상: `v7_harness/execution/{engine,launcher,lease}.py` (2026-09-17 13:15 기준). 코드는 수정하지 않았다.

| # | 등급 | 위치 | 결함 | 재현 시나리오 | 보강안 |
|---|---|---|---|---|---|
| 1 | P1 | `launcher.py` TimeoutExpired 분기 | 타임아웃을 `effect_state="NONE", retryable=True`로 기록한다 | 실제 worker가 파일·외부 write를 끝낸 뒤 응답 전에 타임아웃됨 → 재시도로 **중복 부작용** | worker capability가 `read_only`일 때만 NONE. 그 외는 `UNKNOWN` + `NEEDS_RECONCILIATION`, 자동 재시도 금지. 근거: 메모 01 E2 실측에서 agy가 `status:ERROR`를 반환했는데도 파일이 실제로 써졌다 |
| 2 | P1 | `launcher.py` `proc.kill()` | Windows에서 직계 프로세스만 종료되고 자식 트리는 남는다 | 실제 `agy`는 하위 프로세스를 띄운다. 타임아웃 뒤 고아 자식이 fence 이동 후에도 계속 쓰기 | Job Object(`CreateJobObjectW` + `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`)에 worker를 넣거나 `taskkill /T /F /PID`. 테스트: mock worker가 자식 프로세스를 띄운 뒤 타임아웃 → 자식 생존 0 |
| 3 | P2 | `lease.py` `assert_fence` 만료 분기 | `UPDATE leases SET state='EXPIRED'` 직후 같은 트랜잭션에서 raise → `with connection:`이 rollback해 **EXPIRED 기록이 사라진다** | lease 만료 뒤 늦게 도착한 완료 → 거부는 되지만 lease는 계속 `ACTIVE`로 남음 → 다음 claim의 중복 판정이 시각 비교에만 의존 | 만료 표시를 별도 짧은 트랜잭션으로 커밋한 뒤 거부하거나, 예외 대신 결과 코드를 반환하고 phase3 바깥에서 기록 |
| 4 | P1 | `engine.py` phase3 stale fence 거부 | fence 거부 시 결과 트랜잭션 전체가 rollback된다. 실제 worker는 이미 작업을 수행했을 수 있다 | 긴 worker 실행 중 lease 만료·재배정 → 늦은 결과 폐기, **부작용 여부 기록 없음** | 거부 시 별도 트랜잭션으로 `effects(state='UNKNOWN', reason='STALE_FENCE')` + event를 남기고 reconciliation 대상으로 올린다 |
| 5 | P2 | lease 기간 vs 실제 실행 시간 | mock은 1초 기본 timeout. 실측 agy 호출은 25~156초 | 실제 연결 시 lease가 실행 중 만료 → #4 빈발 | worker 실행 중 lease renew(heartbeat, 조건부 UPDATE `WHERE fencing_token=?`)를 U12 인터페이스에 포함하고, 테스트에 "renew 성공 시 완료 커밋 허용 / renew 실패 시 거부"를 추가 |

## 추가 테스트 제안 (U12 인수 기준 "timeout/crash/partial-result handling" 보강)

1. `test_timeout_effectful_worker_is_unknown_not_retryable`
2. `test_timeout_kills_worker_process_tree`
3. `test_expired_lease_state_persists_after_rejection`
4. `test_stale_fence_rejection_records_unknown_effect`
5. `test_lease_renew_extends_and_stale_renew_rejected`
