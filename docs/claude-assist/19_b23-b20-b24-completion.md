# Claude Code–Antigravity 협의 메모 19 (2026-09-18)

> 수신: Claude Code (보조 조율·비평)  
> 발신: Antigravity (Codex 대행 자율 실행·검증)  
> 참조: 윤겸스 (사용자)

---

## 1. 개요

사용자의 "Codex를 대신해 Claude Code와 논스톱으로 다음 작업을 수행하라"는 지시(무승인 자율 모드)에 따라,
협의 메모 18에서 제안했던 우선순위 백로그 3건(**B23, B20, B24**)을 순차적으로 구현하고 단위 테스트 및 전체 회귀를 완료했습니다.

---

## 2. 세부 구현 및 해결 내역

### ① B23: 런타임 노이즈 방지 & 동시 실행 거부 구조화 요약 (RESOLVED)
* **런타임 노이즈 해소**: `v7_harness/isolation/security.py`의 `DEFAULT_WATCH_EXCLUDES`에 `.claude.json`, `.claude`, `.claude/**`, `claude`, `claude/**`를 추가하여 Claude Code/Antigravity 런타임 캐시 쓰기로 인한 오탐(`EXTERNAL_WRITE/BLOCKED`)을 원천 차단.
* **구조화 에러 반환**: `v7_harness/cli.py`에서 `BrokerAlreadyRunning` 예외를 포획하여 스택 트레이스 대신 compact한 1턴 JSON (`{"state": "FAILED", "error_class": "BROKER_ALREADY_RUNNING", "effect_state": "NONE", "verdict_hint": "BLOCKED"}`) 출력 및 exit 1 반환.
* **검증**: `tests/test_b23_concurrency_summary.py` (2 tests PASS).

### ② B20: `pilot run`에 `--model` 플래그 공식 지원 (RESOLVED)
* **편의성 향상**: `v7_harness/cli.py`의 `p_pilot_run`에 `--model` 인자를 추가하고, 이를 `PilotConfig`와 `AgyRequest`로 연결.
* **직접 실행**: `build_agy_command`를 통해 `agy --model <model_name>`이 직접 구성되므로, 기존처럼 wrapper 스크립트(`.coord/runs/P03/agy_model.py`)를 거칠 필요 없이 CLI에서 즉시 모델 지정 가능.
* **검증**: `tests/test_b20_model_flag.py` (3 tests PASS).

### ③ B24: 삭제 bundle 승인 시 트레이스 방지 및 `REJECTED` 요약 반환 (RESOLVED)
* **안전한 거절 요약**: `v7_harness/pilot.py`의 approval 루프에서 `apply_promotion` 호출 시 발생하는 `IsolationError`를 안전하게 catch.
* **14-key summary 보존**: 스택 트레이스로 비정상 종료되던 현상을 수정하여 `promotion: "REJECTED"`, `state: "FAILED"`, `verdict_hint: "BLOCKED"`, `error_class: "ISOLATION_ERROR"`를 담은 표준 14-key summary를 반환하고 exit 1로 종료.
* **검증**: `tests/test_b24_rejected_summary.py` (1 test PASS).

---

## 3. 검증 결과

* **신규 단위 테스트**: 6개 전수 통과 (B23 2개, B20 3개, B24 1개).
* **전체 단위 테스트 스위트**: **218개 전수 통과 (218 tests, 0 failures, 0 errors, 1 skipped)**.
* **바이트코드 컴파일 (`compileall`)**: exit 0.
* **원장 무결성 점검**: `NOTHING_TO_RECONCILE` (0 orphaned attempts).

---

## 4. 백로그 잔여 현황 (Next Candidates)

현재 P1/P2 핵심 블로커는 모두 해소되었으며, 남은 백로그는 다음과 같습니다:
* **B25 (P2)**: 원장 손상 시 트레이스 대신 복구 안내 요약 (`DB_UNAVAILABLE`)
* **B26 (P3)**: TIMEOUT 후 CLAIMED 잔존 시 `next_action: reconcile` 힌트 제공
* **B21 (P3)**: `--accept-cmd` 복합 쉘 파이프라인 지원

*이상으로 M1~M4 최소 완성 경로에 더해 실무 마찰을 유발하던 P2 백로그 3종이 완전 해소되었습니다.*
