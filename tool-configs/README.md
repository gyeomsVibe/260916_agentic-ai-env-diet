# 도구 설정 사본 (tool-configs)

저장소 밖(사용자 홈)에 있어 버전 관리가 안 되던 설정의 사본입니다. 잃어버리거나 새 PC로 옮길 때 이 폴더에서 복원합니다. 전역 규칙 정본(Codex·Antigravity)은 `260718.../shared/global-rules`에 있고, 여기에는 그 생성기가 배포하지 않는 것만 둡니다.

| 사본 | 원래 위치 | 내용 |
|---|---|---|
| `claude/CLAUDE.md` | `~/.claude/CLAUDE.md` | Claude Code 전역 규칙 |
| `claude/output-styles/brief-ko.md` | `~/.claude/output-styles/` | 매 요청에 붙는 보고 양식(결과·과정·근거) |
| `claude/settings.hooks.json` | `~/.claude/settings.json`의 `hooks`·`outputStyle`만 | `olla` 훅 3종(작업 시작·읽기 직전·턴 종료) |
| `codex/hooks.json` | `~/.codex/hooks.json` | `olla` 훅 3종(작업 시작·셸 읽기 직후·턴 종료). Codex `/hooks`에서 신뢰해야 작동 |

권한 목록 등 나머지 설정은 담지 않습니다. 비밀값은 없습니다.
