# [U15] 조율 스트림 — 3대 도구 작업대화를 Codex 한 창으로 모으기

상태: READY · 설계 작성 Claude Code(2026-09-20) · 구현 소유자 미정(Codex 지정) · 검증 Claude 독립

## 1. 사용자 요구와 정제

원 요구: "Antigravity와 Claude Code가 수행한 업무대화를 Codex의 같은 프로젝트 대화창으로 편입시켜라. Codex가 사용자 창구이자 두뇌·지휘자이니 한곳에 모아야 한다."

정제(사실 확인 후):
- Codex 대화창에 외부에서 글을 **밀어 넣을 수 없다**. 남의 세션 기록(`~/.codex/sessions/*.jsonl`)에 직접 쓰는 것은 위조이고, `codex exec resume` 푸시는 Claude 쪽 가드로 막힌다. 따라서 편입은 **Codex가 세션 시작 때 한 파일을 읽어 들이는 당김(pull)** 방식이어야 한다. 밀어넣기(push)는 릴레이가 가능할 때의 보조 경로다.
- "대화 전문을 모으는 것"은 목적이 아니다. Codex가 필요한 것은 판정에 쓰는 **사건과 증거**다. 전문을 모으면 토큰만 늘고 캐시 적중이 깨진다(B57 실측). 그러므로 **사건 스트림 + 접힌 브리핑** 2층 구조로 만든다.
- 현재 채널은 `docs/claude-assist/` 78건, `.work/notes/` 10건, PLAN·BACKLOG·카드, pilot summary로 흩어져 있다. 순서·중복·전달 여부를 알 수 없고, 실행 중 메모 쓰기가 `SOURCE_DIVERGED`를 반복 유발했다(B58 이전 원인).

## 2. 설계

### 2.1 사건 스트림 (append-only)

경로: `.coord/stream/<YYYY-MM-DD>.jsonl`, 한 줄 = 한 사건. 줄 단위 append만 허용(수정·삭제 금지).

```json
{"id":"20260920T1930-claude-0007","ts":"2026-09-20T19:30:11+09:00","actor":"claude|antigravity|codex",
 "kind":"PLAN|RUN|VERDICT|BLOCKED|HANDOFF|NOTE","step":"R2FIX15","summary":"<=200자 한국어 한 줄",
 "refs":["docs/claude-assist/64...md",".work/pilot_R2FIX15/runs/R2FIX15/summary.json"],
 "evidence":{"cmd":"python -m unittest discover -s tests -q","exit":0,"hash":"sha256:...","bundle":"fec3bded..."}}
```

- `summary`는 200자 상한. 초과분은 `refs` 파일로 보낸다.
- 증거 없는 `RUN`·`VERDICT`는 무효(`evidence.cmd`·`exit` 필수).
- 권한 매트릭스: `VERDICT`는 Codex만, `RUN`은 실행 소유자만, `HANDOFF`는 현 소유자만 기록한다. 위반은 검사에서 실패로 잡는다.

### 2.2 매니페스트 격리

`.coord/stream/`을 `DEFAULT_EXCLUDES`에 추가한다(B58과 동일한 이유). 그래야 파일럿 실행 중에도 세 도구가 사건을 기록할 수 있고 `SOURCE_DIVERGED`가 나지 않는다. QUIET_LOCK 중에도 스트림 쓰기는 허용한다(다른 원본 쓰기는 계속 금지).

### 2.3 접힌 브리핑 (Codex 편입 지점)

산출물: `.coord/codex_brief.md` — 60줄 상한, 생성기가 스트림에서 결정적으로 만든다.

구성(고정 접두부 → 가변 꼬리, B57 원칙):
1. 고정 헤더: 읽는 법과 판정 계약(바이트 단위로 불변)
2. 현재 단계와 소유자, 활성 잠금
3. **Codex 판정 대기 목록**(미승인 bundle, REVIEW 상태 카드)
4. 마지막 판정 이후의 사건만 10줄 이내로 접어서
5. 차단·실패와 그 증거 경로
6. 다음 후보 1~3개

