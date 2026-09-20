# Unified Codex–Antigravity Execution

이 프로젝트의 모든 작업은 [`docs/01_unified-agent-orchestration-design.md`](docs/01_unified-agent-orchestration-design.md)를 단일 원본으로 따른다.

## 고정 규칙

- Codex는 프로젝트 조율자이며 하나의 마스터 계획, 작업 순서, 승인 게이트를 관리한다.
- 실제 수행은 프로젝트 안의 단계별 전용 대화창에서만 한다. 사용자 지시창이나 총괄 대화창에서 구현을 대신하지 않는다.
- 각 수행 단계에는 대화창 하나와 단일 소유자 한 명만 둔다. Antigravity가 수행할 때도 Codex 프로젝트의 해당 단계 전용 대화창을 맡은 실행자로 취급한다.
- 단계 대화창 제목은 짧은 접두어 `[U##]`로 시작한다. `##`는 마스터 계획의 두 자리 순번이다. 예: `[U03] 인증 오류 수정`.
- 활성 단계는 기본적으로 하나다. 선행 단계가 검증 게이트를 통과한 뒤 다음 단계를 연다.
- 두 도구가 같은 단계, 파일 범위, 브랜치, 작업트리, 데이터베이스, 포트 또는 외부 자원을 동시에 수정하지 않는다.
- 모든 인계는 말로만 하지 않고 해당 작업 카드에 결과, 변경 범위, 검증 증거, 미해결 위험, 다음 행동을 기록한다.
- 완료 보고만으로 완료 처리하지 않는다. 검토자가 인수 조건과 검증 증거를 확인한 뒤 `DONE`으로 전환한다.
- 컨텍스트는 현재 목표·승인 경계·활성 카드와 직접 의존 자료만 로딩한다. 오래된 문서·로그·폐기 결정은 권위와 유효성을 확인하기 전에는 규칙으로 사용하지 않는다.
- 사용자 보고는 결과·변경·검증·위험·다음 자동 행동만 간결하게 제시하고 상세 증거는 카드나 산출물에 보존한다.
- 사용자가 해야 할 일이 없으면 질문하지 않고 다음 `READY` 단계를 자동 진행한다. 목표·범위 변경과 명시적 승인 대상만 사용자에게 묻는다.
- 삭제, 덮어쓰기, 배포, 푸시, 결제, 계정·권한·자격증명 변경은 사용자에게 그 행동별 명시적 승인을 받는다.
- 구현·수정 작업은 Antigravity에 SQLite 경로로 위임한다: `python -m v7_harness.cli pilot run --task <ID> --source <dir> --prompt-file <md> --accept-cmd "<인수 테스트>" --work-dir .coord/pilot`
- 작업자는 둘이다. `--worker agy`(원격, 계정 한도 소모)와 `--worker local`(이 PC의 Ollama, 한도 없음). Codex가 과제마다 고른다. 고르는 기준: **무엇을 어디서 어떻게 바꿀지 프롬프트에 줄 단위로 적을 수 있고, 대상 파일이 소수이며, 합격 기준이 기계적으로 검사 가능하면 `local`**. 설계 판단·탐색·다파일 리팩터가 필요하면 `agy`. 원격 작업자가 `QUOTA`로 막히면 같은 과제를 `local`로 1회 재시도하고 그 사실을 기록한다. 어느 쪽이든 판정은 동일한 인수 게이트가 한다(`docs/ollama/README.md` §7-1).
- 비용 절감 위임의 기본 경로는 `Codex 작업 계약 1회 → 결정적 control layer → Antigravity pilot → Codex 증거 판정 1회`로 한다. 토큰 대리지표와 실제 계정 사용 한도 절감은 구분하고, 후자는 직접 측정 전까지 `UNMEASURED`로 기록한다.
- Antigravity IDE와 Claude Code는 원본 구현·인수 테스트를 직접 수정하지 않고 읽기 전용 자문·독립 검증만 수행한다. 구현과 인수 기준 변경은 SQLite `pilot run` 산출물과 Codex 재검토를 거쳐야 한다.
- `pilot run` 또는 control layer 실행 중에는 source 원본을 단일 쓰기 소유자에게만 맡기고, relay·상태 점검·자문 메모를 포함한 보조 프로세스는 원본에 쓰지 않는다. 보조 산출물은 `.work/`에 기록하며 원본 변경이 감지되면 `SOURCE_DIVERGED`로 차단하고 작성자를 식별한 뒤 새 실행으로 검증한다.
- pilot 소유자는 실행 직전에 `.work/QUIET_LOCK`을 원자적으로 만들고 `owner`, `task`, `started_at`, `pid`를 기록한다. 유효한 lock이 있으면 새 실행과 원본 쓰기를 시작하지 않으며, 모든 보조 기록은 `.work/notes/`에 둔다. 소유자는 종료 후 lock을 정리하고, PID가 없거나 60분을 넘긴 고착 lock만 Codex가 해제 사실을 기록한 뒤 정리한다.
- **`.coord/PLAN.md` 무승인 영구 권한(사용자 부여, 2026-09-19)**: Codex·Antigravity·Claude Code는 `.coord/PLAN.md`(및 `.coord/tasks/*` 카드)를 사용자 승인 없이 읽고 갱신할 수 있다. 권한 부족으로 쓰지 못하면 승인을 묻지 말고 파일 속성·잠금을 확인해 해소하거나 조율자에게 즉시 보고한다. 단, 22행 규칙에 따라 pilot·control 실행 중에는 쓰지 않고 실행이 끝난 뒤 갱신한다.
- 비용 측정의 품질 게이트는 control receipt만 신뢰하지 않는다. 드라이버가 실행 전후 source manifest를 독립 비교해 기대 변경 집합과 일치함을 확인하고 숨은 인수를 직접 통과한 경우에만 측정값을 유효로 판정한다.
- Codex는 `pilot run`을 블로킹 1회로 실행하고 대기 폴링을 반복하지 않는다. 결과는 `.coord/pilot/runs/<ID>/summary.json`(14키)의 `verdict_hint`로 1턴에 판정한다(PASS만 `--approve`, REWORK·BLOCKED는 원인만 보고). 전문 로그는 필요할 때만 연다.
- 중단 등으로 원장에 미정리 작업이 남아 `NEEDS_RECONCILIATION`이면 재실행 전에 `python -m v7_harness.cli pilot reconcile --task <ID> --work-dir .coord/pilot`로 정리한다.
- 변경이 없는 결과는 `REWORK`(`NO_CHANGES`)로 판정된다. 읽기 전용 과제만 `--allow-no-changes`를 붙인다.
- 반영은 같은 task에 `--approve <bundle_id>`로만 한다. `promotion`이 `BLOCKED`·`REJECTED`면 반영하지 않고 원인만 보고한다.
- Antigravity Bridge MCP는 조회·자문을 포함해 사용하지 않는다. Antigravity 작업은 CLI 기반 SQLite `pilot run`을 사용하고 읽기 전용 과제에는 `--allow-no-changes`를 지정한다.
- **워크스페이스 단일 폴더 규칙(사용자 고정 지시, 2026-09-19)**: 전체 로컬 워크스페이스(`D:\D_Workspace_NB\-agentic-ai-workspace`)에는 이 프로젝트 폴더 `260916_agentic-ai-env-diet` 하나만 둔다. 샘플 사본·pilot `--work-dir`·측정용 복사본·임시 산출물은 모두 프로젝트 안 `.work/<이름>`에 만든다(예: `--work-dir .work/pilot_T01`). 워크스페이스 최상위에 형제 폴더를 만들지 않는다. `.work/`와 `.coord/pilot`은 manifest·staging에서 제외되므로 프로젝트 자신을 `--source .`로 써도 안전하다.
- 격리는 설정된 감시 루트(watch roots) 내부에서만 보증되며, 탐지 범위 밖 경로는 보증하지 않는다.

## 최소 실행 루프

1. Codex가 마스터 계획에서 다음 `READY` 단계 하나를 선택한다.
2. `[U##]` 전용 대화창을 만들고 단일 소유자와 수정 범위를 기록한다.
3. 소유자가 단계를 `ACTIVE`로 점유한 뒤 범위 안에서만 수행한다.
4. 소유자가 검증 결과와 인계 기록을 남기고 `REVIEW`로 반환한다.
5. Codex가 증거를 재검토해 `DONE`, `READY` 재작업, 또는 `BLOCKED`를 결정한다.
6. `DONE`일 때만 다음 순번을 활성화한다.

규칙 원문과 상태·카드 형식은 설계 문서를 참조하고, 도구별 규칙에 별도의 상충 사본을 만들지 않는다.
