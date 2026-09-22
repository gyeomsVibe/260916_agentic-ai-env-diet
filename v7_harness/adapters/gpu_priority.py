"""GPU 우선순위: 파일럿 로컬 작업자가 먼저, 보조 호출(olla·MCP)은 양보한다.

왜: GPU 는 하나이고 Ollama 는 한 번에 1건만 처리한다(OLLAMA_NUM_PARALLEL=1). 몇 분 걸리는 요약이
돌면 관문을 거치는 파일럿 작업이 그 뒤에 줄 서서 시간 초과 위험이 생긴다(B74). 파일럿 결과는 원본에
반영되는 작업이고 보조 호출은 비싼 모델이 대신할 수 있으므로, 파일럿이 도는 동안 보조 호출은 즉시
"사용 중"을 돌려주고 비싼 모델은 Read·Grep 으로 진행한다.

기계 전역이어야 한다: GPU 는 프로젝트를 가리지 않는다. 그래서 프로젝트별 SQLite 가 아니라
사용자 캐시 폴더의 표식 파일로 조정한다. 표식에는 만료 시각을 적는다 — 파일럿이 죽어도 만료 뒤엔
보조 호출이 다시 돈다(Windows 에서 os.kill(pid, 0)은 프로세스를 끝내므로 생존 확인에 쓰지 않는다).
"""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

GPU_DIR = Path(os.environ.get("OLLA_GPU_DIR", Path.home() / ".cache" / "olla" / "gpu"))
MARGIN_S = 30  # 생성 시간 제한에 더하는 여유. 정리(파일 쓰기) 시간


def _marker(pid: int) -> Path:
    return GPU_DIR / f"pilot-{pid}.json"


@contextmanager
def pilot_holds(timeout_s: int) -> Iterator[None]:
    """파일럿 로컬 생성 동안 표식을 둔다. 끝나면 지운다."""
    marker = _marker(os.getpid())
    try:
        GPU_DIR.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({"pid": os.getpid(), "expires_at": time.time() + timeout_s + MARGIN_S}), encoding="utf-8")
    except OSError:
        pass  # 표식을 못 남겨도 파일럿은 돈다. 양보만 안 될 뿐이다
    try:
        yield
    finally:
        try:
            marker.unlink()
        except OSError:
            pass


def pilot_active(now: float | None = None) -> bool:
    moment = time.time() if now is None else now
    if not GPU_DIR.is_dir():
        return False
    for path in GPU_DIR.glob("pilot-*.json"):
        try:
            if json.loads(path.read_text(encoding="utf-8")).get("expires_at", 0) > moment:
                return True
        except (OSError, ValueError):
            continue
    return False


BUSY_MESSAGE = ("GPU busy: a pilot local-worker run has priority. Continue with Read (offset/limit) or Grep "
                "instead of waiting; retry the local model later.")
