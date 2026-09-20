# Claude → Codex 지원 메모 05 — U13 판정용: 외부 쓰기 감시의 실사용 가능성

## A. 독립 재검증 (L1, 2026-09-17 15:0x)

`python -m unittest discover -s tests -p "test_*.py"` → **128 tests OK, exit 0.** Codex 보고와 일치한다.

## B. 실측: 실제 PC에서 감시 루트 크기

`security.snapshot_watch_roots()`는 루트 전체를 `os.walk`로 돌며 모든 파일 내용을 해시한다. 같은 순회를 stat만 하도록 이 PC에서 측정했다.

| 루트 | 파일 수 | 용량 | stat만 순회한 시간 |
|---|---|---|---|
| `HOME` (`C:\Users\Kimyoongyeom`) | **289,749개 이상** | **39.3GB 이상** | **50초에 중단(미완료)** |
| `TEMP` | 2,246개 | 4.2GB | 0.7초 |

## C. 판정에 영향 주는 결함

| # | 등급 | 결함 | 결과 |
|---|---|---|---|
| 1 | P1 | HOME 전체를 내용까지 해시 → 위임 1회마다 수십 GB를 **실행 전후 두 번** 해시한다 | 실제 위임에서 수 분~수십 분 지연. fixture 테스트로는 드러나지 않음 |
| 2 | P1 | HOME·TEMP는 다른 프로세스가 계속 쓴다. Codex 자신도 `~/.codex/sessions/*.jsonl`에 계속 쓰고, 브라우저·AppData도 마찬가지다 | 모든 실행이 `ExternalWriteDetectedError(UNKNOWN)` → **정상 작업도 promotion 불가** |
| 3 | P2 | 해시 실패 파일을 `"ERROR"`로 기록 → 잠긴 파일이 전후로 ERROR/해시를 오가면 거짓 변경 | 잡음 증가 |

단위 테스트 128개 PASS와 별개로, 실제 HOME을 감시 루트로 쓰는 순간 인수 조건 4(staging 밖 쓰기 감지)가 **거짓 양성으로 운영 불가**가 된다.

## D. 보강안 (감지 목적 유지)

1. **stat 1차 + 해시 2차:** 실행 전후 `(size, mtime_ns)`만 비교하고, 달라진 파일만 해시한다.
2. **시간 창 필터:** 실행 시작 이후 `mtime`·생성 시간이 바뀐 항목만 후보로 둔다.
3. **감시 루트를 좁게, 잡음 경로 제외:**
   - 포함: HOME 최상위 파일, `Desktop`, `Documents`, `Downloads`, 프로젝트 상위 폴더, TEMP 최상위. 메모 01 E2에서 agy가 HOME 최상위에 썼다.
   - 제외 기본값: `AppData`, `.codex`, `.gemini\antigravity\brain` 등 에이전트 자체 상태, `.cache`, 브라우저 프로필, `node_modules`.
   - 제외 목록은 카드·설정에 명시해 감사 가능하게 둔다.
4. **실시간 감시 대안(선택):** 실행 중에만 `ReadDirectoryChangesW`(ctypes)로 감시 루트 변경 이벤트를 수집한다. 순회 비용이 0이고 시간 창이 정확하다.
5. **판정 규칙:** 제외 경로 밖 + 시간 창 안 + staging 밖 변경만 `UNKNOWN`. 제외 경로의 변경은 이벤트로만 기록한다.

## E. 추가 테스트

- `test_watch_roots_ignores_noise_dirs` — AppData·.codex에서 실행 중 쓰기가 발생해도 promotion 허용
- `test_watch_roots_stat_first_only_hashes_changed` — 변경 없는 대용량 파일은 해시 호출 0
- `test_watch_home_top_level_write_detected` — HOME 최상위 새 파일은 UNKNOWN (E2 재현)
- `test_watch_roots_budget` — 합성 5만 파일 트리에서 전후 스냅샷이 설정한 시간 예산 이내

## F. 조율자 판정 제안

U13 fixture 인수 조건은 충족했다. 다만 실제 연결 단계(U14 이후) 전에 D.1~D.3을 반영해야 한다. 이번에 U13을 재작업할지, U14 선행 조건으로 넘길지는 조율자가 정한다.
