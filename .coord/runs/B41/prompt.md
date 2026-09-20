# 실행 규칙(필수)
- 백그라운드 작업 금지. 모든 수정·테스트를 동기적으로 끝낸 뒤에만 최종 답변. 최종 답변에 수정 파일 목록과 테스트 결과(Ran N / OK).

# B41 묶음 — 백로그 P2 해소 (B41·B36·B35·B39)

수정 허용: `v7_harness/pilot.py`, `v7_harness/cli.py`, `v7_harness/isolation/security.py`, `tests/test_m4_efficiency.py`, 새 테스트 `tests/test_b41_bundle.py`. 그 외 수정·삭제 금지. 전역 설정 파일을 실제로 건드리지 말 것(테스트는 임시 폴더만).

1. B41: watch 불변식 위반(`ExternalWriteDetectedError`)으로 `EXTERNAL_WRITE`가 되면 summary에 `external_paths`(바뀐 상대 경로 목록, 최대 20개, `root|rel` 문자열)를 넣는다. 예외에 경로 정보가 없으면 security.py의 탐지 지점에서 예외 속성(`paths`)으로 실어 보낸다.
2. B36: `dry_run_promotion`·`apply_promotion`의 `SourceDivergenceError`가 트레이스로 CLI를 죽이지 않게, pilot에서 잡아 `state=FAILED`, `error_class=SOURCE_DIVERGED`, `promotion=BLOCKED`, `verdict_hint=BLOCKED`, `error_detail` 요약으로 반환한다.
3. B35: `tests/test_m4_efficiency.py`의 summary 키 수 검사를 `assertGreaterEqual(len(summary), 14)`에서 `assertLessEqual(len(summary), 18)`과 `assertGreaterEqual(len(summary), 14)` 둘 다로 바꾼다.
4. B39: re-include 순회 중 `node_modules`, `.venv`, `venv`, `__pycache__`, `.git` 하위는 감시에서 제외(재포함보다 우선)한다. `.claude/skills/x/node_modules/a.js` 변경은 탐지 안 됨, `.claude/skills/x/SKILL.md` 변경은 탐지됨을 테스트.
5. `tests/test_b41_bundle.py`에 1·2·4 테스트를 추가한다(fake agy fixture와 임시 폴더 사용).
6. 끝나면 `python -m unittest discover -s tests -q` 통과.
