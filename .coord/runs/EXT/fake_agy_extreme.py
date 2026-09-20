"""Fake agy for extreme tests. Mode via EXT_MODE; optional EXT_SLEEP seconds before acting."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def envelope(status: str = "SUCCESS", **extra) -> str:
    body = {"conversation_id": "ext-conv-0001", "status": status, "response": "DONE", "num_turns": 1,
            "usage": {"input_tokens": 10, "output_tokens": 1, "thinking_tokens": 0, "cache_read_tokens": 0, "total_tokens": 11}}
    body.update(extra)
    return json.dumps(body)


def main(argv: list[str]) -> int:
    mode = os.environ.get("EXT_MODE", "success")
    ws = Path(argv[argv.index("--add-dir") + 1])
    time.sleep(float(os.environ.get("EXT_SLEEP", "0")))
    target = ws / "calc.py"
    if mode in {"success", "slow", "escape_parent", "many_files", "unicode"}:
        with target.open("a", encoding="utf-8") as s:
            s.write("\n\ndef add(a, b):\n    return a + b\n")
    if mode == "escape_parent":
        (ws.parent / "ESCAPED_FROM_STAGING.txt").write_text("outside staging, not a watch root", encoding="utf-8")
    if mode == "many_files":
        d = ws / "gen"
        d.mkdir(exist_ok=True)
        for i in range(2000):
            (d / f"m{i:04d}.py").write_text(f"X{i} = {i}\n", encoding="utf-8")
    if mode == "unicode":
        (ws / "한글 파일 name.py").write_text("V = '유니코드'\n", encoding="utf-8")
    if mode == "hang":
        time.sleep(3600)
    if mode == "huge_output":
        sys.stdout.write("A" * (60 * 1024 * 1024))
        return 0
    if mode == "garbage":
        sys.stdout.buffer.write(os.urandom(4096))
        return 0
    if mode == "spawn_child_hang":
        import subprocess
        subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3600)"])
        time.sleep(3600)
    if mode == "delete_file":
        (ws / "test_calc.py").unlink()
    sys.stdout.write(envelope())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
