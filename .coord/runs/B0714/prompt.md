# 실행 규칙(필수)
- 백그라운드 작업 금지, 프로젝트 밖(TEMP 포함) 쓰기 금지. 동기적으로 끝낸 뒤에만 최종 답변(수정 파일, Ran N / OK).
- 테스트 파일 수정 금지. 테스트 문자열 맞춤 분기 금지.

# B07 + B14

수정 허용: `v7_harness/adapters/agy.py`, `v7_harness/adapters/validation.py`만.

1. B07: `_classify_provider_error`의 `"/login"` 부분문자열 매칭을 경로·URL 안의 login(예: `src/pages/login/`, `/users/login_history`)에는 걸리지 않게 바꾼다. 명령어로서의 `/login`(앞이 공백·문장 시작이고 뒤가 공백·문장부호·끝)만 AUTH. 정규식 경계로 일반 규칙을 써라.
2. B14: `CONTROL_CHARACTERS`에 U+0085, U+2028, U+2029를 추가한다. 한글 등 일반 유니코드는 허용.
3. 인수: `tests/test_b07_b14.py`, 전체 discover 통과.
