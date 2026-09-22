"""olla MCP 서버 — 로컬 모델을 에이전트의 '도구 목록'에 올린다.

왜: 안내(11회)·요약본 인계·큰 읽기 거부를 다 해도 에이전트는 olla 를 거의 쓰지 않았다. 에이전트는
도구 목록에 있는 것 중에서 고른다. 도구 선택은 요청과 도구 이름·설명의 의미 일치가 가장 강한 예측
변수다(BiasBusters, arXiv:2510.00307; 설명 문구만 바꿔도 선택이 크게 바뀜, arXiv:2505.18135).
셸 명령 `olla` 는 목록에 없어서 Read·Grep 과 경쟁조차 못 했다. 그래서 같은 기능을 MCP 도구로 노출한다.

의존성 없이 표준 입출력 JSON-RPC(한 줄 = 한 메시지)만 구현한다. 판정은 하지 않는다.
"""

from __future__ import annotations

import json
import sys
import urllib.error
from pathlib import Path
from typing import Any

from v7_harness import olla

PROTOCOL_VERSION = "2025-06-18"

TOOLS = [
    {
        "name": "local_read_map",
        "description": (
            "Read a large file for 0 paid tokens. Returns a line-numbered map of the file (which lines hold "
            "which functions, sections, and facts), written by the local model. Use this FIRST whenever you need "
            "to understand or locate something in a file over ~300 lines, then read only the lines you need. "
            "Cached per file content, so repeat calls are instant."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path of the file."},
                "question": {"type": "string", "description": "What you are looking for (optional, English)."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "local_draft",
        "description": (
            "Draft text for 0 paid tokens with the local model: commit messages, summaries, docstrings, "
            "changelog lines, classifications, first drafts. Prompt in English with the format, length, and one "
            "example. Set korean=true only for text the user will read. Always check the result before using it; "
            "the tool reports invented file or test names."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "instruction": {"type": "string"},
                "files": {"type": "array", "items": {"type": "string"}, "description": "Absolute paths to include."},
                "korean": {"type": "boolean"},
            },
            "required": ["instruction"],
        },
    },
    {
        "name": "local_search",
        "description": (
            "Find files by meaning for 0 paid tokens (local embeddings). Use when you do not know the exact "
            "keyword to grep for. Returns the most similar text files under a folder."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "folder": {"type": "string", "description": "Absolute folder path."},
                "top": {"type": "integer"},
            },
            "required": ["query", "folder"],
        },
    },
]


def _text(value: str, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": value}], "isError": is_error}


def _needs_gpu(name: str, args: dict[str, Any]) -> bool:
    if name == "local_read_map":
        path = Path(str(args.get("path") or ""))
        try:
            return path.is_file() and not olla._digest_cache_path(path, str(args.get("question") or ""), olla.CHAT_MODEL).is_file()
        except OSError:
            return False
    return name in ("local_draft", "local_search")


def call_tool(name: str, args: dict[str, Any]) -> dict:
    from v7_harness.adapters.gpu_priority import BUSY_MESSAGE, pilot_active

    if _needs_gpu(name, args) and pilot_active():  # 파일럿 우선(B74). 캐시된 지도는 GPU 없이 바로 준다
        olla.log_usage("yield_to_pilot", via="mcp")
        return _text(BUSY_MESSAGE, True)
    try:
        if name == "local_read_map":
            path = Path(str(args.get("path") or ""))
            if not path.is_file():
                return _text(f"no such file: {path}", True)
            question = str(args.get("question") or "")
            cache = olla._digest_cache_path(path, question, olla.CHAT_MODEL)
            if cache.is_file():
                digest, cached = json.loads(cache.read_text(encoding="utf-8"))["digest"], True
            else:
                digest, _ = olla.digest_file(path, question, olla.CHAT_MODEL, 900)
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(json.dumps({"path": path.as_posix(), "digest": digest}, ensure_ascii=False), encoding="utf-8")
                cached = False
            before = round(path.stat().st_size / olla.BYTES_PER_TOKEN)
            after = round(len(digest.encode("utf-8")) / olla.BYTES_PER_TOKEN)
            olla.log_usage("digest", file=str(path.resolve()), paid_tokens_if_read=before, paid_tokens_digest=after,
                           cached=cached, via="mcp")
            return _text(digest + f"\n(map ~{after:,} tokens instead of ~{before:,}; confirm exact lines with a ranged read)")
        if name == "local_draft":
            files = [str(f) for f in args.get("files") or []]
            empty = [f for f in files if Path(f).is_file() and not Path(f).read_text(encoding="utf-8", errors="replace").strip()]
            if empty:
                return _text(f"empty input file (the model would invent content): {', '.join(empty)}", True)
            prompt = str(args.get("instruction") or "")
            if files:
                prompt += "\n" + olla._read_files(files)
            if args.get("korean"):
                prompt = olla.KO_RULES + prompt
            text, usage = olla.worker._generate(olla.CHAT_MODEL, prompt, 900)
            olla.log_usage("ask", ko=bool(args.get("korean")), via="mcp", **usage)
            fake = olla.missing_refs(text, Path.cwd())
            note = f"\n\n[check: references not found, likely invented: {', '.join(fake)}]" if fake else ""
            return _text(text.strip() + note)
        if name == "local_search":
            base = Path(str(args.get("folder") or ""))
            if not base.is_dir():
                return _text(f"no such folder: {base}", True)
            skip = {".git", ".work", "__pycache__", "node_modules", ".venv"}
            candidates = []
            for path in base.rglob("*"):
                if any(p in skip for p in path.parts) or not path.is_file() or path.suffix not in olla.TEXT_SUFFIXES:
                    continue
                body = path.read_text(encoding="utf-8", errors="replace")[:2000]
                if body.strip():
                    candidates.append((path, body))
                if len(candidates) >= 300:
                    break
            if not candidates:
                return _text("no text files", True)
            vectors = olla._embed([str(args["query"])] + [body for _, body in candidates])
            query, docs = vectors[0], vectors[1:]
            ranked = sorted(zip(candidates, docs), key=lambda item: olla._cosine(query, item[1]), reverse=True)
            olla.log_usage("find", via="mcp")
            top = int(args.get("top") or 5)
            return _text("\n".join(f"{olla._cosine(query, v):.3f}  {p.as_posix()}" for (p, _), v in ranked[:top]))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return _text(f"local model unreachable: {exc}", True)
    return _text(f"unknown tool: {name}", True)


def handle(message: dict) -> dict | None:
    method, msg_id = message.get("method"), message.get("id")
    if msg_id is None:
        return None  # 알림(notifications/*)에는 답하지 않는다
    if method == "initialize":
        result: dict = {"protocolVersion": PROTOCOL_VERSION, "capabilities": {"tools": {}},
                        "serverInfo": {"name": "olla", "version": "1.0"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = message.get("params") or {}
        result = call_tool(str(params.get("name")), params.get("arguments") or {})
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def main() -> int:
    stdin = sys.stdin.buffer
    for raw in stdin:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            reply = handle(json.loads(line))
        except ValueError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        if reply is not None:
            sys.stdout.buffer.write((json.dumps(reply, ensure_ascii=False) + "\n").encode("utf-8"))
            sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
