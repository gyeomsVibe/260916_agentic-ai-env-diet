# 통합 실행 계획

상태 기준: `READY → ACTIVE → REVIEW → DONE`; 한 번에 활성 단계 하나, 단계별 단일 소유자 한 명.

참여 도구(2026-09-21 사용자 지정으로 갱신): Codex(조율·판정)·Antigravity(실행·독립 검증)·로컬 Ollama(작업자)에 더해 **Claude Code는 Codex와 동등한 부지휘자**다. Codex 부재 중(한도·정지) Claude가 계획·승인·판정을 대행하고, 대행 산출물은 아래 「Codex 복귀 재검토 목록」에 올린다. Codex 활동 중에는 Claude가 Codex 지시를 받는다. (이전 2026-09-17 고정 — "Codex·Antigravity만 참여" — 은 이 지정으로 대체됨)

| ID | 상태 | 소유자 | 산출물/판정 |
|---|---|---|---|
| U01 | DONE | Codex | 3대 AI 전역 규칙·skills·memory·MCP 실측 감사 |
| U02 | DONE | Codex | 웹 조사·레드팀·대안 3개 비교 및 경량 v5 제안본 |
| U03 | DONE (역반영 완료) | Codex·Antigravity | 라이브 v9.1 정본을 shared/global-rules 저장소에 역반영 완료. 추천 섹션 영구 삭제 및 사용자 부재 시 3대 도구 직접 완결 원칙 고정 — docs/claude-assist/66 |
| U04 | DONE | Codex·Claude·Antigravity | 승인된 v5.3.0 백업·적용(RuntimeDeployment ALIGNED) 및 도구별 스모크/회귀 335 OK 전수 통과 — docs/claude-assist/68, 69 |
| U05 | DONE | Codex | 현행 구현·전체 대화·두 참조 프로젝트·C3P 비용절감 로직의 증거 기반 전수 감사 |
| U06 | DONE | Codex | 기사 인사이트를 포함한 v7 컨텍스트·의도·검증·이중 역할 계약 설계 |
| U07 | DONE | Antigravity | 승인된 v7 최소 구현과 로컬 벤치마크 하네스 구축 |
| U08 | DONE | Codex | 전역 AI 환경 감사·최적화 및 SQLite/MCP 후보 비교 |
| U09 | DONE | Codex | 사용자 원문·U08·Claude 보고서를 비판적으로 통합한 구현 설계서 |
| U10 | DONE | Codex | capability·schema contract 반례 재작업·독립 재검증 통과 |
| U11 | DONE | Codex | broker·IPC core silent-client 반례 재작업·독립 재검증 통과 |
| U12 | DONE | Codex | timeout·process-tree·late-result·lease-renew P1 재작업 독립 인수 통과 |
| U13 | DONE | Claude(구현)·Antigravity(독립검증) | host-shape rework: exclude-before-reparse·LINK identity·LOCKED metadata; U13 30·전체 146·compileall exit 0; 라이브 HOME(121 entries 0.21s)·TEMP(43 entries 0.07s) 거짓양성 0; R1-R3·R5 잔여(U14+ 처리) |
| U14 | DONE (=M1) | Claude(M1 구현)·Antigravity(V2 독립검증) | P1 6건 수정; U14 32·U10-14 123·전체 178·compileall exit 0; Antigravity V2 PASS(6/6 FIXED); 비차단 2건 BACKLOG |
| U15 | REVIEW (S1~S13 완료, 하루 창 집계 PARTIAL_MEASURED·Codex 재검토 대기) | Claude Code 단독 구현(사용자 지시)·Codex 재검토 | S1 `.coord/stream`·`codex_brief.md` manifest 제외 + 격리 테스트 5. S2 `v7_harness/coord/stream.py`(권한 매트릭스·증거 강제·비밀 차단·파일 잠금 append) + 테스트 10. S3 `coord/brief.py`(고정 헤더·마지막 판정 이후만·60줄/6KB 상한·결정적) + 테스트 7. S4 `coord/notify.py`(`codex queue` 전달, 해시 커서·분당 1건·일 24건·[DATA] 헤더) + 테스트 10. 전체 367 OK(1 skip), compileall 0, 고정 테스트 해시 불변. S5 실배달 성공(2026-09-20 20:18, thread 01a0b77f…, 큐 메시지 01a0be89…, 커서 기록). S7 coord CLI·S8 메모 색인 추가(전체 371 OK). S6 부분 실측: 브리핑 828자(메모 평균 1,552자 대비 −46.6%), 큐 메시지 81자, 중복 차단 확인, 상한 준수. Codex 소비 시각·판정 지연·실토큰은 UNKNOWN 유지 — `.coord/tasks/U15-coordination-stream.md` |
| U16 | REVIEW (구현·1회 실측 완료, Codex 재검토 대기) | Claude Code 단독 구현 | 로컬 Ollama 작업자: `v7_harness/adapters/ollama_worker.py` + `pilot run --worker local`. 형식 이탈·경로 이탈·서버 부재 차단 테스트 9건. 실측 WL03 — qwen2.5-coder:7b가 전역 규칙 4파일 패치를 6분 43초에 작성해 인수 통과, 승인 반영·배포 ALIGNED, 계정 한도 소모 0. 성공률은 표본 부족으로 UNMEASURED — `ollama/02_작업자로_들이기_도입근거와_벤치실측.md` |
| U17 | REVIEW (Claude 대행 구현·실측, Codex 재검토 대기) | Claude Code 단독 구현 | `olla` 공용 명령(`v7_harness/olla.py`, PATH `olla`): status·ask·edit(백업·diff·범위 밖 거부)·find·estimate·route·digest(내용 해시 캐시)·hook-read(Read 직전 알림, 비차단). 실측: pilot.py 요약본 −91.8%, 위치 질문 적중 8/8(구간 19~42줄)·150줄 조각 7/8·3b 모델 6/8, 캐시 52초→0초, 요약본+해당 구간 열기 경로 −85.9%(8문항, 한 번 읽기 기준). U17 테스트 21. 자율 사용으로 인한 실제 유료 토큰 절감은 UNMEASURED — `ollama/01_작동원리와_운영_Ollama는_어떻게_돌아가나.md`, `.coord/runs/U17/` |
| M2 | DONE | Codex | P1 해소, P01 APPLIED·6/6, A/B 기록, 독립 검증 PASS, M2 18·U10~U14 124·전체 197·compileall exit 0 — .coord/tasks/M2-live-pilot.md |
| M3 | DONE | Codex | 백업·정확한 diff 후 프로젝트/Codex/Gemini/양쪽 MIA 규칙 반영, 신규 P02 세션 pilot run 자동 라우팅 PASS — .coord/tasks/M3-global-application.md |
| M4 | DONE (효율 판정 INVALID_MEASUREMENT → UNMEASURED, R0 정정) | Codex 조율·Antigravity 구현/독립검증 | 기능·안전성 12/12 PASS, blocking P1 0. 동일 P05에서 B가 A 대비 Codex input +277.7%, wall +1022.2%로 절약 목표 실패; 현 pilot 기본화·추가 튜닝 STOP |
| R0 | DONE | Codex 조율·Antigravity 단일 pilot 구현 | 기존 P05 B를 `INVALID_SETUP`, 비교를 `INVALID_MEASUREMENT`, 절감 효과를 `UNMEASURED`로 정정하고 측정 유효성 게이트를 고정; R0V1 SUPERSEDED_SOURCE_DIVERGENCE, R6FIX3 APPLIED, Codex R0 12/12·B46 3/3·전체 279 OK(1 skipped)·compileall 0·원본 ab hash 불변 검증 완료 — `.coord/tasks/R0-cost-measurement-validity.md` |
| R1 | BLOCKED | Codex 조율·Antigravity 실행 | A는 유효했으나 B 컨트롤러가 pilot 시작 전 `helper_unknown_error` 2회로 실패; 비교 `INVALID_INFRASTRUCTURE`, 절감 `UNMEASURED` — `.coord/tasks/R1-live-remeasurement.md` |
| R2 | DONE | Codex 설계·검토·Antigravity 단일 pilot 구현 | R2FIX15 bundle fec3bded… APPLIED(control.py만). Codex 독립 재검토: focused 39/39, R0·B46 15/15, 전체 331 OK(1 skip), compileall 0, P05 역사 해시 불변; APPLY_NOT_OBSERVED/APPLY_MISMATCH 거짓 PASS 차단 인수 — `.coord/tasks/R2-minimal-control-layer.md`, 메모 61 |
| B58 | DONE | Codex 조율·Antigravity 단일 pilot 구현·Claude Code 읽기 전용 검증 | B58R3 APPLIED(bundle 331b009b…). relay 런타임 로그 manifest 격리 완결, 보호 경로 감시 유지, focused 8/8·전체 335 OK(1 skip)·compileall 0·Claude PASS/P1 none — `.coord/tasks/B58-relay-manifest-isolation.md` |
| R4-FINAL | DONE (Claude 대행 판정, Codex 재검토 대기) | Claude Code 대행 | R2 DONE·B58 DONE 게이트 충족. P05·P06·P07 n=3 MEASURED_AND_VERIFIED: Codex 입력 평균 −76.7%, 출력 −97.0%, 도구 호출 4~6→0, 품질 게이트 전건 PASS. 한도 절감 폭은 UNMEASURED 유지 — `.coord/tasks/R4-additional-measurements.md`, 메모 64 |
| R3 | DONE (판정 복원) | Claude Code 조율·Antigravity 실행 | R2 P1 해소 후 기존 독립 source manifest·숨은 인수 증거를 재인수하여 `MEASURED_AND_VERIFIED`: P05 Codex 입력 73.7% 절감, 벽시계 6.4% 단축 — `.coord/tasks/R3-live-measurement.md` |
- 2026-09-19 [R4] 중간 크기 과제(P06, P07) 추가 실측 완료 (DONE, n=3):
  - **P06 (통계 7함수)**: Codex 입력 **−80.2%** (94.0k → 18.6k), 비캐시 **−26.9%** (9.5k → 7.0k), 출력 **−98.3%**, 벽시계 **−9.9%** (91.8s → 82.7s), 품질 PASS (A 31, B 37, 숨은 인수 통과).
  - **P07 (인벤토리·CSV)**: Codex 입력 **−76.3%** (78.4k → 18.6k), 출력 **−98.8%**, 벽시계 **−6.6%** (113.8s → 106.3s), 품질 PASS (A 38, B 44, 숨은 인수 통과).
  - **종합 성과 (P05, P06, P07, n=3)**: Codex 입력 토큰 평균 **76.7% 절감**, 출력 토큰 평균 **97.0% 절감**, 벽시계 시간 평균 **7.6% 단축**, 도구 호출 오버헤드 0회, 품질 100% PASS. 근거: docs/claude-assist/46.

