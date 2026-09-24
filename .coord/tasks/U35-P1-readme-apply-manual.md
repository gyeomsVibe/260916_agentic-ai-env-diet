```contract
work_id: U35-P1
worker: apply
goal: Replace three stale lines in `README.md` with the dictated EDIT blocks below (n=1 caveat for the -46.6% figure, test count 660, docs/35-37 links).
inputs:
- README.md sha256=2147168d05fb130cea9506b6906c1b61440d91f030376d02c51c228485b8b3c9
allow:
- README.md
acceptance: python -c "import pathlib;t=pathlib.Path('README.md').read_text(encoding='utf-8');assert 'n=1' in t and '660' in t and 'docs/37' in t"
forbidden: design changes; edits outside allow; editing or deleting tests; network; commit/push
stop: two failures with the same cause; input hash mismatch; no output
judge: claude
timeout_s: 120
remote_budget_tokens: 0
```

## 역할과 이유

- 작업자: `apply`(모델 없음, 0토큰). 지휘자(Claude, Codex 부재 중 대행)가 바꿀 문장을 이미 정했으므로 모델에 맡기면 받아쓰기뿐이고 삭제 위험만 생긴다(P08). 이 매뉴얼의 EDIT 블록을 그대로 적용한다.
- 판정자: Claude. 작성자와 판정자가 같으므로 Codex 복귀 재검토 목록에 올린다.
- 근거: U31 감사(`docs/35` §4) — README의 −46.6%는 첫 표본 1건(n=1)이었고 이후 측정은 −32.2%다. 테스트 수 478·429는 오래된 값이다(2026-09-25 현재 660).

## Dictated edits

===EDIT: README.md===
<<<<<<< SEARCH
조율 인계 1회 분량도 줄었습니다: 기존 메모 평균 1,552자 → 브리핑 828자(**−46.6%**), 지휘자 창에 실제 들어가는 메시지는 81자.
=======
조율 인계 1회 분량도 줄었습니다: 첫 표본(n=1)에서 기존 메모 평균 1,552자 → 브리핑 828자(**−46.6%**), 이후 측정 범위 828~1,450자·최신 측정 −32.2%(`.coord/runs/U15/measurement_s6.json`). 지휘자 창에 실제 들어가는 메시지는 81자.
>>>>>>> REPLACE
===EDIT: README.md===
<<<<<<< SEARCH
| `tests/` | 인수 테스트 478개 |
=======
| `tests/` | 인수 테스트 660개(2026-09-25) |
>>>>>>> REPLACE
===EDIT: README.md===
<<<<<<< SEARCH
토큰예산 운영은 [3대 도구 예측·역할 전환 규칙](docs/27_token-budget-routing-policy.md)에서 시작합니다. [Claude](docs/28_claude-budget-manual.md)·[Antigravity](docs/29_antigravity-budget-manual.md)·[Ollama](docs/30_ollama-calculator-manual.md) 실행 매뉴얼이 이어집니다.
=======
토큰예산 운영은 [3대 도구 예측·역할 전환 규칙](docs/27_token-budget-routing-policy.md)에서 시작합니다. [Claude](docs/28_claude-budget-manual.md)·[Antigravity](docs/29_antigravity-budget-manual.md)·[Ollama](docs/30_ollama-calculator-manual.md) 실행 매뉴얼이 이어집니다.

사용자 5대 비유의 실현도 감사는 [docs/35](docs/35_five-metaphors-realization-audit_2026-09-25.md), 그 보강 구현 기록은 [docs/36](docs/36_metaphor-realization-implementation-record_2026-09-25.md), 모든 프로젝트에 쓰는 표준 작업 프로세스와 Ollama·Antigravity 하네스·계약 매뉴얼 설계는 [docs/37](docs/37_standard-process-and-worker-harness.md)에 있습니다.
>>>>>>> REPLACE
