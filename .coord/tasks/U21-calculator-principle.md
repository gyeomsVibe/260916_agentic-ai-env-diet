# U21 계산기 원칙 (Calculator principle)

- 상태: REVIEW (Claude 대행 지휘, Codex 복귀 시 재검토 대상)
- 소유자: Claude Code(지휘) / 수행: Ollama qwen2.5-coder:7b → Antigravity(cascade·auto)
- 목표: 지휘자(Claude·Codex)는 계획·프롬프트·숨은 인수·판정만 하고, 구현은 계산기(Ollama·Antigravity)가 한다. Antigravity도 단순 노동은 Ollama에 맡긴다.

## 결과
| 하위 | 내용 | bundle | 경로 |
|---|---|---|---|
| U21a | `--worker auto`, 로컬 실패 시 agy 승격, `routed_by` | e9de073 | 로컬 PROVIDER_ERROR → agy |
| U21b | `v7_harness/calculator_gate.py`, `.githooks/commit-msg` | 2c1a5e1 | 로컬 REWORK → agy |
| U21c | AGENTS.md 계산기 원칙 줄, docs/01 §16 | 7ebf190 | 로컬 PROVIDER_ERROR → agy |
| U21d | `tests/test_u21_calculator.py` 12개 | 8a8264d | 구체성 45 → agy 직행 |

## 검증 증거
- 숨은 인수: `.work/u21/accept_{auto,gate,rules,tests}.py` 모두 Red → PASS. accept_tests는 관문의 CRLF 정규화를 뒤집는 변이(mutation)를 넣어 테스트가 잡는지 확인한다.
- 관문 음성시험: 손으로 고친 `v7_harness/accept_triage.py` → rc 1과 위임 안내, `Calculator-Exempt:` 줄 → rc 0.
- 전체 회귀: `python -m unittest discover -s tests -t .` 539 OK(skipped 1), 77초. 기존 테스트 파일 diff 0.

## 비용 (Antigravity 토큰)
- U21a 335k, U21b 267k, U21c 276k, U21d 154k. Claude 쪽 절감은 UNMEASURED.

## 미해결 위험
- 로컬 7b 모델은 실과제 3건 중 성공 0건(PROVIDER_ERROR 2, REWORK 1). 큰 파일에서는 VRAM이 부족하다(모델 4.28 GB, 16k 컨텍스트, 6 GB 카드). 그래서 실제로는 agy가 대부분을 처리했다.
- Antigravity IDE가 Ollama를 쓰는지는 규칙으로만 정해져 있고 강제하지 않는다.
- 관문은 `core.hooksPath`에 의존한다. 새 클론(clone)에서는 `git config core.hooksPath .githooks`를 다시 설정해야 한다. `--no-verify`로 우회할 수 있다.
- Antigravity의 "15m cron" 위치를 모른다(UNKNOWN).

## 다음 행동
- Codex 복귀(2026-09-24 13:41) 후 U18–U21을 재검토한다.
- 로컬 PROVIDER_ERROR를 줄인다. 큰 파일은 compact 모드나 3b 모델로 분할하는 안을 후보로 둔다.
