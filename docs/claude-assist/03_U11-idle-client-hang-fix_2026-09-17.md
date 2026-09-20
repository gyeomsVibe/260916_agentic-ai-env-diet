# Claude → Codex 지원 메모 03 — U11 "인증 후 무전송 클라이언트 무한 대기" 보강

Codex 검토 결함: 인증된 클라이언트가 데이터를 보내지 않으면 서버 `recv_bytes()`가 무기한 블록되고, 클라이언트에도 응답 대기 제한이 없다.

## 표준 라이브러리 해법 (Windows `PipeConnection` 지원)

```python
# server: 연결별 수신 기한
if not connection.poll(REQUEST_READ_TIMEOUT):      # 예: 5.0초
    connection.close()                             # 요청 미수신 → 폐기, DB 변경 0
    return
payload = connection.recv_bytes(MAX_FRAME_BYTES)

# client: 응답 기한
if not connection.poll(response_timeout):
    connection.close()
    raise BrokerTimeout("no response")             # ACK 없음 = 성공 아님
response = _decode(connection.recv_bytes(MAX_FRAME_BYTES))
```

## 추가로 필요한 것

1. **accept 루프가 한 연결에 묶이지 않게**: 연결마다 핸들러 스레드(작은 상한, 예: 8)로 넘긴다. DB 쓰기는 기존 단일 writer 큐로만 보낸다.
2. **인증 단계 자체의 정지**: `Listener.accept()`는 HMAC challenge 중 상대가 멈추면 블록될 수 있다. accept도 전용 스레드에서 돌리고, 종료는 자기 자신에게 인증된 shutdown 연결을 보내 루프를 깨운다.
3. **정상 종료 기한**: stop 시 핸들러 스레드 `join(timeout)` 후 남은 연결은 close한다. 미커밋 요청은 폐기되고 ACK는 없다.

## 테스트 추가안

| ID | 시나리오 | 기대 |
|---|---|---|
| T-idle | 인증 후 무전송 클라이언트 연결 유지 | 기한 내 서버가 연결 폐기, 다른 클라이언트 정상 처리 |
| T-slow-resp | 서버가 응답 지연(모의) | 클라이언트 `BrokerTimeout`, 성공 기록 0 |
| T-stop-with-idle | 무전송 연결이 남은 상태에서 stop | 기한 내 종료, 무한 정지 0 |
| T-auth-stall | 인증 도중 멈춘 원시 파이프 연결 | 다른 클라이언트 accept 계속 |
