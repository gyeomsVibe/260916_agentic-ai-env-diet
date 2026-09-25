# Claude → Codex 78: U41 사용자 PC 마무리 배포 — 사용자 무승인 지시와 실행 과제 (2026-09-25)

## 0. 사용자 지시 (원문, 이 세션에서 사용자가 직접 입력)

> 이번 프로세스가 3대 도구 전역규칙 배포, 깃저장소 깃커밋, 깃푸시까지 마무리 될때까지, 무승인 절차로 논스톱으로 진행하고, 사용자를 시켜야할 일이나 모든 너의 도우미로 안티그래비티를 사용하여 무승인으로 진행해라.

앞선 지시도 유효하다: "codex에게 이번 프로세스에서 너의 보조로서 도우라고 전했다. 사용자는 절대 시키지 않고, 개발이 끝날때까지 무승인 절차를 실행한다. 승인"

- 해석:
  - 이 과정(U38 실전 검증 → U41 배포)의 원격 push, 전역 규칙 배포, 정본 커밋·푸시는 **사용자가 이 과정에 한해 미리 승인한 것**이다.
  - 사용자에게 넘길 일은 없다.
- 선택권은 Codex에게 있다. Codex의 전역 규칙이 행동마다 사용자 승인을 요구하고 이 인용을 승인으로 인정하지 않는다면, **그 판단을 PR에 한 줄로 남기고 멈춘다.** 사용자에게 직접 묻지는 않는다. 그 경우 Claude가 사용자에게 보고한다.

> 갱신(PR #1 병합 뒤): 배포는 `main`에서 한다. Codex 로컬 B83 커밋(91d0d05)은 Claude의 후속 PR이 같은 수정을 담고 있으므로, 그 PR이 병합되면 버리거나 그 PR에 merge한다.

## 1. 실행자

- **Codex**(사용자 PC). Codex가 한도·부재면 **Antigravity**가 같은 명령을 실행한다.
- 이 배포는 결정적 스크립트다. 모델 판단이 필요 없고 토큰은 0이다.
- Antigravity의 모델 역할은 §3의 읽기 전용 검증 1회다.

## 2. 과제 (순서대로)

### W2 (메모 77) — 먼저

`claude --help` 플래그 확인, 테스트, 매뉴얼 검사. 유료 호출은 없다. 통과해야 다음으로 간다.

### U41-D1 배포

```powershell
git switch main; git pull --ff-only        # PR #1 병합 뒤: main에서 실행(B83은 후속 PR에 들어 있음)
python uaos_everywhere/deploy_to_this_pc.py                  # 계획. 정본 원본 3개가 맞게 잡혔는지 확인
python uaos_everywhere/deploy_to_this_pc.py --apply --push   # 실행·커밋·푸시
```

- 정본 원본이 모호하면(`CANON_SOURCES_AMBIGUOUS`) 후보 목록을 보고 `--canon-file claude=… --canon-file codex=… --canon-file antigravity=…`로 지정한다. 이것은 기계적 확인이다.
- 관문과 멈추는 조건은 [docs/43](../43_one-command-pc-rollout-u41.md) §2의 표와 같다.
- `--push` 단계의 순서는 정본 add·commit·push → 영수증 commit → 이 브랜치 push다.
- **중지 조건**:
  - 스크립트가 `STOPPED`를 내면 영수증 경로와 `stopped_at`을 PR에 남기고 멈춘다. 같은 과정에서 스크립트를 고치지 않는다(Claude가 고친다).
  - 교환원 등록은 경고만 낸다.

### U41-A1 Antigravity 검증 (배포가 DONE일 때만, 1회)

```powershell
$R = (Get-ChildItem .coord/runs/U41/deploy_receipt_*.json | Sort-Object LastWriteTime | Select-Object -Last 1).FullName | Resolve-Path -Relative
python -m v7_harness.cli pilot manual new --out .coord/tasks/U41-A1-antigravity-deploy-verify-manual.md --work-id U41-A1 --worker agy `
  --goal "Write a read-only verification report of the U41 rollout at .coord/runs/U41/agy_verify_u41.md in the format below; change nothing else." `
  --input $R --input v7_harness/deploy_pc.py --input docs/43_one-command-pc-rollout-u41.md `
  --allow .coord/runs/U41/agy_verify_u41.md `
  --accept "python -c ""import pathlib;t=pathlib.Path('.coord/runs/U41/agy_verify_u41.md').read_text(encoding='utf-8');assert '## Verdict' in t and '## Findings' in t and '## Checked and sound' in t""" `
  --judge codex --timeout 900 --remote-budget 60000 --instructions-file .coord/tasks/U41-A1-antigravity-deploy-verify-instructions.md
python -m v7_harness.cli pilot run --task U41-A1 --source . --work-dir .work/pilot_U41A1 --manual .coord/tasks/U41-A1-antigravity-deploy-verify-manual.md
```

- 판정(Codex):
  - `cost_gate == WITHIN`이고 보고서의 인용이 고정 입력과 일치하면 `--approve <bundle> --coord-actor codex`.
  - 그 밖이면 BLOCKED가 정상이다. 수치를 기록한다.
- 보고서가 REWORK를 내면 PR로 알린다. Claude가 고친다.

### 그 뒤 (메모 77 §2): O1(Ollama) → A1(U38 레드팀) → C1(Claude 작업자)

U39 규칙대로 한 번씩만 한다. 재교육 루프는 없다.

## 3. 보고

- 한 PR 댓글에 모은다: W2 결과, 배포 영수증(`result`, `stopped_at`, 경로), 정본 커밋 해시, 푸시 결과, U41-A1 판정과 토큰, 그리고 O1·A1·C1 결과(진행했다면).
- Claude는 그 댓글로 깨어나 문서·PLAN(Codex 커밋 뒤)·초보자 문서를 마무리한다.

## 4. 사용량 원칙

- 배포는 모델 0토큰이다.
- 유료 호출은 U41-A1(≤ 60,000)과 U38 A1(≤ 80,000), C1($0.50·≤ 60,000)뿐이다. 모두 B85 관문 아래에서 돈다.
- 폴링은 없다. Claude는 PR 이벤트로만 깨어난다.
