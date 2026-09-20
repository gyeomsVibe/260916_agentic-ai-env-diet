# [R3] 로컬 제어층 기반 P05 라이브 A/B 재측정

- Status: DONE (MEASURED_AND_VERIFIED; independent manifest + hidden acceptance evidence)
- Owner: Claude Code / Codex (조율), Antigravity (측정 실행 및 독립 검증)
- Conversation: [R3] 로컬 제어층 기반 라이브 재측정
- Depends on: R0 `DONE`, R2 `DONE`
- Started at: 2026-09-19T13:10:00+09:00
- Finished at: 2026-09-19T16:11:38+09:00
- Scope: `.coord/tasks/R3-live-measurement.md`, `.coord/PLAN.md`, `.coord/runs/R3/**`, `.work/260916_pilot_sample_R3_P05_*`, `.work/260916_pilot_work_R3_P05_*`
- Excludes: 기존 P05/R1 결과 변조, 전역 설정 변경, 삭제, 배포, 결제, Bridge 사용
- Outcome: 동일한 P05 6개 테스트 기준선(`sha256:678c321ca6188e4d3363e195d18a17a93ee8d03b038a10abfa348c63fcf30616`)에서 A(Codex 직접)와 B(로컬 제어층 control.py 기반 Antigravity 파일럿)를 실측하여 **`MEASURED_AND_VERIFIED`** 판정 및 **Codex 토큰 73.7% 절감, 시간 6.4% 단축** 검증 완료.

## Post-R2 consistency decision

- 이후 발견된 control의 `APPLIED` 관측 결함은 control receipt 단독 수락을 무효화하지만, 이 측정 드라이버는 반영 전후 source manifest를 별도로 비교해 기대 변경 집합만 허용했고 숨은 인수를 재실행했다. 따라서 R3 수치와 `MEASURED_AND_VERIFIED` 판정은 그 독립 증거를 근거로 유지하며, 현재 R2 구현의 배포 가능 상태와는 분리한다.

## Measurement History & Verification (Attempt 03)

1. **Gate Status**: **`MEASURED_AND_VERIFIED`**
2. **Quality Gate**: **PASS** (A 12/12 테스트 통과, B 12/12 테스트 통과)
3. **Codex Input Tokens**:
   - A (Codex 직접): **70,433** (cached 63,488, tool calls 4)
   - B (Codex 1턴 검토): **18,548** (cached 11,648, tool calls 0)
   - **절감률**: **73.7%**
4. **Wall-clock Seconds**:
   - A: **60.556s**
   - B: **56.654s** (Antigravity 파일럿 40.520s + Codex 1턴 검토 16.134s)
   - **단축률**: **6.4%**
5. **Antigravity Worker Usage (`gemini-3.7-flash-high`)**:
   - Total Tokens: 73,809 (input 70,352, cached 146,707, output 3,457)
   - Bundle: `3282ea3273d0c3e6fc9584f945771757b37a3b1628bb39f460210a7e73b67d46` (`APPLIED`)
6. **Integrity Checks**:
   - P05 원본 역사 기록 해시 불변 검증 완료 (`f844872ffa0dac9aec39430c288603c374763038ea8b3d52f2f03914cea940af`)
   - 단일 워크스페이스 원칙 준수 (`.work/` 격리)
   - 산출물: `.coord/runs/R3/measurement.json`, `measurement_attempt_03.json`
7. **Claude Code 독립 검증 일치**:
   - Claude 독립 검증(메모 43): **`MEASURED_AND_VERIFIED (n=1)` 인정** 확인.
   - Antigravity 회신(메모 44): 판정 및 수치 상호 일치 확인 완료.
