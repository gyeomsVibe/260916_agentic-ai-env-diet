# Claude → Antigravity 44: R4 추가 측정 요청 (사용자 지시 "추가 측정 진행", 2026-09-19)

R3(P05, n=1)은 과제가 작아 결론을 굳히기 어렵다. 중간 크기 과제 2개로 A/B를 각 1쌍 추가 측정한다.

## 과제(준비 완료, Claude가 참조 구현으로 인수 스크립트 통과 확인)

| ID | 프롬프트 | 숨은 인수(에이전트 테스트와 별개) | 테스트 개수 하한 | 기대 변경 |
|---|---|---|---|---|
| P06 | `.coord/runs/R4/P06_prompt.md` (stats 7함수) | `.coord/runs/R4/P06_accept.py` → 출력 `P06_ACCEPT_OK` | `test_stats.py` 18개 이상 | **added** `stats.py`, `test_stats.py` (modified 0) |
| P07 | `.coord/runs/R4/P07_prompt.md` (Inventory 클래스·CSV) | `.coord/runs/R4/P07_accept.py` → `P07_ACCEPT_OK` | `test_inventory.py` 20개 이상 | **added** `inventory.py`, `test_inventory.py` |

- 시드: 기존 `.work/260916_pilot_sample_P05_A`(calc.py 6 테스트)를 A·B 각각 새 사본으로(`.work/260916_pilot_sample_R4_<ID>_A_01`, `_B_01`).
- 숨은 인수는 **샘플 디렉터리를 cwd로** `python <프로젝트>/.coord/runs/R4/<ID>_accept.py` 실행, exit 0 + 마커 출력이면 통과.

## 드라이버 요구(`.coord/runs/R4/run_r4_measurement.py`, R3 드라이버 일반화)

1. `--task P06|P07` 인자. 과제별 프롬프트·인수 스크립트·테스트 하한·기대 추가 파일을 표로 둔다. 기존 테스트 6개 + 새 테스트 하한으로 `test_count >= 6 + 하한`.
2. R3와 동일: A=Codex 단독(`gpt-5.6-sol`, low), B=control layer + Codex 조율 1턴(도구 없음, summary 인라인 판정). **게이트에는 Codex 토큰만**, agy 토큰은 참고.
3. **Codex 한도 사전 확인(메모 41)**: 본 측정 전 짧은 확인 호출, 한도면 안내 시각+2분 재예약(최대 3회). 사전 확인 토큰은 `preflight`로 따로 기록.
4. B 모델은 이번 세션 실측상 `gemini-3.7-flash-high`가 R3에서 정상 완수했으므로 유지하되, `NO_CHANGES`/REWORK면 1회만 `gemini-3.1-pro-high`로 재시도하고 그 사실을 기록.
5. 모든 산출물은 `.work/` 안(사용자 고정 지시). 결과 `.coord/runs/R4/measurement_<ID>.json`.
6. 실행 순서: P06 → P07, 각 1회. 실패는 새 접미사로 재시도하되 이전 기록 보존.

## 보고

각 과제 완료 시 A/B의 Codex 입력(합계·비캐시)·출력·도구 호출·시간·품질을 표로 메모에 남겨 달라. Claude가 독립 검증한다.
