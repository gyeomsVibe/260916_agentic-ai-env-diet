# BACKLOG — 최소 완성 경로 밖 항목

규칙(docs/14 §3): P2·P3와 파일럿 이후 강화 항목은 여기에 한 줄로 기록하고 현재 단계를 막지 않는다. 트리거가 발생하면 별도 단계로 연다.

| ID | 등급 | 항목 | 출처 | 트리거 |
|---|---|---|---|---|
| B01 | P2 | 잠긴 파일(LOCKED) 같은 크기 내용 교체 미탐지 → NTFS ChangeTime/USN | U13 R1, claude-assist/06 | 파일럿에서 LOCKED 파일 판정 불명 발생 |
| B02 | P2 | 지문 예산 초과 시 루트 전체 실패 → 파일 단위 UNVERIFIED 증거 | U13 R2 | 실제 프로젝트 스냅샷 예산 초과 |
| B03 | P2 | reparse 검사↔open TOCTOU, OS ACL 격리 | U13 R3 | 다중 사용자·원격 실행 도입 |
| B04 | P2 | `--flag=value` 형식 도움말 capability 파싱 | U14 V1 | agy 도움말 형식 변경 |
| B05 | P2 | RecursionGuard cycle 집합이 호출 체인 범위 없이 누적(형제 호출 오차단) | U14 V1 | 같은 root에서 동일 intent 반복 호출 필요 |
| B06 | P3 | `call_depth=0` 거부 메시지 명확화 | U14 V1 | — |
| B07 | RESOLVED(B0714) | `/login` 부분문자열로 AUTH 과분류 | U14 V1 | 오분류 실제 발생 |
| B08 | RESOLVED(B30S) | U12 `test_lease_heartbeat…` 부하 시 간헐 실패 → lease 1초→30초로 타이밍 의존 제거 | M1 회귀 실행 | 2026-09-18 1/3 재발로 트리거 충족 |
| B09 | P2 | Named Pipe 상주 broker·MCP 어댑터 | docs/13 §7 | 동시 위임 2건 이상 필요 |
| B10 | P2 | 백업·복구·장애 주입 매트릭스 F01~F24 | docs/13 §17 | 파일럿 3건 누적 |
| B11 | P2 | 삭제·이름변경 포함 bundle 반영 | docs/14 M2-4 | 실제 과제에서 필요 |
| B12 | P2 | backend/frontend 병렬 lane | R19 | 단일 경로 3건 안정 |
| B13 | P3 | Windows Named Pipe DACL·인증키 공급 | U11 | B09 착수 시 |
| B14 | RESOLVED(B0714) | 제어문자 검사에 Unicode 줄/문단 구분자 `\u2028`·`\u2029` 미포함 | M1 V2 | 에이전트 UI가 해당 문자를 줄바꿈으로 표시 확인 시 |
| B15 | P3 | usage 테스트에 유효·무효 혼합 dict 케이스 없음(코드는 거부) | M1 V2 | usage 파서 변경 시 |
| B16 | P2 | TEMP 감시 제외 `????????-????-????-????-????????????.tmp`가 GUID 이름 파일 쓰기를 전부 숨김 | M2 Claude 검토 | agy 외 도구가 TEMP GUID 파일 사용 확인 시 |
| B17 | P2 | 반영(apply) 중 2차 실패 시 롤백 불완전 가능성 | M2 Codex 최종 보고 | 실제 반영 실패 발생 |
| B18 | P2 | 오래된 실패 기록(summary·원장)과 새 실행 혼동 가능성 | M2 Codex 최종 보고 | 같은 task 재사용 빈도 증가 |
| B19 | P3 | M4 이전 실행(P01)의 lease가 ACTIVE로 잔존(신규 실행은 해제됨) | M4 원장 점검 | 같은 resource 재사용 시 |
| B20 | RESOLVED | `pilot run`에 `--model` 옵션 추가(AgyRequest/PilotConfig/cli 연동, 3 tests PASS) | M4 P03 실측, B20 | — |
| B21 | RESOLVED | `--accept-cmd`에 쉘 파이프·체이닝 연산자 감지 시 shell=True 안전 지원 (1 test PASS) | M4 V1, B21 | — |
| B22 | RESOLVED | `work_dir/stage` 얕은 감시+현재 task 제외로 X10 `EXTERNAL_WRITE/BLOCKED` PASS | 극한 테스트 16, B22 R4 | — |
| B23 | RESOLVED | `DEFAULT_WATCH_EXCLUDES`에 Claude 런타임 경로 추가 및 `BrokerAlreadyRunning` 시 구조화 summary/exit 1 반환 (2 tests PASS) | 극한 테스트 16, B23 | — |
| B24 | RESOLVED | 삭제 bundle 승인 시 IsolationError를 REJECTED/ISOLATION_ERROR 구조화 summary로 변환 (1 test PASS) | 극한 테스트 16, B24 | — |
| B25 | RESOLVED | 원장 손상 시 traceback 대신 DB_UNAVAILABLE 요약 및 복구 안내 출력, exit 1 (2 tests PASS) | 극한 테스트 16, B25 | — |
| B26 | RESOLVED | TIMEOUT 및 unreconciled 실패 시 summary에 next_action reconcile 힌트 제공 (1 test PASS) | 극한 테스트 16, B26 | — |
| B27 | 참고 | 5천 파일 staging 36초(X13) → 대형 저장소는 worktree 경로 | 극한 테스트 16 | 대형 저장소 적용 시 |
| B28 | RESOLVED(B30S) | B23 소음 제외가 `~/.claude/**`·`~/.codex/**` 전체를 숨겨 hooks·agents·skills·settings·AGENTS.md·config.toml 변조 미탐지 → `DEFAULT_WATCH_REINCLUDES`로 재포함(8경로 탐지·소음 4경로 제외 실측, HOME 176파일 0.4s) | Claude 레드팀·Antigravity 협의 C01 | — |
| B31 | RESOLVED(B30S) | P1: retry budget `scope_id="pilot"` 고정 → work-dir당 과제 3개 후 전부 `RETRY_BUDGET_EXHAUSTED`(`.coord/pilot` 3/3 소진) → `pilot:<task>` 과제별 | B30 실측 | — |
| B32 | RESOLVED(B30S) | P1: agy가 백그라운드만 띄우고 종료(변경 0)해도 PASS → 무변경은 `REWORK`/`NO_CHANGES`, `--allow-no-changes` | B29 실측 | — |
| B33 | RESOLVED(B30S) | 비-worker 실행 예외가 `EXECUTION_ERROR`로 뭉개짐 → `error_class` 코드·`error_detail` | B30 실측 | — |
| B34 | RESOLVED(B30S) | 인수 테스트 실패 출력 미보존 → `runs/<task>/acceptance.log` | B28R 실측 | — |
| B35 | RESOLVED(B41묶음) | `test_m4_efficiency` summary 키 수 상한(≤14)이 하한(≥14)으로 완화됨 → 선택 키 포함 상한(≤18)으로 복원 (tests PASS) | B30S 리뷰 | — |
| B36 | RESOLVED(B41묶음) | 원본 직접 수정과 `pilot run`이 동시에 일어나면 `SourceDivergenceError` 트레이스로 종료(반영은 안전하게 차단) → 구조화 summary(`SOURCE_DIVERGED`) (2 tests PASS) | B30 실측(IDE 동시 수정) | — |
| B37 | 참고 | agy 쿼터 소진 시 `--print-timeout` 동안 429 재시도만 하다 빈 출력 → 사전 쿼터 탐지·모델 폴백 목록 | 2026-09-18 실측 | 쿼터 소진 재발 |
| B38 | RESOLVED(B3852R) | `--accept-cmd`가 staging cwd에서 실행 → 에이전트가 만든 `python.exe`·`pytest.bat` 등이 PATH보다 먼저 잡힐 수 있음(CWD 바이너리 선점) → 인수 명령은 절대 경로 인터프리터 사용 권장·검사 | 독립 검증 r2 | — |
| B39 | RESOLVED(B41묶음) | re-include 순회가 `.claude/skills` 등에 대용량 폴더가 있으면 감시 예산 초과로 fail-closed(가용성 저하) → re-include 하위 `node_modules`·venv 제외 (2 tests PASS) | 독립 검증 r2 | — |
| B40 | RESOLVED(Claude 핫픽스, Codex 검토 대기) | Claude 앱 `~/.claude/skills/synced/` 주기 동기화가 재포함 감시를 깨 HOME 스캔 예산 초과·EXTERNAL_WRITE → pilot 전체 실행 불가. `DEFAULT_REINCLUDE_NOISE` 추가, 테스트 2, 전체 252 OK | P05C 실측 | — |
| B41 | RESOLVED(B41묶음) | `EXTERNAL_WRITE` summary에 변경 경로가 없어 원인 추적에 별도 diff 필요 → `external_paths` (2 tests PASS) | P05C·P05D 실측 | — |
| B42 | 운영 | 전역 설정(`~/.codex/skills` 등) 편집과 pilot 실행이 겹치면 설계대로 BLOCKED. 측정·위임은 전역 편집이 없는 시간대에 | P05D 실측(Codex가 mia-vaccine-test 편집 중) | — |
| B43 | RESOLVED(R0P2·R0P3) | 재포함 트리 무거운 폴더 처리: 이름 충돌 은닉(venv 스킬, hooks/.git) 해소, node_modules 등은 제외 대신 메타데이터 감시(지문 예산 0) | 독립 검증 r3·r4 | — |
| B44 | RESOLVED(B44S) | `measure_p05.py` 라이브 러너 `read_terminal_ledger`가 source_hash를 `UNKNOWN`으로 반환 → 라이브 B 측정이 항상 INVALID_PILOT_IDENTITY가 될 위험. 재측정 전 원장/summary의 실제 해시 사용 | 독립 검증 r5 | P05 B 재측정 전 필수 |
| B45 | 참고 | summary·ledger 양쪽 bundle_id가 None이면 신원 일치로 통과 가능(정상 PASS는 항상 bundle 존재) | 독립 검증 r5 | — |
| B46 | RESOLVED(Claude 핫픽스)/P2 잔여 | TEMP 최상위 VS 백그라운드 다운로드 로그(`dd_*.log`)·`tmp????.tmp`가 EXTERNAL_WRITE 유발 → 소음 제외 + 테스트. 잔여: 사전 스냅샷 중 불안정 파일(`WATCH_SCAN_UNAVAILABLE`)이 요약 없이 트레이스로 종료 → 1회 재시도·구조화 summary | B44·B44R 실측 | — |
| B47 | RESOLVED(B4647) | `_record_checkpoint_and_identity`가 attempts 행이 없으면 `RUNNING`으로 INSERT OR IGNORE — 정상 흐름엔 영향 없으나 원장 위조 여지, 없으면 실패하도록 | B44S 리뷰 | — |
| B48 | RESOLVED(R6FIX3) | r6 P1: B 실행 전 원장 스냅샷 없음 → 도구 0회 실패도 이전 성공 attempt로 VALID 가능 → `pre_run_attempt_ids`·`INVALID_STALE_RUN`. B46 패턴 축소(`dd_backgrounddownload_*.log`, `tmp[hex4].tmp`) | 독립 검증 r6 | — |
| B49 | P2 | r6 잔여: identity.json과 checkpoints가 같은 함수에서 동시 기록(독립성 약함), 비-hex bundle_id 해시 정규화 불일치, `P05-` 접두 허용으로 파생 과제 오인 | 독립 검증 r6 | 라이브 재측정 전 검토 |
| B50 | 운영 | 라이브 러너가 과제 ID `P05` 재사용 → 같은 task 재시도 한도(3)에 막힐 수 있음. 재측정은 새 ID 사용 | R6FIX 리뷰 | 재측정 시 |
| B51 | RESOLVED(B4647) | B46 잔여: 사전 스냅샷 불안정 시 1회 재시도, 재실패는 구조화 `WATCH_SCAN_UNAVAILABLE` summary | B44 실측 | — |
| B52 | RESOLVED(B3852R) | approve replay 경로가 B47 체크포인트 거부(RuntimeError)를 `pass`로 삼킴 → identity.json/checkpoint 미기록이 조용히 지나감. summary `error_detail`로 드러내기 | B4647 리뷰 | — |
| B53 | 운영 | 구현 위임 모델: Gemini Flash는 테스트를 백그라운드로 띄우고 대기 메시지로 종료하는 패턴 반복(B29·R2FIX2) → claude-opus-4-6-thinking 우선 | R2FIX2 실측 | — |
| B54 | RESOLVED | `control.py`가 `os.environ["PYTHONPATH"]`를 프로세스 전역으로 변경(IDE 직접 수정 13:40) → 호출자 환경 오염. `sub_env`를 subprocess `env=` 전달로 한정하여 전역 오염 제거 (33 tests PASS) | R3 준비 중 관찰 | — |
| B55 | RESOLVED(B55C) | 사용자 지시: 워크스페이스에는 프로젝트 폴더 하나만 → `.work/`·`.coord/pilot`을 manifest·staging 기본 제외, 형제 폴더 33개를 `.work/`로 이동(삭제 0), 측정 스크립트 경로 `.work` 전환, AGENTS.md 규칙 추가 | 사용자 지시 2026-09-19 | — |
| B56 | RESOLVED | 장기/대규모 실측 드라이버에 본 측정 전 1토큰급 사전 확인(preflight "reply OK") 프로브 추가하여 USAGE_LIMIT 시 자동 안전 지연 (R4 드라이버 구현 완료) | R3 Claude 메모 41 | 차기 실측 드라이버 작성 시 |
| B57 | RESOLVED | 조율 1턴 프롬프트를 고정 접두부(`COORDINATION_PROMPT_PREFIX`, 422자, R3·R4 드라이버 동일)와 가변 꼬리(expected_changed_files + summary JSON)로 분리. 접두부가 바이트 단위로 같아야 캐시 적중이 안정된다. 판정 계약(4조건·APPROVE/REJECT 1줄)은 동일 | Claude 메모 47 | 차기 측정에서 캐시 적중 편차 재확인 |
| B58 | RESOLVED(B58R3) | `.claude/codex-relay/**`의 중첩 `*.log`만 source manifest에서 제외. `.claude` 전체 제외 금지, relay 스크립트·settings·skills/hooks/agents/commands/rules 감시 유지. bundle `331b009b...` APPLIED, focused 8/8·full 335 OK(1 skip)·compileall 0·Claude PASS/P1 none | R2FIX4·R2FIX5 실측, Antigravity 메모 50 | — |

