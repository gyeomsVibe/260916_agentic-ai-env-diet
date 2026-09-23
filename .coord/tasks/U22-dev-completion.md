# U22 개발 완료 마감 (Development completion)

- 상태: DONE (Claude 대행 판정, Antigravity 독립검증 U22-consult, Codex 복귀 재검토 대상)
- 수행: 모든 구현은 `pilot run --worker auto`(Ollama 먼저 → Antigravity). Claude는 프롬프트, 숨은 인수, 판정만 맡음.

## 결과
| 하위 | 변경 | 경로 | Antigravity 토큰 |
|---|---|---|---|
| consult | U15–U21 PASS, 15m cron "NONE" 답변 | agy 읽기 전용 | 202k |
| U22a | `ollama_worker`: `NUM_PREDICT` 4096, `PROMPT_TOO_LARGE` 즉시 실패 | 로컬 PROVIDER_ERROR → agy | 94k |
| U22b | `ollama_worker._apply`: `<relative/path>` 자리표시자 블록 무시 | 로컬 REWORK → agy | 118k |
| U22c | `calculator_gate --install` | **로컬 PASS 73초** | 0 |
| U22d | U22c에서 로컬이 지운 `--pilot-dir` 복구 | 로컬 REWORK → agy | 42k(+62k 재실행) |
| U22e | `tests/test_u22_worker_limits.py` 8개 | 로컬 REWORK → agy | 181k |

## 검증 증거
- 숨은 인수: `.work/u22/accept_{a,b,c,d,e}.py`, 모두 Red → PASS.
- accept_e는 변이 3종(과대 판정 무력화, `--install` 무력화, `num_predict` 변경)을 모두 잡는지 확인한다.
- 전체 회귀: 547 OK(skipped 1), 80초. 기존 테스트 파일 diff 0.

## 교훈
- U22c 인수는 새 동작만 봤다. 그래서 로컬이 지시 밖의 `--pilot-dir` 줄을 지운 것을 놓쳤다.
- 이후 인수는 HEAD 대비 삭제·추가 줄을 대조한다(accept_d). 이 대조가 U22d2 로컬 실패를 실제로 잡았다.
- accept_d의 추가 줄 개수를 9로 잘못 적었다(빈 줄 1개 누락). 10으로 고쳐 새 실행으로 판정했고, 기존 실행을 재승인하지 않았다.

## 미해결 위험
- 로컬 7b는 실과제 9건 중 1건만 성공했다. 실패 원인은 PROVIDER_ERROR, SEARCH 블록 깨짐, 지시 밖 줄 삭제였다. 비용 절감은 대부분 agy가 Claude를 대신한 몫이다(Claude 쪽 절감은 UNMEASURED).
- 21:30에 PLAN 도구 상태 줄이 다시 수정됐다. 주기적으로 쓰는 주체가 있으나 위치는 UNKNOWN이다.
- 제안 3(대형 파일 함수 발췌)은 보류했다.
