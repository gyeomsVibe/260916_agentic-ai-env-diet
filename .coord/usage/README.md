# UAOS 사용 기록 장부

상태: 유지(maintained), 파일럿 자동 수집 활성. 정본 정책: `docs/31_evidence-gated-rsi-for-uaos.md`. `runs.jsonl`은 한 줄에 한 JSON 객체를 추가하는 프로젝트 장부다. 기존 행 수정·삭제·원문 프롬프트/비밀 기록은 금지한다. 잘못된 행은 새 `correction_of` 행으로 정정한다.

신규 v2 행의 필수 필드: `schema`, `work_id`, `actor`, `model`, `kind`, `collection_mode`, `input_tokens`, `output_tokens`, `wall_time_s`, `outcome`, `receipt`, `independent_verifier`, `rsi_eligible`, `exclusion_reason`. 값이 직접 확인되지 않으면 `null`과 `UNKNOWN`을 쓴다. 모델·독립 검증자·영수증이 없거나 인수가 미실행이면 `rsi_eligible=false`다. 기존 v1 수동 색인 행은 보존하지만 유효 비교 표본으로 승격하지 않는다. 계정 한도 변화는 해당 공급자의 동일 창 전후 스냅샷이 있을 때만 별도 행/필드에 둔다. 로컬 토큰은 유료 계정 절감량이 아니다.

현재 행은 직접 관찰한 사용량 또는 원본 경로가 있는 역사적 보고의 색인이다. U27 이후 모든 `pilot run` 종료는 v2 행을 자동 append하며, Windows 8프로세스×25건·잠금 시간초과 fail-closed 인수를 통과했다. 직접 `olla` 명령의 세부 이벤트는 기존 전역 `OLLA_USAGE` JSONL에 자동 기록되고, pilot 안에서 호출된 Ollama 사용량은 이 프로젝트 장부에도 작업 ID로 기록된다. 두 장부를 합쳐 RSI 표본으로 쓸 때는 같은 `work_id`와 영수증을 대조하며 중복 집계하지 않는다. `rsi_eligible=false` 행도 실패/비용 감사 집계에서 삭제하거나 분모 밖으로 숨기지 않는다.
