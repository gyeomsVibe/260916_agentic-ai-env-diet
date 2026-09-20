# Claude → Codex 지원 메모 02 — U11 broker·IPC 구현 근거 (Windows, Python 3.14 표준 라이브러리)

- 대상 카드: `.coord/tasks/U11-broker-ipc-core.md`
- 실측 스크립트: `.claude/codex-relay/u11probe.py` (임시 파이프·뮤텍스만 사용, 영구 변경 없음)

## A. 실측 결과 (L1, 2026-09-17 12:3x)

| 인수 조건 | 표준 라이브러리 수단 | 결과 |
|---|---|---|
| 두 번째 broker 시작 거부 | `multiprocessing.connection.Listener(r"\\.\pipe\NAME", "AF_PIPE", authkey=...)` 같은 이름 2회 생성 | 2번째 `PermissionError(13)` — 내부에서 `FILE_FLAG_FIRST_PIPE_INSTANCE` 사용, **거부 확인** |
| 인증 실패 거부 | 같은 Listener의 `authkey` HMAC challenge | 틀린 키 → 클라이언트·서버 모두 `AuthenticationError` |
| oversize 거부 | `conn.recv_bytes(maxlength=N)` | 초과 시 `OSError`, 연결 폐기 |
| 정상 왕복 | `send_bytes`/`recv_bytes` | `b"ack:hi"` 확인 |
| 단일 인스턴스 보조 잠금 | `ctypes` `CreateMutexW(None, True, r"Local\NAME")` | 2번째 `GetLastError()==183(ALREADY_EXISTS)` |

→ U11은 **외부 패키지 없이** 인수 조건 4개(중복 broker 거부, 잘못된 인증 거부, oversize 거부, 파이프 통신)를 충족할 수 있다.

## B. 구현 시 반드시 지킬 점

1. **`conn.recv()`·`conn.send()` 금지.** 이 둘은 pickle을 쓰므로 인증 뒤라도 역직렬화 코드 실행 위험이 있다. `recv_bytes(maxlength)` + UTF-8 JSON + U10 `command.v1` schema 검증만 쓴다.
2. **authkey HMAC은 연결 인증이지 메시지 replay 방지가 아니다.** replay·중복 방지는 U10 계약의 `idempotency_key`/`request_id` UNIQUE와 nonce 기록으로 DB에서 판정한다.
3. **파이프 DACL은 이번에 검증하지 않았다(`UNKNOWN`).** 현재 사용자 전용 ACL이 필요하면 `_winapi.CreateNamedPipe`는 security attributes를 받지 않는다. ① authkey를 현재 사용자 프로필 아래 ACL 보호 파일에서 읽어 사실상 사용자 한정으로 두거나 ② `ctypes`로 `CreateNamedPipeW` + SDDL `D:P(A;;GA;;;<현재 SID>)`를 직접 구현한다. ①이 U11 범위에서 가장 작다.
4. **mutex는 broker 프로세스 수명 동안 핸들을 유지**하고, 파이프 생성보다 먼저 획득한다. 크래시 시 OS가 abandoned mutex로 해제하므로 재시작이 막히지 않는다.
5. **반쪽 프레임·연결 끊김:** `recv_bytes`가 `EOFError`/`OSError`를 내면 해당 요청은 커밋 전 폐기한다. ACK는 **DB COMMIT 성공 뒤에만** `send_bytes`한다(false ACK 0).
6. `Listener.accept()`는 블로킹이다. graceful stop은 별도 스레드에서 자기 자신에게 인증된 `shutdown` 명령을 보내는 방식이 가장 단순하다.

## C. 위임 연속성 관찰 (R07·R15 보강)

U11 대화 기록상 `antigravity-bridge` job이 Codex 재시작 뒤 `not_found`가 되어 구현을 Codex가 직접 하게 됐다. 이는 v9가 SQLite 연속성을 도입하는 이유를 실제로 재현한 사례다. U11이 끝나기 전까지 Antigravity 초안 위임이 필요하면 브리지 대신 다음처럼 호출하면 결과가 파일로 남는다.

```powershell
agy -p "<U11 초안 지시>" --output-format json --print-timeout 10m > .coord/runs/U11-agy-001.json 2> .coord/runs/U11-agy-001.err
```

판정은 JSON `status`(exit code 아님, 메모 01 E1)와 실제 파일 diff로 한다.
