# [U27] 사용량 장부 자동 기록기 및 올라마 사용기록 보존

- 상태: DONE (2026-09-25, Codex 독립 재검토 및 결함 수리 완료)
- 목표: 모든 pilot run을 프로젝트 v2 장부에 자동 기록하고 직접 `olla` 호출의 전역 원시 로그와 함께 실사용 데이터를 영구 보존하여 프로세스 개선의 근거로 삼는다.
- 허용 파일:
  - 신규 모듈: `v7_harness/coord/usage_ledger.py`
  - 회귀 테스트: `tests/test_u27_usage_ledger.py`
  - 매뉴얼: `docs/32_ollama_process_improvement_manual.md`
  - 이 카드 및 `.coord/PLAN.md`
- 인수 게이트:
  1. 원자적 append: 단일 프로세스 및 다중 프로세스 병렬 쓰기 시 JSON Lines 문법 무결성 100% 보장 (라인 깨짐/유실 0건).
  2. 비밀 패턴 검출 차단: `sk-`, `ghp_`, `Bearer ` 등 토큰/비밀 포함 시 `UsageRejected` 예외 발생.
  3. 정본 `uaos-usage-v2` 필드와 미확인 값 `null`, 독립 검증 전 `rsi_eligible=false` 준수.
  4. 결정론적 단위 테스트 exit 0 통과.
- 비용/작업자: 초기 로컬 구현 뒤 Codex 반례로 재작업. 최종 수리에 Ollama와 Antigravity를 모두 사용했으며 유료 API 토큰 0원 주장은 기각한다.

## 최종 결과 및 증거 (2026-09-25)

1. `usage_ledger.py`: 번들 `60246863…` APPLIED. 잠금 10초 후 무잠금 append 결함 제거, v2 검증·비밀 차단·입력 불변 보장.
2. `tests/test_u27_usage_ledger.py`: 번들 `e25fb43d…` APPLIED. Windows `spawn` 4프로세스×10건, 잠금 시간초과, 비밀·필수 필드·입력 불변 5/5 OK.
3. `pilot.py`: 번들 `c7fb6e25…` APPLIED. 모든 종료 결과를 정본 v2 행으로 자동 기록하고 기록 실패는 요약에 표시.
4. 숨은 인수: Windows 8프로세스×25건 총 201행 무손실, 잠금 보유 중 시간초과 append 0건, 실제 `U27_AUTO_SMOKE`에서 장부 24→25행 자동 증가.
5. 회귀: Codex 복귀 점검 13/13, 전체 580 OK(1 skip), compileall exit 0.
6. 비용: Antigravity 최종 성공 실행 입력 790,213·출력 92,583 토큰, 용량 실패 실행 입력 121,999·출력 16,514 토큰도 분모에 보존한다. 실제 계정 절감은 `UNMEASURED`다.
