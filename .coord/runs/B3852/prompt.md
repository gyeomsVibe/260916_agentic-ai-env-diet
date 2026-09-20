# 실행 규칙(필수)
- 백그라운드 작업 금지, 프로젝트 밖(TEMP 포함) 쓰기 금지. 동기적으로 끝낸 뒤에만 최종 답변(수정 파일, Ran N / OK).
- 테스트 파일 수정 금지. 테스트 값 맞춤 분기 금지.

# B38 + B52

수정 허용: `v7_harness/pilot.py`만.

1. B38: `_resolve_accept_tokens(cmd: str) -> list[str]` 함수를 추가한다. `shlex.split(cmd, posix=False)` 후 따옴표를 벗기고, 첫 토큰이 `python`, `python.exe`, `python3`, `py`(대소문자 무시)면 `sys.executable`로 바꾼다. 나머지는 그대로. shell 연산자가 없는 인수 명령 실행 경로(`shell=False`)가 이 함수를 쓰도록 한다. staging cwd에 놓인 `python.exe`가 먼저 실행되지 않게 하는 목적이다.
2. B52: `_record_checkpoint_and_identity` 호출을 감싼 `except RuntimeError: pass` 두 곳을 없애고, 거부되면 summary에 `error_detail`로 `CHECKPOINT_REFUSED: <메시지>`를 남긴다(상태·판정은 바꾸지 않되, 원인을 숨기지 않는다). 소스에 문자열 `CHECKPOINT_REFUSED`가 들어가야 한다.
3. 인수: `tests/test_b38_b52.py`, `tests/test_b46_b47_hardening.py`, 전체 discover 통과.
