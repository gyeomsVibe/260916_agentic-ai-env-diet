1) **쟁점 판정: 동의 (P2 등급)**
- 근거: `.claude/**`, `.codex/**` 일괄 제외는 `settings.json`·`config.toml`·`AGENTS.md` 등 전역 설정 변조를 놓치는 보안 구멍이 맞음. 런타임 노이즈(캐시·세션·임시파일)만 선별 제외하고 민감 설정 경로는 감시 대상(re-include)으로 정밀화해야 함.
2) **남은 완성 작업 목록 및 순서**
1. `security.py` 감시 제외 정밀화 (민감 설정 re-include / 노이즈 선별 제외).
2. 격리 반례 단위 테스트 추가 및 전체 222+ 테스트·`compileall` 회귀 검증.
3. 실전 `pilot run` 환경에서 런타임 노이즈 오탐지 0건 및 변조 정상 탐지 실측.
4. `.coord/PLAN.md`, `.coord/BACKLOG.md` 최종 동기화 및 조율자 DONE 판정.
3) **변경 파일 및 테스트 계획**
- **변경 파일**: [`v7_harness/isolation/security.py`](file:///D:/D_Workspace_NB/-agentic-ai-workspace/260916_agentic-ai-env-diet/v7_harness/isolation/security.py), [`tests/test_u13_isolation.py`](file:///D:/D_Workspace_NB/-agentic-ai-workspace/260916_agentic-ai-env-diet/tests/test_u13_isolation.py)
- **테스트 계획**: ① 민감 파일(`settings*.json`, `config.toml`, `AGENTS.md` 등) 변조 시 `EXTERNAL_WRITE` 차단 검증, ② 런타임 캐시 변경 시 거짓양성 0건 검증, ③ 전체 회귀(222+ tests, compileall) exit 0 검증.
4) **완성까지 예상 시간**: 약 20~30분 (구현/단위 테스트 10분 + 파일럿 실측 및 전체 회귀 검증 15분)
