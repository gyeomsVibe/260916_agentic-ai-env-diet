# [U09] 구현 설계 통일

- Status: DONE
- Owner: Codex
- Conversation: [U09] 구현 설계 통일
- Depends on: U08
- Started at: 2026-09-17
- Scope: 사용자 요구 R01~R26, 프로젝트 정본, U08 인계, docs/11·12 참고안을 공식 문서·로컬 실측과 대조해 단일 v9 구현 설계 및 후속 구현 단계 후보를 작성
- Excludes: 구현 코드, git init/commit, 전역 설정 수정, 삭제, push, 배포, 결제, 계정·권한·자격증명 변경
- Outcome: 잘못된 구현 가정을 제거하고 권위·상태·격리·복구·측정 계약을 하나로 통일한 실행 가능한 v9 설계서
- Acceptance: 요청된 필수 설계 산출과 레드팀 15개 항목, R01~R26 추적표, 공식/로컬/미검증 구분, 단계별 구현·테스트 계획을 모두 포함하며 비용 절감은 `UNMEASURED`로 유지
- Verification: 문서 구조·요구 추적·링크·로컬 CLI help·상충 결정·금지 작업 미수행 여부를 재현 가능한 검사와 종료 코드로 기록

## Decisions

- `docs/01_unified-agent-orchestration-design.md`는 현 프로젝트 운영 정본으로 유지한다.
- `docs/11`, `docs/12`는 참고 입력이며 사용자 원문·플랫폼/프로젝트 규칙·로컬 실측·공식 1차 근거보다 우선하지 않는다.
- U08의 SQLite/MCP 후보를 포함한 모든 구현 결정을 U09 Decision Gate에서 재검토한다.

## Work log

- 2026-09-17: 정본 규칙, 사용자 원문, U08 보고서·카드, docs/11·12, PLAN을 읽고 U09을 `ACTIVE`로 점유했다. 현재 프로젝트가 비Git임을 확인했으며 승인 대상 행동 없이 설계 문서와 카드만 작성한다.
- 2026-09-17: 공식 SQLite, Google Antigravity, OpenAI Codex/Agents/Symphony 자료와 로컬 `codex-cli 0.154.0`, `agy 1.2.4 --help`를 대조했다. GitHub 이슈는 open/closed와 영향 버전을 분리했고 Reddit은 운영 사례 보조로만 제한했다.
- 2026-09-17: CRITIC/SELFREFINE/REDTEAM/STEPBYSTEP/OPTIMIZE 게이트를 적용했다. DB/계획 권위 충돌, 단일 writer 모순, 비Git 사후 diff, 자동 재개 외부 효과, JSONL 동일 failure domain, headless 과권한, 재귀 위임, runtime resource 충돌을 수정하고 Decision Log에 남겼다.
- 2026-09-17: v9 설계서와 카드만 작성했으며 구현, 후속 카드 생성, git init, 전역 수정, 삭제, push, 배포를 수행하지 않고 `REVIEW`로 반환한다.

## Handoff

- Result: `docs/13_U09_unified-implementation-design_v9_2026-09-17.md`에 Authority Matrix, managed/standalone/imported, broker/Named Pipe+SQLite 단일 writer 결정, schema/invariants/state machine, Windows crash recovery, Git/nonGit isolation/promotion, retry/circuit/quota, threat model, byte/token/schema budget, migration/rollback, U10~U17 후보 계획, fault/측정 계획, R01~R26 추적, 미검증 목록, Claude 지시 처리표와 Go/Pivot/No-Go를 통합했다.
- Changed: `docs/13_U09_unified-implementation-design_v9_2026-09-17.md` 신규, 이 카드 신규/상태 갱신, `.coord/PLAN.md` U09 상태·재개 지점 갱신. 구현·전역·참조 프로젝트는 미변경.
- Checks and exit codes:
  - `codex --version`, `codex --help` -> exit 0 (`codex-cli 0.154.0`; sandbox/worktree/add-dir 의미 확인)
  - `agy --version`, `agy --help`, `agy -p --help` -> exit 0 (`1.2.4`; sandbox/add-dir/dangerous flag/headless 계약 확인)
  - 필수 19개 섹션·R01~R26 정적 검사 -> exit 0 (`missing_sections=` 빈값, `trace_count=26`)
  - `python -m unittest discover -s tests -p "test_*.py"` -> exit 0 (37 tests)
  - `python -m compileall -q v7_harness tests` -> exit 0
  - `git status --short` -> exit 128 (예상된 비Git 프로젝트; git init 미실행)
- Remaining risks: Antigravity 1.2.4 Windows sandbox/headless permission 실제 동작, Named Pipe ACL/Job Object, 비Git binary/junction/ACL promotion, provider effect reconciliation, 사용량 API, broker 성능과 절감률은 `UNKNOWN` 또는 `UNMEASURED`다. 구현 전 각 후보 단계의 fixture/canary가 필요하다.
- Next action: 조율자가 v9 문서와 이 카드의 증거를 독립 검토해 U09을 `DONE` 또는 같은 U09의 `READY` 재작업으로 판정한다. 통과 후에만 U10 capability·schema contract 카드를 제안 범위에서 생성한다.

## Review

- Verdict: PASS
- Reviewed at: 2026-09-17
- Review note: R01~R26 추적 26/26, Authority Matrix, 단일 writer topology, 동적 resource lease, 비Git staging/promotion, UNKNOWN effect 재시도 금지, 승인 경계, fault/측정 계획을 독립 확인했다. 구현 전 검증이 필요한 항목은 UNKNOWN/UNMEASURED로 분리돼 있으므로 U10 계약 단계로 진행한다.
