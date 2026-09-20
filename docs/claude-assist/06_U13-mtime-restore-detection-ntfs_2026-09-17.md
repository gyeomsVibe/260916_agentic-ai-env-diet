# Claude → Codex 지원 메모 06 — U13 P1 "동일 크기 + mtime 복원 미탐지" 해법 실측

대상 결함(조율자 06:27 UTC): 같은 크기로 내용을 바꾸고 mtime을 되돌리면 stat-first 비교가 변경을 놓친다.
실측 스크립트: `.claude/codex-relay/usnprobe.py` (TEMP의 임시 파일만 생성·삭제)

## A. 실측 (Windows NTFS, 비관리자, Python 3.14)

시나리오: `"AAAA"` 기록 → `"BBBB"`로 덮어쓰기(같은 크기) → `os.utime`으로 원래 atime/mtime 복원

| 신호 | 전 | 후 | 탐지 | 비용 |
|---|---|---|---|---|
| size | 4 | 4 | ✗ | — |
| mtime(LastWriteTime) | 복원됨 | 동일 | ✗ | — |
| **NTFS ChangeTime** (`GetFileInformationByHandleEx(FileBasicInfo)`) | 134341005858955663 | 134341005870137946 | **✓** | 파일당 약 0.11ms (200회 0.022초) |
| **파일별 USN** (`fsutil usn readdata <file>`, FSCTL_READ_FILE_USN_DATA) | 0x…15ed48 | 0x…15ef00 | **✓** | 프로세스 호출 약 80ms/회 → ctypes DeviceIoControl로 직접 호출 권장 |

## B. 권장 비교 키

`(file_id, size, LastWriteTime, ChangeTime, USN)` 중 하나라도 다르면 후보로 올리고, 후보만 SHA-256으로 확인한다.

- **ChangeTime:** `os.utime`/`SetFileTime`으로는 되돌릴 수 없고, 쓰기·속성 변경 시 NTFS가 갱신한다. 비용이 매우 싸서 1차 키로 적합하다. 단, `SetFileInformationByHandle(FileBasicInfo)`로 의도적으로 설정할 수는 있다 → 악의적 은폐까지 막으려면 USN을 병행한다.
- **USN:** 사용자 모드에서 되돌릴 수 없는 단조 증가 값이다. 볼륨 저널이 꺼져 있으면 0이므로 preflight에서 0이면 `UNKNOWN` 처리(fail-closed).
- **file_id(FileIndex):** 삭제 후 같은 이름으로 다시 만드는 교체를 탐지한다.

## C. basename 과제외 P1

전역 이름 제외(`browser`, `cache` 등) 대신 **감시 루트 기준 상대 경로 prefix 제외**만 허용한다.

- 예: HOME 루트 기준 `AppData/`, `.codex/`, `.gemini/antigravity/brain/`
- 프로젝트 루트 아래에는 제외 규칙을 적용하지 않는다. `product/browser/logic.py`는 감시한다.

## D. 테스트 추가안

1. `test_same_size_mtime_restored_detected_by_changetime`
2. `test_usn_zero_journal_disabled_fail_closed`
3. `test_delete_recreate_same_content_detected_by_file_id`
4. `test_project_path_named_browser_not_excluded`
5. `test_root_relative_exclusion_only_under_declared_root`
