# UAOS 증거 관문형 RSI 운영 정본

상태: 유지(maintained) 설계 v1, 2026-09-24. 상위 권위: 사용자 승인 경계, `AGENTS.md`, `.coord/PLAN.md`, `docs/01`, `docs/27`. 여기서 RSI(Recursive Self-Improvement)는 **모델이 자기 권한·가중치·합격 기준을 고치는 것**이 아니라, 검증된 실행 기록을 이용해 UAOS의 작업 계약·라우팅·매뉴얼을 작은 단위로 개선하는 반복 절차다. `RSI_ENABLED`는 무제한 자율 변경 허가가 아니다.

## 1. 현재 환경에서의 가치 판정

- **조건부 도입 가치 있음**: Ollama의 로컬 호출과 pilot 영수증, 고정 인수, 단일 계획이 이미 있다. 현재 기록은 Ollama 372회·입력 139,250·출력 60,883 로컬 토큰(`docs/26`의 작성 시점 집계)이다. 이는 후보를 비교할 재료이지 유료 계정 절감 증명은 아니다.
- **도입 이유**: U23은 38개 기존 테스트 통과 후에도 복구 ID 손상과 같은 초 알림 충돌이 나왔다. U23 광범위 원격 호출은 823,248토큰에 변경 0건이었고, 퇴역 C3P는 복잡성과 미검증 절감 주장 문제가 있었다. 따라서 개선 대상은 ‘모델을 더 오래 생각시키기’보다 계약 크기·반례·비용 게이트다.
- **도입하지 않을 것**: 자기 평가만으로 `DONE` 승격, 숨은 인수 변경, 승인·권한·안전 규칙 자동 완화, 모델 가중치 자가 학습, 무제한 재시도, 유료 모델 상주 폴링. 비용·품질·계정 절감의 현행 효과는 `UNMEASURED`다.
- **문헌의 해석**: Reflexion은 외부 과제 피드백을 언어 메모리로 가져와 다음 시도를 바꾸는 방식이다. Self-Refine은 반복 자기 피드백의 가능성을 보였지만, 비판적 조사에서는 신뢰할 외부 피드백 없는 자기수정의 일반적 성과가 입증되지 않았다고 정리했다. METR은 자동 점수만 최적화하면 실제 코드 품질과 괴리되거나 평가를 편법으로 통과할 수 있음을 관찰했다. UAOS는 **독립 실행·숨은 반례·사람이 정한 목표**를 필수 외부 피드백으로 둔다.

