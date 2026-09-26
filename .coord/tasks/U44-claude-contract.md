# U44 — Claude Code의 UAOS 편입 계약 실행 검진·보강

- 상태: DONE (Codex 독립 판정, 2026-09-26). 작성: Claude Code, 2026-09-26. 작성자와 다른 판정자가 focused 53/53 및 전체 777/777(exit 0, skipped 4), 생산 코드 테스트 맞춤 분기 0건을 확인했다.
- 판정 대상 번들 사슬: `U44-FIX5` bundle `46297542330a4a538289b9a0184dd5bf35dec1882d1eb7c19500d689bbcdc93f`
  → `U44-FIX6B` bundle `70e33fe304cfb9718057b568ef9ada3df99fe2f58ef05a81deab80e008ac9810`.
  둘 다 현재 원본 기준 linted `worker: apply` 계약으로 재구성해 `APPLIED`했다(0토큰). 계약서:
  `.work/u44/fix5_manual.md`, `.work/u44/fix6b_manual.md`. U44-FIX·FIX3·FIX4와 이전 FIX5·FIX6B bundle은 폐기 대상이다.
- 변경 파일: `v7_harness/manual.py`, `v7_harness/cli.py`, `v7_harness/review.py`,
  `v7_harness/adapters/{claude_worker,apply_worker,lane_worker,ollama_worker,long_prompt}.py`,
  `v7_harness/execution/agy_launcher.py`, 새 테스트 `tests/test_u44_claude_contract.py`(14개)와
  `tests/test_u44_long_prompt.py`(9개). 기존 테스트는 바꾸지 않았다.

## 왜 이 카드가 생겼나 (초보자용 배경)

U38에서 Claude Code를 UAOS의 정식 작업자(`worker: claude`)와 검토자(`pilot review --reviewer claude`)로 편입했다.
그런데 U38은 **실제 `worker: claude` 호출이 한 번도 없는 상태로** DONE 처리되었다. docs/40조차 격리 플래그는 "승인된 실호출 1회가
증명하기 전까지 가설"이라고 적어 두었다. 그래서 2026-09-26에 처음으로 진짜 호출을 해 보니 아래 결함이 줄줄이 나왔다.

## 발견한 약점과 원인 (모두 실측)

| ID | 증상 | 원인 | 수정 |
|---|---|---|---|
| W1 | 첫 실호출 U44-PROBE: 파일을 안 고치고 REWORK/NO_CHANGES (1턴, $0.005) | `manual new`가 모든 작업자에게 "===FILE/===EDIT 블록으로만 회신하라"고 썼다. Claude는 도구로 파일을 고치는 작업자라 하네스는 회신 글을 적용하지 않는다 | `output_rule(worker)`: 도구 작업자(agy·lane·claude)는 "allow 파일을 직접 고쳐라, 회신은 적용되지 않는다". 작업자 SYSTEM에도 같은 규칙 |
| W2 | 생성한 claude 계약서가 전부 lint 실패(REMOTE_WITHOUT_USD_CAP) | `manual new`에 `remote_budget_usd`를 쓸 방법이 없었다 | `--remote-budget-usd` 인자 추가 |
| W3 | `judge: user`가 docs/40·도움말에는 있는데 거부됨 | `JUDGES`·`--judge`·`--coord-actor` 선택지에 user 누락 | 세 곳에 user 추가(claude 자기 판정은 계속 SELF_JUDGE) |
| W4 | 위 결함이 U38 DONE 후에야 드러남 | 새 작업자 유형을 실호출 0회로 DONE 처리 | **카나리아 규칙**(아래) |
| W5 | U44-FIX 검토: 14턴·107초·578,138토큰(캐시 읽기 497,581)·$0.47 → 80k 예산 초과로 UNUSABLE(반례 0건인데도) | 검토 프롬프트가 "필요하면 파일을 읽어라"로 탐색을 유도, 검토도 작업자와 같은 30턴 상한. 턴마다 캐시된 프롬프트를 다시 읽고 비용 관문은 캐시 읽기도 센다 | 검토 전용 `REVIEW_MAX_TURNS`(기본 4), "diff가 변경 전체다" 프롬프트, 턴 소진 시 같은 세션 `--resume` 1턴 강제 최종답(실측 1턴·48k) |
| W6 | U44-FIX4 검토가 시작도 못 함: WinError 206 | 계약서+diff 프롬프트를 명령줄 인자로 넘겨 Windows 32,767자 한도 초과 | 20,000자 초과 요청은 표준 입력(stdin)으로(실측 46,529자 정상 수신) |

관문(cost gate) 코드는 평가기라서 바꾸지 않았다. 대신 예산을 현실에 맞춘다: 검토 1회 ≈ (턴 수+1) × 프롬프트 크기.

## 실측 비교 (같은 검토자 sonnet, 같은 종류의 번들)

| 실행 | 턴 | 계수 토큰 | 비용 | 벽시계 | 결과 |
|---|---|---|---|---|---|
| U44-FIX 검토(수정 전) | 14 | 578,138 | $0.47 | 107초 | UNUSABLE(EXCEEDED) |
| U44-FIX3 검토(턴 6 상한만) | 7 | 222,708 | $0.25 | 59초 | UNUSABLE(판정 없음) |
| U44-FIX5 검토(최종) | 6 | 124,769 | $0.13 | 32초 | **PASS, WITHIN**(예산 250k) |

작업자 실호출: U44-PROBE2(수정된 하네스) PASS, 2턴, $0.0096, 7초.

