# Claude → Codex 인계 07 — U13 대행 판정·재작업 결과 (독립 판정 요청)

Codex 조율자 세션이 06:49 UTC 사용량 한도로 중단돼, 사용자 지시로 Claude가 U13 최종 판정과 재작업을 이어받았다.

1. **대행 판정:** REJECT. 실제 PC의 HOME 최상위 symlink·junction 17개와 TEMP 잠긴 파일 때문에 기본 설정 감시가 즉시 `WATCH_SCAN_UNAVAILABLE`로 실패했다. → `.coord/reviews/U13-claude-coordinator-gate.md`
2. **재작업:** `v7_harness/isolation/security.py`
   - 얕은 스캔에서 exclude를 reparse 검사보다 먼저 적용
   - 순회하지 않는 링크는 `LINK:<target>` 식별 정보로 기록
   - 잠긴 파일은 `LOCKED` 메타데이터 증거로 기록
   - 재귀 순회의 링크 거부와 루트 치환 거부는 유지
3. **테스트:** `tests/test_u13_isolation.py`에 5개 추가. U13 30, U12 29, 전체 146, compileall 모두 exit 0.
4. **라이브 스모크:** HOME 121 entries(LINK 16, LOCKED 3) 0.36초, TEMP 36 entries(LOCKED 7) 0.15초. 둘 다 10초 뒤 거짓 변경 0건.
5. **잔여 위험:**
   - 잠긴 파일은 메타데이터만 비교한다(메모 06의 ChangeTime/USN으로 보강 가능).
   - 예산 초과 시 루트 전체 실패는 유지했다.
6. **상태:** PLAN·카드 U13 = `REVIEW`. Claude는 자기 승인하지 않았다. **Codex의 독립 판정을 요청한다.** U14는 열지 않았다.
