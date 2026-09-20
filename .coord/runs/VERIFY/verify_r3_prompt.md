[읽기 전용 독립 검증 — 파일 수정·생성 금지, 백그라운드 작업 금지, 끝까지 동기 수행 후 답변]
대상:
- R0: `.coord/runs/measure_p05.py`의 `evaluate_measurement`, `tests/test_r0_measurement_validity.py`, `.coord/runs/R0/p05-correction.json` (원본 `.coord/runs/P05/ab.json` 무변경이어야 함)
- B40: `v7_harness/isolation/security.py`의 `DEFAULT_REINCLUDE_NOISE`(`.claude/skills/synced`), `tests/test_b40_synced_noise.py`
- B41 묶음(IDE 직접 반영): B41 `external_paths`, B36 `SOURCE_DIVERGED` 구조화, B35 summary 키 14~18, B39 re-include 하위 node_modules/.venv/venv/__pycache__/.git 제외, `tests/test_b41_bundle.py`
할 일: 1) 항목별 PASS/FAIL과 한 줄 근거 2) 반례 탐색: (a) R0가 무효 측정을 VALID로 통과시키는 입력 (b) B39 제외가 재포함 민감 파일(예: `.claude/hooks/.git/x`나 `.claude/skills/venv/SKILL.md` 같은 이름 충돌)을 숨기는지 (c) B40 synced 제외가 사용자가 직접 만든 스킬을 숨기는지 (d) SOURCE_DIVERGED가 반영을 실제로 막는지 3) blocking P1 목록.
형식: JSON {"items":[{"id","verdict","evidence"}],"counterexamples":[{"case","finding","severity"}],"blocking_p1":[]}
