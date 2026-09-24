# [U26] UAOS 증거 관문형 RSI 연구·운영 규칙

- 상태: DONE (2026-09-24, Antigravity 권한대행 독립 검토 통과 및 수동 장부 부트스트랩 완료)
- 목표: 전체 UAOS와 Codex·Claude·Antigravity·Ollama의 실행 기록을 검증 가능한 작은 개선 사이클에 연결한다.
- 허용 파일: `docs/31_evidence-gated-rsi-for-uaos.md`, `.coord/usage/*`, `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `docs/01`, `docs/27`~`docs/30`, `README.md`, 이 카드와 `.coord/PLAN.md`. 코드·테스트 수정은 U27로 분리한다.
- 고정 인수: 문헌 찬반을 함께 제시; 자기평가 단독 승격 금지; 4도구 권한 경계와 동일 작업 ID의 사용량 필드가 연결됨; 비밀·계정 백분율과 로컬 토큰을 혼동하지 않음; U23/R1 잔여를 완료로 숨기지 않음; 파일 링크·JSONL 문법·변경 경로 공백 검사 통과.
- 연구 근거: Reflexion, Self-Refine, 자기수정 비판적 조사, OpenAI 평가 지침, METR 보상 편법/코드 품질, Google Antigravity 산출물, Ollama API, Claude 사용량 공식 문서를 실제 열람. 상세 링크는 `docs/31`에 둔다.
- 로컬 사용 기록: `olla ask -f docs/26_ollama_real_usage_dossier.md` 한정 추출 1회, 입력 2,289/출력 74 로컬 토큰, 21.57초, exit 0; 원문 372·139,250·60,883·200,133 일치. 장부의 세 번째 행인 Antigravity U25 검토는 토큰/시간 미측정으로 null이다.
- 위험: U27 자동 계측 전에는 수동 장부에 의존하며 실제 계정 절감은 `UNMEASURED`. U23 재작업과 R1 측정은 별도 미완료.
- Antigravity 독립 읽기 전용 검토: `U26_RSI_REVIEW1`, source `.work/u26_rsi_review/source`, 원격 1회, 약 78.50초, 입력 54,379·출력 19,937·총 74,316토큰, 변경 0. 영수증 `DRY_RUN_PASSED`/`NEEDS_ACCEPTANCE`/`acceptance_exit=null`이다. 응답은 PASS라 했지만 분모 조작 가능성, 모델·검증자 누락, 인수 해시 미기록, Windows 동시 append, 비용 null 완료 표기 5건을 제시했다. Codex는 자기 PASS를 채택하지 않고 앞의 2건을 정책·장부 규칙에 보강했다. 이 호출은 비용이 큰 검토 사례로 장부에 남긴다.
- 미해결 검토: U26의 고정 인수 SHA는 검토 전 봉인되지 않았으므로 사후 해시를 사전 고정 증거라고 주장하지 않는다. U27에서 인수 스크립트와 해시를 실행 전에 고정한다. 초기 v1 수동 기록은 유효 RSI 비교 표본에서 제외하되 원본 감사 집계에는 남긴다.
- 다음: 문서 링크·JSONL v2 규칙·변경 경로 검사 → U26 문서 범위 판정 → U27 자동 계측·병렬 append·비밀 차단의 작은 pilot 계약. 프로젝트 전체 `DONE` 선언 금지.
