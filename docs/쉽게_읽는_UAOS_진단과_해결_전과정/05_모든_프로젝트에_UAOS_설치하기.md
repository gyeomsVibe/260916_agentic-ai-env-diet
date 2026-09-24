# 05. 모든 프로젝트에 UAOS 설치하기 (Windows 기준, 따라 하기)

## 설치하면 무엇이 달라지나

- 어느 프로젝트에서 Codex·Claude·Antigravity를 열어도 **UAOS 규칙 문단**을 읽는다.
- UAOS 프로젝트(`.coord/PLAN.md`가 있는 폴더)에서는 세션을 열 때 **출석부가 자동으로** 찍힌다. Claude·Codex는 시작할 때 한 줄 요약도 받는다. 우편함 대기 수, 급한 알림 수, 자가개선 검토 수, 도구 출석이 들어 있다.
- UAOS가 아닌 프로젝트에서는 **아무 일도 일어나지 않는다**. 파일도, 출력도, 토큰도 없다.
- Claude의 유료 예약 도구(`CronCreate`·`ScheduleWakeup` 등)가 막힌다.
- (선택) 한 프로젝트에 24시간 교환원이 로그온할 때마다 자동으로 뜬다.

## 따라 하기 — 명령 네 줄

PowerShell에서 이 저장소 폴더로 이동한 뒤 실행한다.

```powershell
git switch claude/cool-hamilton-yj6wwo; git pull
python uaos_everywhere/install_uaos_everywhere.py            # ① 미리보기: 바뀔 파일 목록만 보여 줌(아무것도 안 씀)
python uaos_everywhere/install_uaos_everywhere.py --apply    # ② 설치: 원본을 ~/.uaos-backups/<시각>/ 에 먼저 복사
python uaos_everywhere/install_uaos_everywhere.py --check    # ③ 확인: 종료 코드 0이면 정상
```

24시간 교환원(선택):

```powershell
python uaos_everywhere/install_uaos_everywhere.py --apply --register-sentinel D:\경로\260916_agentic-ai-env-diet
schtasks /Query /TN "UAOS Sentinel 260916_agentic-ai-env-diet"     # 등록 확인
Get-Content D:\경로\260916_agentic-ai-env-diet\.work\sentinel\sentinel.log -Tail 3   # 60초마다 한 줄
```

## 미리보기 결과 읽는 법

| action | 뜻 |
|---|---|
| CREATE | 없던 파일을 새로 만든다 |
| UPDATE | 기존 파일에 UAOS 부분만 더하거나 바꾼다 |
| UNCHANGED | 이미 설치돼 있어 바꿀 것이 없다 |
| SKIP | 건너뛴다. 도구가 설치되지 않았거나, JSON이 깨졌거나, 사용자가 일부러 끈 설정일 때다. `detail`에 이유가 있다 |
| REMOVE | 제거할 때만 나온다 |

## 새 프로젝트를 UAOS로 만들기

```powershell
python $HOME\.uaos\uaos.py coord init --project D:\경로\새프로젝트
```

- `.coord/PLAN.md`, `.coord/tasks/`, `.coord/mailbox/`, `.work/`를 만든다.
- `.gitignore`에 런타임 파일 줄을 더한다. 사용량 장부처럼 커밋하면 안 되는 파일이 대상이다.
- 이미 있는 파일은 덮어쓰지 않는다. 두 번 실행해도 안전하다.

## 되돌리기

```powershell
python uaos_everywhere/install_uaos_everywhere.py --apply --uninstall --unregister-sentinel D:\경로\260916_agentic-ai-env-diet
```

- UAOS가 넣은 문단·훅·차단만 뺀다. 원래 있던 설정은 그대로다.
- 사용자가 원래 막아 둔 도구는 계속 막혀 있다.
- 이미 떠 있는 교환원은 작업 관리자에서 `pythonw.exe`를 끄거나 재부팅하면 멈춘다.
- 원본은 `~/.uaos-backups/<시각>/`에 남아 있다.

## 자주 막히는 곳

| 증상 | 원인 | 해결 |
|---|---|---|
| `--check`가 1을 내고 `drift`에 `codex rules` 등이 나옴 | 전역 규칙 생성기(`sync-global-rules.ps1 -Mode Apply`)가 규칙 파일을 다시 만들며 UAOS 문단을 지웠다 | `--apply`를 다시 실행한다. **영구 해결**은 정본(`260718…/shared/global-rules`)에 `uaos_everywhere/uaos_global_rule_block.md` 내용을 넣는 것이다 |
| Codex에서 출석이 안 찍힘 | Codex가 새 훅을 아직 신뢰하지 않았거나(`/hooks`), 업데이트 뒤 훅이 멈춘 알려진 문제(openai/codex#21639) | Codex에서 `/hooks`로 확인·승인한다. 그래도 안 되면 수동으로 `uaos coord presence --tool codex --state ACTIVE`를 실행한다 |
| Antigravity에서 출석이 안 찍힘 | API 키 인증에서는 훅이 실행되지 않는다는 보고(antigravity-cli#893) | Google 계정 로그인으로 쓴다. 출석이 없으면 1시간 뒤 UNKNOWN으로 표시될 뿐 오작동은 없다 |
| 교환원 등록이 "액세스 거부" | 로그온 작업은 관리자 권한이 필요할 수 있다 | 관리자 PowerShell에서 다시 실행하거나, `shell:startup` 폴더에 `~/.uaos/sentinel_<이름>.cmd` 바로가기를 둔다 |
| 저장소 폴더를 옮긴 뒤 명령이 안 됨 | 실행기(`~/.uaos/uaos.py`)에 옛 경로가 들어 있다 | 새 위치에서 `--apply`를 다시 실행한다 |
| 미리보기 `detail`에 "PowerShell" 경고 | 파이썬 경로에 공백이 있어 명령이 따옴표로 시작한다. PowerShell은 이런 명령을 실행하지 않는다 | 공백 없는 경로의 파이썬으로 설치기를 실행하거나(`py -3.12` 등), 해당 훅 명령 앞에 `& `를 붙인다 |
| 이미 열린 세션에 규칙이 안 보임 | 규칙·훅은 **새 세션부터** 적용된다 | 세션을 새로 연다 |

## 알고 쓰기 — 아직 확인하지 못한 것

- 이 설치기는 Linux의 가짜 홈 폴더에서만 시험했다. **Windows 실제 설치는 첫 실행이 곧 첫 확인이다.** 그래서 미리보기(①)를 꼭 먼저 본다.
- Antigravity 전역 규칙 파일 위치(`~/.gemini/GEMINI.md`)는 이전 배포 기록에 근거한 가정이다. 다르면 `--rules-file <경로>`로 지정한다.
- Codex·Antigravity의 유료 예약 기능을 설정으로 막는 방법은 확인하지 못했다. 규칙 문단으로만 금지한다.