| B59 | RESOLVED | 전체 회귀 간헐 실패 원인 규명: U12 IPC 동시성 픽스처의 `dispatcher_capacity=4`에 동시 8건을 보내 일부가 재시도 가능한 `QUEUE_SATURATED`로 반환됨(부하·U13 무관). 픽스처 용량을 8로 맞추고 응답 제한시간 2→10s 여유 부여. 포화 동작은 359행 전용 테스트가 계속 검사. 4중 병렬 전체 회귀 4/4 OK(335, 1 skip) | R2FIX9·2026-09-20 재현 | — |
| B60 | RESOLVED | (해결: 2026-09-19 고정 테스트를 `ApplyingFakePilotRunner(defect=...)`로 교정, R2FIX15 APPLIED·R2 DONE) 원문:  R2 고정 테스트 모순: `test_post_apply_acceptance_failure_is_not_success`가 반영을 쓰지 않는 `FakePilotRunner`로 POST_APPLY_ACCEPTANCE_FAILED를 기대 → APPLY_NOT_OBSERVED 계약과 양립 불가, R2FIX11이 테스트 맞추기 분기로 통과(미승인). Codex가 해당 케이스를 `ApplyingFakePilotRunner`(defect 전달)로 교정 필요 | R2FIX11 | R2 재개 전 |
| B61 | RESOLVED | 회귀 실패 이름 유실 방지: `.coord/runs/run_regression.py`가 전체 회귀를 `-v`로 돌려 `.work/logs/regression-<타임스탬프>.log`에 전문을 남기고 FAIL·ERROR 이름만 요약 출력한다. 이후 회귀는 이 진입점을 쓴다 | 2026-09-20 회귀 | — |
| B62 | RESOLVED | 승인 화이트리스트(전역 룰 v5.6.0): Claude 가드로 직접 편집이 불가능한 항목을 로컬 Ollama 작업자가 pilot(WL03)에서 작성·인수 통과 → 승인 반영 → 두 도구 배포 ALIGNED → 원격 push. 로컬 모델의 첫 실사용 성공 사례 | 2026-09-20 | — |
| B63 | RESOLVED | Windows 잠금 경합에서 `PermissionError`가 `coord/stream._exclusive` 밖으로 샘(삭제 대기 중 잠금 파일 열기). 8프로세스×300회 프로세스당 3~11건 → 0건. `tests/test_u15_lock_contention.py`(6프로세스, 수정 전 실패·후 통과). olla 사용 기록 병렬 테스트가 199/200으로 발견 |
| B64 | RESOLVED (Claude 대행, Codex 재검토 대상) | U11 STOP 후 자식 exit 1: 회귀 로그 스택 `serve_forever → drain(timeout=max(0.1, 남은 기한)) → DISPATCHER_STOP_TIMEOUT`. 작업자 대기로 기한을 다 쓰면 SQLite close에 0.1초만 남음. `DRAIN_FLOOR_S=2.0` 최소 정리 시간 부여. 부하 재현 0/47로 드물어 느린 close를 주입한 결정적 테스트(`tests/test_b64_broker_drain_budget.py`, 옛 식 재현·새 식 통과) |
| B65 | OPEN | 출력 규칙(진행 설명 0, 보고 3줄) 위반 실측: Claude 최근 11턴 진행 설명 0~9개(규칙 준수 5/11), Codex 최근 5턴 2~33개(0/5). Antigravity 기록 위치 UNKNOWN. 대책: 매 턴 지시 직후 `olla hook-plan`에 출력 규칙 한 줄, Stop 훅 `olla hook-stop`이 턴마다 기록 → `olla stats`의 turns_within_rule로 추적 추적(9/22 02:10~11:37, Claude 11턴): 매 턴 주입 이후 진행 설명 5턴 1~3개 → 이후 7턴 연속 0개. 최종 보고 5줄 초과는 11턴 중 5턴(최대 10줄)으로 남은 과제 |
| B66 | RESOLVED | Biz항해 세션(9/22 16:07~16:25 실측): 도구 호출 87건 중 olla 0건, 3천 토큰 넘는 통째 읽기 2건(약 12만 토큰) 모두 읽기 알림 0건. 원인: 훅이 stdin을 cp949로 읽어 한글 경로가 깨져 파일을 못 찾고 침묵. `_stdin_text()`로 UTF-8 고정, 실제 프로세스 바이트 테스트(수정 전 실패·후 통과). 작업 시작 알림은 1회 도착했으나 사용으로 이어지지 않음 → 재측정 필요. 자료 `.coord/runs/U17/biz_session_olla_audit.json` |
| B67 | RESOLVED | 읽기 훅 강화: 알림만으로는 사용 0건(B66) → 캐시된 요약본(질문 없음)을 훅이 그 자리에서 건넴(cli.py 8,466토큰 → 약 680토큰), 없으면 낮은 우선순위로 뒤에서 만들어 둠(15분 중복 방지). 요약 중 전체 회귀의 30초 예산 테스트가 30.6초로 1회 넘침(단독 3/3 통과) → BELOW_NORMAL 우선순위. 기록에 세션 번호 추가 |
| B68 | RESOLVED | Biz항해 세션 보고가 길었던 원인: 작업 위치가 260자를 넘어 Stop 훅이 `ENOENT uv_spawn bash.exe`로 실행 실패(길이 제한 미작동). 규칙 v5.20.0: 셸은 프로젝트 루트·절대 경로. Stop 훅은 줄 수 외에 글자(600자)·하위 목록도 판정. 도구 간 통신(브리핑·전달 문구) 영어화 |
| B69 | RESOLVED | 반복 오류 전수 대책: (1) 올라마 미사용 → 매 지시에 세션 성적(olla 사용·큰 읽기·보고 위반) 되비춤 (2) 긴 보고 → Stop 훅 줄·글자·중첩 판정(B68) (3) 깊은 cd로 셸·훅 정지 → PreToolUse `olla hook-bash`가 200자 넘는 cd 거부 (4) 시험의 실제 상태 오염 3회 → 회귀 실행기가 격리 공간(OLLA_USAGE·OLLA_CACHE)에서 돌리고 스트림 변경 시 실패 (5) heredoc 소스 파손 5회 → Edit·Write만 (6) 사용자에게 일 넘김 → 복귀 후 일은 PLAN으로 |
