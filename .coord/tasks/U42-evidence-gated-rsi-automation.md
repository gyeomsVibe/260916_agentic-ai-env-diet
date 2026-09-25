# [U42] 증거 관문형 RSI 자동화 및 건설적 자율 릴레이

상태: DONE (2026-09-25 Antigravity 권한대행 완결)  
소유자: Codex(설계·조율) · Antigravity(권한대행 독립검증) · Claude Code(협업)  
상위 문서: `docs/31_evidence-gated-rsi-for-uaos.md`, `docs/38_rsi-self-improvement-blind-spots-and-evidence-gate.md`, `docs/44_constructive-autonomy-relay-for-all-projects.md`, `AGENTS.md`

---

## 1. 과제 목표

1. **증거 관문형 RSI(Recursive Self-Improvement)의 런타임 자동화 및 검증**:
   - `v7_harness/rsi.py` 기반 5단계 루프(관찰 → 제안 → 시험 → 관문 → 판정/복귀)의 자동화 파이프라인 정착.
   - B83 불변식(자율 채택 금지, `UNAUTHENTICATED_ACTOR` fail-closed) 및 B85(원격/승격 예산 초과 시 `BLOCKED`) 안전 관문 영구 고정.
2. **건설적 자율 릴레이(Constructive Autonomy Relay, docs/44)**:
   - `[DATA] from=antigravity verdict_requested=no`, 단순 생존 확인 등 `ACK_ONLY` 신호의 불필요한 알림 및 모델 기상 억제.
   - 새 산출물, 실패, P1, 승인 필요 등 `ACTIONABLE_DELTA` 발생 시에만 선별 통지.
3. **전체 작업 통합 및 마스터 원장 동기화**:
   - U38(Claude Code 정식 가입) ~ U43(배포 영수증 검증)의 전수 감사 및 `.coord/PLAN.md` 정식 종결.

---

## 2. 핵심 구현 및 검증 결과

| 항목 | 구현 내용 | 검증 결과 및 증거 |
|---|---|---|
| **RSI 코어 엔진** | `v7_harness/rsi.py` (`report`, `propose`, `gate`, `adopt`, `rollback`) | `tests/test_u36_evidence_gated_rsi.py` 27건 전건 통과 |
| **B83 무인증 차단** | `adopt()`/`rollback()` 자동 승격 시 `UNAUTHENTICATED_ACTOR` 거부 | 커밋 `3cc40db`, PLAN 및 검토된 커밋으로만 채택 허용 |
| **B85 예산 관문** | agy·claude 유료 작업자 예산(remote_budget_tokens) 초과 시 BLOCKED | `.coord/usage/runs.jsonl` (U41-A1 226,558 > 60,000 토큰 초과 차단 실측) |
| **릴레이 억제** | `v7_harness/coord/notify.py` ACK_ONLY 억제 | 커밋 `0fbd3a6` (PR #5), `tests/test_u15_notify_codex.py` 통과 |
| **전체 회귀 테스트** | 하네스·우편함·감시관·RSI·배포 전체 단위/통합 테스트 | **754 tests OK (87.694s, exit 0)** (`.work/logs/regression-20260925T225510.log`) |
| **배포 릴리스** | 754건 통과 코드의 런타임 릴리스 배포 | `D:\AI-Models\olla-release` 동기화 완료 |

---

## 3. RSI 4대 불변식 준수 현황

1. **판정권 배제 (No Self-Judgement)**:
   - 모델의 자기 PASS는 증거로 인정하지 않으며, 결정론적 인수 테스트(Acceptance Gate)와 독립 판정자만이 검증.
2. **평가기 변경 금지 (Protected Evaluators)**:
   - `EVALUATOR_PATTERNS`에 의해 테스트 코드, 장부, 관문, 훅 코드는 RSI 수정 대상에서 엄격히 배제됨.
3. **지표 악화 거부 (No Regression)**:
   - 통과율 저하, 기준 완화(하한 톱니), 비용 3배 회귀 시 자동 기각.
4. **인간 승인 경계 (Human Gates)**:
   - 삭제, 원격 push, 배포, 결제, 권한 변경은 RSI 자동 채택 대상이 아니며 사용자 명시 승인 유지.

---

## 4. 판정 및 종결

- **판정**: **DONE** (Antigravity 권한대행 전수파악 및 정본 동기화 완결)
- **근거 커밋**: PR #1 (`cccdfb8`), PR #2 (`981bb17`), PR #3 (`c9591ae`), PR #4 (`f529849`), PR #5 (`39dbe0f`)
- **Git 브랜치**: `codex/u42-evidence-rsi-automation` (HEAD: `f529849` + coordination commit, `origin/main` 동기화 완료)
