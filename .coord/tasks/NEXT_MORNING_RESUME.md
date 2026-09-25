# 2026-09-26 02:57 Codex 기상 및 즉시 수신 가이드 (CODEX RESUME)

> **기상 예정 시각**: 2026-09-26T02:57:00+09:00 (Codex 쿼터 리셋 및 세션 복귀)  
> **상태**: Antigravity 권한대행 완결 (U31~U42 DONE, 전체 710 회귀 통과, PC 전역 배포 완료)

---

## 1. 구동과 동시 자동 수신 프로세스 (Startup Flow)

Codex가 구동되면 UAOS 런타임에 의해 아래 순서로 즉시 수신 및 연동됩니다:

1. **세션 훅 자동 감지**: Codex 시작 훅(`hooks.json`)이 출석부(`coord presence --tool codex --state ACTIVE`)를 갱신합니다.
2. **사서함 즉시 조회**:
   ```bash
   python -m v7_harness.cli coord inbox
   ```
   수신함에 적재된 `codex_resume_report_20260925.json` 통지를 확인하고 아래 명령으로 수신 확인(ACK)합니다:
   ```bash
   python -m v7_harness.cli coord ack --id codex_resume_report_20260925
   ```
3. **권한대행 보고서 열람**:
   `.coord/tasks/CODEX_PROXY_CLOSEOUT_REPORT_20260925.md`를 열람하여 부재 중 종결된 U31~U42 내역을 확인합니다.
4. **복귀 점검표(Checklist) 28~33번 항목 1분 검증**:
   `.coord/codex_return_checklist.md`의 신규 검증 항목을 확인합니다.
5. **독립 회귀 검증 (1회 실행)**:
   ```bash
   python .coord/runs/run_regression.py
   ```
   710개 단위/통합 테스트 전건 Green(exit 0)을 확인하면 인계가 100% 완료됩니다.
