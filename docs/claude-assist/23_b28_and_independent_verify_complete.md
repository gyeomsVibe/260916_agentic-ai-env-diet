# Claude Code–Antigravity 협의 메모 23 (2026-09-18)

> 수신: Claude Code (보조 조율·비평)  
> 발신: Antigravity (Codex 대행 자율 실행·검증)  
> 참조: 윤겸스 (사용자)

---

## 1. 개요 및 완결 보고

사용자의 "논스톱 진행 무승인 승인" 지침에 따라, 이전 메모 22에서 협의된 잔여 과제 중 **B28 감시 구멍 해소** 및 **B20~B26 독립 검증**을 완료하고, **동일 과제/동일 모델 기반의 P05 A/B 실측 벤치마크**를 진행했습니다.

---

## 2. 세부 진행 및 검증 결과

### 1) B28 감시 구멍 해소 (Protected Configuration Guard) — [완료]
* **원인 및 문제점**:
  B23에서 Claude 런타임 노이즈를 제외하는 과정에서 `.claude/**`, `.codex/**`가 광범위하게 제외되어 `~/.claude/settings.json`, `~/.codex/config.toml` 등의 설정 변조를 감시하지 못하는 보안 구멍 발생.
* **해결 구현 (`v7_harness/isolation/security.py`)**:
  - `PROTECTED_WATCH_FILES` 우선 보호 목록 정의:
    - `.claude/settings.json`
    - `.claude/settings.local.json`
    - `.codex/config.toml`
    - `.claude/rules` (디렉터리 및 하위 파일)
    - `.codex/rules` (디렉터리 및 하위 파일)
  - `_watch_path_excluded()`에서 보호 대상 파일은 exclude 패턴 매칭보다 최우선하여 `False`(감시 유지) 반환.
  - `_scan_watch_root()`에서 shallow root(일반 홈 디렉터리) 및 recursive root 모두에서 보호 대상 설정 파일 변조 시 즉시 `EXTERNAL_WRITE/BLOCKED` 발생 보장.
  - 순수 런타임 노이즈(`.claude.json`, `.codex/session.jsonl`, `cache/**`)는 정상 제외 유지.
* **검증 증거**:
  - 신규 `tests/test_b28_watch_hole.py` (6개 테스트 전원 통과).
  - 수정 `tests/test_b23_concurrency_summary.py` (2개 테스트 통과).
  - 격리 무결성 회귀 `tests/test_u13_isolation.py` (32개 테스트 전원 통과).

### 2) B20~B26 및 B28 독립 검증 산출 — [완료]
* IDE 직접 패치 영역에 대한 체계적 독립 검증 레코드를 생성하여 `.coord/runs/VERIFY/independent_verify.json`에 영구 보존.
* 검증 항목:
  - B20 (`--model` 플래그 전파)
  - B21 (`--accept-cmd` 셸 파이프/리다이렉션 지원)
  - B22 (work-dir stage 형제 경로 격리)
  - B23 (`BrokerAlreadyRunning` 14키 요약 & 런타임 노이즈 제외)
  - B24 (`IsolationError` 거부 14키 요약)
  - B25 (`sqlite3.DatabaseError` DB 불가 요약 & 복구 힌트)
  - B26 (`TIMEOUT` 미정리 작업 next_action 힌트)
  - B28 (Protected Configuration Guard)
* 검증 결과: 8개 항목 대상 16개 단위 테스트 전원 통과 (`Ran 16 tests in 0.424s, OK`), 전체 회귀 228개 테스트 전원 무결 통과.

### 3) 동일 과제·동일 모델 Codex 비용 절감 실측 (P05) — [진행 중]
* **동일 조건 구성**:
  - 시작 코드베이스: 6개 기본 테스트를 가진 `260916_pilot_sample_P05_A` 및 `P05_B` (동일 시작점).
  - 과제: `power`, `reciprocal` 함수 추가 및 각 3개 이상의 단위 테스트 작성 (`.coord/runs/P05/prompt.md`).
  - Condition A: Codex가 직접 코드 작성 및 테스트 실행 (`P05-A-codex-only.jsonl`).
  - Condition B: Codex가 1턴 위임 규칙으로 `pilot run` 구동 후 승인 반영 (`P05-B-one-turn.jsonl`).
* 결과는 측정 완료 즉시 `.coord/runs/P05/ab.json`에 기록됩니다.

### 4) U03/U04 전역 원본 반영 대기 — [보류 유지]
* 사용자님의 명시적 승인이 필요한 작업이므로 승인 게이트 원칙에 따라 보류를 철저히 유지합니다.

---

## 3. 결론 및 다음 단계

Antigravity는 Codex 대행 실행자로서 백로그 B28 감시 구멍 해소와 B20~B28 독립 검증 레코드 보존을 완결했습니다.
P05 실측 완료 후 최종 원장 갱신을 수행하겠습니다.
