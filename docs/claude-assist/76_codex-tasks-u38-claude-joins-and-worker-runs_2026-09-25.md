# Claude → Codex 76: U38 Claude Code 정식 가입·B85 수정 완료, Codex 실행 과제 C1~C6 (2026-09-25)

- 지휘: **Claude 주도, Codex 보조**. 사용자 지시는 "codex가 보조로 돕는다. 사용자에게 시키지 말고 Codex에게 시켜라. 개발이 끝날 때까지 무승인 진행. Antigravity·Ollama를 제대로 쓰고 기록하라. Claude Code UAOS 정식 가입."
- 원칙: 사용자에게 넘길 일은 모두 이 메모의 Codex 과제다. 판정은 Codex가 한다(Claude 작성물).
- 사용량:
  - `/usage`는 클라우드 세션이라 UNKNOWN이다.
  - 이 컨테이너에는 ollama·agy·claude 작업자 실행 환경이 없다. 그래서 세 작업자 호출은 0회이고, 모두 아래 과제로 Codex가 사용자 PC에서 실행한다.

## 1. 끝낸 것 (브랜치 `claude/cool-hamilton-yj6wwo`)

| 커밋 | 내용 | 증거 |
|---|---|---|
| `1d9bcc0` | **B85 수정.** 유료 작업자(agy·claude)와 cascade 승격 **모두**에 예산 관문을 적용한다. 관문은 파일럿 안에서, `summary.json`·장부를 쓰기 **전**에 돈다. 입력+출력+캐시 두 종류를 합산하고, 미보고는 UNKNOWN이다. WITHIN이 아니면 `BLOCKED`(`COST_EXCEEDED`/`COST_UNKNOWN`)라 두 승인 경로 모두 거부된다. 매뉴얼 검사에 `REMOTE_WITHOUT_BUDGET`, 승인에 `APPROVER_UNKNOWN`을 추가했다 | `tests/test_u38_cost_gate_and_claude_worker.py`(수정 전 실패). U34 cascade 테스트는 옛 결함(입력만 계산)을 기대하던 것을 고쳤다 |
| `dc474aa` | **U38.** `worker: claude`(`adapters/claude_worker.py`), `pilot review --reviewer claude`(읽기 전용·참고 증거·자기 번들 거부·작성자 불명 시 거부), P1 대행(`--say p1`, Codex 비ACTIVE일 때만 한 줄), 작업자 표기 수정(lane이 agy로 기록되던 결함), 캐시·비용 장부 필드 | 가짜 `claude`로 테스트. 돌연변이 5종을 모두 잡는다 |
| (이번 커밋) | 계약 `model:` 칸, 매뉴얼 3건 발행, docs/40 상태, 전역 규칙 문단(claude 작업자, `rsi adopt` 안내 제거), 진입 규칙 한 줄씩, 이 메모 | 매뉴얼 3건 모두 lint 통과 |

- Linux 결과: 729개 중 실패 1(B75)·건너뜀 5. 비유 재현 5/5 NOT_REPRODUCED.
- 회귀 뒤 `.coord/usage/runs.jsonl`은 생기지 않았다(오염 없음).

## 2. Codex 과제 (순서대로, 사용자 PC)

### C1. 브랜치 정리 (지난 댓글 요청)

1. B83 fail-closed 번들(`3d4161cd…3ace`)과 PLAN·BACKLOG 로컬 수정을 커밋하고, 이 브랜치를 **merge**(rebase 금지)한 뒤 푸시한다.
2. BACKLOG의 B85는 `RESOLVED(1d9bcc0)`로 바꾸고, PLAN에 U38 행을 넣는다. 문구는 §4를 그대로 쓰면 된다.
   - Claude는 PLAN·BACKLOG를 고치지 않았다. 동시 수정을 피하기 위해서다.
3. 충돌이 나면 두 쪽 사실을 모두 남긴다.

### C2. Windows 검증

```powershell
python -m unittest tests.test_u38_cost_gate_and_claude_worker tests.test_u34_precision_harness tests.test_u37_install_everywhere
python .coord/runs/run_regression.py
```

- 관문:
  - 첫 줄은 모두 OK.
  - 전체는 B83 병합 결과 기준으로 exit 0. Linux 729개에 B83 쪽 테스트 변화가 더해진다.
- 중지: 새 테스트가 실패하면 테스트 이름과 트레이스백 앞부분만 PR에 남기고 멈춘다.

### C3. Ollama — `U38-O1` (계산기: 원문 추출)

```powershell
python -m v7_harness.cli pilot manual lint --manual .coord/tasks/U38-O1-ollama-claude-worker-facts-manual.md --source .
python -m v7_harness.olla_evidence --manual .coord/tasks/U38-O1-ollama-claude-worker-facts-manual.md --evidence v7_harness/adapters/claude_worker.py --sha256 <아래 참고> --keys worker_tools,review_tools,default_model,max_turns_line,worker_marker --prompt "Copy the five values exactly as they appear." > .work/u38/o1.json
```

