# 사용자 지시 전달 39 (Claude → Codex·Antigravity, 2026-09-19)

## 사용자 고정 지시

> 전체 로컬 워크스페이스에는 `260916_agentic-ai-env-diet` 폴더 하나만 존재한다. 이 프로젝트의 모든 작업 공간은 그 안의 별도 섹션에서 생성하고 해결한다.

## 반영 완료

- 하네스(B55C, pilot 경로 APPLIED): `.work/`와 `.coord/pilot`을 manifest·staging 기본 제외 → 프로젝트 안에 work-dir을 두고 `--source .`로 자기 자신을 대상으로 해도 복사·불일치 문제 없음. 전체 325 OK.
- 워크스페이스 정리: 형제 폴더 33개(`260916_pilot_*`, `260916_agentic-ai-env-diet-r0-pilot`)를 `260916_agentic-ai-env-diet/.work/`로 **이동**(삭제 0, 이름 유지). 최상위에는 프로젝트 폴더 하나만 남음.
- 스크립트 경로: `measure_codex_cost.py`, `measure_p05.py`, `R1/run_r1_measurement.py`, `R3/run_r3_measurement.py`의 `WORKSPACE`를 `PROJECT / ".work"`로 변경. R3 드라이버 시드 경로 확인 완료.
- `AGENTS.md`에 "워크스페이스 단일 폴더 규칙" 추가.

## 앞으로의 규칙 (Codex·Antigravity 공통)

1. 새 샘플·사본·`--work-dir`은 **반드시** `.work/<이름>`에 만든다(예: `--work-dir .work/pilot_T01`).
2. 워크스페이스 최상위(`D:\D_Workspace_NB\-agentic-ai-workspace`)에 `260916_*` 형제 폴더를 만들지 않는다.
3. **R3 2차(_02, 16:08 예약)**: 드라이버가 이미 `.work`를 가리키므로 그대로 실행하면 된다. 다른 경로를 하드코딩한 스크립트가 있으면 먼저 `.work`로 바꾼다.
4. 예전 경로(`..\260916_pilot_*`)를 참조하는 문서·로그는 역사 기록으로 두되, 실행 명령은 `.work\...`를 쓴다.
