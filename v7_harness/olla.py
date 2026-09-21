"""olla — 세 도구가 어느 프로젝트에서든 로컬 Ollama 모델을 부려 쓰는 공용 명령.

설계 근거(`docs/ollama/README.md` §10, `shared/global-rules/REFERENCES.md`):
- FrugalGPT(arXiv:2305.05176)·RouteLLM(ICLR 2025): 싼 모델을 먼저 쓰고 부족할 때만 비싼 모델로
  올리면 비용을 크게 줄이면서 품질을 지킬 수 있다(캐스케이드).
- GitHub의 Ollama 위임 도구들(claude-sidekick, mcp-local-llm 등)의 공통 분업:
  "생각은 비싼 모델이, 기계적인 일은 로컬 모델이".
- 이 프로젝트 벤치: 로컬 모델의 유일한 실패 축은 지시의 모호함이었다.

그래서 이 명령은 **파일럿 밖**에서도 쓰이지만, 파일럿이 해 주던 안전장치 중 핵심 셋을 스스로 한다.
1. 편집 전 백업(`.work/backup_olla_<시각>/`), 2. 편집 결과를 diff로 보여 줌,
3. 판정은 하지 않는다 — 부른 도구가 테스트로 확인한다.

명령:
  olla status                         서버·모델 상태
  olla ask "질문" [-f 파일 ...]        초안·요약·설명·분류 같은 한 번짜리 답
  olla edit -f 파일 ... "지시"         파일을 고치고 diff 출력(백업 후), --dry-run 이면 diff만
  olla find "질문" [-d 폴더]           폴더 안 텍스트 파일을 의미로 검색(임베딩)
"""

from __future__ import annotations

import argparse
import difflib
import json
import math
import os
import shutil
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from v7_harness.adapters import ollama_worker as worker

HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
CHAT_MODEL = os.environ.get("OLLA_MODEL", worker.DEFAULT_MODEL)
EMBED_MODEL = os.environ.get("OLLA_EMBED_MODEL", "qwen3-embedding:0.6b")
TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".toml", ".yml", ".yaml", ".ps1", ".sh", ".js", ".ts"}
MAX_FILE_CHARS = 200_000


