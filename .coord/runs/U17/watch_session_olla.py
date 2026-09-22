"""U17: 살아 있는 Claude 세션이 올라마를 쓰는지 실시간으로 본다. 한 줄 = 한 사건(Monitor 용).

사용: python watch_session_olla.py <세션 jsonl 절대 경로> [초]
- OLLA  : olla 셸 호출 또는 local_* MCP 도구 호출
- BIG   : 3천 토큰 넘는 파일의 통째 읽기(Read, offset/limit 없음)
- HOOK  : 사용 기록(usage.jsonl)의 그 세션 사건 중 읽기 알림·거부·양보·요약
- TURN  : 턴 종료 모양(진행 설명 수, 보고 줄·글자)
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

USAGE = Path(os.environ.get("OLLA_USAGE", Path.home() / ".cache" / "olla" / "usage.jsonl"))
BYTES_PER_TOKEN = 3.0
# 이미지는 바이트 수가 토큰 수가 아니다(PNG 72만 바이트를 24만 토큰으로 잘못 셌음).
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf")
EVENTS = {"hint_read", "deny_whole_read", "digest", "ask", "find", "yield_to_pilot", "deny_deep_cd", "turn_shape"}


def main() -> int:
    transcript = Path(sys.argv[1])
    duration = float(sys.argv[2]) if len(sys.argv) > 2 else 1800
    session = transcript.stem
    t_pos = transcript.stat().st_size
    u_pos = USAGE.stat().st_size if USAGE.is_file() else 0
    end = time.time() + duration
    while time.time() < end:
        with transcript.open("rb") as handle:
            handle.seek(t_pos)
            chunk = handle.read()
            t_pos += len(chunk)
        for raw in chunk.decode("utf-8", errors="replace").splitlines():
            try:
                row = json.loads(raw)
            except ValueError:
                continue
            content = (row.get("message") or {}).get("content")
            if row.get("type") != "assistant" or not isinstance(content, list):
                continue
            for block in content:
                if block.get("type") != "tool_use":
                    continue
                name, args = block.get("name", ""), block.get("input") or {}
                command = str(args.get("command") or "")
                if "local_" in name or re.search(r"\bolla\b", command):
                    print(f"OLLA {name} {command[:80]}", flush=True)
                elif name == "Read" and not (args.get("offset") or args.get("limit")) and not str(args.get("file_path", "")).lower().endswith(IMAGE_SUFFIXES):
                    try:
                        tokens = round(os.path.getsize(args.get("file_path", "")) / BYTES_PER_TOKEN)
                    except OSError:
                        continue
                    if tokens >= 3000:
                        print(f"BIG Read ~{tokens:,} tokens {Path(args['file_path']).name}", flush=True)
        if USAGE.is_file():
            with USAGE.open("rb") as handle:
                handle.seek(u_pos)
                chunk = handle.read()
                u_pos += len(chunk)
            for raw in chunk.decode("utf-8", errors="replace").splitlines():
                try:
                    rec = json.loads(raw)
                except ValueError:
                    continue
                if rec.get("session") != session or rec.get("event") not in EVENTS:
                    continue
                if rec["event"] == "turn_shape":
                    print(f"TURN narration={rec.get('narration_blocks')} lines={rec.get('final_lines')} "
                          f"chars={rec.get('final_chars')}", flush=True)
                else:
                    print(f"HOOK {rec['event']} {Path(str(rec.get('file', ''))).name}", flush=True)
        time.sleep(5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
