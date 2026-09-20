# Codex 복귀 인계 — Codex 정지 이후 진행분 (2026-09-18)

참여자는 Codex(조정·최종 판정)와 Antigravity(실행)로 고정한다. Claude는 외부 보조로 기록만 남긴다.

## 1. Codex 정지 이후 진행한 일

| # | 항목 | 상태 | 근거 |
|---|---|---|---|
| 1 | M4 효율 튜닝(one-turn 규칙, verdict_hint, reconcile) | DONE(사용자 승인) | `.coord/tasks/M4-efficiency-tuning.md`, 문서 14 |
| 2 | P03 B 실측(Antigravity, gemini-3.7-flash-high) | PASS·APPLIED, 37초, agy 입력 55,972 | `.coord/runs/P03/ab.json` |
| 3 | 극한 테스트 16종 | 15 PASS / 1 GAP(X10) | 문서 16, `.coord/runs/EXT/results.json` |
| 4 | BACKLOG 반영 | B22~B27 추가 | `.coord/BACKLOG.md` |
| 5 | Codex 측 비용 재측정 | **미실행(PENDING_CODEX)** | Claude는 Codex 자율 실행을 띄울 수 없음. 무효 기록은 되돌림 |

전체 단위 테스트는 207개 통과(1 skip). 삭제·push·배포·전역 설정 변경은 하지 않았다.

## 2. 자체 비판(CRITIC·REDTEAM)

| 심각도 | 판정 | 근거 | 영향 | 수정안 |
|---|---|---|---|---|
| P1 | 격리 보증 범위가 과대 표현될 위험 | X10: staging 밖 비감시 경로 쓰기 미탐지 | 실프로젝트 적용 시 원본 밖 오염을 놓칠 수 있음 | B22: work_dir·source 상위를 기본 watch-root에 추가하고, AGENTS.md에 "탐지 범위 밖 보증 없음"을 한 줄 명시 |
| P1(목표) | "Codex 사용량 절약" 효과가 아직 수치로 확인되지 않음 | P01 B는 +8%p로 A(+2%p)보다 비쌌음. M4 개선 후 재측정 없음 | 사용자 핵심 목표의 증거 공백 | 아래 §3-②③ 측정 |
| P2 | 실측 모델이 기본 모델이 아님 | 기본 모델 사용량 소진으로 3.7 flash wrapper 사용 | 품질 비교 편향 가능 | B20 `--model` 옵션 |
| P2 | 오류 3종이 트레이스로 종료 | X01·X11·X12 | Codex가 원인 파악에 추가 턴 소모 → 비용 증가 | B23~B25를 구조화 summary로 |

유지할 강점: 거짓 성공 0, 무승인 반영 0, 원장 무결성 손상 0.

## 3. Codex에게 요청하는 일(순서대로, 각 1회)

1. **업무 지시 확정**: 아래 ②~④ 중 우선순위를 정해 Antigravity 지시 또는 직접 수행 여부를 판단해 한 줄로 회신.
2. **P03 A 측정**: `..\260916_pilot_sample_A`에서 `.coord/runs/P03/prompt.md`를 Codex 단독으로 수행하고 `python -m unittest`를 실행. 전후 5h%와 도구 호출 수를 `.coord/runs/P03/ab.json` A에 기록.
3. **P04 B 측정(one-turn)**:
   `python -m v7_harness.cli pilot run --task P04 --source ..\260916_pilot_sample --prompt-file .coord/runs/P04/prompt.md --accept-cmd "python -m unittest -q" --work-dir .coord/pilot --agy-command python .coord/runs/P03/agy_model.py`
   - 한 번 실행 후 summary.json을 한 번만 읽는다.
   - PASS면 `--approve <bundle_id>`로 한 번 더 실행한다.
   - 전후 5h%와 도구 호출 수를 `.coord/runs/P04/ab.json`에 기록한다.
   - P01 기준선(147회, 1,661만 토큰, +8%p)과 비교한다.
4. **B22 결정**: 단기 대책(감시 범위 확장 + 문구 명시)을 Antigravity에 구현시키고 X10 재실행(`python .coord/runs/EXT/extreme_suite.py`)으로 확인할지 판정.

보고 형식: 비교표 1개와 결론 3줄.
