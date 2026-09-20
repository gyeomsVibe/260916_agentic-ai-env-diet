# [B58] 조율 로그 manifest 격리

- Status: DONE
- Owner: Codex 조율 · Antigravity 단일 SQLite pilot 구현 · Claude Code 읽기 전용 독립 검증
- Conversation: [B58] 조율 로그 manifest 격리
- Depends on: R2 DONE
- Started at: 2026-09-19T21:40:00+09:00
- Scope: `v7_harness/isolation/manifest.py`, B58 고정 반례와 검증 증거, 이 카드 및 `.coord/PLAN.md`
- Excludes: `.claude` 전체 제외, `.claude/settings.json`, skills/hooks/agents/commands/rules 감시 약화, 원본 직접 구현, 삭제, push, 배포, 계정·설정 변경
- Outcome: `.claude/codex-relay/**`의 런타임 로그 쓰기만 source manifest에서 제외하고 보호 설정·코드 경로 변경은 계속 탐지한다.
- Acceptance: 고정 반례가 relay 중첩 `.log` 변경에는 동일 manifest, relay 스크립트와 여섯 보호 경로 변경에는 다른 manifest를 증명한다. focused/full/compileall과 독립 manifest 검증이 통과한다.
- Verification: `python .work/b58_fixed_acceptance.py`; `python -m unittest discover -s tests -v`; `python -m compileall -q v7_harness tests`

## Decisions

- 광범위한 `.claude` 제외는 금지한다.
- 고정 반례는 pilot 전에 `.work/b58_fixed_acceptance.py`에 두고 worker 수정 범위 밖에서 RED를 확인한다.
- 구현은 B58 SQLite `pilot run` 1회에서만 생성하고 PASS bundle만 같은 task의 `--approve`로 반영한다.

## Work log

- 2026-09-19: B58 전용 단계 점유. 현행 manifest는 정확 경로/하위 트리 제외만 지원하며 `.claude/codex-relay/sent.log`를 포함하는 것을 확인했다.
- 2026-09-19: 고정 반례 4개를 먼저 실행해 relay 중첩 로그 격리 1개만 RED, 보호 경로·relay 스크립트 7종 탐지는 GREEN임을 확인했다.
- 2026-09-19: 최초 preflight는 Claude Code가 `.claude/scheduled_tasks.lock`을 초기화해 staging 중 `SourceMutationError`로 worker/attempt/bundle 없이 차단됐고 원장은 `NOTHING_TO_RECONCILE`였다.
- 2026-09-19: 안정성 확인 뒤 B58 worker 1회는 bundle `9fd09b9e...`와 고정 acceptance exit 0을 만들었으나, 잠금 중 Claude Code가 원본 `docs/claude-assist/62_r2-independent-verify-pass-and-next-steps_2026-09-19.md`를 생성해 승인 replay가 `APPROVAL_MISMATCH`로 차단됐다. 원본 구현 반영은 0이며 해당 bundle은 승인하지 않는다.
- 2026-09-19: 정본 규칙의 `SOURCE_DIVERGED` 복구 계약에 따라 새 실행 B58R1만 허용한다. 기존 staging diff를 참고로 쓰지 않고 새 source baseline에서 worker·고정 acceptance·동일 bundle 승인을 다시 검증한다.
- 2026-09-19: B58R1은 외부 변조 없이 끝났으나 worker가 테스트 대기 메시지만 반환하고 변경 0, acceptance exit 1로 `REWORK/NO_CHANGES` 판정됐다. B53 권고에 따라 `claude-opus-4-6-thinking` 모델의 마지막 B58R2를 사용하고, 실패하면 추가 자동 재시도하지 않는다.
- 2026-09-19: B58R3 실행 완료. 번들 `331b009b4aaaae7cd73a58b3fa8b9dc89c1b4aca2dc2bee95fc15d1d4f1e3da1`가 APPLIED로 정식 반영됨. 변경 파일: `v7_harness/isolation/manifest.py`, `tests/test_b58_relay_manifest.py`. 고정 인수 4/4 통과, 포커스 4/4 통과, 전체 회귀 335 통과 (1 skipped), compileall exit 0. B58 종결.
- 2026-09-19: Codex 독립 fixture는 relay log hash 불변=true, relay script와 보호 경로 7종 변경 탐지=true를 확인했다. Claude Code safe/restricted/plan/read-only 검토는 `VERDICT PASS`, blocking P1 none이다.

## Handoff

- Result: DONE
- Changed: `v7_harness/isolation/manifest.py`, `tests/test_b58_relay_manifest.py`
- Checks and exit codes: `b58_fixed_acceptance.py` 4/4 OK + `tests/test_b58_relay_manifest.py` 4/4 OK = focused 8/8 exit 0; full regression 335 OK (1 skipped) exit 0; compileall exit 0; Claude Code PASS/P1 none
- Remaining risks: 대소문자 혼합 relay 경로는 현 프로젝트의 명시된 소문자 경로 범위 밖이다. 비용·토큰 절감은 `UNMEASURED`.
- Next action: B58 선행 게이트가 끝났으므로 R4 최종 판정만 `READY`로 연다.