- **SHA 주의**:
  - LF 기준 해시는 `2bb37e1e…f4a2`다.
  - Windows 체크아웃(`core.autocrlf=true`)에서는 바이트가 달라 `INPUT_HASH_MISMATCH`가 난다.
  - 그럴 때는 U35-O2 때처럼 Windows 바이트로 고정한 사본 매뉴얼(`…-windows-manual.md`)을 발행한다. 다른 칸은 바꾸지 않고, 두 해시를 모두 기록한다.
- **판정 기대값**(작업자 매뉴얼에는 없음, 각각 증거 파일에 정확히 1회):

| 키 | 기대값 |
|---|---|
| worker_tools | `Read,Edit,Write,Glob,Grep` |
| review_tools | `Read,Glob,Grep` |
| default_model | `sonnet` |
| max_turns_line | `MAX_TURNS = os.environ.get("CLAUDE_WORKER_MAX_TURNS", "30")` |
| worker_marker | `env["UAOS_WORKER"] = "claude"` |

- 기록: 로컬 입력·출력 토큰, 벽시계, 5개 중 일치 수. `olla_evidence`가 exit 0이어도 값이 다르면 REWORK이다.

### C4. Antigravity — `U38-A1` (독립 레드팀, 예산 80,000)

```powershell
python -m v7_harness.cli pilot run --task U38-A1 --source . --work-dir .work/pilot_U38A1 --manual .coord/tasks/U38-A1-antigravity-redteam-manual.md
```

- **B85의 첫 실전 확인이다.** `summary.json`의 `cost_gate`를 본다.
  - `WITHIN`이면 보고서 품질을 판정하고 `--approve <bundle> --coord-actor codex`로 반영한다.
  - 그 밖(`EXCEEDED`/`UNKNOWN`)이면 BLOCKED가 정상 동작이다. 승인하지 말고 수치를 기록한다.
- 보고서 `.coord/runs/U38/agy_redteam_u38.md`의 발견은 Claude가 받아 red-first로 고친다(PR 댓글로 알려 달라).

### C5. Claude 작업자 첫 실전 — `U38-C1` (예산 60,000, Haiku)

사전 확인(UNKNOWN 해소, 결과를 PR에 남김):

```powershell
claude --version
claude --help   # --bare, --tools, --max-turns, --disallowedTools, --strict-mcp-config, --disable-slash-commands 존재 여부
python -m v7_harness.cli coord presence   # claude가 LIMITED이면 C5는 CLAUDE_LIMITED로 거부된다(정상)
```

```powershell
python -m v7_harness.cli pilot run --task U38-C1 --source . --work-dir .work/pilot_U38C1 --manual .coord/tasks/U38-C1-claude-worker-docs37-manual.md
```

- 판정: 격리 사본 diff가 매뉴얼의 세 변경과 일치하고, 다른 줄이 그대로이고, `cost_gate == WITHIN`인지 본다. 그 뒤 `--approve <bundle> --coord-actor codex`.
- 검토: 이 번들은 claude가 만들었으므로 `pilot review --reviewer claude`는 **거부되는 것이 정상**(`REVIEWER_IS_AUTHOR`)이다. 거부되는 것을 한 번 확인해 기록한다.
- 기록: 장부의 `worker: claude`, `model`, 토큰 네 종류, `cost_microusd`.
- 중지:
  - Claude 세션 안에서 중첩 실행이 거부되면 오류 문구를 PR에 남기고 멈춘다(설계 가정 확인).
  - `docs/37` 입력 해시가 Windows에서 다르면 C3처럼 Windows 사본으로 고정한다.

### C6. 보고

- C1~C5 결과(명령, exit, 토큰·시간·비용, 판정)를 PR 댓글 하나로 올린다.
- Claude는 그 댓글을 받아 A1 발견 수정, 문서·초보자 문서·PLAN 반영(PLAN은 C1 뒤)을 이어서 한다.

## 3. 예산과 기록 원칙

- 유료 호출은 C4(≤ 80,000)와 C5(≤ 60,000)뿐이다. 둘 다 계약 예산과 B85 관문 아래에서 돈다.
- 모든 실패도 장부의 분모에 남긴다(docs/31 §4). 같은 원인으로 두 번 실패하면 그 경로는 멈춘다.
- 유료 폴링과 예약 호출은 없다. Claude는 PR 댓글과 푸시로만 깨어난다.

## 4. PLAN에 넣을 행 (C1용 문구)

```
| U38 | REVIEW (Claude 구현 2026-09-25 · Codex 실행 C3~C5·판정 대상) | Claude Code(사용자 지시 "UAOS 정식 가입", Codex 보조) | Claude Code 파이프라인 참여: worker claude(예산 필수·판정 codex/user·LIMITED 거부·--bare·tests/.coord 쓰기 금지), pilot review(읽기 전용·참고 증거·자기 번들 거부), P1 대행(--say p1), 장부 캐시·비용, 작업자 표기 수정. B85 비용 관문(모든 유료 작업자·합계 토큰·BLOCKED·승인 거부) `1d9bcc0`·`dc474aa`. 매뉴얼 U38-O1(Ollama)·A1(Antigravity 80k)·C1(Claude 60k) 발행 — docs/40, 메모 76 |
```
