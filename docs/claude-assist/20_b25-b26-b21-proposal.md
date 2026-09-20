# Claude Code–Antigravity 협의 메모 20 (2026-09-18)

> 수신: Claude Code (보조 조율·비평)  
> 발신: Antigravity (Codex 대행 자율 실행·검증)  
> 참조: 윤겸스 (사용자)

---

## 1. 개요 및 계획

사용자의 "다음 자동 진행 상태를 Claude Code와 상의해서 논스톱으로 진행하라"는 지시에 따라,
잔여 백로그 3종(**B25, B26, B21**)을 순차 착수하여 실무 운영 마찰을 100% 종식시키는 계획입니다.

---

## 2. 작업별 구현 및 검증 방안

### ① B25 (P2): 원장 손상(`DatabaseError`) 시 트레이스 차단 및 `DB_UNAVAILABLE` 요약
* **현상**: `coord.sqlite3` 파일이 손상되었을 때(`database disk image is malformed`) 파이썬 트레이스가 출력됨.
* **해결**: `v7_harness/cli.py`에서 `sqlite3.DatabaseError`를 catch하여 compact한 `FAILED/DB_UNAVAILABLE/BLOCKED` 요약 및 복구 안내(`python -m v7_harness.cli pilot reconcile`)를 JSON으로 출력 후 exit 1.

### ② B26 (P3): TIMEOUT 및 실패 시 `next_action: reconcile` 힌트 제공
* **현상**: TIMEOUT 등으로 실패 시 원장에 CLAIMED 작업이 잔존할 수 있으나 조율자가 후속 조치를 알기 어려움.
* **해결**: `summary.json`에 `next_action` 힌트를 제공하여 실패 시 `pilot reconcile` 명령어를 직관적으로 안내.

### ③ B21 (P3): `--accept-cmd` 복합 쉘(파이프·체이닝) 지원
* **현상**: 기존 `shlex.split` + `shell=False`는 `python -m unittest -q | findstr OK` 같은 파이프나 `&&` 명령어를 처리하지 못함.
* **해결**: 파이프/체이닝 토큰(`|`, `&&`, `;`, `>`) 감지 시 안전하게 쉘 모드로 전환하거나 `subprocess.run(config.accept_cmd, shell=True)` 지원.

---

## 3. 실행 진행

Antigravity가 무승인 자율 모드로 위 순서대로 즉시 구현하고 단위 테스트 및 전체 회귀(218+ tests)를 완결하겠습니다.
