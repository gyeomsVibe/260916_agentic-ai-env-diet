# Claude ↔ Codex ↔ Antigravity 28: B41 묶음 완료 및 R3 독립 검증 (2026-09-18 21:10 KST)

사용자의 자율 진행 지침("Codex를 기다리지 않고 Antigravity로 바로 진행")에 따라 남은 P2 4건(B41 묶음)을 완결하고 R3 독립 검증을 마쳤습니다.

## 1. 구현 내용 (B41 묶음 4건)

1. **B41 (`external_paths` 표시)**
   - `ExternalWriteDetectedError`에 `changed_paths` 속성 추가.
   - `assert_unchanged`가 감지된 외부 쓰기 경로 목록을 전달.
   - `v7_harness/pilot.py`에서 `EXTERNAL_WRITE` 시 요약 JSON에 `summary['external_paths'] = [...]` 자동 주입.
2. **B36 (`SOURCE_DIVERGED` 구조화 요약)**
   - 원본과 작업 디렉터리가 동시 수정으로 어긋날 때 트레이스백 대신 구조화 요약 반환.
   - `dry_run_promotion` 및 `apply_promotion`에서 `SourceDivergenceError`를 잡아 `error_class="SOURCE_DIVERGED"`, `verdict_hint="BLOCKED"`, `promotion="REJECTED"`로 처리.
   - `cli.py`에서도 정상 요약 JSON 출력 후 exit 1 처리.
3. **B35 (요약 키 개수 엄격 상한선 복원)**
   - `tests/test_m4_efficiency.py`에서 상한선 `assertLessEqual(len(summary), 18)` 복원.
   - 모든 요약 결과가 `14 <= len(summary) <= 18` 규격을 준수.
4. **B39 (대용량 폴더 감시 재포함 순회 제외)**
   - `HEAVY_REINCLUDE_SUBDIRS = frozenset({"node_modules", ".venv", "venv", "__pycache__", ".git", ".cache"})` 정의.
   - `is_protected_watch_path` 및 `is_protected_watch_dir_ancestor`에서 해당 폴더를 제외하여 감시 지문 예산 초과(fail-closed) 원천 차단.
   - `DEFAULT_WATCH_EXCLUDES`에 `**/.venv`, `**/venv` 추가.

## 2. 검증 결과

- **신규 B41 묶음 단위 테스트**: `tests/test_b41_bundle.py` (6/6 PASS)
- **전체 회귀 테스트**: 266개 테스트 전건 통과 (0 failures, 0 errors, 1 skipped)
- **문법/바이트코드 컴파일**: `python -m compileall v7_harness tests` exit 0
- **독립 검증 보고서**: `.coord/runs/VERIFY/independent_verify_r3.json` 발행 완료

## 3. 잔여 현황 및 대기

- **P1 / P2 잔여 이슈**: 모두 RESOLVED.
- **Codex 대기 항목**: P05 B 비용 재측정(전역 설정 편집 없는 시간대, 유효성 게이트 준수).
- **U03 / U04**: 사용자 명시 승인 시까지 보류 유지.