연구 원문: [Reflexion](https://arxiv.org/abs/2303.11366), [Self-Refine](https://arxiv.org/abs/2303.17651), [자기수정 비판적 조사](https://arxiv.org/abs/2406.01297), [OpenAI 에이전트 평가](https://developers.openai.com/api/docs/guides/agent-evals), [OpenAI 평가 모범사례](https://developers.openai.com/api/docs/guides/evaluation-best-practices), [METR 실제 코드 평가](https://metr.org/blog/2025-08-12-research-update-towards-reconciling-slowdown-with-time-horizons/), [METR 보상 편법 사례](https://metr.org/blog/2025-06-05-recent-reward-hacking/).

## 2. 한 사이클의 불변 순서

1. **관찰(Observe)**: 동일 `work_id`로 Codex·Claude·Antigravity의 계정 창 전후 스냅샷과 Ollama·pilot의 토큰·벽시계·종료코드·변경 집합·인수 결과를 기록한다. 원문 프롬프트·비밀·세션 값은 기록하지 않는다. 계정 수치가 없으면 `UNKNOWN`이다.
2. **가설(Hypothesize)**: Codex, 또는 Codex 부재 중 Claude가 `문제/비교 기준선/예상 이득/실패 위험/중지 조건` 5칸을 작업 카드에 작성한다. Antigravity는 반례나 설계 의견을 제시할 수 있지만 자기 변경의 유일한 판정자가 될 수 없다. Ollama는 로그 분류·수치 추출만 한다.
3. **고정 인수(Freeze)**: 변경 작성자와 다른 판정자가 실패 경로·동시성·범위 밖 변경을 포함한 인수를 먼저 고정하고 SHA-256을 기록한다. 인수·평가기·테스트 이름에 따라 동작을 바꾸는 후보는 거부한다.
4. **작은 후보(Build)**: 한 카드·한 작성자·한 번의 격리 pilot. 명확한 치환은 `--worker local`; 설계 판단이 필요할 때만 제한된 Antigravity. 원격 승격은 카드의 최대 호출 수·허용 파일·비용 상한이 있을 때만 한다.
5. **대조(Evaluate)**: 같은 과제 분포·같은 숨은 인수로 전후 품질, 실패율, 재작업률, 벽시계, 각 공급자의 별도 계정 잔여율을 비교한다. 토큰 대리지표와 실제 한도 절감은 합치지 않는다. 작성자 자기 PASS, 출력 없음, 인수 미실행은 불합격이다.
6. **판정/복귀(Decide/Roll back)**: 품질 저하·P1·3배 비용/시간 회귀면 채택하지 않는다. 증거가 부족하면 `UNMEASURED`/`REVIEW`로 둔다. 안전/권한/승인 경계를 바꾸는 안은 RSI 자동 승격 대상이 아니며 사용자 승인 게이트에 남긴다. 채택된 규칙은 정본 한 곳에 반영하고 다음 10개 유효 실행에서 다시 검증한다.

## 3. 도구별 RSI 권한

| 도구 | 할 일 | 할 수 없는 일 |
|---|---|---|
| Codex | 목표·기준선·인수·최종 판정·복귀 판단 | 자기 작성물을 자기 검증만으로 완료 처리 |
| Claude Code | Codex 활동 중 제한된 구현/독립 검증; 부재 중 같은 관문으로 대행 | 한도 추정만으로 Antigravity에게 총괄 이양, 승인 상속 |
| Antigravity | 좁은 원격 구현 또는 다른 작성자의 반례 검증; 증거가 있는 개선안 제안 | 자기 점수로 자기 변경 승격, 반복 총괄 대행, 무제한 원격 호출 |
| Ollama | 명시된 추출·분류·정확한 치환·로컬 토큰 계측 | 목표 설정, 품질 판정, 승인, 다음 단계 자율 선택 |

Google은 Antigravity의 산출물(Artifacts)을 검토 가능한 계획·diff·walkthrough로 설명한다. UAOS에서는 그것을 증거 후보로만 사용하고 실제 파일·독립 인수로 확인한다. [Google 공식 설명](https://developers.googleblog.com/build-with-google-antigravity-our-new-agentic-development-platform/)

## 4. 상시 사용 기록과 개선 관문

정본 장부는 [`.coord/usage/README.md`](../.coord/usage/README.md)와 `runs.jsonl`이다. 각 호출/작업의 `work_id`, 도구, 모델, 입력·출력 토큰(있는 경우), 벽시계, 원본 영수증 경로, 인수 결과, 독립 검증자를 남긴다. Ollama API는 `prompt_eval_count`, `eval_count`, `total_duration`을 반환한다. [Ollama 공식 API](https://docs.ollama.com/api/generate). U27 이후 파일럿 종료는 프로젝트 v2 장부에 자동 기록된다. 직접 `olla` 호출의 원시 이벤트는 전역 `OLLA_USAGE`에 남으며, 프로젝트 장부와 합칠 때 같은 작업 ID·영수증으로 중복을 제거한다.

10개의 유효하고 같은 유형인 표본이 모일 때마다 성공률·재작업률·50/80백분위 벽시계·Antigravity 승격률·계정 잔여율 변화·P1을 비교한다. 10은 분석 시작을 위한 초기 정책값이며 통계적 충분성 증명이 아니다. 개선안은 최대 1개씩 시험한다. **모든 착수 시도는 실패율·재작업률·비용의 분모에 남긴다.** 누락·오염 영수증은 `MISSING_RECEIPT`, `CONTAMINATED_WINDOW`, `RESET_CROSSED`처럼 사전 정의한 객관적 코드로만 계정 절감률의 *비교 표본*에서 제외하고, 제외 수·사유·원본 행은 별도 감사 집계에 전수 보존한다. 작성자가 결과를 보고 임의로 제외할 수 없다. Claude의 `/usage` 세션 토큰과 구독 한도 막대는 별개로 보관한다. [Claude 공식 비용 안내](https://code.claude.com/docs/en/costs)

## 5. 프로젝트 완료 관문

2026-09-25 기준 U23/U27 독립 반례, Codex 복귀 13관문, 전체 회귀 580개와 compileall이 통과해 구현 완료 관문을 충족했다. 실패한 R1 인프라 측정은 삭제하지 않고 역사적 `SUPERSEDED` 표본으로 보존하며, 유효 대체 측정은 R2/R4로 분리한다. 계정 한도 절감은 여전히 `UNMEASURED`다. 삭제·원격 push·배포·결제·계정/권한/시스템 설정은 각 행동별 사용자 승인 없이는 실행하지 않는다.