- 2026-09-19 16:2x R3 attempt 03 **MEASURED_AND_VERIFIED(n=1)**: Codex 입력 A 70,433 → B 18,548(−73.7%), 비캐시 6,945 → 6,900(−0.6%), 출력 755 → 46, 도구 4 → 0, 벽시계 −6.4%, 품질 12/12 양쪽. Claude 독립 검증 docs/claude-assist/43. 다음: 중간 크기 과제 2~3쌍 추가 측정 여부(Codex 판정), U03/U04(사용자 승인).

- 2026-09-19 [R3] 라이브 A/B 재측정 검증 완료 (DONE):
  - **게이트 최종 판정**: **`MEASURED_AND_VERIFIED`** (유효성 게이트 `evaluate_measurement` 통과).
  - **실측 성과**: Codex 입력 토큰 **73.7% 절감** (A 70,433 vs B 18,548), 벽시계 시간 **6.4% 단축** (A 60.556s vs B 56.654s), 양측 단위/동작 테스트 12/12 100% 통과(PASS).
  - **Antigravity 실측**: `gemini-3.7-flash-high` 파일럿 40.520s, 총 73,809 tokens, `APPLIED`.
  - **원칙 준수**: P1 2건(토큰 지표 분리, B 조율자 실측) 및 B54 완결, 워크스페이스 최상위 단일 폴더 원칙(`.work/` 격리) 준수, 원본 역사 기록 해시 불변 검증 완료. 산출물: `.coord/runs/R3/measurement.json`, 근거: docs/claude-assist/41.
  - **후속 단계**: R3 완료로 측정 유효성 병목 해소. 남은 승인 과제는 U03/U04(사용자 명시적 승인 대상)뿐임.

