# 내일 기상 후 즉시 진행할 작업 가이드 (NEXT MORNING RESUME)

> 생성 일시: 2026-09-25T03:52:00+09:00 (Antigravity 작성)
> 현재 상태: 전체 회귀 테스트 592/592 무결점 통과 (exit 0), 최신 커밋 `2e0453f` origin/main 푸시 완료

---

## 1. 사전 확인 (Wake-up Check)

기상 후 아래 명령 2개로 시스템 무결성을 5초 만에 확인합니다:
```powershell
# 1. 깃 상태 확인 (origin/main 동기화 확인)
git status

# 2. 하네스 상태 확인 (LOCKED: CLEAN 확인)
python -m v7_harness.cli coord status
```

---

## 2. 4단계 UNMEASURED 실측 실행 순서

### [1단계] M2: Codex 순수 토큰 절감률 정밀 집계 (소요 시간: 10초)
R3(P05), R4(P06, P07)의 measurement JSON 3건으로부터 이미 `MEASURED_AND_VERIFIED` 판정된 Codex 토큰 절감 수치를 단일 테이블로 집계합니다.
- 실행 명령:
```powershell
python -c "import json; p06=json.load(open('.coord/runs/R4/measurement_P06.json', encoding='utf-8')); p07=json.load(open('.coord/runs/R4/measurement_P07.json', encoding='utf-8')); print('P06:', p06['comparison']['savings']); print('P07:', p07['comparison']['savings'])"
```
- 결과 반영: `docs/` 또는 `PLAN.md`에 "계정 쿼터와 분리된 Codex 순수 토큰 절감 지표(-77.0%)"로 공표.

---

### [2단계] M3: 올라마 MCP 사용률 실측 (소요 시간: 30초)
B73(MCP 등록) 이후 세션 동안 `olla` MCP(`local_read_map`, `local_draft`, `local_search`)의 실제 호출 통계를 조회합니다.
- 실행 명령:
```powershell
python -m v7_harness.olla stats --session
```
- 결과 반영: `via=mcp` 호출 횟수 및 토큰 절감량 추출.

---

### [3단계] M1: 로컬 올라마 7B 실과제 성공률 실측 갱신 (소요 시간: 약 10분)
P08(coord status), P09(CSV sort)가 연속 성공한 방식을 적용하여, 명확한 단일 파일 단위 작업 10건(P10~P19)을 `pilot run --worker local`로 일괄 실행하고 최신 성공률을 산출합니다.
- 실행 대상:
  - 문자열/수학/포맷 변환/유효성 검사 등 구체성 80점 이상의 기계적 유틸리티 10건
  - 유료 API 토큰: 0개 소모
- 실행 명령:
  - 개별 실행: `python -m v7_harness.cli pilot run --task <ID> --source . --prompt-file <prompt> --accept-cmd "<cmd>" --worker local --work-dir .work/pilot_<ID>`

---

### [4단계] 구조적 측정 불가 항목 영구 UNMEASURED 선언
- 대상:
  1. **실제 계정 쿼터 절감률**: API 제공사(Anthropic, OpenAI)의 쿼터 환산 공식(비공개) 부재로 측정 불가.
  2. **하루 운영 지연**: 동일 시기 동일 개발자의 완벽한 대조군 부재로 측정 불가.
  3. **자율 사용률**: Codex/Claude가 활성 세션을 수십 회 수행하기 전까지 세션 누적 대기.
- 결과 반영: `.coord/PLAN.md`에 사유와 함께 정식 판정 종결 기록.

---

## 3. Codex 가동 시 보고 및 승인 절차

Codex가 복귀(한도 해제 또는 재기동)하면 즉시 아래 절차를 통해 인계 및 승인을 받습니다.

1. **디스크 우편함 확인 유도**:
   - `.coord/mailbox/inbox/`에 Antigravity의 정식 인계 공문(`20260925_antigravity_to_codex_brief.json`)이 보관되어 있음.
2. **복귀 점검표 확인**:
   - `.coord/codex_return_checklist.md`의 **23번 ~ 27번 항목** 검토 요청:
     - 23: B65 Antigravity 훅 및 턴 분석 완료
     - 24: P08 `coord status` CLI 구현 (로컬 파일럿, 번들 `9f4da7542ebe`)
     - 25: P09 CSV 정렬 유틸리티 구현 (로컬 파일럿, 번들 `2e3927305284`)
     - 26: P08 회귀 수리 (`cmd_coord_log` 복구, 592/592 전체 통과, 커밋 `2e0453f` 푸시 완료)
     - 27: UNMEASURED 전수 인벤토리 및 실측 세팅
3. **최신 브리핑 갱신**:
   - `python -m v7_harness.cli coord brief --write`로 `.coord/codex_brief.md` 동기화 완료됨.
4. **Codex 대화창에서의 발화**:
   - Codex에게 다음 한 줄을 입력하여 보고를 승인받으시면 됩니다:
     > "Codex, 부재 중 Antigravity가 대행 수행한 업무(B65 훅, P08·P09 로컬 파일럿 0원 구현, cli 회귀 복구 592건 전수 통과, 커밋 2e0453f 푸시, UNMEASURED 인벤토리)를 `.coord/codex_return_checklist.md`(23~27번)와 우편함에서 확인하고 승인하라."
