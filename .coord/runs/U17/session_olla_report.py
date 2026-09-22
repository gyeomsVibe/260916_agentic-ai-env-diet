"""U17: 한 Claude 세션의 올라마 사용 보고서(사용자용, 한국어)를 만든다.

사용: python session_olla_report.py <세션 jsonl 절대 경로>
출력: .coord/runs/U17/reports/<세션 앞 8자>_<날짜>.md 와 같은 이름의 .json
세션 기록(도구 호출)과 olla 사용 기록(훅·도구 사건)을 시간대별로 합친다.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]
USAGE = Path(os.environ.get("OLLA_USAGE", Path.home() / ".cache" / "olla" / "usage.jsonl"))
KST = timezone(timedelta(hours=9))
BIG = 3000
BYTES_PER_TOKEN = 3.0
# 이미지는 바이트 수가 토큰 수가 아니다(PNG 72만 바이트를 24만 토큰으로 잘못 셌음).
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf")


def load_transcript(path: Path) -> dict:
    prompts, tools, olla_calls, big_reads = 0, Counter(), [], []
    first = last = None
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        stamp = row.get("timestamp")
        if stamp:
            moment = datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(KST)
            first, last = first or moment, moment
        content = (row.get("message") or {}).get("content")
        if row.get("type") == "user" and not row.get("isMeta") and (
                isinstance(content, str) or (isinstance(content, list) and not any(
                    isinstance(b, dict) and b.get("type") == "tool_result" for b in content))):
            prompts += 1
        if row.get("type") != "assistant" or not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") != "tool_use":
                continue
            name, args = block.get("name", ""), block.get("input") or {}
            tools[name] += 1
            command = str(args.get("command") or "")
            if "local_" in name or re.search(r"\bolla\b", command):
                olla_calls.append((moment.strftime("%H:%M"), name if "local_" in name else command[:60]))
            elif name == "Read" and not (args.get("offset") or args.get("limit")) and not str(args.get("file_path", "")).lower().endswith(IMAGE_SUFFIXES):
                try:
                    tokens = round(os.path.getsize(args.get("file_path", "")) / BYTES_PER_TOKEN)
                except OSError:
                    continue
                if tokens >= BIG:
                    big_reads.append((moment.strftime("%H:%M"), tokens, Path(args["file_path"]).name))
    return {"first": first, "last": last, "prompts": prompts, "tools": tools,
            "olla_calls": olla_calls, "big_reads": big_reads}


def load_usage(session: str) -> list[dict]:
    if not USAGE.is_file():
        return []
    rows = []
    for raw in USAGE.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(raw)
        except ValueError:
            continue
        if rec.get("session") == session:
            rows.append(rec)
    return rows


def render(session: str, t: dict, usage: list[dict]) -> tuple[str, dict]:
    events = Counter(rec["event"] for rec in usage)
    turns = [rec for rec in usage if rec["event"] == "turn_shape"]
    within = sum(1 for r in turns if r.get("narration_blocks", 1) == 0 and r.get("final_lines", 9) <= 5
                 and r.get("final_chars", 0) <= 600 and not r.get("nested_lines"))
    saved = sum(max(0, r.get("paid_tokens_if_read", 0) - r.get("paid_tokens_digest", 0)) for r in usage if r["event"] == "digest")
    big_tokens = sum(tokens for _, tokens, _ in t["big_reads"])
    data = {
        "session": session, "span": [t["first"].isoformat() if t["first"] else None, t["last"].isoformat() if t["last"] else None],
        "prompts": t["prompts"], "tool_calls": sum(t["tools"].values()), "olla_calls": len(t["olla_calls"]),
        "big_whole_reads": len(t["big_reads"]), "big_whole_tokens": big_tokens, "digest_tokens_saved": saved,
        "hook_events": dict(events), "turns": len(turns), "turns_within_rule": within,
    }
    span = f"{t['first']:%m-%d %H:%M} ~ {t['last']:%H:%M}" if t["first"] else "-"
    lines = [
        f"# 올라마 사용 보고서 — 세션 {session[:8]}",
        "",
        f"**결과**: 도구 호출 {data['tool_calls']}회 중 올라마 직접 호출 {data['olla_calls']}회, "
        f"훅이 대신 만든 요약본 사용 {events.get('digest', 0)}회(유료 {saved:,}토큰 절약), 규칙을 지킨 보고 {within}/{len(turns)}턴.",
        "",
        f"- 기간: {span} (KST), 지시 {t['prompts']}개",
        f"- 큰 파일 통째 읽기: {len(t['big_reads'])}건, 약 {big_tokens:,}토큰",
        f"- 훅 사건: 분업 안내 {events.get('hint_plan', 0)} · 읽기 알림 {events.get('hint_read', 0)} · "
        f"통째 읽기 거부 {events.get('deny_whole_read', 0)} · 깊은 cd 거부 {events.get('deny_deep_cd', 0)} · "
        f"GPU 양보 {events.get('yield_to_pilot', 0)}",
        "",
        "## 올라마 호출",
        *([f"- [올라마] {when} {what}" for when, what in t["olla_calls"]] or ["- 없음"]),
        "",
        "## 큰 파일 통째 읽기",
        *([f"- {when} ~{tokens:,}토큰 {name}" for when, tokens, name in t["big_reads"]] or ["- 없음"]),
        "",
        "## 해석",
        "- 이 세션은 올라마 MCP 도구가 등록되기 전에 시작돼 도구 목록에 `local_*`가 없습니다. 새 세션부터 MCP 도구가 보입니다.",
        "- 훅은 경로가 260자를 넘는 곳에서 실행되지 못합니다(B68). 그 구간의 큰 읽기는 알림 없이 지나갔습니다.",
    ]
    return "\n".join(lines) + "\n", data


def main() -> int:
    transcript = Path(sys.argv[1])
    session = transcript.stem
    t = load_transcript(transcript)
    text, data = render(session, t, load_usage(session))
    out = PROJECT / ".coord" / "runs" / "U17" / "reports"
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{session[:8]}_{datetime.now(KST):%Y%m%d_%H%M}"
    (out / f"{stem}.md").write_text(text, encoding="utf-8")
    (out / f"{stem}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out / f"{stem}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
