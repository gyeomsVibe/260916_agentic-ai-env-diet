# 협의 10 — 사용자 지시 "빠르게 마무리" 분업안 + M3 초안 (Codex [M2]에게)

## 1. 사용자 지시

**"빠르게 일을 마쳐라. 협조해서 함께 빨리 마무리하라."** 아래 분업은 쓰기 범위가 겹치지 않게 짰다.

## 2. 병렬 분업안 (충돌 없음)

| 트랙 | 담당 | 쓰기 범위 | 할 일 |
|---|---|---|---|
| A. M2 본선 | **Codex → Antigravity** | `v7_harness/**`, `tests/**`, PLAN, M2 카드, `.coord/pilot/**` | P1 2건 수정 → 실제 P01 `pilot run`(B) → 인수 확인 → 같은 task `--approve` 반영(사용자 승인) |
| B. A/B 대조군 준비 | Claude (완료) | `260916_pilot_sample_A\` | B와 같은 초기 상태의 복사본을 준비했다. Codex는 이 폴더에서 A(단독 수행)만 하면 된다 |
| C. M3 초안 | Claude (완료) | 이 문서 §4 | 규칙 전환 문구를 미리 작성했다. Codex는 검토·적용만 하면 된다(전역 파일은 사용자 승인) |

## 3. 속도를 위한 합의 제안

1. **독립 검증 1회로 끝낸다.** M2 게이트 = `test_m2_pilot` 17/17 + 전체 회귀 + 실제 P01 B 인수 테스트 통과 + 범위 밖 쓰기 0. Antigravity 독립 검증은 P1이 새로 나올 때만 추가한다(docs/15 §3).
2. **A 측정은 가볍게 한다.** Codex 새 대화(또는 `codex exec`)에서 `260916_pilot_sample_A`에 같은 `.coord/runs/P01/prompt.md`를 수행한다. 기록 항목: 시작·종료 시각, Codex 5h% 전후, 인수 테스트 exit.
3. **B 측정:** `summary.json`의 `agy_usage`, 벽시계 시간, Codex는 판정 턴 수만 기록한다.
4. `.coord/runs/P01/ab.json` 형식:

```json
{"task":"P01","A_codex_only":{"wall_s":0,"codex_5h_pct_before":0,"codex_5h_pct_after":0,"acceptance_exit":null},
 "B_codex_plus_antigravity":{"wall_s":0,"codex_5h_pct_before":0,"codex_5h_pct_after":0,"codex_turns":0,"agy_usage":{},"acceptance_exit":null,"promotion":""},
 "notes":"measured values only; no extrapolation"}
```

5. M2 DONE 즉시 M3를 같은 흐름으로 진행한다. M3는 §4 초안을 적용하고, 새 Codex 세션 1회로 확인한다.

## 4. M3 적용 초안

### 4.1 프로젝트 `AGENTS.md` — "## 고정 규칙" 끝에 추가

```markdown
- 구현·수정 작업은 Antigravity에 SQLite 경로로 위임한다: `python -m v7_harness.cli pilot run --task <ID> --source <dir> --prompt-file <md> --work-dir .coord/pilot`
- Codex는 `.coord/pilot/runs/<ID>/summary.json`(12키)만 읽고 판정한다. 전문 로그는 필요할 때만 연다.
- 반영은 같은 task에 `--approve <bundle_id>`로만 한다. `promotion`이 `BLOCKED`·`REJECTED`면 반영하지 않고 원인만 보고한다.
- `antigravity-bridge` MCP는 조회·대화형 보조용이며 프로젝트 구현 위임에 쓰지 않는다.
```

### 4.2 `~/.codex/AGENTS.md` 29행 교체 (사용자 승인 필요)

현재:
```markdown
- Antigravity 위임은 `antigravity-bridge`만 사용하고 목표 하나·허용 파일·완료 조건을 준다. 결과를 직접 검토·검증하며 위임자의 커밋·푸시·병합은 허용하지 않는다.
```
교체:
```markdown
- 프로젝트에 `v7_harness`가 있으면 Antigravity 위임은 `pilot run`(SQLite 원장·staging·검증)을 우선한다. 없으면 `antigravity-bridge`를 쓴다. 어느 경로든 목표 하나·허용 파일·완료 조건을 주고, 판정은 요약·diff·테스트로만 하며 위임자의 커밋·푸시·병합은 허용하지 않는다.
```

### 4.3 `~/.gemini/GEMINI.md` "## Antigravity 역할" 끝에 추가 (사용자 승인 필요)

```markdown
- `pilot run`으로 호출되면 주어진 staging 작업공간 안에서만 파일을 수정하고, 사용자 홈·TEMP·원본 경로에 쓰지 않는다. 결과는 한 줄 요약으로 끝낸다.
```

### 4.4 `mia-vaccine-test` (C2)

vibe-clinic MCP 참조 문장 뒤에 다음을 추가한다.
```markdown
MCP가 없으면 로컬 테스트·재현 스크립트로 진단한다.
```

## 5. Claude의 이후 역할

계획 밖 지원만 한다. Codex가 요청한 실측·조사만 수행하고, `v7_harness/**`·PLAN·카드는 수정하지 않는다.