def _post(path: str, payload: dict, timeout: int = 900) -> dict:
    request = urllib.request.Request(
        f"{HOST}{path}", data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _get(path: str, timeout: int = 10) -> dict:
    with urllib.request.urlopen(f"{HOST}{path}", timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _read_files(paths: list[str]) -> str:
    chunks = []
    for raw in paths:
        path = Path(raw)
        if not path.is_file():
            raise FileNotFoundError(raw)
        text = path.read_text(encoding="utf-8", errors="replace")[:MAX_FILE_CHARS]
        chunks.append(f"\n===CURRENT FILE: {raw.replace(os.sep, '/')}===\n{text}\n")
    return "".join(chunks)


def cmd_status(_: argparse.Namespace) -> int:
    try:
        tags = _get("/api/tags")
        loaded = _get("/api/ps")
    except (urllib.error.URLError, OSError) as exc:
        print(json.dumps({"ok": False, "error": f"ollama unreachable: {exc}", "host": HOST}, ensure_ascii=False))
        return 1
    print(json.dumps({
        "ok": True,
        "host": HOST,
        "chat_model": CHAT_MODEL,
        "embed_model": EMBED_MODEL,
        "installed": [m.get("name") for m in tags.get("models", [])],
        "loaded": [{"name": m.get("name"), "vram_gb": round((m.get("size_vram") or 0) / 1e9, 2)} for m in loaded.get("models", [])],
    }, ensure_ascii=False))
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    context = _read_files(args.file) if args.file else ""
    prompt = f"{args.prompt}\n{context}" if context else args.prompt
    try:
        text, usage = worker._generate(args.model, prompt, args.timeout)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"ollama unreachable: {exc}", file=sys.stderr)
        return 1
    print(text.strip())
    print(json.dumps({"model": args.model, **usage}, ensure_ascii=False), file=sys.stderr)
    return 0


def _backup(files: list[Path], root: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    dest = root / ".work" / f"backup_olla_{stamp}"
    for path in files:
        target = dest / path.resolve().relative_to(root.resolve())
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    return dest


def cmd_edit(args: argparse.Namespace) -> int:
    root = Path.cwd()
    files = [Path(f) for f in args.file]
    for path in files:
        if not path.is_file():
            print(f"no such file: {path}", file=sys.stderr)
            return 2
        if not str(path.resolve()).startswith(str(root.resolve())):
            # 부른 도구의 작업 폴더 밖은 고치지 않는다. 다른 프로젝트를 건드리는 사고를 막는다.
            print(f"outside the current project: {path}", file=sys.stderr)
            return 2

    before = {p: p.read_text(encoding="utf-8") for p in files}
    longest = max(len(text.splitlines()) for text in before.values())
    rules = worker.EDIT_RULES if longest >= worker.EDIT_MODE_MIN_LINES else worker.FORMAT_RULES
    names = " ".join(f"`{p.as_posix()}`" for p in files)
    prompt = f"{rules}\n\nTASK:\n{args.instruction}\nFiles: {names}\n\nCURRENT CONTENTS:{_read_files(args.file)}\n\nNow output the blocks."
    try:
        text, usage = worker._generate(args.model, prompt, args.timeout)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"ollama unreachable: {exc}", file=sys.stderr)
        return 1

    # 먼저 임시 사본에 적용해 본다. 실패하면 원본은 건드리지 않는다.
    scratch = root / ".work" / f"olla_scratch_{os.getpid()}"
    if scratch.exists():
        shutil.rmtree(scratch)
    for path in files:
        target = scratch / path.resolve().relative_to(root.resolve())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(before[path], encoding="utf-8")
    try:
        written = worker._apply(text, scratch)
    except ValueError as exc:
        shutil.rmtree(scratch, ignore_errors=True)
        print(f"model output rejected: {exc}", file=sys.stderr)
        return 3
    if not written:
        shutil.rmtree(scratch, ignore_errors=True)
        print("model changed nothing", file=sys.stderr)
        return 3

    diffs = []
    after: dict[Path, str] = {}
    for path in files:
        new_text = (scratch / path.resolve().relative_to(root.resolve())).read_text(encoding="utf-8")
        after[path] = new_text
        diffs.extend(difflib.unified_diff(
            before[path].splitlines(keepends=True), new_text.splitlines(keepends=True),
            fromfile=f"a/{path.as_posix()}", tofile=f"b/{path.as_posix()}",
        ))
    shutil.rmtree(scratch, ignore_errors=True)
    sys.stdout.write("".join(diffs) or "(no textual change)\n")

    if args.dry_run:
        print(json.dumps({"applied": False, "dry_run": True, **usage}, ensure_ascii=False), file=sys.stderr)
        return 0
    backup = _backup(files, root)
    for path, new_text in after.items():
        path.write_text(new_text, encoding="utf-8")
    print(json.dumps({"applied": True, "backup": str(backup), **usage}, ensure_ascii=False), file=sys.stderr)
    return 0


def _embed(texts: list[str]) -> list[list[float]]:
    body = _post("/api/embed", {"model": EMBED_MODEL, "input": texts})
    return body.get("embeddings") or []


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def cmd_find(args: argparse.Namespace) -> int:
    base = Path(args.dir)
    skip = {".git", ".work", "__pycache__", "node_modules", ".venv"}
    candidates: list[tuple[Path, str]] = []
    for path in base.rglob("*"):
        if any(part in skip for part in path.parts) or not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")[:2000]
        if text.strip():
            candidates.append((path, text))
        if len(candidates) >= args.limit:
            break
    if not candidates:
        print("no text files", file=sys.stderr)
        return 1
    try:
        vectors = _embed([args.query] + [text for _, text in candidates])
    except (urllib.error.URLError, OSError) as exc:
        print(f"ollama unreachable: {exc}", file=sys.stderr)
        return 1
    query, docs = vectors[0], vectors[1:]
    ranked = sorted(zip(candidates, docs), key=lambda item: _cosine(query, item[1]), reverse=True)
    for (path, _), vector in ranked[: args.top]:
        print(f"{_cosine(query, vector):.3f}  {path.as_posix()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="olla", description="로컬 Ollama 모델을 어느 프로젝트에서든 부려 쓰는 명령")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("status")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("ask")
    p.add_argument("prompt")
    p.add_argument("-f", "--file", action="append", default=[])
    p.add_argument("--model", default=CHAT_MODEL)
    p.add_argument("--timeout", type=int, default=900)
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("edit")
    p.add_argument("instruction")
    p.add_argument("-f", "--file", action="append", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--model", default=CHAT_MODEL)
    p.add_argument("--timeout", type=int, default=900)
    p.set_defaults(func=cmd_edit)

    p = sub.add_parser("find")
    p.add_argument("query")
    p.add_argument("-d", "--dir", default=".")
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--limit", type=int, default=300)
    p.set_defaults(func=cmd_find)
    return parser


def main(argv: list[str] | None = None) -> int:
    # Windows 콘솔 기본 인코딩(cp949)에서는 한국어 답이 깨진다. 부르는 도구가 읽을 수 있게 UTF-8로 고정한다.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
