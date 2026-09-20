# [U08] 전역 AI 환경 감사·최적화

- Status: DONE
- Owner: Codex
- Conversation: [U08] 전역 AI 환경 감사·최적화
- Depends on: U07
- Started at: 2026-09-17
- Scope: Codex/Antigravity 전역 규칙·skills·memory·vibe 진단·MCP 인벤토리, 충돌·중복·비용 감사, 2026-09-16 기준 공식자료·공개 GitHub·Reddit 조사, 로컬 참조 프로젝트와 Git 이력 비교, 역할·권한·인계·실패·독립 실행 계약, scoped lease·격리·예산 라우팅·회로 차단기 설계, 가역적 정리 제안
- Excludes: Claude Code 감사·설계·변경, 삭제 실행, 설치, 덮어쓰기, push, 배포, 결제, 계정·권한·자격증명 변경, 승인 게이트 우회, U07 구현 변경
- Outcome: 사실·추론·미확인을 구분한 전역 환경 감사와 최소 역할 계약·예산 라우터·가역적 최적화안. 삭제 후보는 정확한 대상·근거·롤백·검증을 기록하되 실행하지 않는다.
- Acceptance: 아래 Decisions의 모든 연구 질문에 공식/로컬/커뮤니티 증거 등급을 부여하고, 성과·완료율·정확도·비용·지연의 측정 계획과 중단 조건, 반증표, 최소 계약안, 미검증 주장 목록, 삭제 없는 적용 순서를 제시한다.
- Verification: 로컬 경로·Git 객체·비민감 설정의 읽기 검증, 공식 링크 유효성, 주장-근거 매트릭스, 중복 규칙 diff, MCP 인벤토리, Ollama 실측 판정, 역할/충돌/쿼터 실패 시나리오를 재현 가능한 명령과 종료 코드로 기록한다.

## Decisions

- Codex는 managed context의 Planner/Commander/Verifier, Antigravity는 위임 범위의 Executor로 정의한다. 사용자의 강한 위임 의도는 보존하되 기계 규칙에서는 오해 없는 역할·권한 용어를 쓴다. standalone 모드는 별도 계약으로 분리한다.
- `c3p 협의체의 예산절약` 로직은 `260823_codex-3p-orchestrator`의 정확한 로컬 출처와 공개 근거를 확인하고, `260912_multi-party-ai-agent-real-time-orchestration-mcp`의 구현·Git 이력과 2026-09-16 기준 공식자료·GitHub·Reddit을 비교한다. 출처 없는 명칭·수치는 `UNVERIFIED`다.
- 예산 라우터는 성과·완료율·정확도·비용·지연을 함께 측정하고 중단 조건을 둔다. Step-by-step, Deep-dive, Red-team, Self-refine, Optimize, Critic 관점은 복제 스킬이 아니라 반증표와 최소 계약 검토 렌즈로만 사용한다.
- Codex 시작 시 `antigravity-bridge` 자동 연결 가능성과 실패/쿼터 폴백을 실측한다. Antigravity 2.0/IDE standalone에서 필요 시 Codex 호출 지원 여부와 `Codex=Security & Skeleton, Antigravity=Multi-agent Orchestration` 주장은 공식 문서·실측 전까지 미검증이다.
- `shared-specs.md`와 `AGENTS-CONSENSUS.md` 후보의 중복을 평가하고 단일 원본을 설계한다. 대화창이 아니라 worktree/branch를 쓰기 격리 경계로 취급하며 파일·DB·포트·브랜치를 scoped lease에 포함한다.
- 병렬 실행은 독립성 검사를 통과할 때만 허용하고 기본은 순차 단일 소유자다. Planning 모드와 사용자 승인 요구는 정상 실행의 무승인 원칙을 훼손하지 않는 범위에서 기계 검증 게이트로 대체 가능한지 평가한다.
- Antigravity 쿼터 저하·소진 시 신규 위임 차단, 활성 작업 체크포인트, Codex 단독 재계획으로 이어지는 회로 차단기를 설계한다.
- Ollama 유지/삭제는 실제 상주 자원·호출 경로·대체 가치로 판정한다. 삭제는 이 단계에서 실행하지 않는다.
- 공개 근거 후보에는 Google Antigravity 공식 overview/product/codelab, `openai/symphony` SPEC, agent-permissions, orchestrated-coding SPEC, Reddit의 worktree/merge-train/ledger 운용 사례를 포함하되 실제 확인된 내용만 사실로 기록한다.

## Work log

