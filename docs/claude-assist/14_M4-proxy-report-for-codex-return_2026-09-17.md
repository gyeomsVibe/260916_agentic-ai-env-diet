# 보고 14 — Codex 한도 중 M4 대행 결과 (Codex 복귀 시 읽기)

Codex는 2026-09-17 20:4x 사용량 한도로 멈췄다(재설정 09-18 00:15). 사용자 지시로 Claude가 조율을 대행했고, 구현·검증은 Antigravity가 맡았다.

## 1. 한 줄 현황

**M4 구현·검증·실측(B)을 완료했다. Codex가 할 일은 3개다:** ① M4 판정 ② P03 A 측정 ③ 새 규칙으로 P04 B를 직접 1회 수행해 Codex 비용 재측정.

## 2. 완료 항목

| 항목 | 결과 | 증거 |
|---|---|---|
| Codex 사용량 원인 분해 | M2 대화: 도구 호출 147회(wait 폴링 32회), 입력 1,661만 토큰(캐시 98.7%), 2턴 | `.coord/runs/M4/codex-cost-breakdown.md` |
| 실패 테스트 고정 | 11개 red → green | `tests/test_m4_efficiency.py` |
| 구현(Antigravity) | `--accept-cmd`·`verdict_hint`·`acceptance_exit`(14키), 실패 시 approve BLOCKED, 실행 후 lease RELEASED, `reconcile_pilot`/`pilot reconcile`, 미정리 작업 재실행 차단, 정리 후 새 attempt | `v7_harness/pilot.py`, `cli.py`; 위임 `.coord/runs/M4/delegation-02-gemini-3.7-flash-high.json` |
| 모델 사용량 | Gemini 3.8 Flash·3.1 Pro·Claude Sonnet 4.6은 개별 사용량 소진(약 166h), **Gemini 3.7 Flash로 성공** | `.coord/runs/M4/delegation-0*.json` |
| 검증 | M4+M2 28개, 전체 207개(1 skip), compileall 모두 exit 0 | — |
| P02 정리 | 실제 원장: attempt FAILED, delivery DEAD, lease REVOKED | `pilot reconcile --task P02 --work-dir .coord/pilot` |
| 규칙 | 프로젝트 `AGENTS.md`: `--accept-cmd`, 블로킹 1회·폴링 금지·`verdict_hint` 1턴 판정, reconcile 절차 | `AGENTS.md` 19~21행 |
| P03 실측 B | 37초, agy 입력 55,972, 인수 exit 0, PASS → 승인 재실행 **APPLIED**(agy 재실행 없음), 샘플 테스트 18개 통과, 외부 쓰기 0 | `.coord/runs/P03/ab.json` |
| 마감 정리 | 문서 참조 docs/14↔15 갱신, BACKLOG 20건(B16~B20 추가) | `.coord/BACKLOG.md` |
| 독립 검증 | Antigravity 읽기 전용 1회 | `.coord/runs/M4/independent-verify.json` (§4) |

## 3. Codex가 할 일 (새 짧은 대화에서)

1. **M4 판정:** 카드 `.coord/tasks/M4-efficiency-tuning.md`와 §4 독립 검증 결과만 보고 DONE 또는 재작업을 결정한다(재확인만, 결함 재탐색 금지).
2. **P03 A 측정:** `260916_pilot_sample_A`에서 `.coord/runs/P03/prompt.md`를 Codex 단독으로 수행한다. `ab.json` A 항목에 벽시계·5h%·도구 호출·입력 토큰·인수 exit를 기록한다.
3. **P04 B(Codex 직접, 새 규칙):** 새 과제 1건을 `pilot run ... --accept-cmd` 블로킹 1회 + summary 1회 읽기로 판정한다. 도구 호출·입력 토큰·5h%를 기록해 P01 기준선(147회, 1,661만, +8%p)과 비교한다.
   - 기본 agy 모델 사용량이 소진됐으므로 `--agy-command python .coord/runs/P03/agy_model.py`(Gemini 3.7 Flash 고정)를 쓴다. `--model` 옵션 부재는 B20.

## 4. 독립 검증 결과

- Antigravity(Gemini 3.7 Flash, `--mode plan` 읽기 전용, 입력 96,322 토큰): **PASS**, 정상 경로 P1 0건. 6개 인수 조건 모두 확인.
- 비차단: `--accept-cmd`는 shell 파이프·리다이렉트를 지원하지 않음(필요 시 `python -c`/래퍼) → BACKLOG B21.
- M4 상태: **REVIEW** (DONE은 Codex 판정 또는 사용자 승인으로).
