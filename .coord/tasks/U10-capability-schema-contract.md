# [U10] capability·schema contract

- Status: DONE
- Owner: Codex (implementation executor: Antigravity via antigravity-bridge)
- Conversation: [U10] capability·schema contract
- Depends on: U09
- Started at: 2026-09-17
- Scope: 신규 versioned JSON Schema, SQLite DDL v1 및 forward migration metadata/checksum, Authority Matrix 순수 validator, schema/app/capability 호환성 판정, 핵심 DB 불변식 계약, 임시 로컬 DB 계약 테스트, 이 카드와 PLAN의 U10 상태
- Excludes: 기존 v7 동작 변경, 실제 runtime DB/daemon/Named Pipe/worker launch/MCP adapter, PLAN/card 권위의 DB 대체 또는 자동 덮어쓰기, secrets/full prompts/full model outputs 저장, U11 생성·시작, dangerous permission 확대, push/deploy/install/account·credential 변경
- Outcome: U09 v9의 capability·schema·authority·fencing·delivery/effect/receipt 계약을 실행 가능한 최소 모듈과 재현 가능한 테스트로 고정
- Acceptance: 필수 15개 테이블, versioned command/envelope/result/capability schema, migration checksum/forward-only/idempotency, Authority Matrix, app/schema/capability compatibility, stale fence 및 UNKNOWN effect retry 거부, delivery/effect/receipt 기본 계약이 임시 SQLite 테스트에서 검증되고 기존 37개 테스트가 통과
- Verification: `python -m unittest discover -s tests -p "test_*.py"`, `python -m compileall -q v7_harness tests`; 신규 계약 테스트 수와 전체 테스트 수, 각 exit code를 기록

## Decisions

- `docs/01 + .coord/PLAN.md + task card`가 계획 권위이며 DB는 execution projection이다.
- SQLite 직접 연결은 U10 테스트 프로세스의 임시 로컬 DB로만 허용한다.
- 비용·토큰 절감은 `UNMEASURED`로 유지한다.

## Work log

- 2026-09-17: 정본 규칙, U09 설계·카드, PLAN, 기존 v7 harness/tests 구조를 확인하고 U10을 `ACTIVE`로 점유했다. 현재 디렉터리는 비Git이므로 `git status --short`는 exit 128이며 git init은 수행하지 않는다.
- 2026-09-17: `antigravity-bridge` job `mu4eh6wc_89qlfp`에 단일 목표와 제한 경로, sandbox=true, auto_approve=false를 부여했다. 10분 print timeout으로 정상 결과 없이 종료됐지만 이후 filesystem 검사에서 부분 초안과 테스트가 생성된 것을 확인했다. 기존 `v7_harness/__init__.py`의 범위 밖 export 변경은 측정된 기존 상태로 복구했고, 초안의 free-form result/event payload 저장은 artifact ref/hash-only로 보강했다.
- 2026-09-17: Codex가 `v7_harness/contracts/**`에 versioned schema, Authority Matrix validator, compatibility 판정, DDL/migration, lease/fence/delivery/effect/receipt/promotion transaction contract를 구현했다. E1/E2 실측에 따라 exit 0·DONE 문구를 성공 근거로 쓰지 않고, ERROR+불명 effect를 UNKNOWN/non-retryable로 처리하며 503을 TRANSIENT_CAPACITY로 분류했다.
- 2026-09-17: Claude Code 2.1.270 CLI preflight는 exit 0이었다. 읽기 전용 단일 CRITIC/REDTEAM 호출은 5분 이상 결과가 없어 추가 호출 없이 `UNAVAILABLE`로 기록하고 정확한 review process만 종료했다. Codex 독립 검토 결과와 미해결 위험은 `.coord/reviews/U10-claude-review.md`에 남겼다.
- 2026-09-17: R19/R24/R25 조정안은 U10 범위 밖이므로 `design feedback pending`으로만 보존하며 docs/13은 수정하지 않았다. 비용·토큰 절감은 `UNMEASURED`다.
- 2026-09-17: 조율자 독립 검토에서 negative card revision, zero fence, non-hex hash, INTENDED effect 이후 SUCCEEDED 반례가 통과해 인수가 거부됐다. U10을 `READY` 재작업으로 회수한 뒤 같은 전용 단계에서 `ACTIVE`로 재점유했으며 authoritative contracts/tests만 보강한다.
- 2026-09-17: 순수 schema validator에 integer minimum/maximum과 string pattern을 구현하고 revision/fence/hash/ref 제약 및 result/envelope 교차 필드 의미 검증을 추가했다. DB hash 열도 64자리 hex로 제한했다. INTENDED/UNKNOWN/FAILED effect가 attempt success와 promotion을 차단하도록 보강했으며 delivery ACK는 CLAIMED에서만 허용하고 동일 hash 재-ACK만 멱등 처리한다. 강제 ACK 실패 시 event와 delivery 전이가 함께 rollback되는 반례까지 검증하고 `REVIEW`로 반환한다.