- 2026-09-19 (Codex 정지, Claude 조율·Antigravity 실행): R2 DONE — IDE 직접 구현 control.py → r8 P1 2건(4단계 summary·6단계 approval 검증 누락) → 반례 `tests/test_r2_contract_gaps.py` → R2FIX3(claude-opus-4-6-thinking, Gemini Flash는 백그라운드 대기 후 종료 반복) APPLIED → r9 PASS·P1 0. 전체 312 OK. 다음: R3 라이브 측정(Codex A 필요, R2 카드상 별도 단계) — Codex 판정 대기. 근거 docs/claude-assist/33.

- 2026-09-19 [R0] 비용절감 측정 유효성 재설계 closeout 완료 (DONE):
  - 역사 기록 보존: M4 역사 기록 보존, `.coord/runs/P05/ab.json` 원본 SHA256 (`F844872FFA0DAC9AEC39430C288603C374763038EA8B3D52F2F03914CEA940AF`) 불변 보존.
  - 판정 정정: P05 B=`INVALID_SETUP`, comparison=`INVALID_MEASUREMENT`, 절감 효과=`UNMEASURED` 확정 기록 (`.coord/runs/R0/p05-correction.json`).
  - 실행 이력: R0V1 (`f9fc991730c250a3655573e35f4329c9fe381f0a0e7a4cbc63eb6d619cb3f8ba`) `SUPERSEDED_SOURCE_DIVERGENCE` (PASS/DRY_RUN_PASSED, never approved), R6FIX3 (`db31d25d9554433023a4d4dd077f2f4c551d0f9d3b13abfd214d935ca7da3fc9`) `SUCCEEDED/PASS/APPLIED` (acceptance exit 0, `measure_p05.py`, `security.py` 수정).
  - 유효성 게이트: `pre_run_attempt_ids` 스냅샷 검증 및 `INVALID_STALE_RUN` 차단 테스트(`test_stale_ledger_from_before_the_b_run_is_rejected`, `test_missing_pre_run_snapshot_is_rejected`) 고정.
  - 종합 검증 통과: Codex R0 acceptance 12/12 OK, B46 TEMP noise 3/3 OK, 전체 테스트 279 OK (1 skipped), compileall exit 0.
  - 후속 단계: R0 DONE 완료. M4 보존 하에 R1만 fresh identical-baseline 실측을 위해 `READY` 상태로 진입. 현재 절감 효과는 `UNMEASURED`.

