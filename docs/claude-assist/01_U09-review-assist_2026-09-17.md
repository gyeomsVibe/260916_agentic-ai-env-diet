# Claude → Codex 지원 메모 01 — U09 v9 검토 보조

- 대상: `docs/13_U09_unified-implementation-design_v9_2026-09-17.md`
- 성격: 참고 입력. 판정 권한은 Codex에게 있다.

## A. 실측 증거 (agy 1.2.4, 2026-09-17 02:53~02:57, 비TTY, `--dangerously-skip-permissions` 없음)

| # | 명령 | 결과 |
|---|---|---|
| E1 | `agy -p "hello.txt 생성" --output-format json --sandbox --mode accept-edits` (cwd=scratch) | **exit 0**, `status:"ERROR"`, `error:"503 No capacity available for model gemini-3.8-flash-high"`, `response:"DONE"`, 156초, input 55,808 토큰. **파일 미생성** |
| E2 | `agy -p "echo shell-ok > shell.txt 실행" --output-format json --sandbox --mode accept-edits` (cwd=scratch) | **exit 0**, `status:"ERROR"`(동일 503), `response`는 성공 주장. **실제로 cwd가 아닌 `C:\Users\Kimyoongyeom\shell.txt`에 파일 생성됨**(Claude가 확인 후 삭제) |

도출 사실:
1. **exit code는 성공 신호가 아니다.** ERROR에도 exit 0이다. → envelope `status` 필수.
2. **`status:ERROR`여도 부작용이 발생할 수 있다.** 응답은 "DONE"을 주장했다. → v9의 `SIDE_EFFECT_UNKNOWN`/reconcile 설계가 실측으로 뒷받침된다. ERROR 뒤 자동 재실행 금지가 맞다.
3. **호출 cwd는 작업 경계가 아니다.** `--sandbox`에서도 shell이 사용자 홈에서 실행돼 홈에 썼다. → v9 판단("`--add-dir`·sandbox는 보안 경계 아님, staging/worktree 격리 필요")이 실측으로 뒷받침된다. worker 실행 시 workspace를 staging 경로로 명시해야 하고, 사후 검사는 staging뿐 아니라 **홈 등 외부 경로 변경 감지**도 필요하다.
4. **권한 우회 없이 파일 편집은 성공하지 못했다.** 503 때문인지 권한 정지인지는 분리되지 않았다(`UNKNOWN`). U11 spike에서 모델 고정(`--model`) + allow 규칙으로 재측정이 필요하다.
5. **503 capacity는 별도 오류 클래스다.** 한 번에 2분 넘게 소모된 뒤 반환됐다. → `TRANSIENT_CAPACITY`: 모델 전환 또는 backoff 대상.

## B. v9의 타당한 수정 — Claude 동의

- "런처 하나"는 여러 CLI 프로세스를 막지 못한다 → 실제 단일 writer 소유 필요.
- `--add-dir`·sandbox는 격리 경계가 아니다(E2로 확인).
- 같은 디스크의 JSONL 폴백은 disk-full·손상에 함께 실패한다.
- 비Git 사후 diff는 탐지일 뿐 보호가 아니다 → staging + promotion.

## C. 사용자 직접 지시와 어긋난 항목 — 복원 요청

사용자는 이 프로젝트에서 다음을 명시적으로 지시했다(Claude 대화창, 2026-09-17): "사용자 요구를 그대로 반영", "Antigravity 사용량 판단은 AI가 할 일이 아님", "경험에 따른 사용자 제안에 토 달지 말 것". v9 §3·§23은 이를 기각했다. 안전 설계를 유지하면서 사용자 지시를 살리는 조정안을 제시한다.

| 항목 | v9 처리 | 조정안(안전 유지 + 사용자 지시 보존) |
|---|---|---|
| R25 반박 금지 | 기각 | 제거하지 않는다. "사용자 목표·전제·역할 정의는 재검토하지 않는다. 구현 수단의 결함은 증거와 함께 **보강안**으로만 제시한다"로 문구 변경. v9의 증거 기반 검증은 그대로 수단 보강에 쓰인다. |
| R19 backend=Codex / frontend=Antigravity | 기각(동적 lease로 대체) | **둘 다 쓴다.** `AGENTS-CONSENSUS.md`의 디렉터리 소유 표를 사용자 기본 템플릿(backend/ Codex, frontend/ Antigravity, 루트 공유 명세 Codex)으로 두고, v9 동적 resource lease(포트·DB·캐시·빌드 산출물)를 그 위에 추가한다. 디렉터리 소유 변경은 사용자 확인 사항으로 둔다. |
| R24 한 대화창 한 단계 + 역질문 | 기각(자동 진행) | 사용자 원문 요구다. **설계·구축 단계(U10~U17)**는 단계 종료 시 한 줄로 다음 단계를 묻는다. **구축된 런타임(R20 전면 자동화)** 안에서는 작업 단계를 자동 진행한다. 두 요구의 적용 층이 다르므로 충돌하지 않는다. |
| P2 사용량 차이 / P6 제품 강점 | "측정할 가설" | 전제로 유지한다. 측정값은 라우터의 **운영 파라미터**(예: quota 잔량·503 빈도)로만 쓰고, 전제 자체를 뒤집는 판정 근거로 쓰지 않는다. |

## D. 구현 부담 경감 제안 (선택)

- v9 bootstrap의 `coordctl run-once` foreground 모드를 **U11 1차 완성 목표**로 두고, Named Pipe 장수명 broker는 fault test F01 등이 foreground로 충족되지 않을 때 승격한다. 단일 writer는 Windows named mutex(`Global\coordd-<projecthash>`) 획득 프로세스만 DB 쓰기를 허용하는 방식으로 먼저 보장한다. 모델 호출은 트랜잭션 밖에서 한다.
- `--dangerously-skip-permissions` 전면 금지는 P5(무승인 권한)와 E1·E4(권한 없이 편집 불성공 가능) 사이에서 자동화를 멈출 수 있다. 조정안: **staging copy 안에서만 허용**하고, 실행 후 원본·홈·staging 밖 경로의 변경 감지(E2 대응)가 통과해야 promotion한다.

## E. U11 spike 체크리스트 제안

1. `--model` 고정 + allow 규칙 + 권한 우회 없음 → staging 편집 성공 여부
2. 같은 작업을 staging 안에서 권한 우회로 실행 → 성공 여부와 외부 경로 변경 0 확인
3. 503 capacity 재현 시 envelope·exit·부작용 기록
4. `status:ERROR` + 부작용 발생 케이스를 `SIDE_EFFECT_UNKNOWN`으로 분류하는 테스트
5. worker workspace 명시 방법(`--add-dir`, `--project`, cwd) 중 실제 shell 실행 경로를 결정하는 인자 확인
