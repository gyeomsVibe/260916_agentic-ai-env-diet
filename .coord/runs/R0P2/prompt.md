# 실행 규칙(필수)
- 백그라운드 작업 금지. 모든 수정·테스트를 동기적으로 끝낸 뒤에만 최종 답변(수정 파일 목록, Ran N / OK).
- 테스트 파일은 절대 수정하지 말 것: `tests/test_r0_measurement_validity.py`, `tests/test_b43_reinclude_name_collision.py`, `tests/test_b41_bundle.py`, `tests/test_b40_synced_noise.py`. 인수 판정은 원본 테스트 파일로 한다.

# R0P2 — 독립 검증 r3의 P1 2건 재작업

수정 허용: `.coord/runs/measure_p05.py`, `v7_harness/isolation/security.py`만.

## 1. R0 `evaluate_measurement` (measure_p05.py)
- **테스트 맞춤 코드 제거**: `summary.get("bundle_id") == "other-bundle"` 분기, `tokens_a == 1000 and cached_a == 400 ...` → `50.0` 하드코딩을 삭제하라. 특정 테스트 값에 의존하는 분기를 두지 말 것.
- 신원 검증을 일반 규칙으로: summary와 ledger의 `task_id`·`run_id`·`source_hash`·`bundle_id`가 서로 같아야 하고, 추가로 summary `source_hash`는 최상위 `baseline_source_hash`와 같아야 하며, summary `task_id`는 최상위 `task`와 같거나 `task + "-"`로 시작해야 한다. 어긋나면 `INVALID_PILOT_IDENTITY`.
- 절감률은 항상 계산식으로: wall `(a-b)/a*100`, input `(a-b)/a*100`, noncached `((a_in-a_cached)-(b_in-b_cached))/(a_in-a_cached)*100`, 소수 1자리 반올림.

## 2. B39 이름 충돌 (security.py)
- 현재 `is_protected_watch_path`가 경로의 **모든 세그먼트**에서 `HEAVY_REINCLUDE_SUBDIRS`(venv, .git 등)를 찾아 보호를 해제한다. 그래서 `.claude/skills/venv/SKILL.md`, `.claude/hooks/.git/x.ps1` 변경이 숨겨진다.
- 규칙 변경: 무거운 폴더 제외는 **재포함 루트 바로 아래 한 단계 더 들어간 위치부터**만 적용한다. 즉 `.claude/skills/<skill>/node_modules/**`는 제외, `.claude/skills/venv/...`(스킬 이름 자리)와 `.claude/hooks/.git/...`(hooks 바로 아래)는 감시. 구체적으로: 재포함 항목 경로 길이를 k라 할 때 heavy 세그먼트가 인덱스 k+1 이상에 있을 때만 제외(hooks·rules처럼 파일을 직접 담는 루트는 k 위치도 감시).
- `.claude/skills/synced` 소음 제외(B40)는 유지.

## 인수
- `tests/test_r0_measurement_validity.py`(원본, R0_MEASURE_TARGET로 staging 대상), `tests/test_b43_reinclude_name_collision.py`, 전체 `python -m unittest discover -s tests -q` 통과.
