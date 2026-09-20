# U13 조율자 최종 판정 — Claude 대행

- 판정 시각: 2026-09-17 16:4x (Asia/Seoul)
- 대행 사유: 조율자 Codex 세션 `01a0aa34`가 06:49 UTC 최종 판정 시작 직후 `You've hit your usage limit`로 중단됐다. 사용자가 Claude에게 작업을 이어받도록 지시했다.
- 판정 대상: `v7_harness/isolation/**`, `tests/test_u13_isolation.py` (카드 "Final bounded-fingerprint" 스냅샷)
- 코드 변경: 없음. 이 문서, U13 카드의 판정 절, PLAN U13 상태만 기록했다.

## Verdict

**REJECT → U13 `READY (REWORK)`.** U14는 열지 않는다.

## 1. 확인된 통과 항목

| 항목 | 명령·근거 | 결과 |
|---|---|---|
| U13 테스트 | `python -m unittest tests.test_u13_isolation` | exit 0, 25 tests |
| 전체 회귀 | `python -m unittest discover -s tests -p "test_*.py"` | exit 0, 141 tests |
| 컴파일 | `python -m compileall -q v7_harness tests` | exit 0 |
| P1: 같은 크기 + mtime 복원 | 전체 내용 SHA-256 지문 + `test_watch_detects_same_size_content_with_restored_mtime` | 해결 |
| P1: basename 전역 제외 | root 상대 glob 단일 matcher + `test_recursive_excludes_are_root_relative_not_global_basenames` | 해결 |
| 스캔 불가 ≠ 거짓 삭제 | `WatchScanResult.root_exists`, `WATCH_SCAN_UNAVAILABLE` | 해결 |

## 2. 차단 결함 (실제 호스트 실측, L1)

`snapshot_watch_roots([Path.home()])`와 `snapshot_watch_roots([TEMP])`를 기본 설정으로 이 PC에서 실행했다(읽기 전용).

| # | 등급 | 결과 | 원인 |
|---|---|---|---|
| B1 | **P1** | HOME 스냅샷이 즉시 `WATCH_SCAN_UNAVAILABLE: reparse or symlink C:\Users\Kimyoongyeom\.antigravity-ide` | HOME 최상위에 사용자가 만든 symlink/junction이 **17개** 있다(`.antigravity-ide`, `.cache`, `.gradle`, `.vscode` → `D:\AI-Models\home\…`, Windows 기본 `Application Data`, `Cookies`, `Local Settings`, `My Documents` 등). 얕은 스캔 분기는 `entry.is_symlink() or is_symlink_or_reparse()`를 **exclude 검사보다 먼저** 수행하고, 디렉터리인지 따지지 않고 거부한다. |
| B2 | **P1** | 사용자가 `excludes`에 해당 이름을 추가해도 같은 오류가 15회 반복됐다 | 얕은 분기에서는 exclude가 reparse 검사 뒤 `record()` 안에서만 적용되므로, **어떤 설정으로도 이 PC의 HOME을 감시할 수 없다.** |
| B3 | **P1** | TEMP 스냅샷이 `WATCH_SCAN_UNAVAILABLE: fingerprint …\Temp\114304dc-….tmp: [Errno 13] Permission denied` | 다른 프로세스가 독점 잠금한 파일 하나 때문에 루트 전체가 UNKNOWN이 된다. TEMP·HOME 최상위(NTUSER.DAT류)에는 잠긴 파일이 상시 존재한다. |

결과: 실제 위임에서 HOME·TEMP 감시를 켜면 **모든 실행이 시작 전에 fail-closed**된다. fixture 테스트 25개는 모두 깨끗한 임시 디렉터리에서 실행돼 이 조건을 재현하지 못했다.

## 3. 보조 결함

| # | 등급 | 내용 |
|---|---|---|
| S1 | P2 | `test_watch_roots_budget`는 `_scan_watch_root`를 mock으로 바꿔 비교 루프만 측정한다. 실제 5만 파일 스캔·해시 시간 예산을 증명하지 않는다. |
| S2 | P2 | 64MiB/루트 지문 예산은 HOME 최상위에 대용량 파일 하나만 있어도 루트 전체를 UNKNOWN으로 만든다. 예산 초과 파일을 개별 "미검증" 증거로 분리하는 정책이 없다. |

## 4. 필수 재작업 (인수 조건)

1. **순서:** 모든 스캔 분기에서 `exclude 판정 → reparse 판정` 순서로 통일한다.
2. **얕은 스캔의 디렉터리 reparse:** 순회하지 않는 최상위 디렉터리 링크는 실패가 아니라 **링크 자체의 식별 정보**(대상 경로 문자열, 링크 mtime/ctime)로 기록한다. 링크 교체·신규 링크 생성은 변경으로 탐지한다. 재귀 대상 루트 안의 링크 순회 거부는 유지한다.
3. **잠긴 파일:** 파일 단위 `Permission denied`/sharing violation은 루트 전체 UNAVAILABLE이 아니다. 해당 파일을 `(size, mtime, ctime, "LOCKED")` 메타데이터 증거로 기록하고, 전후 메타데이터가 달라지면 그 파일만 UNKNOWN 변경으로 보고한다. 루트 열거 실패만 루트 UNAVAILABLE로 유지한다.
4. **예산 초과 파일:** 루트 전체 실패 대신 파일 단위 `UNVERIFIED_BUDGET` 증거로 남기고, 메타데이터 변경 시 UNKNOWN으로 보고한다.
5. **실호스트 형태 회귀 테스트 추가:**
   - `test_shallow_home_with_directory_junctions_snapshots` — 최상위 디렉터리 junction 3개가 있는 fixture HOME이 성공 스냅샷
   - `test_excluded_reparse_entry_is_skipped_before_reparse_check`
   - `test_locked_file_recorded_as_metadata_not_root_failure` — `msvcrt.locking` 또는 공유 거부 핸들로 잠금
   - `test_top_level_junction_retarget_detected`
   - `test_real_scan_budget_5k_files` — mock 없는 실제 파일 스캔 시간 상한
6. **라이브 스모크(읽기 전용):** 실제 `Path.home()`와 `%TEMP%`에 대해 snapshot → 10초 대기 → `assert_unchanged` 결과와 소요 시간을 카드에 기록한다. 판정 기준: 스냅샷 성공, 정상 백그라운드 활동만 있을 때 거짓 UNKNOWN 0건. 발생 시 원인 경로를 exclude 후보로 기록한다.

## 5. 후속 — 사용자 지시에 따른 Claude 대행 재작업 결과

- 반영: 4절의 1·2·3·5·6항. 4항(예산 초과 파일 단위 증거)은 기존 fail-closed 인수 테스트와 충돌해 보류했다(P2 잔여).
- 검증: U13 30 tests(ResourceWarning 오류 취급) exit 0, U12 29 exit 0, 전체 146 exit 0, compileall exit 0.
- 라이브 스모크: HOME 121 entries(LINK 16, LOCKED 3) 0.36초 스냅샷, 10초 뒤 변경 없음 / TEMP 36 entries(LOCKED 7) 0.15초, 10초 뒤 변경 없음.
- 상태: `REVIEW`. 재작업을 한 Claude는 자기 승인하지 않는다. Codex 사용량 복구 후 독립 판정이 필요하다.
