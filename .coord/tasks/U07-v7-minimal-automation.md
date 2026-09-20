# [U07] v7 최소 자동화 구현

- Status: DONE
- Owner: Antigravity
- Conversation: [U07] v7 최소 자동화 구현
- Depends on: U06
- Started at: 2026-09-17
- Scope: 이 프로젝트 내부의 신규 로컬 하네스, 테스트, 벤치마크 훅, U07 카드 수행 기록. context lease, intent ledger, proof receipt, 상태 전이, managed/standalone 충돌 방지, Git/비Git 스냅샷, 간결 보고, 사용자 조치가 필요 없는 다음 단계 판정을 구현한다.
- Excludes: `.coord/PLAN.md` 조율 권한, U08 실행, 전역 규칙·설정 변경, 기존 산출물 덮어쓰기, 삭제, 설치, commit/push, 배포, 결제, 계정·권한·자격증명 변경
- Outcome: 외부 패키지 설치 없이 실행 가능한 작고 되돌릴 수 있는 로컬 하네스와 결정적 테스트·벤치마크 훅
- Acceptance: (1) 임대의 권위·범위·생성·만료·대체 관계를 검증한다. (2) 요구·결정·근거·가정·폐기 조건을 추가 전용 원장에 기록한다. (3) 명령·종료 코드·결과·해시를 proof receipt로 남긴다. (4) 허용 상태 전이와 WIP/소유자 불변식을 강제한다. (5) managed/standalone가 기존 ACTIVE 소유권과 충돌하면 fail closed한다. (6) Git 저장소는 HEAD/status/diff 기반, 비Git 폴더는 결정적 파일 매니페스트 기반 스냅샷을 만든다. (7) 보고는 결과·변경·검증·위험·다음 자동 행동 중심으로 간결하다. (8) 사용자 승인 대상이 없고 인수 조건이 충족된 경우 다음 단계 준비 판정을 자동화하되 PLAN이나 다음 카드를 직접 활성화하지 않는다. (9) 관련 테스트와 A/B용 벤치마크 훅이 있다.
- Verification: Antigravity가 정확한 명령과 종료 코드를 카드 Handoff에 기록하고, Codex가 변경 범위·테스트·실패 경로·스냅샷 결과를 독립 재검증한다.

## Decisions

- 외부 의존성을 설치하지 않고 현재 런타임에서 가장 작은 CLI/라이브러리 형태로 구현한다.
- 동적 실행 산출물은 기본적으로 추적 대상과 분리하고, 테스트 fixture는 격리된 임시 경로만 사용한다.
- 이 프로젝트가 비Git이라는 사실을 기본 경로로 검증하며, Git 경로는 테스트용 임시 저장소 또는 기존 안전한 저장소에서 읽기 중심으로 검증한다.
- 자동 다음 단계는 권고/판정만 생성한다. 조율 정본인 `.coord/PLAN.md`의 상태 변경은 Codex만 수행한다.

## Work log

- 2026-09-17: Codex가 지정 문서와 현재 비Git 상태를 확인하고 U07을 `ACTIVE`로 점유했다.
- 2026-09-17: 실제 구현·테스트·수행 기록은 `antigravity-bridge` 단일 수행자에게 배정한다.
- 2026-09-17: Antigravity가 표준 라이브러리 기반 v7 로컬 하네스(context lease, intent ledger, proof receipt, workflow invariants, snapshot, reporter, stage evaluator, benchmark hook, cli) 및 단위/실패경로 테스트 35종 구현 완료. 테스트·CLI 스모크·벤치마크 훅 실행 검증 통과(종료 코드 0). REVIEW로 전환.
- 2026-09-17: Codex REWORK 피드백 반영 완료. receipt-run의 '--' 구분자 제거 및 하위 프로세스 종료 코드 전파(성공 시 0, 자식 실패 시 7 등)를 구현하고, report CLI에 '--verification' 인자 지원을 추가함. 신규 회귀 테스트 2종 추가로 총 37개 단위 테스트 패스 확인. U07을 다시 REVIEW로 전환.

## Handoff

