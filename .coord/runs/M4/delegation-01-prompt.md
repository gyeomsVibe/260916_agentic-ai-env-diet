[M4] 효율 튜닝 구현 (Antigravity 실행자)

너는 실행자다. 조율자가 고정한 실패 테스트를 통과시키는 구현만 작성한다. 테스트 파일은 수정하지 않는다(단 아래 예외 1건).

반드시 읽을 것:
- tests/test_m4_efficiency.py (인수 계약 11개)
- tests/test_m2_pilot.py (기존 계약, 회귀 금지)
- .coord/tasks/M4-efficiency-tuning.md
- v7_harness/pilot.py, v7_harness/cli.py (pilot 부분)
- v7_harness/contracts/database.py (attempts/leases/deliveries/effects/events 상태 CHECK 값)

수정 허용 파일(그 밖 수정 금지):
1. v7_harness/pilot.py
2. v7_harness/cli.py (pilot run/reconcile 부분만)
3. tests/test_m2_pilot.py 의 `self.assertLessEqual(len(summary), 12)` 한 줄만 14로 변경 (예외 허용)

계약:
A) PilotConfig 에 `accept_cmd: str | None = None` 추가. CLI `pilot run --accept-cmd "<명령>"`.
B) agy 성공 + 외부쓰기 없음일 때만 accept_cmd 를 staging 디렉터리를 cwd 로 실행(shlex.split(cmd, posix=False) 후 각 토큰의 양끝 큰따옴표 제거, shell=False, timeout 300s). summary 에 `acceptance_exit`(int 또는 None), `verdict_hint` 추가(총 14키 이하):
   - 실행 실패/외부쓰기/재조정 필요 → "BLOCKED", acceptance_exit None (accept 실행 안 함)
   - 성공 + accept_cmd 없음 → "NEEDS_ACCEPTANCE"
   - 성공 + exit 0 → "PASS"; exit != 0 → "REWORK"
   - approve 요청 시 verdict_hint 가 PASS 가 아니면 promotion "BLOCKED" (원본 쓰기 0). replay 승인 경로도 저장된 verdict_hint 가 PASS 여야 적용.
C) 실행 종료(성공·실패 모두) 후 해당 attempt 의 ACTIVE lease 를 RELEASED 로 바꾼다(core 트랜잭션, events 에 기록 가능하면 기록).
D) 재조정:
   - `reconcile_pilot(*, work_dir: Path, task_id: str) -> dict` : work_dir/coord.sqlite3 를 BrokerCore 로 열고, task_id 의 attempts 중 state IN ('RUNNING','PENDING','VERIFYING','NEEDS_RECONCILIATION') 인 것에 대해: attempt → 'FAILED', 해당 delivery(state 'CLAIMED' 또는 'PENDING') → 'DEAD', 해당 ACTIVE lease → 'REVOKED'. 대상이 있으면 runs/<task>/summary.json 을 {"state":"ABANDONED", ...} 로 저장하고 {"state":"ABANDONED","reconciled_attempts":n} 반환, 없으면 {"state":"NOTHING_TO_RECONCILE","reconciled_attempts":0}. SUCCEEDED attempt·원본 파일은 건드리지 않는다.
   - CLI `pilot reconcile --task <ID> --work-dir <dir>` → `from .pilot import reconcile_pilot` (함수 내부 import 로 mock 가능하게), JSON 출력, 반환 0.
   - run_pilot: 시작 시 같은 task 에 미정리 attempt(RUNNING/PENDING/VERIFYING/NEEDS_RECONCILIATION)가 있으면 agy 실행 없이 summary error_class "NEEDS_RECONCILIATION", verdict_hint "BLOCKED", state "FAILED" 반환.
   - 재실행 번호: 같은 task 의 기존 attempts 수를 n 이라 하고, DEAD delivery 가 있으면 새 attempt_id f"{task}-a{n+1:03d}", command_id f"{task}-cmd-r{n+1}", idempotency_key 에 f":r{n+1}" 를 붙여 새로 enqueue 한다. 저장 summary 가 ABANDONED 면 replay 하지 않는다. 최초 실행은 기존 id(a001, {task}-cmd) 유지(기존 테스트 호환).
E) KeyboardInterrupt 등 BaseException 은 잡지 않는다(중단 상태가 원장에 남는 것이 테스트 전제).

완료 후 변경 요약만 짧게 보고. 테스트 실행은 조율자가 한다.
