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