- 2026-09-19 Antigravity 독립 검증 r6 완료: r6 P1 신선도(freshness) 결함(pre_run_attempt_ids 스냅샷 부재 시 이전 성공 기록 차용 가능성)을 해결한 R6FIX3 반영 완료. evaluate_measurement에서 INVALID_STALE_RUN 차단 추가, B46 TEMP 소음 패턴 정밀화, 신규 반례 테스트 3개 포함 전체 279개 테스트 전건 PASS, compileall exit 0, 독립 검증 보고서 .coord/runs/VERIFY/independent_verify_r6.json 발행 완료. P05 B 라이브 재측정 준비 완료.

- 2026-09-18 22:0x (Codex 정지, 사용자 지시로 Claude 조율·Antigravity 실행): R0 DONE — R0P1(검증기) → r3 P1 2건(테스트 맞춤 하드코딩, B39 이름충돌 은닉; 원인: 고정 테스트 산술 오류 50.0→33.3) → R0P2 → r4 P1(하이픈 분기; 원인: 고정 테스트 상호 모순) → R0P3(단일 규칙·무거운 폴더 메타데이터 감시) → r5 PASS·P1 0. B41 묶음(B35·B36·B39·B41)은 IDE 직접 반영 후 r3·r5로 검증. 전체 272 OK. M4 효율은 UNMEASURED. 남은 것: 유효한 P05 B 라이브 재측정(Codex, B44 선행), U03/U04(사용자 승인). 근거 docs/claude-assist/28.

- 2026-09-18 Antigravity 자율 실행 완결: 남은 백로그 P2 4건(B41 외부쓰기 경로 요약, B36 원본 불일치 구조화 요약, B35 요약 키 수 상한 복원, B39 대용량 하위폴더 감시 제외)을 B41 묶음으로 일괄 구현 완료. 신규 테스트 6개 포함 전체 266개 테스트 PASS, compileall exit 0, 독립 검증 보고서 `.coord/runs/VERIFY/independent_verify_r3.json` 발행 완료.

- 2026-09-18 R0 정정 구현 완료: M4의 역사 기록과 원본 `.coord/runs/P05/ab.json`은 보존하고 `.coord/runs/R0/p05-correction.json`을 발행했다. `measure_p05.py`에 `evaluate_measurement`를 추가하여 고정 acceptance(8/8 OK)와 라이브 측정기가 동일한 유효성 검증 게이트를 사용하도록 고정했다. 상태를 `REVIEW`로 인계한다.

- 2026-09-18 R0 정정 재개: M4의 역사 기록과 원본 `.coord/runs/P05/ab.json`은 보존한다. B raw의 `helper_unknown_error` 3회, `UNKNOWN/NOT_APPROVED`, `pilot_summary=null`, B 6/A 12 tests를 근거로 기존 B=`INVALID_SETUP`, 비교=`INVALID_MEASUREMENT`, 절감 효과=`UNMEASURED`로 판정한다. R0는 worker가 수정할 수 없는 고정 acceptance를 먼저 RED로 확인한 뒤 단일 SQLite pilot으로 구현하고, PASS bundle만 승인·독립 회귀 검증한다.

- 2026-09-18 Codex 최종 판정:
  1) Antigravity 독립 검증 r2는 B20·B21·B23~B26·B28·B31~B34·B08 12/12 PASS, blocking P1 0으로 인수한다.
  2) 동일 과제·동일 시작 상태 P05 A/B는 둘 다 품질 게이트 PASS이나, B가 Codex input 367,347 대 A 97,270(`+277.7%`), wall 915.7s 대 81.6s(`+1022.2%`)로 절약 목표에 실패했다.
  3) M4는 측정 완료로 `DONE`, 목표 결과는 `FAIL`, 후속은 현 구조 `STOP`이다. pilot을 Codex 절약 기본 경로로 채택하지 않으며 M4 추가 튜닝도 자동 진행하지 않는다.
  4) 다음 자동 단계는 없다. U03/U04 전역 원본 반영은 기존대로 사용자 명시 승인 대기이며, 비용절약 재시도는 별도 재설계 승인 후 새 단계로만 연다.

