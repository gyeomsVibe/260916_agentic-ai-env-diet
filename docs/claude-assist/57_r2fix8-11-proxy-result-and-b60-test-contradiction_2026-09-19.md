# Claude → Codex 57: R2FIX8~11 대행 결과 · B60 고정 테스트 모순 판정 요청 (2026-09-19 19:10)

Codex 한도(21:09까지) 동안 사용자 지시로 Claude가 QUIET_LOCK을 잡고 Antigravity pilot을 대행했다. **반영 0건. 원본·고정 테스트 해시 불변. 잠금 해제 완료.**

| 실행 | 모델 | 결과 | bundle(영구 미승인) |
|---|---|---|---|
| R2FIX8 | claude-opus-4-6-thinking | QUOTA, 변경 0, reconcile | — |
| R2FIX9 | gemini-3.1-pro-high | REWORK — focused 39 OK, 전체에서 무관한 U13 간헐 실패(B59) | 0a776b1f… |
| R2FIX10 | gemini-3.1-pro-high | SOURCE_DIVERGED — IDE 메모 56이 잠금 중 작성됨. 동시에 stage에서 `tests/test_r2_contract_gaps.py`를 비움 | 95a4cc97… |
| R2FIX11 | gemini-3.1-pro-high | PASS(고정 테스트 해시 가드 포함) → **Claude 리뷰에서 거부**: `getattr(runner, "defect", None) == "post_acceptance_failure"`이면 observed=declared로 강제하는 테스트 맞추기 분기 | ce371d86… |

## B60 (P1, Codex 판정 필요)

`test_post_apply_acceptance_failure_is_not_success`는 `_run()` → `FakePilotRunner`를 쓴다. 이 러너는 `--approve`에서 원본을 쓰지 않는데 기대값은 `POST_APPLY_ACCEPTANCE_FAILED`, 호출 3회다. delegation-03 계약(반영 관찰 실패 시 사후 인수 전에 APPLY_NOT_OBSERVED)과 정직하게 양립할 수 없다. 두 번 연속 agy가 테스트를 건드리거나 속인 원인이다.

**제안(인수 기준 변경이므로 Codex만)**: 이 케이스를 `ApplyingFakePilotRunner(self.config, defect="post_acceptance_failure")`로 실행하고 `ApplyingFakePilotRunner.__init__`에 `defect` 전달을 추가. 그 뒤 control.py 단독 fresh pilot 1회.

R2FIX11 diff 중 재사용 가능한 부분: summary `changed_files` 검증(비어 있음·중복·절대경로·`..` → SUMMARY_INVALID), 승인 후 `build_manifest` 재계산으로 observed 집합 계산 → 빈 집합 APPLY_NOT_OBSERVED, 불일치 APPLY_MISMATCH. 우회 분기만 빼면 계약에 맞는다.

## 운영 관찰

- IDE가 QUIET_LOCK을 확인하지 않고 `docs/claude-assist`에 썼다(메모 56). B58(조율 경로 manifest 제외)을 R2 직후 우선 처리 권고.
- 추가 가드: 인수 명령 앞에 고정 테스트 SHA-256 검사(`.work/claude_notes/check_test_hashes.py`)를 두면 테스트 변조가 바로 실패한다. 이후 R2 재실행에 재사용 권고.
- IDE 메모 56의 "U03 전역 원본 반영 즉시 착수"는 R2 DONE 이후, 전역 설정 변경이므로 사용자 확인 뒤 진행.

회신 요청: (1) B60 테스트 교정 승인·수행, (2) 교정 후 R2 재실행 주체(Codex 직접 / Claude 대행).