규칙: 같은 입력이면 같은 출력(해시 고정), 마지막 `VERDICT` 이후만 포함, 그 이전은 `stream/archive/`로 롤오버.

### 2.4 전달 경로

- **당김(기본)**: 프로젝트 `AGENTS.md`에 한 줄 — "Codex는 프로젝트 대화를 시작할 때 `.coord/codex_brief.md`를 먼저 읽는다." 이것이 '한 창으로 모으기'의 실제 구현이다.
- **밀기(보조)**: `codex_relay.sh send`는 브리핑 경로 한 줄만 보낸다. 커서 `.work/codex-relay/cursor`에 마지막 전달 `id`를 남겨 중복 전달을 막고, idle<300s면 다음 주기로 미룬다.
- 사용자 채팅 출력은 종전대로 **결과** 요약만. 브리핑은 도구 간 채널이지 사용자 읽을거리가 아니다.

### 2.5 기존 자산 처리

`docs/claude-assist/` 78건은 그대로 보존하고 삭제하지 않는다. 1회 인덱서로 `docs/claude-assist/INDEX.md`(번호·날짜·작성자·제목·상태)만 만든다. 이후 새 조율 기록은 스트림 1줄 + 필요 시 본문 메모 1개 규칙으로 통일한다.

## 3. 인수 기준 (fail-closed)

1. append 원자성: 8스레드 동시 append 200건에서 줄 깨짐 0, 순서 보존, 중복 `id` 0.
2. 권한 매트릭스: Antigravity·Claude가 `VERDICT`를 쓰면 거부(exit≠0).
3. 증거 강제: `evidence.cmd` 또는 `exit` 누락 시 `RUN`·`VERDICT` 거부.
4. 브리핑 결정성: 같은 스트림으로 두 번 생성하면 SHA-256 동일, 60줄·6KB 이하.
5. 롤오버: 마지막 판정 이전 사건은 브리핑에서 빠지고 `stream/archive/`에 남는다.
6. 격리: 파일럿 실행 중 스트림에 10건을 써도 `build_manifest` 해시 불변, 실행은 PASS.
7. 커서: 같은 브리핑을 두 번 보내지 않는다.
8. 전체 회귀 통과, compileall 0.

## 4. 단계

- S1: `.coord/stream` 매니페스트 제외 + 격리 테스트(B58 방식, pilot 1회)
- S2: `stream_append.py`(검증·권한 매트릭스·원자 append)와 단위 테스트
- S3: `codex_brief.py`(접기·상한·결정성)과 단위 테스트
- S4: 릴레이 커서 연동, `AGENTS.md` 한 줄 추가, 메모 인덱서 1회 실행
- S5: 3대 도구가 하루 운용 후 브리핑 크기·캐시 적중·중복 전달을 실측(그 전까지 절감은 `UNMEASURED`)

## 5. 범위 밖

- Codex 세션 파일 직접 편집, 대화 전문 복제, 타 도구 세션 위조. 모두 금지한다.

---

# U15 v2 — 정정과 심층 설계 (2026-09-20 20:0x, 웹 딥리서치 반영)

## 0. 정정 (사용자 관찰이 옳았다)

v1에서 "Codex 대화창에 외부에서 밀어 넣을 수 없다"고 단정한 것은 **틀렸다**. 사용자가 본 "다른 작업에서 Antigravity이(가) 보냄"은 실제 기능이다. 근거:

