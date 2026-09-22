# 도구 설정 사본 (tool-configs)

저장소 밖(사용자 홈)에 있어 버전 관리가 안 되던 설정의 사본입니다. 잃어버리거나 새 PC로 옮길 때 이 폴더에서 복원합니다. 전역 규칙 정본(Codex·Antigravity)은 `260718.../shared/global-rules`에 있고, 여기에는 그 생성기가 배포하지 않는 것만 둡니다.

| 사본 | 원래 위치 | 내용 |
|---|---|---|
| `claude/CLAUDE.md` | `~/.claude/CLAUDE.md` | Claude Code 전역 규칙 |
| `claude/output-styles/brief-ko.md` | `~/.claude/output-styles/` | 매 요청에 붙는 보고 양식(결과·과정·근거) |
| `claude/settings.hooks.json` | `~/.claude/settings.json`의 `outputStyle`·`env`만 | 자동 압축 22%(1M 창 약 220k). 훅 없음 |
| `codex/hooks.json` | `~/.codex/hooks.json` | 비어 있음 |
| `antigravity/hooks.json`, `mcp_config.json` | `~/.gemini/config/` | 비어 있음 |
| `bin/olla`, `bin/olla.cmd` | `D:/AI-Models/bin/` | 퇴역. 어느 도구에도 연결돼 있지 않음 |

올라마(olla) 연결은 2026-09-23에 3대 도구 모두에서 뺐습니다. 근거는 `.coord/runs/U17/mia_strategic_20260923.md`의 Retire 절을, 되돌릴 때는 `.work/backup_20260923/olla_removal/`의 원본과 이 폴더의 git 기록을 보세요.

권한 목록 등 나머지 설정은 담지 않습니다. 비밀값은 없습니다.