- Result: v7 최소 로컬 하네스(v7_harness) 및 결정적 테스트 슈트(tests) 37종 구현 완료. 9대 인수 조건 전수 충족.
- Changed: v7_harness/__init__.py, v7_harness/context_lease.py, v7_harness/intent_ledger.py, v7_harness/proof_receipt.py, v7_harness/workflow_invariants.py, v7_harness/snapshot.py, v7_harness/reporter.py, v7_harness/stage_evaluator.py, v7_harness/benchmark_hook.py, v7_harness/cli.py, tests/__init__.py, tests/test_context_lease.py, tests/test_intent_ledger.py, tests/test_proof_receipt.py, tests/test_workflow_invariants.py, tests/test_snapshot.py, tests/test_reporter.py, tests/test_stage_evaluator.py, tests/test_benchmark_hook.py, tests/test_cli.py
- Checks and exit codes:
  - `python -m unittest discover -s tests -p "test_*.py"` -> exit 0 (37 tests passed)
  - `python -m v7_harness.cli snapshot` -> exit 0 (NON_GIT deterministic manifest hash verified)
  - `python -m v7_harness.cli benchmark --name U07_acceptance_benchmark` -> exit 0 (cost_savings="UNMEASURED", token_savings="UNMEASURED")
  - `python -m v7_harness.cli receipt-run --task-id U07 --actor Antigravity -- python -c "print('v7 harness smoke verified')"` -> exit 0 (output_hash verified)
  - `python -m v7_harness.cli receipt-run --task-id U07 --actor Antigravity -- python -c "import sys; sys.exit(7)"` -> exit 7 (child failure exit code propagation verified)
  - `python -m v7_harness.cli eval-next --current-task-id U07 --next-task U08` -> exit 0 (eligible=True, plan_mutated=False)
  - `python -X utf8 -m v7_harness.cli report --result "v7 minimal automation harness implemented" --changed "v7_harness/*" "tests/*" --verification "37 tests passed" "receipt success exit 0" "receipt failure propagation exit 7" --risks "None" --next-action "Codex review for U08 readiness"` -> exit 0
- Remaining risks: 대규모 파일트리 스냅샷 시 I/O 시간 및 실제 멀티프로세스 동시 락 경합은 U08 실측 대상. 비용·토큰 절감은 비교 측정 전까지 `UNMEASURED`.
- Next action: Codex가 변경 범위 및 검증 증거(37개 테스트, receipt-run exit 0/exit 7 전파, report --verification)를 독립 재검증하고 U07 Verdict 판정 및 U08 활성화 여부를 결정한다. (사용자 할 일 없음)

## Review

- Verdict: PASS
- Evidence: Codex 독립 재검증에서 `python -m unittest discover -s tests -p "test_*.py"` exit 0(37개), 비Git snapshot·benchmark·eval-next·compileall exit 0, receipt 성공 exit 0, 자식 실패 exit 7 전파, `report --verification` exit 0을 확인했다. Git 스냅샷 경로는 임시 Git fixture 테스트로 검증됐다.
- Acceptance: context lease, 추가 전용 intent ledger, proof receipt, 상태/WIP/owner 불변식, managed/standalone fail-closed, Git/비Git snapshot, 간결 보고, PLAN 비변형 다음 단계 판정, A/B 훅의 9개 조건을 코드와 테스트로 확인했다.
- Remaining risk: 대규모 트리 I/O와 실제 멀티프로세스 락 경합은 미실측이며 비용·토큰 절감은 `UNMEASURED`다. 실행 중 생성된 `__pycache__`는 삭제 승인 없이 보존했다.
- Prior Review History (REWORK):
  - Evidence: Codex 독립 재검증에서 전체 35개 테스트와 snapshot/benchmark/eval-next/compileall은 exit 0이었으나, 카드에 기록된 `receipt-run ... -- python ...`는 `--`를 실행 파일로 해석해 receipt 내부 exit 127이었고, 간결 보고 명령은 `--verification`을 지원하지 않아 CLI exit 2였다.
  - Required fix: `receipt-run`이 문서화된 `--` 구분자를 제거해 실제 명령을 실행하도록 하고 성공 receipt의 프로세스 종료 코드를 CLI 종료 코드에 반영한다. `report`가 검증 항목을 명시적으로 받거나 동등한 검증 정보를 출력하도록 계약·테스트·카드 증거를 일치시킨다.
