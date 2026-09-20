# 실행 규칙(필수)
- 이 실행은 네가 최종 답변을 내는 순간 종료된다. 백그라운드 작업·비동기 명령을 쓰지 말고, 모든 코드 수정과 테스트 실행을 동기적으로 끝낸 뒤에만 최종 답변하라.
- 최종 답변에는 수정한 파일 목록과 테스트 결과(Ran N / OK)를 적는다.

# B28 — 감시 제외 정밀화: 전역 설정 파일 re-include

목표: `v7_harness/isolation/security.py`의 `DEFAULT_WATCH_EXCLUDES`는 HOME의 `.claude/**`, `.claude.json`, `.codex/**` 전체를 제외한다. 런타임 소음은 계속 제외하되, 에이전트가 전역 설정을 바꾸는 쓰기는 반드시 EXTERNAL_WRITE로 탐지되게 한다.

요구사항
1. `DEFAULT_WATCH_REINCLUDES`(frozenset, casefold·`/` 정규화)를 추가한다. 제외 패턴에 걸려도 여기에 걸리면 감시한다(제외보다 우선).
   - `.claude/settings.json`, `.claude/settings.local.json`, `.claude/CLAUDE.md`, `.claude/hooks/**`, `.claude/agents/**`, `.claude/skills/**`, `.claude/commands/**`, `.claude/rules/**`
   - `.codex/config.toml`, `.codex/AGENTS.md`, `.codex/rules/**`, `.codex/skills/**`
   - `.claude.json`은 Claude 실행 중 매번 바뀌는 소음이므로 계속 제외한다(re-include 하지 않음).
2. 제외 판정 로직(`_watch_exclude_regex`를 쓰는 곳)에 re-include 우선 규칙을 넣는다. 제외된 디렉터리 안으로 내려가야 re-include 파일을 볼 수 있으면, `.claude`·`.codex` 디렉터리는 순회하되 re-include에 걸리지 않는 항목만 무시하도록 한다. 순회 비용은 re-include 경로만 확인하는 방식으로 최소화한다(예: 위 파일·디렉터리만 직접 지문).
3. 기존 동작(현재 task staging 제외, sibling 탐지, 기존 excludes, custom excludes)은 그대로 유지한다.
4. 테스트를 `tests/test_b28_reinclude.py`에 추가한다.
   - 임시 HOME 루트에서 `.claude/settings.json` 쓰기 → 탐지됨
   - `.codex/config.toml` 쓰기 → 탐지됨
   - `.claude/hooks/x.ps1` 생성 → 탐지됨
   - `.claude/projects/a/b.jsonl`, `.claude.json`, `.codex/sessions/x.jsonl` 쓰기 → 탐지 안 됨(소음)
   - 대소문자 변형(`.CLAUDE/Settings.json`) → 탐지됨
5. 수정 범위는 `v7_harness/isolation/security.py`와 새 테스트 파일로 한정한다. 다른 파일 수정·삭제 금지. 전역 설정 파일을 실제로 건드리지 말 것(테스트는 임시 폴더만).
6. 끝나면 `python -m unittest discover -s tests -q`가 통과해야 한다.

## 추가 요구(B08 간헐 실패 해소)
7. `tests/test_u12_execution.py`의 `test_lease_heartbeat_renews_conditionally_and_failed_renew_reconciles_late_result`는 `default_lease_duration=1`(1초) 때문에 전체 테스트 부하 중 lease가 heartbeat 전에 만료돼 3회 중 1회 ERROR가 난다. 테스트 의도(조건부 갱신 성공 / owner·fence 변경 시 LATE_RESULT_NEEDS_RECONCILIATION)는 그대로 두고, 두 엔진의 `default_lease_duration`을 30으로 올리는 식으로 타이밍 의존만 제거하라. 제품 코드(`v7_harness/execution/*`)는 수정하지 않는다.
8. 이 항목 때문에 수정 범위에 `tests/test_u12_execution.py`를 추가로 허용한다.

## 추가 요구(무변경 PASS 거짓 성공 차단)
9. `v7_harness/pilot.py`에서 agy가 SUCCEEDED이고 인수 테스트가 통과했더라도 `changed_files`가 비어 있으면 `verdict_hint`를 `REWORK`로 하고 `summary["reason"]="NO_CHANGES"`를 넣는다(승인 대상 bundle이 없으므로 반영 불가). 읽기 전용 과제용으로 `PilotConfig`에 `allow_no_changes: bool = False`, CLI에 `--allow-no-changes` 플래그를 추가해 이 경우만 PASS를 허용한다.
10. 인수 테스트 실패 원인 추적을 위해 인수 명령의 stdout/stderr 마지막 4000자를 `runs/<TASK>/acceptance.log`에 저장하고 summary에 `acceptance_log_path`를 넣는다(summary 기존 키는 유지).
11. 테스트: `tests/test_b30_no_change_verdict.py`에 무변경→REWORK/NO_CHANGES, `--allow-no-changes`→PASS, acceptance.log 생성 검증을 추가한다(기존 fake agy fixture 활용).
12. 수정 범위에 `v7_harness/pilot.py`, `v7_harness/cli.py`, `tests/test_b30_no_change_verdict.py`를 추가로 허용한다.

## 추가 요구(P1: 재시도 예산 누적 차단)
13. `v7_harness/pilot.py`는 retry budget·quota의 `scope_id`를 고정값 `"pilot"`으로 써서, 한 work-dir에서 과제 3개를 실행하면 이후 모든 과제가 `CircuitOpenError("RETRY_BUDGET_EXHAUSTED")`로 막힌다(실측: `.coord/pilot` 원장 usage 3/3). `scope_id`를 과제별 `f"pilot:{task_id}"`로 바꿔 예산이 과제 단위로 적용되게 하고, 필요한 quota 레코드(`AVAILABLE`)도 같은 scope로 생성한다. 같은 task의 재시도 한도(3회)는 유지한다.
14. `engine.execute`에서 `WorkerExecutionError`가 아닌 `ExecutionError`(예: `CircuitOpenError`, `QuotaFailClosedError`)가 나면 `error_class`에 예외 메시지 코드(예: `RETRY_BUDGET_EXHAUSTED`)를 넣고, 그 외 예외도 `summary["error_detail"]`에 `type(exc).__name__: 메시지` 앞 300자를 넣는다. 현재는 모두 `EXECUTION_ERROR`로 뭉개져 원인을 알 수 없다.
15. 테스트(`tests/test_b30_no_change_verdict.py`에 추가): 같은 work-dir에서 서로 다른 task 4개를 fake agy로 연속 실행 → 4번째도 SUCCEEDED; 같은 task 예산 초과 시 `error_class=RETRY_BUDGET_EXHAUSTED`.
