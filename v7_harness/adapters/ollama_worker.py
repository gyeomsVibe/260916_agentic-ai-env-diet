"""로컬 Ollama 모델을 파일럿 작업자로 쓰는 어댑터.

파일럿은 작업자에게 `-p <프롬프트> --output-format json --print-timeout Ns --add-dir <작업공간>`
형태로 말을 걸고, 작업자가 그 작업공간의 파일을 고친 뒤 JSON 한 덩어리를 찍어 주길 기대한다.
이 스크립트는 그 규격을 로컬 모델에 맞춰 준다.

의도적으로 좁게 만든다. 7B 모델에게 자유로운 편집을 맡기면 거의 실패한다. 대신
"파일 전체를 새로 써 달라"는 한 가지 형식만 받아들이고, 형식을 벗어나면 실패로 끝낸다.
판정은 이 스크립트가 하지 않는다. 파일럿의 인수 검사와 게이트가 한다.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

# 서버 주소·모델·문맥 크기는 환경변수로 덮어쓸 수 있다. 기본값은 이 PC의 실측 설정이다
# (GTX 1660 Ti 6GB에서 qwen2.5-coder:7b Q4_K_M 이 VRAM 4.3GB, 문맥 16384로 동작).
HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
API = f"{HOST}/api/generate"
DEFAULT_MODEL = os.environ.get("OLLAMA_WORKER_MODEL", "qwen2.5-coder:7b")
NUM_CTX = int(os.environ.get("OLLAMA_WORKER_NUM_CTX", "16384"))
KEEP_ALIVE = os.environ.get("OLLAMA_WORKER_KEEP_ALIVE", "30m")
BLOCK_RE = re.compile(r"^===FILE:\s*(?P<path>[^\n=]+?)\s*===\n(?P<body>.*?)(?=^===FILE:|\Z)", re.M | re.S)

FORMAT_RULES = """
You are editing files inside the given workspace. Reply with nothing but file blocks.

Format, repeated once per file you change:
===FILE: <relative/path>===
<the complete new content of that file>

Rules:
- Output the WHOLE file, not a diff and not a fragment.
- Do not add explanations, markdown fences, or comments about your work.
- Only touch files the task names. Leave every other line of those files byte-identical.
"""


def _generate(model: str, prompt: str, timeout_s: int) -> tuple[str, dict[str, int]]:
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": KEEP_ALIVE,
            # 낮은 온도. 이 작업자는 창작이 아니라 지시받은 줄을 그대로 옮기는 손이다.
            "options": {"temperature": 0.1, "num_ctx": NUM_CTX},
        }
    ).encode("utf-8")
    request = urllib.request.Request(API, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        body = json.loads(response.read().decode("utf-8"))
    usage = {
        "input_tokens": int(body.get("prompt_eval_count") or 0),
        "output_tokens": int(body.get("eval_count") or 0),
    }
    return str(body.get("response") or ""), usage


def _apply(text: str, workspace: Path) -> list[str]:
    """모델이 돌려준 파일 블록을 작업공간에 쓴다. 작업공간 밖 경로는 거부한다."""
    written: list[str] = []
    for match in BLOCK_RE.finditer(text):
        rel = match.group("path").strip().replace("\\", "/")
        body = match.group("body")
        target = (workspace / rel).resolve()
        if not str(target).startswith(str(workspace.resolve())):
            raise ValueError(f"PATH_ESCAPE:{rel}")
        if not target.parent.is_dir():
            raise ValueError(f"UNKNOWN_DIR:{rel}")
        target.write_text(body.rstrip("\n") + "\n", encoding="utf-8")
        written.append(rel)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--prompt", required=True)
    parser.add_argument("--output-format", default="json")
    parser.add_argument("--print-timeout", default="600s")
    parser.add_argument("--add-dir", dest="workspace", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--conversation", default=None)
    parser.add_argument("--json-schema", default=None)
    parser.add_argument("--dangerously-skip-permissions", action="store_true")
    args, _unknown = parser.parse_known_args(argv)

    workspace = Path(args.workspace)
    timeout_s = int(str(args.print_timeout).rstrip("s") or 600)

    def envelope(status: str, response: str, usage: dict[str, int], error: str = "") -> int:
        print(json.dumps(
            {"status": status, "response": response, "usage": usage, "conversation_id": "ollama-local", "error": error},
            ensure_ascii=False,
        ))
        return 0 if status == "SUCCESS" else 1

    # 과제가 가리키는 파일의 현재 내용을 함께 준다. 7B 모델은 파일을 스스로 찾지 못한다.
    named = sorted({
        candidate.replace("\\", "/")
        for candidate in re.findall(r"`([^`\n]+\.(?:md|py|txt))`", args.prompt)
        if (workspace / candidate.replace("\\", "/")).is_file()
    } | {
        name for name in ("core.md", "GLOBAL_RULES.ko.md", "VERSION", "history.md")
        if (workspace / name).is_file() and name in args.prompt
    })
    context = "".join(
        f"\n===CURRENT FILE: {name}===\n{(workspace / name).read_text(encoding='utf-8')}\n"
        for name in named[:4]
    )

    prompt = f"{FORMAT_RULES}\n\nTASK:\n{args.prompt}\n\nCURRENT CONTENTS:{context}\n\nNow output the file blocks."
    try:
        text, usage = _generate(args.model, prompt, timeout_s)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return envelope("ERROR", "", {"input_tokens": 0, "output_tokens": 0}, f"ollama unreachable: {exc}")

    if "===FILE:" not in text:
        return envelope("ERROR", "", usage, "model returned no file block")
    try:
        written = _apply(text, workspace)
    except ValueError as exc:
        return envelope("ERROR", "", usage, str(exc))
    if not written:
        return envelope("ERROR", "", usage, "no file written")
    return envelope("SUCCESS", f"wrote: {', '.join(written)}", usage)


if __name__ == "__main__":
    sys.exit(main())
