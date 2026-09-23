"""Gemini API -> Ollama shim, so Antigravity CLI (agy) can run its own agent loop on the local model.

Why: agy has no custom-endpoint setting for its reasoning model, but in Gemini-API mode
(`modelProvider: "gemini"` in settings.json + GEMINI_API_KEY) it honors GOOGLE_GEMINI_BASE_URL. Probe (2026-09-23,
agy 1.2.9): it then sends plain `POST /v1beta/models/<m>:streamGenerateContent` requests there; the agent turn was
63.8 KB with 14 tools (~18k tokens), which fits qwen3.5-32k's 32k window.

Run agy against it in a sandbox home so the user's real agy settings and sign-in are untouched:
  USERPROFILE=<sandbox> GEMINI_API_KEY=local GOOGLE_GEMINI_BASE_URL=http://127.0.0.1:8788 agy -p ...
Headless agy denies file writes unless run with --dangerously-skip-permissions (measured 2026-09-23). Binds 127.0.0.1 only; the api key header is ignored and never logged.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
MODEL = os.environ.get("GEMINI_SHIM_MODEL", "qwen3.5-32k")
PORT = int(os.environ.get("GEMINI_SHIM_PORT", "8788"))
LOG = Path(os.environ.get("GEMINI_SHIM_LOG", Path.home() / ".cache" / "gemini_shim" / "requests.jsonl"))


def _schema(node):
    """Gemini schemas may use upper-case OpenAPI types (OBJECT, STRING); Ollama expects JSON Schema."""
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k == "type" and isinstance(v, str):
                out[k] = v.lower()
            elif k in ("nullable", "propertyOrdering"):
                continue
            else:
                out[k] = _schema(v)
        return out
    if isinstance(node, list):
        return [_schema(x) for x in node]
    return node


def to_ollama(req: dict) -> dict:
    messages = []
    sys_parts = (req.get("systemInstruction") or {}).get("parts") or []
    sys_text = "\n".join(p.get("text", "") for p in sys_parts if "text" in p)
    if sys_text:
        messages.append({"role": "system", "content": sys_text})
    for turn in req.get("contents") or []:
        role = "assistant" if turn.get("role") == "model" else "user"
        texts, calls = [], []
        for part in turn.get("parts") or []:
            if part.get("thought"):
                continue  # model's own earlier thinking; not needed as context
            if "text" in part:
                texts.append(part["text"])
            elif "functionCall" in part:
                fc = part["functionCall"]
                calls.append({"function": {"name": fc.get("name"), "arguments": fc.get("args") or {}}})
            elif "functionResponse" in part:
                fr = part["functionResponse"]
                messages.append({"role": "tool", "tool_name": fr.get("name"),
                                 "content": json.dumps(fr.get("response"), ensure_ascii=False)})
        if texts or calls:
            msg = {"role": role, "content": "\n".join(texts)}
            if calls:
                msg["tool_calls"] = calls
            messages.append(msg)
    tools = []
    for group in req.get("tools") or []:
        for fd in group.get("functionDeclarations") or []:
            params = fd.get("parametersJsonSchema") or fd.get("parameters") or {"type": "object", "properties": {}}
            tools.append({"type": "function", "function": {"name": fd.get("name"), "description": fd.get("description", ""),
                                                           "parameters": _schema(params)}})
    gc = req.get("generationConfig") or {}
    options = {k2: gc[k1] for k1, k2 in (("temperature", "temperature"), ("topP", "top_p"), ("topK", "top_k"),
                                         ("maxOutputTokens", "num_predict")) if k1 in gc}
    out = {"model": MODEL, "messages": messages, "stream": False, "options": options, "think": False}
    if tools:
        out["tools"] = tools
    return out


def to_gemini(resp: dict) -> dict:
    msg = resp.get("message") or {}
    parts = []
    if msg.get("content"):
        parts.append({"text": msg["content"]})
    for call in msg.get("tool_calls") or []:
        fn = call.get("function") or {}
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                args = {"raw": args}
        parts.append({"functionCall": {"name": fn.get("name"), "args": args or {}}})
    if not parts:
        parts.append({"text": ""})
    p_in, p_out = int(resp.get("prompt_eval_count") or 0), int(resp.get("eval_count") or 0)
    return {"candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": "STOP", "index": 0}],
            "usageMetadata": {"promptTokenCount": p_in, "candidatesTokenCount": p_out, "totalTokenCount": p_in + p_out},
            "modelVersion": MODEL}


def _log(row: dict) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, status: int, payload: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):  # model listing etc.: not served
        self._send(404, b'{"error":{"code":404,"message":"not served by gemini_shim","status":"NOT_FOUND"}}',
                   "application/json")

    def do_POST(self):
        started = time.monotonic()
        path = self.path.split("?")[0]
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if not (path.endswith(":streamGenerateContent") or path.endswith(":generateContent")):
            return self.do_GET()
        try:
            body = to_ollama(json.loads(raw))
            with urllib.request.urlopen(urllib.request.Request(
                    OLLAMA + "/api/chat", data=json.dumps(body).encode("utf-8"),
                    headers={"Content-Type": "application/json"}), timeout=900) as r:
                answer = to_gemini(json.loads(r.read()))
        except Exception as exc:  # report as a Gemini error so agy surfaces it instead of hanging
            _log({"path": path, "error": f"{type(exc).__name__}: {exc}"[:300]})
            msg = json.dumps({"error": {"code": 500, "message": f"gemini_shim: {type(exc).__name__}",
                                        "status": "INTERNAL"}}).encode()
            return self._send(500, msg, "application/json")
        data = json.dumps(answer, ensure_ascii=False)
        if path.endswith(":streamGenerateContent"):
            if "alt=sse" in self.path:
                self._send(200, f"data: {data}\r\n\r\n".encode("utf-8"), "text/event-stream")
            else:
                self._send(200, f"[{data}]".encode("utf-8"), "application/json")
        else:
            self._send(200, data.encode("utf-8"), "application/json")
        _log({"path": path, "query": self.path.partition("?")[2][:40], "in_bytes": len(raw),
              "n_tools": len(body.get("tools") or []), "calls": [p.get("functionCall", {}).get("name")
              for p in answer["candidates"][0]["content"]["parts"] if "functionCall" in p],
              "tokens": answer["usageMetadata"], "ms": int((time.monotonic() - started) * 1000)})


def main() -> int:
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