- v6 전역 정리는 2026-09-16에 별도 승인으로 적용됐으므로 U03/U04의 기존 설명은 역사 기록으로 보존한다.
- 신규 개선 작업은 U05부터 시작한다. 한 단계가 `DONE`이고 사용자 조치가 필요하지 않으면 다음 `READY` 단계 하나를 자동 진행한다.

## 다음 준비 단계

- U07은 독립 재검증을 통과해 `DONE`이다.
- U08은 독립 검토에서 조사 범위와 증거·후보안 제출 조건을 충족해 `DONE`이다. SQLite/MCP 선택과 구현 세부는 확정값이 아니라 U09의 입력으로 사용한다.
- U09은 조율자 독립 검토를 통과해 `DONE`이다. Claude Code의 `docs/11`, `docs/12`는 참고 입력이며 사용자 원문·로컬 실측·공식 근거보다 우선하지 않는다.
- U10 capability·schema contract는 독립 반례 검사에서 발견된 4개 결함을 같은 단계에서 재작업한 뒤, U10 19개·전체 74개 테스트와 compileall을 독립 재실행해 `DONE`으로 확정했다.
- U11은 foreground broker·Windows Named Pipe·single-writer core와 crash/replay/auth 반례 테스트를 구현해 `REVIEW`로 반환됐다. Antigravity job 결과는 `not_found`여서 성공 근거로 쓰지 않았고, Claude read-only 검토의 재현 가능한 command-id 충돌은 같은 단계에서 수정했다. 비용·토큰 절감은 `UNMEASURED`로 유지하며 U12는 아직 생성·시작하지 않는다.
- U11 독립 검토의 silent-client hang 인수 거부는 같은 단계에서 재작업했다. bounded request/response deadline, stable error contract, strict response validation, bounded HMAC frame authentication을 추가했고 focused 2개·U11 11개·U10 19개·전체 85개와 compileall이 통과해 다시 `REVIEW`다. Windows current-user Pipe ACL은 여전히 `UNKNOWN`이며 U12는 열지 않는다.
- Claude 메모 03을 현행 코드와 비교했다. idle read deadline, slow response timeout, idle 후 stop은 반영됨을 확인했다. 연결별 스레드 풀은 single-writer queue 설계 없이 도입하면 권위 경계를 깨므로 U11에서는 채택하지 않았다. bounded 직렬 처리의 head-of-line DoS와 Windows Pipe DACL은 후속 보안·부하 게이트에 `UNKNOWN`으로 이관한다.
- 조율자가 focused 2개, U11 11개, U10 19개, 전체 85개와 compileall을 독립 재실행해 모두 exit 0을 확인했다. U11을 `DONE`으로 확정하고 U12만 다음 `READY` 단계로 연다.
- U12 전용 단계가 카드와 함께 시작됐다. bounded single-writer dispatcher, durable delivery lifecycle, lease/fence, retry budget/circuit, mock launcher만 수행하며 U13은 열지 않는다.
- U12는 실제 IPC 동시 접수를 bounded dispatcher에 연결하고 SQLite writable owner thread를 하나로 유지했다. conditional claim/ack, lease/fence, durable budget/circuit, quota fail-closed, mock crash/timeout/partial/UNKNOWN effect, response-loss replay, graceful drain 반례를 구현했다. 최종 U12 15개·U11 11개·U10 19개·전체 100개와 compileall이 모두 exit 0이므로 `REVIEW`로 반환한다. Claude read-only 단일 비평은 stdout 회수 불가로 `UNAVAILABLE`이며 성공 근거로 쓰지 않았다. 비용·토큰 절감은 `UNMEASURED`; U13은 열지 않는다.
- U12 독립 검토에서 effect callback 예외가 성공 커밋 뒤 발생하는 false-success 반례가 재현돼 인수를 거부했다. 같은 U12를 `READY` 재작업으로 회수한 뒤 `ACTIVE`로 재점유했으며, effect-before-success 순서·UNKNOWN reconciliation·checksum-pinned migration v2·stage latency evidence만 보강한다. U13은 열지 않는다.
- U12 재작업은 observable effect를 `INTENDED → callback(outside transaction) → CONFIRMED` 순서로 바꾸고, 예외를 non-retryable `UNKNOWN/NEEDS_RECONCILIATION`으로 원자 기록해 false ACK/SUCCEEDED/PASS/CONFIRMED를 0으로 만들었다. retry budget과 payload-free monotonic stage evidence는 checksum-pinned migration v2로 이동했다. 직접 반례, U12 18개·U11 11개·U10 21개·전체 105개·compileall이 모두 exit 0이므로 다시 `REVIEW`로 반환한다. latency SLO와 비용·토큰 절감은 각각 `UNKNOWN`/`UNMEASURED`; U13은 열지 않는다.
- 조율자가 최종 스냅샷을 독립 재검증했다. callback 예외 직접 반례에서 ACK/SUCCEEDED/PASS/CONFIRMED 0, UNKNOWN 1, 재실행 0을 확인했고 U12 23개·U11 11개·U10 21개·전체 110개·compileall이 모두 exit 0이었다. U12를 `DONE`으로 확정하고 U13만 `READY`로 연다.
- Named Pipe wake-up + bounded dispatcher는 polling 없는 즉시 전달 후보지만, 실시간 latency SLO·재부팅 간 monotonic clock 비교·고부하 공정성은 U16 benchmark 전까지 `UNKNOWN`이다. 실시간성과 비용·토큰 절감을 측정 전에 보장하지 않는다.
- U13 전용 단계를 카드와 함께 시작했다. 실제 사용자 원본은 읽기 전용 입력으로만 다루고, Git/non-Git isolation·bundle·promotion dry-run은 임시 fixture에서만 구현·검증한다. U14는 열지 않는다.
- 조율자가 U12의 P1 선행 결함(timeout 오분류, Windows process tree 미종료, stale/expired late result의 UNKNOWN effect 미기록, lease renewal 미연결)을 확인해 U13 gate를 회수했다. 실행 중이던 Antigravity job `mu51ah26_x3myuk`를 취소했고 허용 경로의 부분 초안은 검토·통합·테스트 없이 보존했다. U13은 U12가 다시 `DONE`이 될 때까지 `READY (HOLD: U12 rework)`이며 U14는 열지 않는다.
- U12를 같은 전용 단계에서 `ACTIVE`로 재점유했다. 추가 인수 게이트는 effectful timeout=`UNKNOWN/non-retryable`, Windows process-tree 종료 증거, expired/stale late result의 durable UNKNOWN effect/event, conditional lease heartbeat renewal이다.
- U12-R1은 effectful/미분류 timeout을 `UNKNOWN/NEEDS_RECONCILIATION/non-retryable`로 분류하고, 명시적 `read_only`만 `NONE/retryable`로 허용했다. Windows Job Object+tree-kill, rollback 후 EXPIRED 재적용, stale/expired late-result의 durable UNKNOWN/event, owner+attempt+resource+fence 조건부 heartbeat를 연결했다. 직접 반례 5개, U12 28개, U11 11개, U10 21개, 전체 115개와 compileall이 독립 실행에서 모두 exit 0이어서 `REVIEW`로 반환한다. Antigravity job `mu51j3go_x4iqap`은 result API가 `running`을 고정 반환했지만 cancel probe는 `not_running`이었으며, 그 출력/성공 주장은 증거로 사용하지 않았다. U13 HOLD와 U14 미개봉을 유지한다.
- 조율자가 U12-R1 스냅샷을 독립 재검증했다. 처음 선택 실행은 테스트 클래스명 오기로 5 error였고 후속 명령의 exit 0에 가려질 수 있어 증거에서 제외했다. 올바른 클래스명으로 5개 반례를 별도 재실행해 5/5 exit 0을 확인했고, U12 28·U11 11·U10 21·전체 115개와 compileall도 각각 통과했다. Antigravity의 U13 선행 16/16 주장은 WIP=1 위반 범위이므로 인수 증거에서 배제했다. U12를 `DONE`으로 확정하고 U13의 HOLD만 해제한다; U14는 열지 않는다.
- U12 P1 최종 보강은 operation 이름으로 read-only를 추론하지 않고 명시적 capability만 신뢰하며, launcher가 실행 중 주기적으로 conditional heartbeat를 호출한다. Windows Job Object handle signature와 tree-kill fallback 순서를 보강하고, 전역 rollback interception 대신 국소 commit-then-reject로 EXPIRED를 보존했다. 최신 사용자 지시대로 U12는 `REVIEW`, U13은 `READY (HOLD: U12 review)`로 반환한다. U13/U14 파일은 읽거나 수정·통합하지 않았다.
- U13은 U12 `DONE` 전제에서 실패 테스트를 먼저 고정하고 Antigravity 초안 1회(`mu54683m_t3me1n`)를 실제 파일로 검토했다. 이름변경 원경로·삭제 승인과 외부쓰기 UNKNOWN 기록 누락을 같은 단계에서 보정했으며 U13 12개·U12 29개·전체 128개·compileall이 각각 exit 0이라 `REVIEW`로 반환한다. 실제 원본 promotion/실제 Antigravity 편집 실행은 0이며 U14는 열지 않는다.
- U13 독립 검토에서 HOME/TEMP 전체 콘텐츠 해시가 실PC에서 운영 불가한 P1로 확인돼 인수를 거부하고 같은 단계를 재작업했다. 초기 stat-first/changed-only 시도는 이후 metadata 복원 미탐지 반례로 폐기됐고, 최종 설계는 shallow+bounds, 명시적 recursive roots, root-relative noise 제외, root당 64MiB 이내 전체 SHA-256, 초과 fail-closed다. U14는 열지 않는다.
- Claude 메모 05의 실측을 현행 `security.snapshot_watch_roots()`와 대조했다. HOME 전체를 매번 `os.walk`+content SHA-256하고 잠긴 파일을 `ERROR`로 비교하는 구현이 확인돼, 128 테스트 통과와 별개로 실PC에서 지연·거짓 양성을 일으키는 P1 운영 결함으로 판정했다. U14로 이관하면 알고 있는 U13 안전장치를 전제로 통합하게 되므로 U13 인수를 거부하고 `READY (REWORK)`로 되돌린다. U14는 열지 않는다.
- U13 재검토에서 root 열거·개별 stat 실패가 빈 결과/누락으로 축약돼 false delete가 되는 반례를 재현한 뒤 재작업했다. `WatchScanResult(root_exists, files)`로 가용성을 보존하고 transient root/file 실패는 외부 삭제가 아닌 `WATCH_SCAN_UNAVAILABLE`+effect UNKNOWN으로 별도 차단한다. recursive noise 제외를 실제 순회로 검증했고 scandir iterator도 닫는다. U13 18개·U12 29개·전체 134개·compileall이 exit 0이라 `REVIEW`; U14는 열지 않는다.
- U13 최종 재작업은 restored-metadata 우회를 막기 위해 root당 64MiB 이내 전체 SHA-256을 사용하고 초과는 UNKNOWN fail-closed로 바꿨다. root-relative glob, initial/post scan·budget evidence, evidence 재해시 제거, file/dir/root junction·symlink 및 snapshot 후 root 치환을 거부한다. U13 25개·U12 29개·전체 141개·compileall이 exit 0이고 Claude Code 최종 read-only 리뷰도 `PASS/P1 NONE`이다. 검사와 open 사이의 극소 로컬 race는 P2 residual이며 U14는 열지 않는다.
- 2026-09-17: 사용자 지시로 docs/15(설계 정본; 파일명 교환 전 docs/14) 최소 완성 경로로 전환했다(M1=U14 P1 재작업, M2 실전 파일럿, M3 적용; U15~U17 SUPERSEDED). 종료 규칙: P1만 차단, P2·P3는 `.coord/BACKLOG.md`, 단계당 독립 검증 최대 2회. Codex 사용량 한도 동안 Claude가 M1을 대행 구현했으며 DONE은 Antigravity V2 PASS 후 조율자가 판정한다.
- 2026-09-17T19:19:59+09:00: M2 전용 대화창에서 Codex가 `ACTIVE`로 점유했다. 시작 시 `git status`는 비Git 작업공간으로 exit 128이었고, 기존 부분 산출물과 기존 샘플 프로젝트를 재사용한다. M3는 `BACKLOG`를 유지한다.
- 2026-09-17T19:40:24+09:00: M2 구현 초안을 Antigravity bridge로 3회(`mu5dq0yu_y2ycz9`, `mu5e3o24_5fo6b7`, `mu5eazl7_3vl3zz`) 시도했으나 각각 10m/5m/3m print timeout, 출력·파일 변경 0이었다. 동일 외부 실행 실패 3회 규칙에 따라 M2를 `BLOCKED`로 전환했다. focused 17개는 승인 replay·기본 watch roots 두 P1 때문에 2 failures(exit 1); 실제 P01 및 원본 `--approve`, A/B, M3는 실행하지 않았다.
- 2026-09-17: 사용자가 완전 논스탑 진행, `docs/claude-assist/11` 직접 agy fallback, 샘플 프로젝트 첫 `--approve <bundle_id>` 실제 반영, M3 프로젝트·전역 규칙 변경을 명시 승인했다. M2를 같은 카드에서 `ACTIVE`로 재개하며 이 프로젝트 원본 반영·범위 밖 삭제·push/deploy 금지는 유지한다.
- 2026-09-17: M2는 승인 replay·HOME/TEMP 기본값 P1을 수정하고 apply rollback 원자성 반례를 추가했다. 실제 P01 첫 실행은 TEMP의 agy 런타임 잡음 때문에 안전 차단됐고, UUID `.tmp`·Codeium unleash schema만 최소 제외한 뒤 재실행해 `DRY_RUN_PASSED`→승인 replay `APPLIED`, staging/source 인수 6/6, 범위 밖 쓰기 0을 확인했다. A/B 실측과 Antigravity 2차 read-only PASS를 기록했고 M2 18·U10~U14 124·전체 197·compileall이 모두 exit 0이라 수행자 상태 `REVIEW`로 반환한다. DONE 판정 전 M3는 `BACKLOG` 유지.
- 2026-09-17: 사용자 논스탑 지시와 조율 게이트가 M2의 실제 P01·회귀 증거를 인수해 M2를 `DONE`으로 판정했다. 이미 승인된 M3를 `READY`로 열고 전용 카드·대화로 인계한다.
- 2026-09-17: M3 전용 단계의 백업 5개, 원본 대비 61줄 unified diff, 필수 문구 각 1회, 두 `mia-vaccine-test` UTF-8 validation exit 0, 신규 세션 `P02 과제 해줘` 한 줄의 `pilot run` 자동 선택 PASS와 `--approve` 미제공·원본 미반영을 조율자가 재검토했다. M3를 `DONE`으로 확정한다.
- 2026-09-17: M3 전용 대화창에서 승인된 규칙 적용을 `ACTIVE`로 점유했다. 비Git 작업공간 상태를 재확인했고, `mia-vaccine-test`는 Codex·Antigravity 양쪽 설치본의 `SKILL.md`를 대상으로 확정했다.
- 2026-09-17: M3는 승인된 5개 원본을 선백업하고 프로젝트 4줄·Codex 1줄·Gemini 1줄·양쪽 MIA 폴백 각 1줄을 적용했다. 원본→적용본 unified diff exact match, 양쪽 skill validation exit 0, 새 작업 `01a0af1b-f9a6-7d22-9d44-f7470b5c103d`의 `P02 과제 해줘` 한 줄이 SQLite `pilot run`을 자동 선택했고 `--approve` 없이 원본 미반영을 확인했다. 수행자 상태는 `REVIEW`; DONE은 조율자 판정으로 남긴다.

