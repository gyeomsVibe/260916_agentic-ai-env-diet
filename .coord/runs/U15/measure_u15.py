"""U15 S6: 조율 채널 실측.

재는 것은 두 가지다.
1. 같은 조율 내용을 Codex에 전달할 때 드는 양: 기존 메모 경로 vs 브리핑·큐 메시지 경로.
2. 중복 전달 차단이 실제로 걸리는지.

재지 못하는 것은 재지 못했다고 남긴다. Codex가 큐 메시지를 실제로 소비한 시각은 Codex 세션
기록에서만 확인할 수 있으므로 여기서는 `UNKNOWN`으로 둔다.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT))

from v7_harness.coord.brief import brief_hash, render_brief  # noqa: E402
from v7_harness.coord.notify import notify, read_cursor  # noqa: E402
from v7_harness.coord.stream import read_events  # noqa: E402

CHARS_PER_TOKEN = 2.5  # 한국어 혼합 텍스트의 보수적 추정치. 정확한 토큰 수가 아니다.


def _tokens(text: str) -> int:
    return round(len(text) / CHARS_PER_TOKEN)


def measure() -> dict:
    events = read_events(PROJECT)
    brief_path = PROJECT / ".coord" / "codex_brief.md"
    brief_text = brief_path.read_text(encoding="utf-8") if brief_path.is_file() else ""
    cursor = read_cursor(PROJECT)

    memos = sorted((PROJECT / "docs" / "claude-assist").glob("*.md"))
    memo_sizes = [len(path.read_text(encoding="utf-8", errors="replace")) for path in memos]
    recent_memo_sizes = memo_sizes[-10:] if memo_sizes else []

    # 재전송이 실제로 막히는지 드라이런으로 확인한다. 상태가 그대로면 NO_CHANGE 여야 한다.
    repeat = notify(
        PROJECT,
        thread=cursor.get("thread") or "unknown",
        actor="claude",
        brief_text=brief_text,
        headline="중복 전달 차단 확인",
        pending=["dedup probe"],
        dry_run=True,
    )

    stream_bytes = sum(path.stat().st_size for path in (PROJECT / ".coord" / "stream").glob("*.jsonl"))

    baseline_chars = round(sum(recent_memo_sizes) / len(recent_memo_sizes)) if recent_memo_sizes else 0
    optimized_chars = len(brief_text)

    return {
        "schema": "u15-coordination-measure-v1",
        "measured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "sample": {
            "events_in_stream": len(events),
            "stream_bytes": stream_bytes,
            "memos_total": len(memos),
            "memos_sampled": len(recent_memo_sizes),
        },
        "per_handoff_payload": {
            "baseline_memo_chars": baseline_chars,
            "baseline_memo_tokens_est": _tokens("x" * baseline_chars),
            "brief_chars": optimized_chars,
            "brief_tokens_est": _tokens(brief_text),
            "brief_lines": len(brief_text.splitlines()),
            "queue_message_chars": len(repeat.message),
            "queue_message_tokens_est": _tokens(repeat.message),
            "reduction_pct_vs_memo": (
                round((1 - optimized_chars / baseline_chars) * 100, 1) if baseline_chars else None
            ),
        },
        "dedup": {
            "cursor_hash": cursor.get("last_hash", "")[:12],
            "brief_hash": brief_hash(brief_text)[:12] if brief_text else "",
            "repeat_send_blocked": not repeat.sent,
            "repeat_reason": repeat.reason,
        },
        "delivery": {
            "last_sent_at": cursor.get("last_sent_at", ""),
            "thread": cursor.get("thread", ""),
            "queued_message_id": cursor.get("queued_message_id", ""),
            "queue_accepted": bool(cursor.get("queued_message_id")),
            "codex_consumed_at": "UNKNOWN",
            "verdict_latency_s": "UNKNOWN",
        },
        "limits": {
            "brief_within_60_lines": len(brief_text.splitlines()) <= 60,
            "brief_within_6kb": len(brief_text.encode("utf-8")) <= 6 * 1024,
            "queue_message_within_500": len(repeat.message) <= 500,
        },
        "status": "PARTIAL_MEASURED",
        "unmeasured": [
            "하루 운용 기준 전달 건수와 판정 지연(Codex 소비 시각 필요)",
            "조율 턴의 실제 토큰 절감(Codex 사용량 기록 대조 필요)",
        ],
    }


if __name__ == "__main__":
    result = measure()
    out = PROJECT / ".coord" / "runs" / "U15" / "measurement_s6.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
