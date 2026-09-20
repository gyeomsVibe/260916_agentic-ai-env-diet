# M2 동기화 09 — 중복 작업 방지 및 현황 (Codex [M2] 대화에게)

## 1. 충돌 방지 조치 (19:21 KST)

- Claude가 19:17에 같은 P1 2건 재작업을 Antigravity에 지시했으나, Codex `[M2]` 대화가 19:20에 같은 작업을 위임한 것을 확인하고 **Claude 쪽 위임을 즉시 중단**했다.
- 중단된 위임은 파일을 수정하지 않았다(`pilot.py` 19:14:41, `cli.py` 19:14:56 이후 변경 없음).
- 현재 남은 agy 프로세스(19:21 시작)는 Codex bridge 위임 1건뿐이다. **M2 쓰기 주체는 Codex 위임 하나로 고정한다.**

## 2. M2에서 이미 완료된 것 (Codex가 재사용)

| 항목 | 파일 | 상태 |
|---|---|---|
| 인수 테스트 | `tests/test_m2_pilot.py` (17개 + fake agy) | 15 통과 / 2 실패(P1 고정) |
| 가짜 agy | `tests/fixtures/fake_agy.py` | success·error503_write·outside_write·partial_timeout·no_change |
| 실제 agy 실행기 | `v7_harness/execution/agy_launcher.py` | Antigravity 초안(delegation-01), 테스트 통과 |
| 파이프라인 | `v7_harness/pilot.py` | 동일, P1 1(같은 task 승인 replay 미반영) |
| CLI | `v7_harness/cli.py` `pilot run` | 동일, P1 2(watch roots 기본값 없음) |
| 실제 반영 | `v7_harness/isolation/promotion.py` `apply_promotion` | 구현·테스트 통과(승인 ID·삭제 거부·base 재확인·staging 해시 재확인) |
| 샘플 프로젝트 | `D:\D_Workspace_NB\-agentic-ai-workspace\260916_pilot_sample\` (calc.py, test_calc.py) | 생성, 기존 테스트 통과 |
| P01 과제 | `.coord/runs/P01/prompt.md` (`clamp()` + 테스트 5종) | 준비 |
| 위임 기록 | `.coord/runs/M2/delegation-01-*` (input 627,604 tokens, 247초) | 보존 |

## 3. M2 남은 단계 (권장 순서)

| # | 단계 | 담당 | 예상 |
|---|---|---|---|
| 1 | P1 2건 수정 → `test_m2_pilot` 17/17 + 전체 회귀 | Codex→Antigravity (진행 중) | 10~15분 |
| 2 | 실제 P01 실행 B: `python -m v7_harness.cli pilot run --task P01 --source ..\260916_pilot_sample --prompt-file .coord/runs/P01/prompt.md --work-dir .coord/pilot` | Codex | 5~10분 |
| 3 | bundle 확인 → staging에서 `python -m unittest` 인수 확인 → 같은 task `--approve <bundle_id>` 반영 | Codex(사용자 승인 1회) | 5분 |
| 4 | A: 같은 과제를 Codex 단독(샘플 복사본)으로 수행, `ab.json` 기록 | Codex | 10~15분 |
| 5 | Antigravity 독립 검증 1회(docs 종료 규칙, P1만) → M2 DONE | Antigravity→Codex | 10분 |

남은 합계 약 40~55분. 이후 M3(규칙 전환) 약 30분.

## 4. 문서 이름 변경 주의

사용자가 `docs/14`↔`docs/15` 파일명을 교환했다. 설계 정본은 이제 `docs/15_minimum-completion-path-design_2026-09-17.md`, 지시문은 `docs/14_codex-directive-minimum-completion-path_2026-09-17.md`다. 카드·PLAN의 참조는 M2 종료 시 갱신 필요.

## 5. 앞으로의 협업 방식

- Codex가 조율·판정, Antigravity가 실행·검증한다. Claude는 이 계획 밖에서 요청받은 조사·실측만 제공하며 **파일 수정·위임은 하지 않는다.**
- Codex가 필요한 실측(예: 실제 agy 타임아웃 문구, 샘플 A/B 측정 보조)은 이 문서 경로에 요청을 적으면 주기 점검에서 확인한다.
