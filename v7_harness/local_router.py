"""Local router: sends Claude Code's small-model (haiku) requests to Ollama without the agent choosing.

Why: every design that waited for a paid agent to *decide* to delegate got 0 calls (olla retired 2026-09-23). A
proxy on ANTHROPIC_BASE_URL decides per request instead, the pattern of claude-code-router ("model name contains
haiku -> background model"). The main model's requests pass through to Anthropic untouched, OAuth header included.

Safety rules (red-team, 2026-09-23):
- Binds 127.0.0.1 only. Never logs headers or message bodies; logs a 60-char system-prompt head for classification.
- Requests whose system prompt looks like a safety or permission check stay upstream: a 4B model must not weaken
  a guard. Unknown request types stay upstream in `observe` mode, which is the default.
- Local failure before any byte is sent falls back to upstream, so routing can only cost time, not a lost turn.
- Too-big prompts (> LOCAL_MAX_TOKENS) and a GPU held by a pilot run go upstream.

Run: python -m v7_harness.local_router  (env LOCAL_ROUTER_MODE=observe|route, LOCAL_ROUTER_PORT=8787)
"""

from __future__ import annotations

import http.client
import json
import os
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

UPSTREAM = os.environ.get("LOCAL_ROUTER_UPSTREAM", "https://api.anthropic.com")
OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
LOCAL_MODEL = os.environ.get("LOCAL_ROUTER_MODEL", "qwen3.5-32k")
MODE = os.environ.get("LOCAL_ROUTER_MODE", "observe")
PORT = int(os.environ.get("LOCAL_ROUTER_PORT", "8787"))
# num_ctx is 32768; keep ~4k for the answer. Chars/3.5 is a rough token count for mixed code and English.
LOCAL_MAX_TOKENS = int(os.environ.get("LOCAL_MAX_TOKENS", "28000"))
LOG = Path(os.environ.get("LOCAL_ROUTER_LOG", Path.home() / ".cache" / "local_router" / "requests.jsonl"))
GUARD_WORDS = ("injection", "security", "safety", "permission", "classif", "malicious", "policy", "allow", "deny")
LOCAL_KEYS = {"model", "messages", "system", "max_tokens", "stream", "tools", "temperature", "stop_sequences",
              "top_p", "top_k"}
_log_lock = threading.Lock()


def _system_text(body: dict) -> str:
    sysp = body.get("system")
    if isinstance(sysp, list):
        # Claude Code puts a billing header block first; it says nothing about the request type.
        sysp = " ".join(b.get("text", "") for b in sysp if isinstance(b, dict)
                        and not str(b.get("text", "")).startswith("x-anthropic-billing-header"))
    return str(sysp or "")


def system_head(body: dict) -> str:
    return " ".join(_system_text(body).split())[:60]


def is_marker(model: str) -> bool:
    """Claude Code only sends a model we name. Observe log (2026-09-23): with no override every request, Explore
    subagents and the tool-less side calls included, went to the main model; 0 haiku requests. So the handle is an
    explicit marker: CLAUDE_CODE_SUBAGENT_MODEL / ANTHROPIC_DEFAULT_HAIKU_MODEL=local-qwen."""
    return model.startswith("local") or "haiku" in model


def decide(body: dict, raw_len: int, mode: str = MODE, gpu_busy: bool = False) -> tuple[str, str]:
    """Return (route, reason). route is 'local' or 'upstream'."""
    if not is_marker(str(body.get("model", ""))):
        return "upstream", "main-model"
    head = system_head(body).lower()
    if any(w in head for w in GUARD_WORDS):
        return "upstream", "guard-request"
    if len(local_body(body)) / 3.5 > LOCAL_MAX_TOKENS:
        return "upstream", "too-big"
    if mode != "route":
        return "upstream", "observe"
    if gpu_busy:
        return "upstream", "gpu-busy"
    return "local", "marker"


# Tools the local model keeps. Explore subagents arrive with ~39 tools (~49k est. tokens), over the 32k window;
# tool definitions are most of that. Permission checks run in Claude Code, not in the model, so pruning the list
# only narrows what the model may ask for.
LOCAL_TOOLS = set(os.environ.get("LOCAL_ROUTER_TOOLS", "Read,Grep,Glob,Bash,Edit,Write").split(","))


