## UAOS — 모든 프로젝트에 공통인 협업 운영 체계(Unified Agent Operating System)

- 명령 `uaos` = `{uaos}`. UAOS 저장소의 `v7_harness`를 어느 폴더에서든 실행한다. 아래 `uaos …`는 이 명령으로 바꿔 읽는다.
- 프로젝트 안이나 그 상위 폴더에 `.coord/PLAN.md`가 있으면 UAOS 프로젝트다. 시작할 때 `.coord/PLAN.md`의 현재 카드와 소유자를 보고 `uaos coord inbox --project <루트>`로 우편함(mailbox)을 확인한다. 세션 훅이 출석부(presence)를 자동으로 기록한다.
- UAOS 프로젝트가 아니고 둘 이상의 도구가 협업할 일이면 `uaos coord init --project <루트>`로 준비한다. 기존 파일은 덮어쓰지 않는다.
- 작업자(Ollama·Antigravity)에게는 계약 매뉴얼로만 일을 준다: `uaos pilot manual new` → `uaos pilot manual lint` → `uaos pilot run --manual <파일>`. 판정자(judge)는 작성자와 다른 도구여야 한다. 이미 정확한 코드를 안다면 `worker: apply`(토큰 0)로 한다.
- Ollama는 계산기다. 요약·추출·정확한 치환만 하고 설계·승인·판정은 하지 않는다. 같은 원인으로 두 번 실패하면 경로를 바꾼다. 유료 모델로 기다림 폴링이나 예약 호출을 하지 않는다. 기다림은 우편함과 교환원(sentinel)이 맡는다.
- 자가개선(RSI)은 증거 관문을 거친다: `uaos rsi report` → `uaos rsi propose` → 시험 실행 → `uaos rsi gate --candidate <파일>` → 작성자·검증자가 아닌 판정자가 `uaos rsi adopt`를 실행한다. 재측정해 나빠졌으면 `uaos rsi rollback`. 평가기(테스트·장부·관문 코드)는 개선 대상이 아니다.
- 멈추고 사용자에게 물을 것: 삭제, push·배포·게시, 결제, 계정·권한·시스템 설정 변경.
