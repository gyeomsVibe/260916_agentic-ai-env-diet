[읽기 전용 독립 검증 — 파일 수정·생성 금지, 백그라운드 작업 금지, 끝까지 동기 수행 후 답변]
대상: 방금 반영된 B30S(= B28 완결 + B31 과제별 retry budget + B32 무변경 REWORK + B33 error_detail + B34 acceptance.log + B08 lease 30s)와 IDE가 직접 반영한 B20~B26.
읽을 것: v7_harness/pilot.py, v7_harness/cli.py, v7_harness/isolation/security.py, tests/test_b2*.py, tests/test_b30_no_change_verdict.py, docs/claude-assist/23_*.md.
할 일:
1) 각 항목(B20,B21,B23,B24,B25,B26,B28,B31,B32,B33,B34,B08)을 코드와 테스트로 확인해 PASS/FAIL과 한 줄 근거.
2) 반례 탐색: 특히 (a) B21 accept_cmd shell=True 경로의 주입 위험(accept_cmd는 조율자만 제공), (b) re-include가 `.claude` 하위를 순회하며 reparse/junction·대량 파일에서 실패하거나 느려지는 경우, (c) B32가 읽기 전용 과제에서 오판하는 경우, (d) task별 budget으로 바뀌며 같은 task 재시도 한도가 사라졌는지.
3) blocking P1 목록(없으면 0).
4) 다음 단계 합의안: 남은 일(① 동일 과제·동일 모델 A/B 측정 ② PLAN/BACKLOG 갱신 ③ Codex 인계 ④ U03/U04 전역 원본 반영 — 사용자 승인 대상) 순서와 네가 맡을 부분.
형식: JSON 한 덩어리 {"items":[{"id","verdict","evidence"}],"counterexamples":[...],"blocking_p1":[...],"next_steps":[...]}