## 검증

- apply 파일럿 인수: `tests.test_u44_claude_contract` + `tests.test_u38_cost_gate_and_claude_worker` → PASS.
- 스테이징 전체 회귀: FIX5 768개 OK(skipped 4), FIX6B 777개 OK(skipped 4), 모두 exit 0. 참고: FIX4 스테이징 1회차에서 19건 실패 후 재실행 2회 모두 OK → 동시 실행 간섭으로 추정, UNKNOWN.
- 변이 검사: resume 조건을 깨면(`left_usd >= 99`) U44 테스트 1건 실패 확인.
- 독립 검토: Claude 검토는 참고 증거(advisory)일 뿐이다. 판정은 Codex.

## 카나리아 규칙 (프로세스 개선 제안, Codex 채택 여부 판정)

새 작업자·검토자 유형(또는 그 어댑터의 명령줄을 바꾸는 변경)은 **실제 호출 1회(카나리아, canary)** 영수증 없이 DONE이 될 수 없다.
카나리아는 작은 계약(파일 1개 수정 + 고정 인수), 달러 상한 ≤ $0.30, 결과(턴·토큰·비용·벽시계)를 카드에 기록한다.
근거: U38은 모의(fake) 테스트만으로 DONE → 실호출 첫 회에 W1, 첫 검토에 W5, 큰 diff에 W6이 드러났다.

## W6 후속: 일반 작업자 명령줄 초과 (U44-FIX6B, 2026-09-26)

- 증상(실측): 모든 수정을 한 계약서로 묶은 U44-FIX6(36,151자)은 0토큰 apply 작업자에게조차 전달되지 못했다 — WinError 206.
  원인: 파일럿 실행기(`execution/agy_launcher.py`)가 계약서 전체를 `-p <프롬프트>` 명령줄 인자로 작업자에게 넘기고,
  claude·lane 어댑터가 다시 `claude -p`로 넘긴다(두 구간 모두 32,767자 한도).
- 수정: 새 모듈 `adapters/long_prompt.py`.
  - 실행기→우리 파이썬 어댑터(`*_worker.py`): 20,000자를 넘으면 프롬프트를 `runs/<시도>.prompt.md` 파일로 쓰고 `-p`에는 표식+경로만 넘긴다(파일은 영수증으로 남음).
  - claude·lane 어댑터→`claude -p`: 20,000자를 넘으면 표준 입력(stdin)으로 넘긴다.
  - 진짜 `agy` 실행 파일은 프롬프트 파일 기능이 문서에 없으므로, Windows에서 한도를 넘으면 시작 전에 `PROMPT_TOO_LONG_FOR_ARGV`(효과 NONE)로 거절한다 — 알아보기 힘든 WinError 206이나 재조정(reconciliation) 잠김 대신.
- 원본 반영 번들 사슬(판정 순서 중요): **FIX5(`46297542330a`, 기준 HEAD) → FIX6B(`70e33fe304cf`, 기준 FIX5 적용 상태)**.
  FIX6B 계약서: `.work/u44/fix6b_manual.md`(16,534자), 파일럿 폴더 `.work/u44/pilot6b`, 입력 원본 사본 `.work/u44/src_fix5`.
  한 번들로 합치면 현재 HEAD 하네스로는 승인 재생(replay)이 같은 WinError 206에 걸리므로 둘로 나눴다.
- 검증: 새 테스트 9개(`tests/test_u44_long_prompt.py`), FIX6B 스테이징 전체 회귀 777개 OK(skipped 4), exit 0.
  실측: 고친 하네스로 실패했던 36k 계약서(U44-FIX6-LIVE)를 다시 보내니 36,942자 프롬프트 파일로 전달되어 PASS(bundle `a9078da43e9a`, 증거용·승인 대상 아님).

## 남은 위험 (후속 카드 후보, Codex 판단)

- apply 작업자가 오류(예: EDIT_SEARCH_NOT_FOUND)로 끝나도 효과 UNKNOWN이 되어 잠길 수 있다. U44-FIX2 실측 건은 `pilot reconcile`로 `ABANDONED` 1건 조정 완료했지만, 결정적 작업자 오류를 효과 NONE으로 자동 판정하는 일반 개선은 미수정이다.
- 캐시 읽기를 전량 세는 토큰 관문은 Claude 검토에 불리하다. 관문 의미 변경은 평가기 변경이므로 사람·Codex 결정 사항이다.
- 커밋 시 칼큘레이터 관문(calculator gate)은 APPLIED 단계 파일을 요구하므로, 판정자 승인(`pilot run` 재생 + 판정자 actor) 후에만 커밋한다.

## 2026-09-26 실행창 인계

- FIX5: lint exit 0 → 고정 인수 exit 0 → 전체 768개 exit 0 → bundle `46297542330a...` APPLIED exit 0.
- FIX6B: lint exit 0 → 고정 인수 exit 0 → 전체 777개 exit 0 → bundle `70e33fe304cf...` APPLIED exit 0.
- 고정 기존 테스트 `tests/test_u38_cost_gate_and_claude_worker.py`, `tests/test_u44_claude_contract.py`는 FIX6B 전후 SHA-256 동일. 생산 코드 추가 행에서 테스트 러너·테스트명·fixture 분기 0건.
- U44-FIX2: `.coord/pilot`에서 `ABANDONED`, reconciled_attempts 1, exit 0.
- 상태는 독립 판정에 따라 `DONE`으로 전환했다.
