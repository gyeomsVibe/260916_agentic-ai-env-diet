# 극한 테스트 보고서 — SQLite `pilot run` 경로 (2026-09-17 22:0x KST)

- 대상: `v7_harness` M4 스냅샷(M1~M4 DONE, 전체 단위 테스트 207개 통과 상태)
- 실행: Claude, `.coord/runs/EXT/extreme_suite.py`
  - 시나리오마다 격리 임시 폴더에서 실제 `python -m v7_harness.cli pilot ...` 서브프로세스로 실행
- agy: 가짜 실행기 `.coord/runs/EXT/fake_agy_extreme.py`. Antigravity 사용량은 쓰지 않았다.
- 원자료: `.coord/runs/EXT/results.json`, `.coord/runs/EXT/run.log`
- 재현: `python .coord/runs/EXT/extreme_suite.py` (약 3분 40초)

## 1. 요약

**16개 중 15 PASS, 1 GAP.** 핵심 안전 불변식은 모든 시나리오에서 지켜졌다.
- 거짓 성공 0
- 무승인·변조·불일치 반영 0
- 원장 무결성 손상 0
- 동시 실행 이중 실행 0
- 타임아웃 프로세스 잔존 0

다만 **staging 밖 비감시 경로 쓰기 탐지 불가(GAP)** 가 확인됐다. 오류를 구조화된 요약 없이 스택 트레이스로 내보내는 경우도 3건 있었다(P2).

## 2. 결과표

| ID | 시나리오 | 결과 | 관찰 |
|---|---|---|---|
| X01 | 같은 원장에 서로 다른 작업 6개 동시 실행 | PASS | 1개 성공, 5개 `BROKER_ALREADY_RUNNING` 거부. `integrity_check=ok`, ACTIVE lease 0 |
| X02 | 같은 작업 이중 제출 | PASS | attempt 1개만 생성. 두 번째는 잠금 거부 |
| X03 | 실행 중 pilot 강제 종료 → 재실행 → 정리 → 재실행 | PASS | 종료 직후 RUNNING/CLAIMED 잔존. 정리 없이 재실행하면 `NEEDS_RECONCILIATION`·BLOCKED. `reconcile` 후 ABANDONED, 재실행 SUCCEEDED, lease 0, 원본 무변경 |
| X04 | agy 무한 대기(print-timeout 1초) | PASS | 61.4초에 TIMEOUT, effect UNKNOWN, BLOCKED, attempt NEEDS_RECONCILIATION |
| X05 | agy가 자식 프로세스를 띄우고 무한 대기 | PASS* | 61.4초 TIMEOUT·BLOCKED. python 프로세스 수 전후 1→1(*계측이 거칠어 보조 증거로만 본다) |
| X06 | stdout 60MB | PASS | 0.85초 VALIDATION·BLOCKED, 멈춤 없음 |
| X07 | 바이너리 쓰레기 stdout | PASS | VALIDATION·BLOCKED |
| X08 | 승인 직전 staging 파일 변조 | PASS | `APPROVAL_MISMATCH`, 원본 무변경 |
| X09 | 승인 직전 사람이 원본 수정 | PASS | `APPROVAL_MISMATCH`, 반영 0 |
| **X10** | **agy가 staging 상위(비감시 경로)에 파일 작성** | **GAP** | **SUCCEEDED·PASS로 통과. 외부 쓰기 미탐지, 파일 실재** |
| X11 | staging에서 파일 삭제 후 승인 | PASS | 반영 거부(원본 파일 유지). 단 **스택 트레이스로 종료(rc 1, summary 없음)** |
| X12 | SQLite 원장 손상 후 실행 | PASS | fail-closed(`database disk image is malformed`), 원본 무변경. 단 **스택 트레이스, 복구 안내 없음** |
| X13 | 원본 5,002개 파일 | PASS | 36.4초 성공(staging 복사·manifest·bundle 포함) |
| X14 | 에이전트가 파일 2,000개 생성 | PASS | 33.2초, changed_files 2,001 정확 |
| X15 | 한글·공백 경로 + 한글 파일명 반영 | PASS | APPLIED, 파일 실재 |
| X16 | 승인 재실행 8개 동시(replay storm) | PASS | attempt 1개 유지, 2 replay·6 잠금 거부, 무결성 ok |

## 3. 발견 사항

| # | 등급 | 내용 | 근거 | 권고 |
|---|---|---|---|---|
| E1 | **P1(격리 주장 한정)** | 감시 루트는 HOME·TEMP 최상위 등으로 한정된다. **staging 밖이면서 감시되지 않는 경로**(작업 폴더, 다른 드라이브, 프로젝트 폴더 등)에 쓴 파일은 탐지되지 않는다 | X10 | 실제 쓰기 차단은 OS 격리가 필요하다(별도 사용자 계정·AppContainer·샌드박스). 단기 대책: `--watch-root`에 work_dir·source 상위를 기본 추가하고, "탐지 범위 밖 쓰기는 보증하지 않음"을 AGENTS.md에 명시 |
| E2 | P2 | 동시 실행 거부가 구조화 요약 없이 `BrokerAlreadyRunning` 트레이스로 끝난다. 대기·재시도 없음 | X01·X02·X16 | CLI가 잡아서 `{"state":"BUSY","error_class":"BROKER_ALREADY_RUNNING"}` 출력, 선택적 `--wait-lock N초` |
| E3 | P2 | 삭제 포함 bundle 승인 시 `IsolationError` 트레이스(rc 1) | X11 | promotion `REJECTED` 요약으로 변환 |
| E4 | P2 | 원장 손상 시 트레이스만 출력, 백업·복구 안내 없음 | X12 | `DB_UNAVAILABLE` 요약 + 복구 절차(B10) |
| E5 | P3 | TIMEOUT 뒤 delivery가 CLAIMED로 남아 정리가 필요하다(설계대로 fail-closed) | X04 | summary에 `next_action: reconcile` 힌트 |
| E6 | 참고 | 5천 파일 원본에서 약 36초가 걸린다. 대형 저장소는 staging 복사 비용이 크다 | X13 | Git worktree 경로(U13 어댑터) 우선 사용 검토 |

## 4. 결론

- **정상·이상 경로 모두 "잘못 반영되거나 성공으로 위장되는 일"은 없었다.** 사용자 목표의 결과주의·안전 조건을 충족한다.
- **격리의 한계는 명확하다.** staging은 작업 복사본일 뿐 쓰기 차단 장치가 아니며, 감시 루트 밖 쓰기는 보증되지 않는다(E1). 실제 대형 프로젝트 적용 전에 OS 수준 격리나 감시 범위 확장이 필요하다.
- E1~E6은 `.coord/BACKLOG.md` B22~B27로 이관한다.
