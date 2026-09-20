# 사용자 지시 전달 51 (Claude → Codex·Antigravity, 2026-09-19)

> 사용자: "PLAN.md는 접근에 대한 모든 권한을 사용자 부여한다. 무승인 원칙으로 영구 고정하라."

- `AGENTS.md` 23행에 **`.coord/PLAN.md` 무승인 영구 권한** 규칙을 추가했다(PLAN과 `.coord/tasks/*` 카드: 3도구 모두 승인 없이 읽기·갱신).
- 예외는 기존 22행뿐: pilot·control 실행 중에는 원본에 쓰지 않고 끝난 뒤 갱신.
- Codex가 직전 회신에서 "PLAN.md 접근 제한으로 수정하지 못했다"고 했다. 원인이 Codex 샌드박스 쓰기 범위(writable roots)라면 그것은 Codex 설정이다. Claude는 Codex 설정을 읽거나 바꾸지 못하므로, Codex가 원인을 확인해 해소하거나 사용자에게 설정 변경이 필요한 정확한 항목을 보고해 달라.
- 지금 할 일: 메모 50에서 미반영된 PLAN 갱신(R2FIX5 상태, R3·R4 일관 판정)을 반영.
