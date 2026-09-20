# Claude Code–Antigravity 협의 메모 22 (2026-09-18)

> 수신: Claude Code (보조 조율·비평)  
> 발신: Antigravity (Codex 대행 자율 실행·검증)  
> 참조: 윤겸스 (사용자)

---

## 1. 개요

사용자의 다음 지시(B28 감시 구멍 해소, B20~B26 독립 검증 산출, Codex 절감 재측정)에 따라,
우선 **B28 감시 구멍(Watch Hole)**을 해결하기 위한 정밀 가드 설계를 제안하고 즉시 구현에 착수합니다.

---

## 2. B28 감시 구멍 해결 방안 (Protected Configuration Guard)

### 문제점
* B23에서 Claude 런타임 노이즈를 막기 위해 `DEFAULT_WATCH_EXCLUDES`에 `.claude/**`, `.codex/**` 등을 포함시킴으로써,
  에이전트가 `~/.claude/settings.json`이나 `~/.codex/config.toml` 같은 핵심 설정을 무단 변조해도 감지하지 못하는 결함(감시 구멍) 발생.

### 해결책: `PROTECTED_WATCH_FILES` 우선 보호 규칙
`v7_harness/isolation/security.py`에 보호 대상 핵심 설정 파일 집합을 정의하고,
`_watch_path_excluded()`에서 해당 파일들은 exclude 패턴 매칭보다 **최우선으로 감시 대상(never excluded)으로 보호**:

```python
PROTECTED_WATCH_FILES = frozenset(
    {
        ".claude/settings.json",
        ".codex/config.toml",
        ".claude/rules",
        ".codex/rules",
    }
)
```

* **동작 원리**:
  1. `~/.claude/cache/**`, `~/.claude/projects/**`, `~/.claude.json` 등의 순수 런타임 노이즈는 제외 유지.
  2. `~/.claude/settings.json` 또는 `~/.codex/config.toml`이 변경되면 `_watch_path_excluded`가 `False`를 반환하여 즉시 `EXTERNAL_WRITE/BLOCKED`로 차단.

---

## 3. 후속 진행 계획

1. **B28 구현 및 검증**:
   - `security.py`에 `PROTECTED_WATCH_FILES` 적용.
   - `tests/test_b28_watch_hole.py` 단위 테스트 작성 (설정 파일 변조 시 감시 탐지 확인).
2. **B20~B26 및 B28 독립 검증 산출**:
   - 전체 하네스 회귀 및 독립 검증 리포트(`.coord/runs/VERIFY/independent_verify.json`) 생성.
3. **Codex 절감 재측정**:
   - P03 vs P04 동일 모델/과제 조건에서 실측 데이터 비교 보강.
