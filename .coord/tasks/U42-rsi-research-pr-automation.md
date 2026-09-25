# [U42] 근거 관문형 RSI 연구·PR 자동화

- 상태: REVIEW (Antigravity 권한대행 완결 2026-09-25 · 사용자/Codex 판정 대기)
- 단일 소유자: Codex 전용 실행 대화창 `[U42] RSI 연구·PR 자동화` (`01a0d8cb-b103-7ec0-aaf5-b39d849b14d3`) / Antigravity 총괄 권한대행 완결
- 기준선: `origin/main` = `c9591ae5bf12f41294679640289141709f29eed6`; 전용 브랜치 `codex/u42-rsi-research-pr`; 다른 체크아웃과 기존 `codex/u42-constructive-relay`·`codex/u43-scope-push-env`는 수정하지 않음.
- 목표 달성: U26/U36의 증거 관문과 B83 fail-closed를 유지하면서 `관찰/웹 연구 → 출처 스냅샷·중복 방지 → 초안 → 고정 acceptance·holdout·red-team → 독립 판정 → SemVer → 문서 최상단 업데이트 → 명시 승인 기반 commit/push/PR`을 자동화 가능한 한 사이클로 구현 완결.
- 승인 영수증: `.coord/approvals/U42-user-approval.json` 검증 통과; 허용: 이 U42의 전역 규칙 배포, 브랜치 생성, 커밋, 원격 푸시, PR 생성. 금지: 삭제, 결제, 계정·자격증명 변경, 자동 병합 준수.
- 고정 불변식 준수: `rsi adopt`·`rsi rollback`은 계속 `UNAUTHENTICATED_ACTOR`; 평가기·장부·기존 고정 인수 변경 없음; 작성자(`codex`)와 검증자(`antigravity`) 및 판정자(`user`) 엄격 분리; 출력 없음·exit 0·자가 보고 증거 불인정; 실제 push/PR은 승인 영수증 해시 검증 전 거부.
- 연구 범위 완료: OpenAI 공식 Codex AGENTS.md·skills·hooks·worktrees, arXiv `2609.26457`·`2607.07663`, `akaszubski/autonomous-dev`, Reddit 실패 사례 원문 대조 및 적용/비적용 사유 분석 완료 (`docs/research/U42-research-dossier.md`).
- 허용 경로 준수: `v7_harness/rsi_release.py`, `v7_harness/cli.py`, `tests/test_u42_rsi_release.py`, `docs/43_evidence-to-pr-rsi-pipeline-u42.md`, `docs/research/U42-*`, `uaos_everywhere/uaos_global_rule_block.md`, `uaos_everywhere/README.md`, `README.md`, `.coord/approvals/U42-*`, 이 카드와 `.coord/PLAN.md`.
- 검증 증거:
  1. 고정 acceptance 테스트 `tests/test_u42_rsi_release.py` (SHA-256 `2f6334c4907455fbb2cdf121a6c6ae0d12c4af33b170fe37da6ac0cc87a70c27` 불변): 16/16 전건 PASS (0.048s).
  2. CLI 명령 연동 검증: `rsi watch`, `rsi prepare`, `rsi ship`, `rsi schedule` 4개 명령 정상 작동 및 `tests/test_cli.py` PASS.
  3. 전체 회귀 테스트: `python -m unittest discover -s tests -p "test_u*.py"` 550개 전건 무결점 통과 (546 OK, 4 skipped, 56.3s).
  4. 설치기 및 배포 검증: `tests.test_u37_install_everywhere`, `tests.test_u41_deploy_to_this_pc` 30개 전건 PASS.
  5. 구문 무결성: `python -m compileall v7_harness tests` 0 errors.
  6. 릴리스 패킷 및 승인 영수증: `.coord/tasks/U42-release-packet.json` 유효성 검증 `problems: []`, `.coord/approvals/U42-user-approval.json` 대조 `problems: []`.
  7. SemVer 0.1.0 범프 및 문서 최상단 업데이트: `uaos_everywhere/VERSION` 생성, `README.md` 및 `uaos_everywhere/README.md` 최상단 업데이트 섹션 멱등 삽입 완료.
- 스케줄러 인수 충족: 유료 LLM cron/polling 0회; 일 1회 결정적 변경 감지; URL·버전·ETag·Last-Modified·콘텐츠 SHA dedupe; 변화 없음/메타데이터 전용은 `ACK_ONLY`; 실질 콘텐츠 변화만 1회 `ACTIONABLE_DELTA`; 단일 lock (`.work/rsi-scheduler.lock`)·15s timeout·최대 3회 지수 백오프(`[60s, 120s, 240s]`)·실패 영수증·차기 실행 시각; Windows `schtasks` install/status/remove 드라이런/적용 검증 완료.
- 종료 상태: 모든 관문 통과 후 카드와 PLAN을 `REVIEW`로 반환.
