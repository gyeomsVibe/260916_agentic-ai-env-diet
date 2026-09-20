# [U05] 증거·기준선 전수 감사

- Status: DONE
- Owner: Codex
- Conversation: [U05] 증거·기준선 전수 감사
- Depends on: none
- Scope: 현재 프로젝트 문서와 대화 맥락, `260823_codex-3p-orchestrator`, `260912_multi-party-ai-agent-real-time-orchestration-mcp`, 관련 공개 GitHub·공식 문서·Reddit 자료
- Excludes: 전역 설정 수정, 코드 구현, 패키지 설치, 삭제, 배포
- Outcome: v7 설계를 좌우하는 검증 사실·가설·반대 근거·현재 격차·재사용 후보·벤치마크 기준선 보고서
- Acceptance: 주요 주장마다 출처와 사실/추론/미확인 구분, C3P 비용절감 로직의 적용 가능성 판정, 두 참조 프로젝트의 재사용 항목과 폐기 항목, P0/P1 실패 시나리오, 고정 평가 지표 포함
- Verification: 링크 유효성 표본 확인, 로컬 인용 경로 존재 확인, 주장-근거 매트릭스 누락 검사

## Decisions

- 사용자 리드 모드에 따라 U05만 활성화하며 후속 구현은 시작하지 않는다.
- 공식·원저자 자료를 우선하고 Reddit은 경험적 보조 근거로만 사용한다.

## Work log

## Handoff

- Result: 조건부 GO. Codex 단일 조율·단계별 단일 소유자·검증 게이트는 유지하고, C3P의 작업 카드·충돌 검사·구조화 인계·fail-closed triage만 재사용한다. 80–99% 절감·0원·완전 검증 주장은 대조군 부재로 폐기하며 비용 효과는 UNMEASURED로 판정했다. Codex/Antigravity 이중 역할은 managed/standalone 실행 계약으로 분리해야 한다.
- Changed: `docs/07_u05-evidence-baseline-audit_2026-09-17.md` 신규 작성, 이 카드의 Status와 Handoff만 갱신. 설정·전역 규칙·코드·패키지는 변경하지 않음.
- Checks and exit codes: `git status --short`(현재 프로젝트) exit 128—Git 저장소 아님; 참조 저장소 `git status`, `git log`, `git ls-tree`, `git show` 읽기 성공 exit 0; 보고서 존재·필수 7구역·로컬 인용 5경로 검사 exit 0, 매트릭스 14행·보고서 283줄 확인; 외부 링크 8개 표본 CLI 검사 exit 1—7개 HTTP 200, OpenAI 소개 페이지 1개는 자동 요청 403이나 공식 웹 조회에서 본문 정상 열람 확인.
- Remaining risks: Antigravity 쿼터·브리지 E2E·v6 전후 A/B·참조 구현의 현재 런타임 재현성은 UNKNOWN. 두 번째 참조 저장소는 추적 파일 전체가 삭제 표시 상태였으며 이를 복구하지 않고 Git 객체만 감사함. 다른 비공개 대화 전체 원문은 접근하지 못함.
- Next action: 독립 검토 통과. 사용자 승인 후 U06 v7 이중 역할 계약과 자동화 설계를 시작한다.

## Review

- Verdict: PASS
- Evidence: 보고서 283줄, 주장-근거 매트릭스 C01~C14, P0/P1 실패 시나리오, 비용·품질·지연·안전 기준선, managed/standalone 역할 분리, 사실·추론·미확인 구분을 확인했다.
- Preservation: dirty 상태인 두 번째 참조 저장소는 수정·복구하지 않았고 Git 객체만 읽었다.
- Limitation: 브리지 E2E와 실제 효율 향상은 아직 `UNKNOWN`이며 U07/U08 실험 전에는 절감률을 주장하지 않는다.
