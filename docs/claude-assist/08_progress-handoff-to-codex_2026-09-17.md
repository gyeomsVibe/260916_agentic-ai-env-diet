# 인계 08 — 진행 현황·남은 일·대행 결과물 (Codex 조율자에게)

## 1. 참여 도구 고정 (사용자 지시)

- 이 계획은 **Codex(조율·최종 판정)와 Antigravity(실행·독립 검증)만** 참여한다.
- Claude Code는 계획 밖 독립 도구다. 아래 대행 결과물은 Codex 사용량 한도 동안 사용자가 한시로 지시한 기록일 뿐이며, 이후 단계의 경로가 아니다.
- 반영 위치: `.coord/PLAN.md` 머리말, `docs/14` §10, `.coord/tasks/M2-live-pilot.md` Owner/Executor.

## 2. 사실 확인: 지금 Codex↔Antigravity 통신은 SQLite가 아니다

- 현재 실제 경로는 여전히 **MCP `antigravity-bridge`** 다. 근거: `~/.codex/config.toml` `[mcp_servers.antigravity-bridge]`, `~/.codex/AGENTS.md` 29행 "Antigravity 위임은 `antigravity-bridge`만 사용".
- SQLite 경로는 **부품까지 완성, 배선과 전환은 미완**이다.

## 3. SQLite 연결 구현 진척

| 구분 | 단계 | 상태 | 내용 |
|---|---|---|---|
| 계약·스키마 | U10 | DONE | 명령·봉투·결과 스키마, DDL |
| SQLite 단일 writer | U11 | DONE | BrokerCore, 잠금, 인증 IPC |
| 실행 수명주기 | U12 | DONE | lease·fence, 재시도·circuit, Job Object, timeout→UNKNOWN |
| 격리·검증 | U13 | DONE | staging, 외부 쓰기 감시(실PC HOME/TEMP 통과), patch bundle, dry-run |
| agy·Codex 어댑터 | U14=M1 | DONE | 헤드리스 JSON 판정, 인자 주입·대소문자·제어문자 차단, 재귀 방지, 대화 고정 |
| **실제 연결** | **M2** | **READY(미착수)** | 실제 agy 실행기, `pilot run` 파이프라인, 실제 반영, A/B 측정 |
| **전환·적용** | **M3** | **BACKLOG** | AGENTS.md·전역 규칙을 bridge → SQLite 경로로 교체 |

**진척률:** 부품 기준 5/7 단계 완료. 사용자 체감 기준으로는 "SQLite로 실제 위임 0건"이라 **핵심 연결은 아직 남아 있다.**
**남은 예상:** M2 1~2시간(사용자 승인 2회), M3 30분(승인 1회). 합계 약 1.5~2.5시간.

## 4. 한도 동안 대행된 결과물 (재확인 대상)

| 단계 | 대행 내용 | 독립 검증 | 증거 |
|---|---|---|---|
| U13 | 실PC HOME의 symlink 17개·TEMP 잠긴 파일로 감시가 즉시 실패하던 P1 재작업(exclude→reparse 순서, LINK 식별, LOCKED 메타데이터) + 반례 5개 | Antigravity PASS(라이브 HOME·TEMP 스모크 재실행 포함) | `.coord/reviews/U13-claude-coordinator-gate.md`, U13 카드 마지막 절 |
| U14 | 카드·실패 테스트 → 어댑터 구현 → Antigravity V1 REWORK(P1 7) | — | `.coord/runs/U14-V1-agy.json` |
| M1 | 실행 방식 전환(docs/14), BACKLOG 15건, P1 6건 수정(`adapters/validation.py` 신규) + 회귀 8개 | **Antigravity V2 PASS(6/6 FIXED)** | `.coord/runs/M1-V2-agy.json`, U14 카드 M1 절 |
| 설계 | `docs/14` 최소 완성 경로 설계, `docs/15` 단계별 지시문 | — | 파일 |

**검증 수치(최신):** U14 32개, U10~U14 123개, 전체 178개, compileall 모두 exit 0.
**주의:** U12 heartbeat 테스트가 부하 시 1/7 간헐 실패했다(단독 5/5 통과, BACKLOG B08).

## 5. Codex에게 요청

1. 위 대행 기록(U13·M1)을 **재확인만** 하고 결함 탐색으로 되돌리지 말 것(docs/14 §3 종료 규칙).
2. `.coord/tasks/M2-live-pilot.md`를 `ACTIVE`로 점유하고 `docs/15` "다음 대화창용" 지시대로 M2를 진행할 것. 구현 초안과 독립 검증은 Antigravity가 맡는다.
3. 중간 보고마다 "완료 단계 / 남은 단계 / 예상 시간"을 한 줄로 포함할 것.
