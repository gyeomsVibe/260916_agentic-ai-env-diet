# [U25] 작업별 토큰예산 예측과 품질 보존

- 상태: DONE (2026-09-24, 문서·운영 규칙 범위; Codex 증거 판정)
- 사용자 목표: Codex·Claude의 한도 소모를 작업 전에 예상하고, 품질 저하 없이 Ollama·Antigravity를 배치하며 실사용 데이터로 명령 구조를 개선한다.
- 허용 파일: `docs/27`~`docs/30`, `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `docs/01`, `README.md`, 이 카드와 `.coord/PLAN.md`. 참조 프로젝트 5개는 읽기 전용.
- 비목표: 계정·권한·시스템 설정 변경, 사용량 한도 리셋, 배포, 원격 push, U23 코드 수정, 미검증 절감률 공표.
- 인수: Codex·Claude·Antigravity 진입 규칙이 같은 정본을 가리킴; 각 매뉴얼에 실행 계약·예산/품질 게이트·동일 작업 ID의 데이터가 있음; 이 작업의 문서 링크와 변경 경로의 공백 검사가 통과; 기존 파일 변경은 별도 섹션/링크로 국한.
- 증거: 작업 전 git status의 기존 변경은 보존. 공식 OpenAI/Anthropic 사용량 문서와 5개 참조 프로젝트의 현행/퇴역 자료를 대조. Ollama `olla ask` 1회 입력 2,303/출력 82 로컬 토큰, exit 0; docs/26의 수치 4개 원문 일치. `git diff --check -- .coord/PLAN.md AGENTS.md README.md docs/01_unified-agent-orchestration-design.md` exit 0, 새 문서 후행 공백 검사 exit 0, 6개 문서의 로컬 링크 검사 exit 0. 전체 `git diff --check`는 이 작업 밖의 `.coord/codex_return_checklist.md:23` 후행 빈 줄 때문에 exit 1이므로 이 카드의 통과 근거로 쓰지 않는다.
- 위험: U23 무손실·감시관 반복 실행 반례가 미해결. 계정 사용량 절감과 예측 정확도는 아직 `UNMEASURED`다. Claude·Antigravity 현재 계정 잔여율은 `UNKNOWN`.
- 독립 검토: Antigravity가 `.coord/mailbox/inbox/u25_review_u23_fix.json`에 8개 경로의 링크 0건 오류와 불변식 준수 `PASS`를 보고했다. 이 보고는 단독 판정 근거가 아니며 Codex의 변경 경로 공백 검사·로컬 링크 검사·정본 대조와 함께 문서 범위만 인수했다.
- 판정 경계: 실사용 절감·예측 정확도는 `UNMEASURED`; U23 코드와 알림 전달 보증은 인수하지 않았다. U23 재작업은 별도 카드·단일 작성자·독립 반례 인수로 진행한다.
