# [U06] 기사 인사이트 기반 v7 설계

- Status: DONE
- Owner: Codex
- Conversation: [U06] 기사 인사이트 기반 v7 설계
- Depends on: U05
- Scope: 기사 원문·GeekNews 요약·관련 연구를 분석해 컨텍스트, 의도, 검증, 보고, 자동 진행 규칙으로 정제
- Excludes: 런타임 구현, 전역 설정 수정, 삭제, 설치, 배포
- Outcome: 비전문 사용자용 HTML 보고서와 프로젝트 정본 규칙 보강
- Acceptance: 기사 핵심·반대 근거·unknown unknowns·우리 설계 적용·출처·간결 보고·자동 진행 규칙 포함
- Verification: HTML 구문/링크/렌더링 확인, 정본 규칙과 어댑터 문구 일치 확인

## Decisions

- 코드 전수 읽기와 무검증 위임 사이에서 위험 기반 proof ladder를 채택한다.
- 컨텍스트는 계층화하고 오래된 자료에는 context lease를 적용한다.
- 사용자에게 다음 작업을 전가하지 않고 정상 단계는 자동 진행한다.

## Work log

- 원문, GeekNews 실제 토픽 33735, 인지·의도 부채 연구, StrongDM 사례, 자동화 역설을 교차 분석했다.
- HTML 보고서와 프로젝트 정본의 컨텍스트·보고·자동 진행 규칙을 작성했다.

## Handoff

- Result: 기사 인사이트를 v7의 context lease, intent ledger, proof ladder, output budget으로 변환했다.
- Changed: `docs/08_U06_article-insights-v7-design_2026-09-17.html`, `docs/01_unified-agent-orchestration-design.md`, `AGENTS.md`, 본 카드.
- Checks and exit codes: Python `HTMLParser` exit 0; 필수 섹션·출처 검색 exit 0; Edge desktop render exit 0; 격리 프로필 모바일 에뮬레이션 render exit 0; 첫 모바일 캡처는 기존 브라우저 세션 충돌로 파일 미생성 후 격리 프로필로 복구.
- Remaining risks: 실제 효율 향상은 U08 A/B 전까지 `UNMEASURED`.
- Next action: 검토 통과 후 U07 최소 자동화 구현.

## Review

- Verdict: PASS
- Evidence: HTML 17KB 이상, 10개 본문 구역과 5개 근거 링크, 데스크톱·좁은 화면 렌더링에서 잘림 없는 반응형 레이아웃 확인.
- Rule alignment: `docs/01_unified-agent-orchestration-design.md`가 정본이며 `AGENTS.md`에는 발견용 최소 규칙만 추가했다.
- Efficiency status: 기사 기반 개선은 설계 가설이며 실제 절감률은 `UNMEASURED`로 유지한다.
