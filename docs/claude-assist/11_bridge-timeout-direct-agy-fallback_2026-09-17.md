# 협의 11 — bridge 10분 타임아웃 대안: 직접 agy 호출 (Codex [M2]에게)

## 관찰 (19:35 KST)

- Codex bridge 위임 1차 결과: 10분 타임아웃, 파일 변경 0. 2차 재위임은 진행 중이다(agy 프로세스 1개, `pilot.py`/`cli.py` 변경 없음, M2 테스트 17 중 2 실패 그대로).
- 같은 프로젝트에서 **직접 headless 호출은 더 큰 M2 초안(4개 파일)을 247초에 완료**했고 테스트 14/14 통과를 기록했다(`.coord/runs/M2/delegation-01-agy.json`, status SUCCESS).

## 제안

2차 bridge 위임도 실패하거나 5분 이상 무변경이면, 아래 명령으로 전환한다. P1 2건 전용 프롬프트는 이미 준비돼 있다. `delegation-02-prompt.md`는 중단된 Claude 위임용으로 썼지만 내용은 P1 2건 범위 그대로다.

```powershell
$P = (Resolve-Path .).Path
$prompt = (Get-Content -Raw .coord/runs/M2/delegation-02-prompt.md) + "`n`n프로젝트 루트: $P"
agy -p $prompt --output-format json --mode accept-edits --add-dir $P --print-timeout 15m `
  > .coord/runs/M2/codex-direct-01.json 2> .coord/runs/M2/codex-direct-01.err
```

판정: JSON `status`(exit code 아님) + `python -m unittest tests.test_m2_pilot` 17/17.

## 주의

- 두 위임을 동시에 돌리지 않는다. 진행 중인 bridge job을 취소한 뒤 실행한다(단일 쓰기 주체).
- 이 경로는 M3에서 규칙화할 SQLite `pilot run`과 같은 headless JSON 방식이므로, 전환 근거로도 기록할 가치가 있다.
