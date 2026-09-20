# 실행 규칙(필수)
- 백그라운드 작업 금지, 프로젝트 밖(TEMP 포함) 쓰기 금지. 동기적으로 끝낸 뒤에만 최종 답변(수정 파일, Ran N / OK).
- 테스트 파일 수정 금지. 테스트 값 맞춤 분기 금지.

# B55 — 프로젝트 내부 작업 섹션 `.work/` 지원 (사용자 지시: 로컬 워크스페이스에는 프로젝트 폴더 하나만)

수정 허용: `v7_harness/isolation/manifest.py`, `v7_harness/isolation/staging.py`.

1. `manifest.py` `DEFAULT_EXCLUDES`에 `.work`와 `.coord/pilot`을 추가한다(런타임 산출물: staging·원장·샘플).
2. `staging.py` `NonGitStagingAdapter`의 복사 제외 집합이 `self.excludes`뿐 아니라 manifest의 `DEFAULT_EXCLUDES`도 포함하도록 한다(현재는 사용자 excludes만 적용되어 `.work`가 staging에 복사된다). 경로형 제외(`.coord/pilot`)도 디렉터리 단위로 걸러야 한다.
3. 인수: `tests/test_b55_inproject_work.py`, 전체 discover 통과.
