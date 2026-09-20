# 조율 계층 (U15)

세 도구(Codex·Antigravity·Claude Code)가 각자 한 일을 한 곳에 모아 Codex 대화창으로 보내는 통로다.
사람이 읽는 보고서가 아니라 판정에 쓰는 사건과 증거를 다룬다.

## 흐름

```
사건 1줄  →  .coord/stream/<날짜>.jsonl
                     ↓  접기(마지막 판정 이후만, 60줄·6KB 상한)
             .coord/codex_brief.md
                     ↓  상태가 바뀐 경우만 1건
   codex queue --thread <세션> --message <5줄>
                     ↓
   Codex 창에 "다른 작업에서 …이(가) 보냄"
```

## 명령

```bash
# 사건 남기기 (실행·판정에는 증거가 필수)
python -m v7_harness.cli coord log --actor claude --kind RUN --step U15-S4 \
  --summary "전달기 테스트 10건 통과" --ref v7_harness/coord/notify.py \
  --cmd "python -m unittest tests.test_u15_notify_codex" --exit-code 0

# 브리핑 만들기 (판정 대기는 PLAN에서 자동으로 채운다)
python -m v7_harness.cli coord brief --owner "Codex" --write

# 보내기 (기본은 드라이런, 스레드는 이 프로젝트의 최신 Codex 세션)
python -m v7_harness.cli coord notify --actor claude --headline "R2 반영, 전체 380 OK"
python -m v7_harness.cli coord notify --actor claude --headline "..." --send

# 판정 끝난 사건 보관
python -m v7_harness.cli coord archive
```

## 규칙

| 항목 | 값 |
|---|---|
| 판정(`VERDICT`) 기록 | Codex만 |
| `RUN`·`VERDICT` | `--cmd`와 `--exit-code` 필수 |
| 요약 | 200자, 한 줄, 비밀값 패턴 금지 |
| 브리핑 | 60줄·6KB, 같은 입력이면 같은 해시 |
| 큐 메시지 | 6줄·500자, 첫 줄은 `[DATA]`, 값 대신 경로·종료 코드 |
| 전달 빈도 | 브리핑이 바뀔 때만, 분당 1건·하루 24건 |
| 스레드 | 지정하지 않으면 이 프로젝트를 다루는 최신 세션, 못 고르면 보내지 않음 |

## 안전 설계 근거

- `.coord/stream`과 `.coord/codex_brief.md`는 원본 매니페스트에서 제외한다. 그렇지 않으면 기록 한 줄이 파일럿 실행을 `SOURCE_DIVERGED`로 무효화한다.
- 쓰기는 `.coord/stream/.stream.lock` 하나로 직렬화한다. Windows에서 여러 주체의 동시 append는 줄을 통째로 잃고, 보관이 잠금 밖에서 읽으면 그 사이 사건이 사라진다(둘 다 실측·교정됨).
- 큐 메시지 첫 줄 `[DATA]`는 도구가 보낸 내용이 사용자 지시로 오인되지 않게 한다.

설계와 실측 기록은 `.coord/tasks/U15-coordination-stream.md`.
