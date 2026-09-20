[M2-R1] 실전 파일럿 재작업 1회 (P1 2건만)

너는 실행자다. 조율자가 추가한 실패 테스트 2개를 통과시키는 수정만 한다. 새 기능 금지.

실패 테스트 (tests/test_m2_pilot.py, 수정 금지):
1. M2PilotTests.test_approve_same_task_on_replay_applies_saved_bundle
   - 실제 승인 흐름: 같은 task를 먼저 실행(DRY_RUN_PASSED) → 같은 task를 --approve <bundle_id>로 다시 실행하면 agy를 재실행하지 않고(replay) 저장된 bundle을 apply_promotion 해야 한다.
   - 수정 방향(v7_harness/pilot.py만): 첫 실행 성공 시 bundle.to_dict()를 runs/<task>/bundle.json에 저장하고 summary에 staging 경로를 알 수 있게 한다(12개 키 제한 유지: 추가 키 대신 bundle.json 안에 staging_dir 저장). replay 분기에서 approve_bundle_id가 있고 저장 summary의 state가 SUCCEEDED이며 promotion이 DRY_RUN_PASSED이면 PatchBundle.from_dict(bundle.json)으로 apply_promotion(source_dir, staging_dir, bundle, approve_bundle_id) 실행. 일치→"APPLIED", 불일치→"APPROVAL_MISMATCH", IsolationError→"REJECTED". 결과 promotion을 summary.json에도 저장하고 반환에는 "replayed": True 추가. 실패 실행의 replay 승인은 "BLOCKED".
2. PilotCliTests.test_cli_defaults_watch_roots_to_home_and_temp
   - 수정 방향(v7_harness/cli.py cmd_pilot_run만): --watch-root 미지정 시 기본 watch_roots = [Path.home(), Path(tempfile.gettempdir())]. run_pilot은 cmd_pilot_run 안에서 `from .pilot import PilotConfig, run_pilot`으로 import되어 mock.patch("v7_harness.pilot.run_pilot")가 적용되어야 한다(현 구조 유지).

수정 허용 파일: v7_harness/pilot.py, v7_harness/cli.py (pilot 관련 부분만). 그 밖 수정 금지.
완료 후 변경 요약만 짧게 보고.