- 2026-09-17: U07 검증 게이트 통과 후 사용자 추가 지시를 병합해 `READY` 카드로 등록했다. 아직 실행하지 않았다.
- 2026-09-17: `[U08]` 전용 대화창에서 정본 규칙·U07 증거·U08 범위를 확인하고 Codex가 `ACTIVE`로 점유했다. 프로젝트 루트가 비Git임을 재확인했으며, 승인 대상 변경 없이 읽기 감사와 가역적 로컬 산출물 작성으로 진행한다.
- 2026-09-17: MIA Frame/Review/Execute/Verify와 DEEPDIVE/REDTEAM/OPTIMIZE로 전역 rules·skills·memory·vibe/MCP, 두 참조 프로젝트, bridge 구현, agy/Ollama 런타임, 공식 자료를 감사했다.
- 2026-09-17: 사용자 추가 결정을 반영해 MCP 중심안 대신 단일 로컬 머신의 SQLite durable coordination plane을 우선안으로 선택했다. 후보 schema와 원자적 claim/renew/complete, idempotency/fencing, backup/recovery, Codex-only fallback, 24개 장애주입 시나리오를 설계하고 임시 DB에서 DDL 스모크를 통과했다.
- 2026-09-17: 전역 파일·참조 저장소·bridge 구현은 변경하지 않고 보고서와 review-only SQL 후보만 추가한 뒤 `REVIEW`로 반환한다.
- 2026-09-17: REVIEW 보완으로 A=MCP 브리지 보강, B=SQLite+coordctl 완전 대체, C=SQLite durable control plane+선택적 MCP transport를 12개 동일 평가축으로 비교했다. 공식 MCP lifecycle/transports/authorization와 SQLite transaction/WAL 근거를 대조해 C를 56/60 `GO`로 확정했다. SQLite+coordctl이 유일한 권위 상태이며 MCP는 필요 시 외부 tool adapter로만 사용한다.

## Handoff

- Result: 물리 연결 실패 0% 대신 증거 손실·중복 부작용·false success 0건을 목표로 하는 연속 실행 계약을 설계했다. Decision Gate는 C(SQLite durable control plane+선택적 MCP transport) 56/60 `GO`, B(SQLite+coordctl 완전 대체) 50/60 보류, A(MCP 브리지 보강) 40/60 탈락이다. SQLite+coordctl이 유일한 권위 상태 원장이고 antigravity-bridge는 필요 시 DB adapter/worker launcher로만 쓴다. C3P 예산절약은 로컬 내부 명칭이고 85% 절감은 `UNVERIFIED`; 비용·토큰 절감은 `UNMEASURED`. Ollama는 command/process/port가 없어 현재 `NO-GO NOW`다.
- Changed: `docs/09_U08_global-continuity-contract_2026-09-17.md` 신규, `proposals/u08-sqlite-coordination-schema.sql` 신규, 이 카드와 `.coord/PLAN.md` 상태 갱신. 전역 설정·bridge·두 참조 저장소는 미변경.
- Checks and exit codes:
  - `git status --short --branch` (현재 프로젝트) -> exit 128, 비Git 제약 확인
  - `python -m unittest discover -s tests -p "test_*.py"` -> exit 0 (37 tests)
  - `python -m compileall -q v7_harness tests` -> exit 0
  - `python -m v7_harness.cli snapshot` -> exit 0 (`NON_GIT`, 보고서 포함 manifest)
  - `node --check .../mcp/antigravity-bridge/index.js` -> exit 0
  - `npm test --if-present` (bridge) -> exit 0; 실제 test script는 없고 command no-op
  - `agy --version`, `agy agents`, `agy models` -> 각각 exit 0; v1.2.4와 모델 목록 확인
  - Ollama command/process/11434 확인 -> command missing, process absent, port not listening
  - U08 문서 필수 섹션·경로·로컬 링크 검사 -> exit 0
  - SQLite schema 1차 smoke -> exit 1 (fixture의 agents INSERT 값 개수 오류; 연결 미종료로 임시파일 정리 경고 연쇄)
  - SQLite schema 수정 smoke -> exit 0 (`WAL`, foreign_keys=1, synchronous=FULL, busy_timeout=5000, stale fence update 0행, duplicate blocked, events append-only, integrity_check=ok, FK 위반 0)
- Remaining risks: 실제 bridge 위임·재연결·quota 오류와 480회 장애주입은 `UNKNOWN`; 비용 절감은 `UNMEASURED`; SQLite 후보는 배포 전 별도 구현 단계와 로컬 ACL/backup/복구 canary가 필요하다. `260718` 전역 규칙 저장소에는 기존 미확인 수정 5개, `260912`에는 전체 삭제 표시가 있어 모두 보존했다. 스모크가 만든 임시 DB는 Python 임시 디렉터리에서 정상 정리됐으며 첫 실패의 임시파일도 컨텍스트 종료 뒤 OS 정리 대상이다.
- Next action: 조율자가 보고서·후보 DDL·검증 증거를 독립 검토해 `DONE` 또는 같은 U08의 `READY` 재작업을 결정한다. 구현 시 SQLite core를 별도 단계로 열고 mock 장애주입부터 시작한다.

## Review

- Verdict: PASS
- Reviewed at: 2026-09-17
- Review note: U08의 인수 조건인 전역 환경 감사, 근거 등급, 역할·오류·예산 계약 후보, SQLite/MCP 비교, 장애주입 계획, 삭제 없는 적용 순서를 충족했다. 구현 선택과 수치는 아직 검증 전이므로 U09에서 재검토하며, U08 보고서의 후보 결정을 곧바로 전역 규칙이나 런타임에 적용하지 않는다.