## Handoff

- Result: U10의 권위·schema·capability·SQLite 불변식 계약을 구현하고 임시 로컬 DB에서 migration/idempotency/checksum, active lease/fencing, stale checkpoint/receipt/effect/promotion, delivery dedupe/원자적 ACK, 미해결 effect 차단, PASS receipt/SUCCEEDED, append-only event, artifact reference, authority/compatibility 및 E1/E2 오류 계약을 검증했다. 독립 검토의 negative revision, zero fence, non-hex hash, INTENDED effect success 반례는 모두 거부되도록 수정했다. 실제 runtime DB나 daemon/Named Pipe/worker/MCP는 만들지 않았다.
- Changed: authoritative `v7_harness/contracts/**`, `tests/test_u10_contracts.py`; Antigravity partial draft `v7_harness/schema_contract.py`, `tests/test_schema_contract.py`, `v7_harness/contracts/schemas/*.json`; `.coord/reviews/U10-claude-review.md`; 이 카드와 PLAN U10 상태. 기존 v7 export surface는 복구했다.
- Checks and exit codes:
  - `git status --short` -> exit 128 (예상된 비Git 프로젝트; git init 미실행)
  - Antigravity job `mu4eh6wc_89qlfp` -> 10분 print timeout, 정상 결과 없음; partial files 발견 후 Codex 직접 검토
  - `claude --version; claude --help` -> exit 0 (`2.1.270`)
  - Claude read-only review -> 결과 미수신으로 `UNAVAILABLE`; 단일 process stop -> exit 0, 재시도 없음
  - `python -m unittest tests.test_u10_contracts` -> exit 0 (19 tests)
  - `python -m unittest discover -s tests -p "test_*.py"` -> exit 0 (74 tests; 기존 37개 포함)
  - `python -m compileall -q v7_harness tests` -> exit 0
- Remaining risks: unexported Antigravity 중복 초안은 삭제/통합 승인 전까지 남아 있다. 멀티프로세스 race/crash durability, 실제 local NTFS·network/sync 판별, broker single-writer, Named Pipe ACL, worker isolation, provider reconciliation은 U10 비범위라 `UNKNOWN`이다. 비용·토큰 절감은 `UNMEASURED`다. Claude 독립 review 결과도 `UNAVAILABLE`다.
- Next action: 조율자가 authoritative `v7_harness/contracts/**`와 테스트 증거를 검토해 U10을 `DONE` 또는 같은 U10의 `READY` 재작업으로 판정한다. U11은 이 카드에서 생성하거나 시작하지 않는다.

## Independent review

- Verdict: PASS; U10 `DONE`.
- First review rejected acceptance after four counterexamples were reproduced: negative card revision, zero fence, non-hex 64-character hash, and `INTENDED` effect followed by `SUCCEEDED`.
- Rework review independently reran `python -m unittest tests.test_u10_contracts` (19 tests, exit 0), full discovery (74 tests, exit 0), `compileall` (exit 0), and direct counterexample probes (all rejected as required, exit 0).
- Deferred without mutation: unexported Antigravity duplicate drafts, U11+ runtime concerns, and savings claims (`UNMEASURED`).

## Design feedback pending

- Claude 지원 메모의 R19/R24/R25 문구 조정 제안은 U10 범위 밖이다. docs/13 수정 없이 후속 설계 검토 입력으로만 보존한다.
