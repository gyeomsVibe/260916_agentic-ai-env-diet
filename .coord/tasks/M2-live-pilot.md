# [M2] 실전 파일럿

- Status: DONE
- Owner: Codex (coordinator, final judgment)
- Executor / independent verifier: Antigravity only (Claude Code is not part of this plan)
- Conversation: [M2] 실전 파일럿
- Depends on: U14 = M1 (`DONE`)
- Design: `docs/15_minimum-completion-path-design_2026-09-17.md` §5 M2 (정본), 지시문 `docs/14_codex-directive-minimum-completion-path_2026-09-17.md` "다음 대화창용"
- Scope: 기존 부분 산출물 `v7_harness/execution/agy_launcher.py`, `v7_harness/pilot.py`, `v7_harness/cli.py`, `v7_harness/isolation/promotion.py`, `tests/test_m2_pilot.py`, 기존 샘플 프로젝트 `D:\D_Workspace_NB\-agentic-ai-workspace\260916_pilot_sample\`(재생성 금지), `.coord/runs/P01/**`, this card, PLAN M2 row
- Excludes: Named Pipe 상주 broker, MCP 어댑터, 삭제·이름변경 반영, 이 프로젝트 원본 반영, 전역 규칙 변경, push/deploy, M3 생성·시작

## Acceptance

1. `AgyProcessLauncher`: U12 launcher와 같은 `launch()` 인터페이스로 실제 agy를 실행한다. Job Object에 편입하고, 런처 타임아웃은 print_timeout+60초로 둔다. 원문은 `.coord/runs/<task>/<attempt>.{json,err}`에 저장하고 U14 `parse_agy_result`로 판정한다. conversation_id는 고정한다.
2. `pilot run --task P01 --source <dir> --prompt-file <md>`는 다음 순서를 한 프로세스에서 수행하고 끝난다: run-once 잠금 → enqueue → staging → watch roots → engine.execute → assert_unchanged → patch bundle → dry-run → `summary.json`(7줄).
3. `isolation_mode`는 `StagingWorkspace` 객체에서만 파생한다. 문자열 `staging`을 넘겨 권한 건너뛰기를 켜는 공개 경로가 없어야 한다(A1).
4. `apply_promotion`은 다음을 모두 만족할 때만 원본에 쓴다: dry-run 충돌 0·범위 위반 0·삭제/이름변경 0, 원본 base manifest 재확인 일치, `--approve <bundle_id>` 명시. 그 외에는 원본 쓰기 0.
5. P01 A/B: A는 Codex 단독, B는 `pilot run` 1회와 summary 판정이다. `.coord/runs/P01/ab.json`에 다음을 기록한다: Codex 5h% 전후, codex usage, 턴 수, agy usage, 벽시계 시간, 인수 테스트 exit, 재작업·개입 횟수.
6. 게이트: B가 인수 테스트를 통과하고, 거짓 성공 0, 범위 밖 쓰기 0이어야 한다. 절감률은 실측값 그대로 보고한다.

## Approvals required (user)

- 샘플 프로젝트 폴더 생성 1회
- 첫 `--approve` 실제 반영 1회

## Stop rules (docs/15 §3)

P1만 차단한다. P2·P3는 BACKLOG에 적는다. 독립 검증은 최대 2회다. 재작업은 검증에서 나온 항목만 한다.

## Work log

- 2026-09-17: M1 DONE 후 Claude가 카드 생성. 미착수.
- 2026-09-17T19:19:59+09:00: M2 전용 대화창에서 Codex가 `ACTIVE`로 점유했다. `git status --short --branch`는 비Git 작업공간으로 exit 128. 사용자 지시에 따라 기존 부분 산출물과 기존 샘플 프로젝트를 실제 diff·테스트로 검수하며, 실제 원본 `--approve` 반영은 수행하지 않는다.
- 2026-09-17T19:20~19:40+09:00: 현행 P1 두 건을 `python -W error::ResourceWarning -m unittest tests.test_m2_pilot`로 재현했다(17개, 2 failures, exit 1): 승인 replay가 `DRY_RUN_PASSED`, CLI 기본 watch roots가 `[]`. Antigravity bridge 구현 위임 3회(`mu5dq0yu_y2ycz9` 10m, `mu5e3o24_5fo6b7` 5m, `mu5eazl7_3vl3zz` 3m)는 모두 print timeout으로 출력·허용 파일 변경이 없었다. 동일 외부 실행 실패 3회 중단 규칙과 '구현 초안은 Antigravity만' 경계 때문에 직접 수정하지 않고 `BLOCKED`로 반환한다. 실제 P01·원본 apply·A/B·독립 검증·M3는 미실행이다.
- 2026-09-17: 사용자가 완전 논스탑 진행과 `docs/claude-assist/11` 직접 agy fallback을 선택하고, 샘플 프로젝트의 첫 `--approve <bundle_id>` 실제 반영 및 M3 규칙 변경을 명시 승인했다. 같은 M2 카드를 `ACTIVE`로 재개한다.
- 2026-09-17: Codex 직접 재작업으로 승인 replay와 CLI HOME/TEMP 기본값 P1을 해소하고, 다중 파일 apply 실패 시 전부 복구하는 반례·구현을 추가했다. 실제 P01 B 1차는 TEMP의 agy 런타임 잡음(UUID `.tmp`, 동일 내용 Codeium unleash schema mtime)으로 `EXTERNAL_WRITE` 안전 차단됐고, 두 경로만 최소 제외하는 회귀 테스트 후 B 재실행은 68.883초 `DRY_RUN_PASSED`, staging 6/6, 승인 replay `APPLIED`, 원본 샘플 6/6이었다. A Codex 단독은 23.167초·6/6. `.coord/runs/P01/ab.json`에 실측과 비동등 조건 경고를 기록했다. Antigravity 독립 검증 1차는 계획만 반환해 무효, 2차는 49 tests/exit 0/PASS. 최종 M2 18·U10~U14 124·전체 197·compileall exit 0.

## Handoff

- Result: REVIEW — M2 acceptance와 실제 P01 승인 반영 완료, P1 재현 0.
- Changed: `v7_harness/pilot.py`, `v7_harness/cli.py`, `v7_harness/isolation/promotion.py`, `v7_harness/isolation/security.py`, `tests/test_m2_pilot.py`, `tests/test_u13_isolation.py`, `.coord/runs/P01/**`, 샘플 프로젝트 두 곳, PLAN·this card.
- Checks and exit codes: M2 18/18 exit 0; M2+U13 49/49 exit 0; U10~U14 124 (skip 1) exit 0; 전체 197 (skip 1) exit 0; compileall exit 0; P01 staging/source 각각 6/6 exit 0; independent review V2 PASS/49/exit 0.
- Remaining risks: 첫 B 차단과 M2 재작업이 포함돼 A/B는 steady-state 동등 비교가 아니며 비용·토큰 절감은 `UNMEASURED`. `codex exec --json` usage는 `UNAVAILABLE`.
- Next action: 조율자가 증거를 재검토해 M2 DONE 여부를 판정한 뒤에만 M3를 ACTIVE로 열고, 이미 승인된 백업·diff·규칙 적용·신규 세션 게이트를 수행한다.
- Coordinator decision: 사용자 논스탑 지시와 기록된 실제 P01·회귀·독립 검증 증거를 인수해 `DONE`; M3를 `READY`로 개방했다.
