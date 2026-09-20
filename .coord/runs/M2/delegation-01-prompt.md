[M2] 실전 파일럿 구현 초안 (Antigravity 실행자)

너는 이 프로젝트의 실행자다. 조율자가 고정한 실패 테스트를 통과시키는 구현만 작성한다.

## 반드시 읽을 것
- tests/test_m2_pilot.py (인수 계약, 수정 금지)
- tests/fixtures/fake_agy.py (수정 금지)
- .coord/tasks/M2-live-pilot.md
- v7_harness/adapters/agy.py (build_agy_command, parse_agy_result, AgyRequest)
- v7_harness/execution/launcher.py (_create_win_job, _assign_process_to_job, _terminate_process_tree, _cleanup_job, MockSubprocessLauncher.launch 시그니처)
- v7_harness/execution/engine.py (DurableExecutionEngine(target, launcher=...), execute(command, worker_capability=..., timeout_sec=...))
- v7_harness/execution/circuit.py (set_quota_state)
- v7_harness/broker/core.py (BrokerCore(db_path).start()/enqueue()/close())
- v7_harness/isolation/staging.py, manifest.py, promotion.py, security.py (NonGitStagingAdapter, StagingWorkspace.create_patch_bundle, dry_run_promotion, snapshot_watch_roots, ExternalWriteDetectedError, WatchScanUnavailableError)
- tests/test_u12_execution.py 의 make_command 와 set_quota_state 사용 예

## 작성·수정 허용 파일 (이 밖은 절대 수정 금지)
1. v7_harness/execution/agy_launcher.py (신규)
2. v7_harness/pilot.py (신규)
3. v7_harness/isolation/promotion.py 의 apply_promotion 함수만 교체
4. v7_harness/cli.py 에 `pilot run` 서브커맨드 추가(기존 서브커맨드 수정 금지)

## 계약
### AgyProcessLauncher (agy_launcher.py)
- `__init__(self, *, agy_command: list[str], request: AgyRequest, runs_dir: Path)`
- `launch(self, *, attempt_id, acceptance_hash, command_id="c1", mode="success", timeout_sec=None, on_wait_hook=None, worker_capability=None, heartbeat=None, heartbeat_interval_sec=0.25, **kwargs) -> WorkerDecision` (engine이 호출하는 인터페이스 그대로)
- argv = `agy_command + build_agy_command(request)[1:]` (build_agy_command의 첫 원소 실행파일 이름은 agy_command로 대체)
- subprocess.Popen, Windows Job Object 편입, 런처 타임아웃 = request.print_timeout_s + 60초, 초과 시 _terminate_process_tree, heartbeat 실패 시 종료
- stdout/stderr 원문을 runs_dir/`<attempt_id>.json`, `<attempt_id>.err` 로 저장, `self.last_outcome = parse_agy_result(...)`, `self.raw_paths = (json_path, err_path)`
- WorkerDecision 매핑: outcome.successful → WorkerDecision(True, "SUCCEEDED", "CONFIRMED", False, "NONE"); 아니면 WorkerDecision(False, "NEEDS_RECONCILIATION", "UNKNOWN", False, outcome.error_class)
- 타임아웃은 WorkerDecision(False, "NEEDS_RECONCILIATION", "UNKNOWN", False, "TIMEOUT")

### run_pilot (pilot.py)
- `@dataclass PilotConfig(task_id, title, prompt, source_dir: Path, work_dir: Path, agy_command: list[str], watch_roots: list[Path], print_timeout_s: int = 600, approve_bundle_id: str | None = None)`
- `run_pilot(config) -> dict` 순서:
  1. work_dir 생성, db = work_dir/"coord.sqlite3", BrokerCore(db).start() (finally close)
  2. set_quota_state(core.connection, scope_id="pilot", provider="antigravity", quota_state="AVAILABLE")
  3. command: schema_version 1, command_id=f"{task_id}-cmd", task_id, card_revision 1, acceptance_hash=sha256(prompt), idempotency_key=f"{task_id}:{acceptance_hash}", operation "DISPATCH", payload_ref f"prompt:{task_id}", scope_id "pilot", provider "antigravity", resource_id f"res-{task_id}", attempt_id f"{task_id}-a001", owner "antigravity"; core.enqueue(command)
  4. 이미 같은 task의 summary.json(work_dir/"runs"/task_id/"summary.json")이 있고 enqueue가 duplicate=True면 기존 summary에 "replayed": True 로 반환(agy 재실행 금지)
  5. staging_dir = work_dir/"stage"/task_id ; workspace = NonGitStagingAdapter().create_staging(source_dir, staging_dir)
  6. request = AgyRequest(task_id, title, prompt, workspace=workspace.staging_dir, isolation_mode="staging", print_timeout_s=...) — isolation_mode 는 workspace 객체로부터만 만든다(문자열 인자 노출 금지)
  7. watch = snapshot_watch_roots(watch_roots)
  8. launcher = AgyProcessLauncher(...); engine = DurableExecutionEngine(core, launcher=launcher); engine.execute(command, worker_capability="effectful", timeout_sec=print_timeout_s+60) — 예외도 잡아서 실패 summary로 변환
  9. watch.assert_unchanged(): ExternalWriteDetectedError → error_class "EXTERNAL_WRITE", effect_state "UNKNOWN"; WatchScanUnavailableError → error_class "WATCH_SCAN_UNAVAILABLE"
  10. 성공(outcome.successful 이고 외부쓰기 없음)일 때만 bundle = workspace.create_patch_bundle(); dry = dry_run_promotion(source_dir=source_dir, patch_bundle=bundle); promotion = "DRY_RUN_PASSED" if dry.success else dry.status
  11. approve_bundle_id 가 주어졌고 성공이면: 일치 시 apply_promotion(...) → "APPLIED", 불일치 → "APPROVAL_MISMATCH"; 실패 실행이면 promotion "BLOCKED"
  12. summary 는 정확히 다음 12개 키: state("SUCCEEDED"|"FAILED"), error_class, effect_state("CONFIRMED"|"UNKNOWN"), promotion("DRY_RUN_PASSED"|"APPLIED"|"APPROVAL_MISMATCH"|"BLOCKED"|dry-run status), bundle_id(없으면 null), changed_files(정렬된 경로), conversation_id, agy_usage, agy_workspace, raw_stdout_path, raw_stderr_path, summary_path. 재실행(replay) 반환에만 "replayed": True 를 추가한다(저장 파일에는 넣지 않음).
  13. summary 를 work_dir/"runs"/task_id/"summary.json" 에 저장하고 반환

### apply_promotion (promotion.py)
- `apply_promotion(*, source_dir: Path, staging_dir: Path, patch_bundle: PatchBundle, approve_bundle_id: str) -> dict`
- 거부(IsolationError 계열 raise, 원본 쓰기 0): approve_bundle_id != bundle_id; DELETED/RENAMED 항목 존재; build_manifest(source_dir).manifest_hash != bundle.base_manifest_hash; staging 파일 sha256 != item.target_sha256; 경로 검증 실패(validate_canonical_path_in_root, assert_no_reparse_or_symlink)
- 통과 시 ADDED/MODIFIED 항목을 staging 에서 원본으로 복사(부모 디렉터리 생성), 반환 {"applied": [경로...], "bundle_id": ...}

## 완료 보고
구현 후 변경 파일 목록과 각 계약 항목 구현 위치를 짧게 보고한다. 테스트 실행은 조율자가 한다.