def local_body(body: dict) -> bytes:
    out = {k: v for k, v in body.items() if k in LOCAL_KEYS}
    out["model"] = LOCAL_MODEL
    if out.get("tools"):
        out["tools"] = [t for t in out["tools"] if t.get("name") in LOCAL_TOOLS]
    return json.dumps(out).encode("utf-8")


def upstream_body(body: dict, raw: bytes) -> bytes:
    """A marker model does not exist upstream; fall back to the cheapest real model."""
    if is_marker(str(body.get("model", ""))) and str(body.get("model", "")).startswith("local"):
        return json.dumps(dict(body, model=FALLBACK_MODEL)).encode("utf-8")
    return raw


FALLBACK_MODEL = os.environ.get("LOCAL_ROUTER_FALLBACK_MODEL", "claude-haiku-4-5-20251001")


def write_log(row: dict) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with _log_lock, LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _gpu_busy() -> bool:
    try:
        from v7_harness.adapters.gpu_priority import pilot_active

        return pilot_active()
    except Exception:
        return False


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"  # close-delimited bodies: streams pass through without re-chunking

    def log_message(self, *args):  # no header or path logging to stderr
        pass

    def _open(self, base: str, method: str, body: bytes | None, headers: dict):
        u = urllib.parse.urlsplit(base)
        conn_cls = http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection
        conn = conn_cls(u.netloc, timeout=600)
        conn.request(method, self.path, body=body, headers=headers)
        return conn, conn.getresponse()

    def _relay(self, resp) -> int:
        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() not in ("transfer-encoding", "connection", "content-length"):
                self.send_header(k, v)
        self.send_header("Connection", "close")
        self.end_headers()
        head = b""
        while True:
            chunk = resp.read1(65536) if hasattr(resp, "read1") else resp.read(65536)
            if not chunk:
                break
            self.wfile.write(chunk)
            self.wfile.flush()
            head = head or chunk[:300]
        # error bodies are API messages (no secrets); kept so a failed fallback can be diagnosed from the log
        self.error_head = head.decode("utf-8", "replace") if resp.status >= 400 else ""
        return len(head)

    def _upstream_headers(self) -> dict:
        return {k: v for k, v in self.headers.items()
                if k.lower() not in ("host", "content-length", "accept-encoding", "connection")}

    def _forward_upstream(self, method: str, body: bytes | None) -> int:
        conn, resp = self._open(UPSTREAM, method, body, self._upstream_headers())
        try:
            self._relay(resp)
        finally:
            conn.close()
        return resp.status

    def do_GET(self):
        self._forward_upstream("GET", None)

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        started = time.monotonic()
        route, reason, body = "upstream", "not-messages", {}
        if self.path.split("?")[0] == "/v1/messages":
            try:
                body = json.loads(raw)
                route, reason = decide(body, len(raw), gpu_busy=_gpu_busy() if MODE == "route" else False)
            except ValueError:
                reason = "bad-json"
        status = None
        if route == "local":
            try:
                conn, resp = self._open(OLLAMA, "POST", local_body(body),
                                        {"content-type": "application/json", "x-api-key": "ollama"})
                if resp.status == 200:
                    try:
                        self._relay(resp)
                    finally:
                        conn.close()
                    status = 200
                else:
                    conn.close()
                    route, reason = "upstream", f"local-http-{resp.status}"
            except OSError as exc:
                route, reason = "upstream", f"local-{type(exc).__name__}"
        if status is None:
            status = self._forward_upstream("POST", upstream_body(body, raw) if body else raw)
        write_log({"sys_chars": len(_system_text(body)) if body else 0,
                   "tools_chars": len(json.dumps(body.get("tools") or [])) if body else 0,"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "path": self.path.split("?")[0],
                   "model": body.get("model"), "route": route, "reason": reason, "status": status,
                   "est_tokens": int(len(raw) / 3.5), "n_tools": len(body.get("tools") or []),
                   "stream": bool(body.get("stream")), "sys_head": system_head(body) if body else "",
                   "ms": int((time.monotonic() - started) * 1000), "error": getattr(self, "error_head", "")})


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"local_router on 127.0.0.1:{PORT} mode={MODE} -> local {LOCAL_MODEL}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