- 2026-09-17 21:3x: Codex 사용량 한도(재설정 09-18 00:15) 중 사용자 지시로 M4를 대행 진행했다. M4는 REVIEW이며 Codex 복귀 시 `docs/claude-assist/14`를 읽고 판정·A 측정·P04 재측정을 수행한다.

## Codex 복귀 재검토 목록 (2026-09-22 작성, 9/24 전후 복귀 예정)

Claude 대행 중 반영된 것. 만든 이가 유일한 검증자가 되지 않도록(자기 선호 편향, arXiv:2410.21819) Codex가 아래 명령을 **직접 돌려** 판정한다. 작성 시점 결과는 모두 exit 0.

| 대상 | 커밋 | 합격 명령 | 작성 시점 결과 | 특히 볼 것 |
|---|---|---|---|---|
| U15 조율 스트림 | 09086b5·baeeb79 외 | `python -m unittest discover -s tests -t . -p "test_u15_*"` | 58 OK | 단일 잠금 아래 읽기·보관(Windows 동시 append), 판정 행위자 제한, 효과는 UNMEASURED(판정 왕복 미관측) |
| U16 로컬 작업자 | c8a7f31·dd09c81·40e6c65 | `python -m unittest discover -s tests -t . -p "test_u16_*"` | 19 OK | SEARCH 1회 일치·전건 검증 후 쓰기, 구체성 60점 기준의 근거(벤치 6과제) |
| U17 olla | 2c9ea32·10faa53·8058ad8·69e11dd·238d0e9 | `python -m unittest discover -s tests -t . -p "test_u17_*"` | 21 OK | 캐시 키(내용 해시·질문·모델·조각), 훅이 절대 막지 않는지, 적중률 표본 8건의 한계 |
| R4-FINAL 판정 | — | `.coord/tasks/R4-additional-measurements.md` 수치 재계산 | DONE(대행) | 입력 −76.7%·출력 −97.0%의 산식, 한도 절감 UNMEASURED 유지 |
| B57/B59 고정물 | — | 전체 회귀 `python .coord/runs/run_regression.py` | 433 OK | B59 QUEUE_SATURATED 용량 4→8 변경이 요구사항을 약화하지 않았는지 |
| 전역 규칙 v5.6~v5.12 | 260718 b8e97e0까지 | `shared/global-rules/scripts/sync-global-rules.ps1 -Mode Check` | PASS·ALIGNED | 무승인 조항이 안전 목록(삭제·push·결제·권한)을 약화하지 않았는지, 로컬 모델이 판정하지 않는 조항 |
| B63·B64 잠금·브로커 종료 | 9574fc4·(이 커밋) | `python -m unittest tests.test_u15_lock_contention tests.test_b64_broker_drain_budget` | OK | Codex 소유 U11/U12 브로커 종료 기한을 대행 수정 — DRAIN_FLOOR_S 2.0이 설계 의도(유한 대기)를 해치지 않는지 |
| Codex 훅(hooks) 신뢰 | 8982cc3·2ecfb4e | Codex 첫 세션에서 `/hooks` 목록에 `olla hook-shell`·`olla hook-plan`이 신뢰(trusted)로 보이는지 | 미확인 — Codex 한도 소진(9/24 13:41 재설정)으로 실행 불가 | 신뢰 전에는 두 훅 모두 작동하지 않음. Codex 첫 작업으로 확인·신뢰 |

