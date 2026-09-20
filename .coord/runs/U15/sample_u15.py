"""U15 S6 보강: 하루 운용 표본 수집기.

한 번 실행할 때마다 현재 상태를 한 줄로 `daily_samples.jsonl`에 남긴다. 표본이 24시간을 덮으면
`measure_u15.py`가 그 표본으로 '하루 운용' 수치를 만든다. 표본이 모자라면 모자란다고 말한다.

재는 것: 스트림 증가량, 브리핑 분량, 전달 건수, Codex 소비 여부, 판정 대기 건수.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT))

from v7_harness.coord.notify import read_cursor  # noqa: E402
from v7_harness.coord.stream import read_events  # noqa: E402

SAMPLES = PROJECT / ".coord" / "runs" / "U15" / "daily_samples.jsonl"


def _codex_consumed(message_id: str) -> str:
    """큐 메시지가 Codex 세션에 도착했는지 파일 이름 수준에서만 확인한다.

    대화 내용은 읽지 않는다. 확인이 불가능하면 UNKNOWN 을 남긴다.
    """
    if not message_id:
        return "UNKNOWN"
    sessions = Path.home() / ".codex" / "sessions"
    if not sessions.is_dir():
        return "UNKNOWN"
    try:
        hit = subprocess.run(
            ["grep", "-rl", message_id, str(sessions)],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except Exception:  # noqa: BLE001
        return "UNKNOWN"
    if hit.returncode == 0 and hit.stdout.strip():
        newest = max(Path(line) for line in hit.stdout.splitlines() if line.strip())
        return datetime.fromtimestamp(newest.stat().st_mtime).astimezone().isoformat(timespec="seconds")
    return "NOT_SEEN"


def sample() -> dict:
    events = read_events(PROJECT)
    cursor = read_cursor(PROJECT)
    brief = PROJECT / ".coord" / "codex_brief.md"
    brief_text = brief.read_text(encoding="utf-8") if brief.is_file() else ""
    pending = [line for line in brief_text.splitlines() if line.startswith("- ") and "판정" in line]
    return {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "events_total": len(events),
        "events_by_kind": {
            kind: sum(1 for event in events if event.get("kind") == kind)
            for kind in sorted({event.get("kind", "?") for event in events})
        },
        "brief_chars": len(brief_text),
        "brief_lines": len(brief_text.splitlines()),
        "deliveries_today": int(cursor.get("sent_today") or 0),
        "last_sent_at": cursor.get("last_sent_at", ""),
        "queued_message_id": cursor.get("queued_message_id", ""),
        "codex_consumed_at": _codex_consumed(cursor.get("queued_message_id", "")),
        "pending_verdicts": len(pending),
    }


if __name__ == "__main__":
    row = sample()
    SAMPLES.parent.mkdir(parents=True, exist_ok=True)
    with SAMPLES.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(row, ensure_ascii=False))
