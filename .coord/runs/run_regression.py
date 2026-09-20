"""B61: 전체 회귀를 돌리고 실패 이름을 반드시 남긴다.

지난번 회귀에서 실패 1건이 났는데 출력이 섞여 이름을 잡지 못했다. 그 일이 다시 없도록
표준 출력·오류를 `.work/logs/regression-<타임스탬프>.log`에 그대로 저장하고,
실패·오류 이름만 뽑아 화면에 보여준다.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT / ".work" / "logs"
NAME_RE = re.compile(r"^(?P<kind>FAIL|ERROR):\s*(?P<name>\S+)")


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = f"{datetime.now().astimezone():%Y%m%dT%H%M%S}"
    log_path = LOG_DIR / f"regression-{stamp}.log"

    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=PROJECT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    log_path.write_text(output, encoding="utf-8")

    failures = [
        f"{match.group('kind')}: {match.group('name')}"
        for line in output.splitlines()
        if (match := NAME_RE.match(line))
    ]
    summary = next((line for line in output.splitlines() if line.startswith("Ran ")), "Ran ?")
    verdict = "OK" if completed.returncode == 0 else "FAILED"

    print(f"{summary} -> {verdict}")
    print(f"log: {log_path.relative_to(PROJECT)}")
    for item in failures:
        print(item)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