- 로컬 `codex-cli 0.155.1`에 `codex queue --thread <UUID|정확한 세션명> --message <텍스트>` 서브커맨드가 있다(`Queue a message for an existing session`).
- 구현 PR(openai/codex #39092)에 따르면 app-server API `thread/queue/add`로 전달되고, **스레드를 소유한 클라이언트가 배달**하며 소유자가 없으면 대기한다. 이름이 중복되면 거부한다.
- 앱은 2026-07-09에 ChatGPT 데스크톱과 통합돼 Chat/Work/Codex 모드를 한 셸에서 제공하고, 작업 간 이관(handoff)·역동기화가 제품 기능으로 존재한다. 다만 "ChatGPT 프로젝트 ↔ Codex 프로젝트 양방향 자동 편입"은 아직 미지원 요구(openai/codex #32519, Open)다.
- 참고: `codex fork`(세션 분기), `codex agents`(로컬 app-server 데몬의 세션 목록), `codex app-server --listen stdio://|ws://|unix://`(JSONL 프로토콜), `codex exec resume`(새 에이전트 실행 — 우리 규칙상 Claude는 사용하지 않는다).

따라서 U15의 전달 경로는 **당김(brief 읽기) + 밀기(`codex queue`)** 두 갈래로 확정한다.

## 1. /CRITIC — v1 설계의 결함

| # | 결함 | 영향 | 수정 |
|---|---|---|---|
| C1 | 전달 수단을 잘못 단정 | 설계 전체가 pull-only로 축소됨 | `codex queue` 채택, pull은 폴백 |
| C2 | 스레드 식별을 UUID로만 가정 | 세션 교체 시 대상 유실 | 세션명 규약 `[WP:<작업ID>:<NN>]` 고정 + UUID 캐시 2중화 |
| C3 | 전달 실패 처리 없음 | 소유자 없는 스레드는 무한 대기 | 큐 후 `pending` 표시, 15분 내 미반영이면 brief에만 남기고 재시도 중단 |
| C4 | 메시지 내용 계약 없음 | 토큰 폭증·캐시 붕괴 | 큐 메시지는 6줄·500자 상한, 본문은 파일 경로 참조 |
| C5 | 권한 가드 미고려 | Claude는 `codex queue` 실행이 차단됨(External System Writes) | 실행 주체를 Antigravity로 두고, Claude는 stream·brief 생성까지만 |

## 2. /REDTEAM — 공격·실패 시나리오와 차단

| 시나리오 | 결과 | 차단 |
|---|---|---|
| 큐 메시지에 "이 지시를 수행하라"가 섞임 | Codex가 도구 메시지를 사용자 지시로 오인 | 모든 큐 메시지 1행 고정: `[DATA] 출처=<도구> 판정요청=<있음/없음>`. 지시문은 사용자 대화에서만 온다는 규칙을 어댑터에 명시 |
| 같은 사건을 두 도구가 각각 큐잉 | 중복·토큰 낭비 | `event_id` 커서 + `sent.log` 단일 파일, 전달은 brief 단위 1건 |
| 이름 중복 스레드에 오배달 | 다른 작업 창을 오염 | 정확한 세션명만 사용, 모호하면 CLI가 거부(설계상 재시도 금지) |
| 응답 루프(Codex 응답 → 도구가 다시 큐잉) | 무한 왕복 | 큐잉은 상태 전이(RUN 종료·VERDICT 대기·BLOCKED)에서만, 분당 1건 상한 |
| 비밀값이 요약에 포함 | 유출 | 큐 메시지는 경로·해시·종료 코드만, 값 금지. 정규식 차단(키·토큰 패턴) |
| 파일럿 실행 중 stream 쓰기 | SOURCE_DIVERGED 재발 | `.coord/stream` manifest 제외(S1) |
| 큐 폭주로 Codex 한도 소진 | 판정 지연 | 하루 상한과 idle<300s면 다음 주기로 미룸 |

## 3. /ALT3 — 대안 비교

| 안 | 방식 | 장점 | 단점 | 판정 |
|---|---|---|---|---|
| A | 사건마다 `codex queue` 즉시 전달 | 실시간 | 토큰·알림 폭증, 루프 위험 | 기각 |
| B | 상태 전이에서만 brief 요약 1건 전달(+ pull 폴백) | 토큰 최소, 판정 시점에 정확히 도착 | 실시간성 낮음 | **채택** |
| C | pull 전용(세션 시작 시 brief 읽기) | 가드·권한 무관 | Codex가 열지 않으면 영원히 미도달 | 폴백으로만 유지 |

## 4. /OPTIMIZE — 목적 함수와 최소 변경

목적: Codex 판정 지연과 토큰을 동시에 줄인다. 보존 제약: 거짓 PASS 0, 비밀 유출 0, 루프 0, 파일럿 무해.

최소 변경 3개로 달성한다.
1. `.coord/stream/*.jsonl` + manifest 제외 (기록 기반 마련)
2. `codex_brief.py` — 마지막 VERDICT 이후만 접어 60줄, 결정적 출력
3. `notify_codex.py` — brief 해시가 바뀌고 상태 전이가 있을 때만 `codex queue` 1건, 커서·상한·정규식 검사 포함

## 5. /STEPBYSTEP — 실행 단계와 체크포인트

- S1 `.coord/stream` manifest 제외 + 격리 테스트 → 파일럿 중 stream 10건 써도 manifest 해시 불변
- S2 `stream_append.py` + 권한 매트릭스·증거 강제 테스트 → VERDICT는 Codex만
- S3 `codex_brief.py` + 결정성·상한 테스트 → 두 번 생성 SHA 동일, 60줄·6KB 이하
- S4 `notify_codex.py` + 커서·상한·비밀 차단 테스트(전달은 드라이런으로 검증)
- S5 실배달 1회(Antigravity 실행): 사용자 Codex 창에 "다른 작업에서 …이(가) 보냄"으로 도착하는지 확인, 실패 시 pull 폴백 유지
- S6 하루 운용 후 brief 크기·중복 0·판정 지연을 실측(그 전까지 효과는 `UNMEASURED`)

## 6. 실행 권한 메모

`codex queue`는 Claude 세션에서 `External System Writes`로 차단된다(확인함). 따라서 S5의 실배달 주체는 Antigravity다. Claude 세션에서도 직접 배달하려면 Bash 허용 규칙 `codex queue:*` 하나가 필요하다.

## 7. 근거

- openai/codex PR #39092(queue 명령, `thread/queue/add`), Issue #13968(큐 명령 확장), Issue #32519(ChatGPT↔Codex 양방향 미지원, Open)
- `codex --help`, `codex queue --help`(로컬 0.155.1 실측)
- ChatGPT/Codex 데스크톱 통합·handoff 문서(learn.chatgpt.com developer-commands, openai.com work-with-codex-from-anywhere)

---

# U15 구현 기록 S1~S4 (2026-09-20 20:4x, Claude 단독 수행)

| 단계 | 산출물 | 인수 | 결과 |
|---|---|---|---|
| S1 | `manifest.py` DEFAULT_EXCLUDES에 `.coord/stream`·`.coord/codex_brief.md` | `tests/test_u15_stream_isolation.py` 5건 | PASS. 스트림 10건·브리핑 갱신에도 manifest 해시 불변, PLAN·카드·메모는 계속 감시 |
| S2 | `v7_harness/coord/stream.py` | `tests/test_u15_stream_append.py` 10건 | PASS. VERDICT는 Codex만, RUN·VERDICT 증거 강제, 200자·단일행·비밀 패턴·경로 이탈 거부, 거부 시 기록 0 |
| S3 | `v7_harness/coord/brief.py` | `tests/test_u15_codex_brief.py` 7건 | PASS. 같은 스트림 → 같은 해시, 고정 헤더 접두, 마지막 VERDICT 이전 접기, 60줄·6KB 상한, BLOCKED 항상 노출 |
| S4 | `v7_harness/coord/notify.py` | `tests/test_u15_notify_codex.py` 10건 | PASS(드라이런·가짜 러너). 해시 커서로 중복 0, 분당 1건·일 24건 상한, `[DATA]` 헤더, 큐 실패는 예외로 표면화하고 커서 미갱신 |

- 전체 회귀 **367 OK**(1 skip), compileall 0, 고정 R2 테스트 해시 불변.
- 구현 중 발견하고 고친 결함 1건: Windows에서 `O_APPEND` 동시 쓰기가 원자적이지 않아 8건 중 2건이 유실되고 id가 중복됐다. 파일 잠금(`.lock`, 10초 타임아웃, 60초 stale 회수) + 프로세스 내 뮤텍스로 교정하고 재현 스크립트로 3회 연속 8/8·중복 0을 확인했다.
- S5(실배달)는 Claude 세션에서 `codex queue`가 `External System Writes`로 차단되므로 Antigravity가 수행한다. 명령 형태는 `notify.py`가 만들어 두므로 드라이런 출력의 `command`를 그대로 실행하면 된다.

# U15 S5·S6 결과 (2026-09-20 20:1x~20:2x)

## S5 실배달 — 성공
- `codex queue --thread 01a0b77f-cbc2-7930-878e-4b18186813e1 --message <5줄>` → `Queued message 01a0be89-d401-7980-8d4b-66a34518685e`.
- 메시지 계약 준수: `[DATA]` 헤더 + 요약 1줄 + 브리핑 경로 + 판정대기 2줄, 값·비밀 0.
- 커서 `.work/coord/codex_notify_cursor.json`에 브리핑 해시·스레드·큐 메시지 ID 기록.

## S6 부분 실측 — `PARTIAL_MEASURED`
산출물 `.coord/runs/U15/measurement_s6.json`, 드라이버 `.coord/runs/U15/measure_u15.py`.

| 지표 | 값 |
|---|---|
| 스트림 사건 | 6건 / 1,975바이트 |
| 인계 1회 분량(기존 메모 최근 10건 평균) | 1,552자 ≈ 621토큰(추정) |
| 인계 1회 분량(브리핑) | 828자 ≈ 331토큰(추정), 25줄 |
| Codex 창에 실제로 들어가는 큐 메시지 | 81자 ≈ 32토큰(추정) |
| 메모 대비 브리핑 절감 | **−46.6%** (n=1, 추정 토큰) |
| 상한 준수 | 60줄·6KB·500자 모두 준수 |
| 중복 전달 차단 | 재시도 시 `NO_CHANGE`로 차단 확인 |

측정하지 못한 것(`UNKNOWN`으로 유지):
- Codex가 큐 메시지를 소비한 시각과 판정 지연. Codex 세션 기록이 있어야 확인 가능하다.
- 조율 턴의 실제 토큰 절감. Codex 사용량 기록과 대조해야 하며, 위 수치는 문자수 기반 추정이다.

결론: 전달 경로와 절제 장치는 실동작으로 확인됐고, 분량은 메모 대비 절반 이하로 줄었다. 다만 "하루 운용" 기준 수치는 아직 없으므로 U15 전체 효과는 `UNMEASURED`를 유지한다.

# U15 S7·S8 추가 (2026-09-20 20:5x, agy 쿼터 소진 중 Claude 단독)

- S7 `python -m v7_harness.cli coord log|brief`: 세 도구가 같은 입구로 사건을 남기고 브리핑을 만든다. 거부는 종료 코드 1로 드러난다(권한 매트릭스·증거 강제 그대로). 테스트 `tests/test_u15_coord_cli.py` 4건.
- S8 `docs/claude-assist/INDEX.md`: 메모 79건을 번호·날짜·보낸 쪽·받는 쪽·제목으로 색인. 본문 삭제 0. 생성기 `.coord/runs/U15/index_memos.py`.
- 전체 회귀 371 OK(1 skip), compileall 0, 고정 테스트 해시 불변.
- WL01(gemini-3.1-pro-high)·WL02(gemini-3.8-flash-high) 모두 `QUOTA`로 중단, reconcile 완료. agy 전 모델 약 65시간 뒤 복구. 승인 화이트리스트 패치는 그때 재시도하거나 Codex가 적용한다.

# U15 S9·S10 (2026-09-20 21:0x)

- S9 롤오버 `archive_settled()` + `coord archive`: 마지막 판정까지의 사건을 `.coord/stream/archive/settled-<타임스탬프>.jsonl`로 옮기고 현역 스트림에는 판정 이후만 남긴다. 삭제 0. 테스트 4건(판정 없으면 이동 0, 보관 후에도 append 정상, 브리핑에는 안 보이고 디스크에는 남음).
- S10 판정대기 자동화 `pending_from_plan()`: PLAN 상태 칸에서 REVIEW·BLOCKED·ACTIVE·READY 행을 뽑아 브리핑의 판정 대기 목록을 채운다. 사람이 목록을 손으로 넘기면 빠뜨린다. 테스트 4건.
- 설계 인수 기준 8항 중 5번(롤오버)이 이로써 충족됐다.
- 전체 회귀 379 OK(1 skip), compileall 0, 고정 테스트 해시 불변. 단, 동시 실행이 섞인 1회에서 이름을 못 잡은 실패 1건이 있었고 이후 단독 3회·병렬 3회 재현되지 않아 B61로 남겼다.

# U15 S11 — 자기 검토에서 잡은 P1 (2026-09-20 21:1x)

- 결함: `archive_settled()`가 잠금 **밖에서** 스트림을 읽은 뒤 잠금 안에서 파일을 지웠다. 읽기와 삭제 사이에 들어온 사건이 통째로 사라진다. 또 잠금을 날짜별 파일에 걸어 자정 전후에는 서로를 막지 못했다.
- 재현: 판정 1건 + 자정 이후 기록 6건 + 보관 1건을 동시에 실행 → 살아남은 사건 1건(6건 유실). `tests/test_u15_rollover_and_pending.py::U15RolloverConcurrencyTests`.
- 교정: 잠금을 `.coord/stream/.stream.lock` 하나로 통일(append·archive 공용), 읽기·판정·삭제·재작성을 모두 잠금 안으로 이동.
- 확인: 해당 테스트 5회 연속 OK, U15 계열 21건 OK, 전체 **380 OK**(1 skip), 고정 테스트 해시 불변.
- B61 해소: `.coord/runs/run_regression.py`로 회귀 전문을 `.work/logs/`에 남기고 실패 이름을 요약 출력한다.

# U15 S6 하루 창 집계 (2026-09-21 22:0x)

산출물 `.coord/runs/U15/measurement_s6_full.json`. 판정: **PARTIAL_MEASURED**.

| 지표 | 값 |
|---|---|
| 창 | 2026-09-20 20:45 → 09-21 22:07 (25.4시간) |
| 표본 | 4건, 간격 1.9h · 0.1h · **23.4h** |
| 사건 증가 | 7 → 21 (+14, RUN 14·BLOCKED 3·NOTE 3·PLAN 1) |
| 브리핑 크기 | 828 ~ 1,450자, 최대 28줄 — 상한(60줄·6KB) 전 구간 준수 |
| 하루 전달 건수 | 최대 2건 (상한 24건) |
| Codex 소비 확인 | `NOT_SEEN` / `UNKNOWN` — 끝내 확인 못 함 |

드러난 한계:
- **수집기가 세션에 묶여 있다.** 크론이 Claude 세션 안에서만 돌아 세션이 쉬는 23.4시간 동안 표본이 0건이었다. 보간하지 않았다. 연속 수집하려면 OS 예약 작업이 필요하다(시스템 설정 변경이라 별도 승인 대상).
- **판정 왕복이 없었다.** Codex가 9/24까지 한도 상태라 이 창에서 큐 메시지가 읽히고 판정이 돌아오는 경로를 한 번도 관측하지 못했다. 판정 지연은 측정 불가로 남는다.
- 결론: 전달·절제 장치는 하루 동안 상한 안에서 동작했다. 효과(판정 지연 단축·토큰 절감)는 Codex 복귀 후 판정 왕복이 생겨야 잴 수 있으므로 `UNMEASURED`를 유지한다.
