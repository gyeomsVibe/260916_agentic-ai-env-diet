"""olla — 세 도구가 어느 프로젝트에서든 로컬 Ollama 모델을 부려 쓰는 공용 명령.

설계 근거(`ollama/01_작동원리와_운영_Ollama는_어떻게_돌아가나.md` §10, `shared/global-rules/REFERENCES.md`):
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
import hashlib
import json
import math
import os
import shlex
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


# 7b 모델은 영어 지시문 속 "in Korean" 한 마디를 무시했다(1/1 영어). 한국어로 규칙·예시를 주면
# 3/3 한국어였다(2026-09-22 실측). 그래서 --ko 는 지시 자체를 한국어로 감싸고, 결과를 검사해 한 번 더 시킨다.
KO_RULES = (
    "반드시 한국어(한글)로만 답하라. 전문 용어는 한국어로 쓰고 필요하면 영어를 괄호로 병기한다(예: 캐시(cache)).\n"
    "요청한 결과만 쓰고 머리말·설명·따옴표를 붙이지 마라.\n\n"
)
KO_MIN_HANGUL_RATIO = 0.3  # 글자(공백·기호 제외) 중 한글 비율. 코드명·영어 병기를 허용하는 하한


def hangul_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    return sum(1 for c in letters if "가" <= c <= "힣") / len(letters) if letters else 0.0


def cmd_ask(args: argparse.Namespace) -> int:
    context = _read_files(args.file) if args.file else ""
    prompt = f"{args.prompt}\n{context}" if context else args.prompt
    if args.ko:
        prompt = KO_RULES + prompt
    usage_total = {"input_tokens": 0, "output_tokens": 0}
    attempts = 2 if args.ko else 1
    text = ""
    for attempt in range(attempts):
        try:
            text, usage = worker._generate(args.model, prompt, args.timeout)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"ollama unreachable: {exc}", file=sys.stderr)
            return 1
        for key in usage_total:
            usage_total[key] += usage.get(key, 0)
        if not args.ko or hangul_ratio(text) >= KO_MIN_HANGUL_RATIO:
            break
        prompt = "직전 답이 한국어가 아니었다. 같은 요청을 한국어로만 다시 답하라.\n\n" + prompt
    print(text.strip())
    report = {"model": args.model, **usage_total}
    if args.ko:
        report["hangul_ratio"] = round(hangul_ratio(text), 2)
        report["attempts"] = attempt + 1
    print(json.dumps(report, ensure_ascii=False), file=sys.stderr)
    if args.ko and hangul_ratio(text) < KO_MIN_HANGUL_RATIO:
        print("local answer is not Korean after retry — write it yourself", file=sys.stderr)
        return 4
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


# --- 토큰 0 활용: 추정·요약본·경로 결정 -------------------------------------------------
#
# 로컬 모델의 토큰은 0이다. 그러므로 비싼 모델이 무언가를 "읽기 전에" 로컬이 먼저 읽고 줄이는
# 것이 가장 큰 절감이다(LLMLingua, EMNLP 2023: 작은 모델로 입력 최대 20배 압축, 손실 적음).
# 에이전트는 매 턴 문맥을 다시 보내므로 한 번 읽은 큰 파일은 여러 번 과금된다.

# UTF-8 바이트 ÷ 이 값 ≈ 토큰. 한국어·영어·코드가 섞인 이 저장소에서 보수적으로 잡은 값이다
# (tiktoken 같은 토크나이저 없이 O(1)로 추정; 영어 위주면 실제보다 많게, 한국어 위주면 적게 나온다).
BYTES_PER_TOKEN = 3.0
# 이만큼 넘는 읽기는 먼저 로컬 요약본을 만든다. 요약본(약 40줄) 자체가 수백 토큰이므로
# 이보다 작은 파일은 요약하는 편이 오히려 손해다.
DIGEST_MIN_TOKENS = 3000
# 에이전트는 읽은 내용을 이후 턴마다 다시 보낸다. 몇 턴 더 이어진다고 볼지.
REREAD_TURNS = 3
CHUNK_LINES = 300  # U17 실측: 300줄 8/8 적중(구간 19~42줄), 150줄 7/8 — .coord/runs/U17/bench_digest*.json

LOCAL_KINDS = {
    "summarize": ("요약", "정리", "설명", "summar", "explain", "overview", "describe"),
    "classify": ("분류", "판별", "태그", "classif", "categor", "label"),
    "draft": ("초안", "작성", "문서", "docstring", "주석", "draft", "boilerplate", "readme", "changelog", "commit message"),
    "find": ("찾", "어디", "검색", "find", "where", "locate", "search"),
}


def estimate_tokens(paths: list[str], prompt: str = "") -> dict:
    """비싼 모델이 이 파일들을 읽을 때 드는 토큰을 추정한다."""
    per_file = []
    total_bytes = len(prompt.encode("utf-8"))
    for raw in paths:
        path = Path(raw)
        size = path.stat().st_size if path.is_file() else 0
        total_bytes += size
        per_file.append({"file": raw.replace(os.sep, "/"), "tokens": round(size / BYTES_PER_TOKEN)})
    once = round(total_bytes / BYTES_PER_TOKEN)
    return {"read_once": once, "with_rereads": once * (1 + REREAD_TURNS), "files": per_file}


def _kind(task: str) -> str:
    lowered = task.lower()
    for kind, words in LOCAL_KINDS.items():
        if any(word in lowered for word in words):
            return kind
    return "other"


def decide_route(task: str, paths: list[str]) -> dict:
    """사용자 지시 없이 도구가 스스로 정하는 경로.

    - local-digest-then-self: 읽을 양이 크면 로컬이 먼저 요약본을 만들고, 비싼 모델은 그것만 읽는다.
    - local-edit: 수정 지시가 구체적이면(worker_advice 60점 이상) 로컬이 고친다.
    - local-answer: 요약·분류·초안·찾기는 로컬이 답하고 비싼 모델은 검토만 한다.
    - self: 판단이 필요하고 읽을 양도 작으면 비싼 모델이 직접.
    """
    from v7_harness.adapters.worker_advice import advise

    cost = estimate_tokens(paths, task)
    kind = _kind(task)
    advice = advise(task)
    edit_like = any(w in task.lower() for w in ("change", "rename", "replace", "add", "remove", "fix", "바꿔", "변경", "추가", "삭제", "수정", "교체"))

    if cost["read_once"] >= DIGEST_MIN_TOKENS and kind in ("summarize", "find", "other"):
        route = "local-digest-then-self"
        why = f"읽기 약 {cost['read_once']:,}토큰(재전송 포함 {cost['with_rereads']:,}) — 로컬 요약본을 먼저 읽는다"
    elif edit_like and advice.worker == "local":
        route = "local-edit"
        why = f"수정 지시 구체성 {advice.specificity}/100 — 로컬이 고치고 결과만 검증한다"
    elif kind in ("summarize", "classify", "draft", "find"):
        route = "local-answer"
        why = f"{kind} 과제 — 로컬이 답하고 검토만 한다"
    else:
        route = "self"
        why = f"판단이 필요한 과제(구체성 {advice.specificity}/100)이고 읽을 양이 작다"
    saved = cost["with_rereads"] if route != "self" else 0
    return {"route": route, "reason": why, "kind": kind, "estimated_paid_tokens": cost, "tokens_saved_estimate": saved}


def _digest_chunks(text: str) -> list[tuple[int, int, str]]:
    lines = text.splitlines()
    return [
        (start + 1, min(start + CHUNK_LINES, len(lines)), "\n".join(lines[start:start + CHUNK_LINES]))
        for start in range(0, max(len(lines), 1), CHUNK_LINES)
    ]


def digest_file(path: Path, focus: str, model: str, timeout: int) -> tuple[str, dict]:
    """줄 번호가 달린 요약본. 비싼 모델은 이걸 보고 필요한 구간만 연다."""
    text = path.read_text(encoding="utf-8", errors="replace")
    parts: list[str] = []
    usage_total = {"input_tokens": 0, "output_tokens": 0}
    for first, last, chunk in _digest_chunks(text):
        numbered = "\n".join(f"{first + i}: {line}" for i, line in enumerate(chunk.splitlines()))
        prompt = (
            "Summarize this part of a file for another engineer who will decide which lines to open.\n"
            "Output at most 8 bullet lines. Each bullet: `L<start>-<end>: <what is there>`.\n"
            "Name functions, classes, constants, and anything related to the focus. No prose outside bullets.\n"
            f"Focus: {focus or 'general structure'}\n\n{numbered}"
        )
        answer, usage = worker._generate(model, prompt, timeout)
        usage_total["input_tokens"] += usage.get("input_tokens", 0)
        usage_total["output_tokens"] += usage.get("output_tokens", 0)
        parts.append(answer.strip())
    header = f"# digest: {path.as_posix()} ({len(text.splitlines())} lines)"
    return header + "\n" + "\n".join(parts) + "\n", usage_total


# 같은 파일·같은 질문을 세 도구가 따로 요약하면 로컬 몇 분이 매번 다시 든다(U17 실측 파일당 약 1분).
# 내용 해시로 묶으므로 파일이 바뀌면 자동으로 무효가 되고, 프로젝트를 가리지 않는다.
DIGEST_CACHE_DIR = Path(os.environ.get("OLLA_CACHE", Path.home() / ".cache" / "olla" / "digest"))
DIGEST_PROMPT_VERSION = "1"


def _digest_cache_path(path: Path, focus: str, model: str) -> Path:
    key = hashlib.sha256()
    for part in (DIGEST_PROMPT_VERSION, str(CHUNK_LINES), model, focus):
        key.update(f"{len(part)}:{part}".encode("utf-8"))  # 길이 접두로 경계를 모호하지 않게
    key.update(path.read_bytes())
    return DIGEST_CACHE_DIR / f"{key.hexdigest()}.json"


def cmd_estimate(args: argparse.Namespace) -> int:
    print(json.dumps(estimate_tokens(args.file, args.prompt or ""), ensure_ascii=False))
    return 0


def cmd_route(args: argparse.Namespace) -> int:
    print(json.dumps(decide_route(args.task, args.file), ensure_ascii=False))
    return 0


def cmd_digest(args: argparse.Namespace) -> int:
    for raw in args.file:
        path = Path(raw)
        if not path.is_file():
            print(f"no such file: {raw}", file=sys.stderr)
            return 2
        cache = _digest_cache_path(path, args.focus or "", args.model)
        cached = not args.no_cache and cache.is_file()
        if cached:
            saved = json.loads(cache.read_text(encoding="utf-8"))
            digest, usage = saved["digest"].replace(saved["path"], path.as_posix(), 1), {"input_tokens": 0, "output_tokens": 0}
        else:
            try:
                digest, usage = digest_file(path, args.focus or "", args.model, args.timeout)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                print(f"ollama unreachable: {exc}", file=sys.stderr)
                return 1
            try:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(json.dumps({"path": path.as_posix(), "digest": digest}, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass  # 캐시는 편의일 뿐, 못 써도 요약본은 낸다
        before = round(path.stat().st_size / BYTES_PER_TOKEN)
        after = round(len(digest.encode("utf-8")) / BYTES_PER_TOKEN)
        sys.stdout.write(digest)
        print(json.dumps({
            "file": path.as_posix(),
            "paid_tokens_if_read": before,
            "paid_tokens_digest": after,
            "saved_pct": round((1 - after / before) * 100, 1) if before else 0.0,
            "local_tokens": usage,
            "cached": cached,
        }, ensure_ascii=False), file=sys.stderr)
    return 0


# 문서만 두면 규칙 준수가 25~40%, 훅으로 걸면 약 95%(agents.md 가이드 인용, REFERENCES.md §4).
# 그래서 "큰 파일은 요약본 먼저"를 Read 직전에 상기시킨다. 막지는 않는다 — 판단은 비싼 모델 몫이다.
def read_hint(event: dict) -> str | None:
    tool_input = event.get("tool_input") or {}
    if tool_input.get("offset") or tool_input.get("limit"):
        return None  # 이미 필요한 줄만 여는 중
    raw = tool_input.get("file_path") or ""
    path = Path(raw)
    try:
        if not raw or not path.is_file():
            return None
        tokens = round(path.stat().st_size / BYTES_PER_TOKEN)
    except OSError:
        return None
    if tokens < DIGEST_MIN_TOKENS or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ipynb"}:
        return None
    return (
        f"olla: {path.name} is about {tokens:,} tokens. If you only need to locate something, "
        f'`olla digest -f "{path.as_posix()}" --focus "<question>"` gives a line-numbered map for 0 paid tokens '
        "(cached; measured 8/8 hits), then Read with offset/limit."
    )


def cmd_hook_read(args: argparse.Namespace) -> int:
    """Claude Code PreToolUse(Read) 훅. 어떤 입력에도 0으로 끝나 도구를 막지 않는다."""
    try:
        event = json.loads(sys.stdin.read() or "{}")
        hint = read_hint(event)
    except (ValueError, AttributeError):
        return 0
    if hint:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": hint}}, ensure_ascii=False))
    return 0


# Codex 는 파일을 셸로 읽는다. 그리고 PreToolUse 의 additionalContext 를 아직 받지 않으므로(공식 hooks 문서)
# 읽은 직후(PostToolUse)에 알린다. 이미 읽은 파일은 늦었지만, 이후 턴 재전송과 다음 읽기를 줄인다.
WHOLE_FILE_READERS = {"cat", "type", "get-content", "gc", "more", "bat"}
SHELL_WRAPPERS = {"powershell", "pwsh", "bash", "sh", "cmd", "zsh"}
RANGE_FLAGS = {"-totalcount", "-head", "-tail", "-first", "-last", "-n", "--lines"}


def shell_read_targets(command: str) -> list[str]:
    """`cat big.py`처럼 파일을 통째로 출력하는 명령의 대상. 파이프·범위 지정은 이미 줄인 것으로 본다."""
    targets: list[str] = []
    for segment in command.replace("&&", ";").replace("||", ";").split(";"):
        if "|" in segment:
            continue
        try:
            words = shlex.split(segment, posix=False)
        except ValueError:
            continue
        # `powershell -NoProfile -Command "Get-Content x"` 같은 감싸기를 벗긴다
        if words and Path(words[0]).stem.lower() in SHELL_WRAPPERS:
            words = words[1:]
            while words and words[0][:1] in "-/":
                words = words[1:]
            if len(words) == 1 and " " in words[0]:
                targets.extend(shell_read_targets(words[0].strip("'\"")))
                continue
        if not words or words[0].lower() not in WHOLE_FILE_READERS:
            continue
        args = words[1:]
        if any(a.lower() in RANGE_FLAGS for a in args):
            continue
        targets.extend(a.strip("'\"") for a in args if not a.startswith("-"))
    return targets


def shell_read_hint(event: dict) -> str | None:
    command = (event.get("tool_input") or {}).get("command") or ""
    if isinstance(command, list):
        # ["powershell", "-Command", "Get-Content x"] 처럼 셸이 감싼 형태면 실제 명령만 꺼낸다
        parts = [str(part) for part in command]
        if parts and Path(parts[0]).stem.lower() in SHELL_WRAPPERS:
            parts = [part for part in parts[1:] if part[:1] not in "-/"]
        command = " ".join(parts)
    base = Path(event.get("cwd") or ".")
    for raw in shell_read_targets(str(command)):
        path = Path(raw) if Path(raw).is_absolute() else base / raw
        hint = read_hint({"tool_input": {"file_path": str(path)}})
        if hint:
            return hint.replace("then Read with offset/limit.", "then print only those lines (e.g. `sed -n 'A,Bp'`).")
    return None


def cmd_hook_shell(args: argparse.Namespace) -> int:
    """Codex PostToolUse(Bash) 훅. 어떤 입력에도 0으로 끝나 도구를 막지 않는다."""
    try:
        event = json.loads(sys.stdin.read() or "{}")
        hint = shell_read_hint(event) if isinstance(event, dict) else None
    except (ValueError, AttributeError, TypeError):
        return 0
    if hint:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": hint}}, ensure_ascii=False))
    return 0


# 규칙이 문맥에 있어도 계획 단계에서 로컬 모델을 빠뜨렸다(2026-09-22, 사용자가 먼저 물어서야 드러남).
# 그래서 지시가 들어오는 순간(UserPromptSubmit) 분업을 먼저 정하게 한 줄을 넣는다. 서버가 꺼져 있으면 말하지 않는다.
PLAN_HINT = (
    "olla (local model, 0 paid tokens) is up. Before acting, split this task: reading a file over ~3k tokens -> "
    "`olla digest`, drafts/summaries/commit messages -> `olla ask --ko` with format+example, exact edits -> `olla edit`, "
    "semantic search -> `olla find`. Do the rest yourself; verify local output, never let it judge."
)


def _server_up() -> bool:
    try:
        _get("/api/version", timeout=1)
        return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


def cmd_hook_plan(args: argparse.Namespace) -> int:
    """Claude Code·Codex 공통 UserPromptSubmit 훅. 어떤 입력에도 0으로 끝나 막지 않는다."""
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    if not isinstance(event, dict) or not _server_up():
        return 0
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": PLAN_HINT}}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="olla", description="로컬 Ollama 모델을 어느 프로젝트에서든 부려 쓰는 명령")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("status")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("ask")
    p.add_argument("prompt")
    p.add_argument("-f", "--file", action="append", default=[])
    p.add_argument("--ko", action="store_true", help="한국어 규칙을 붙이고, 한국어가 아니면 한 번 다시 시킴(실패 시 종료 코드 4)")
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

    p = sub.add_parser("estimate", help="비싼 모델이 이 파일들을 읽을 때 드는 토큰 추정")
    p.add_argument("-f", "--file", action="append", default=[])
    p.add_argument("--prompt", default="")
    p.set_defaults(func=cmd_estimate)

    p = sub.add_parser("route", help="이 과제를 로컬로 보낼지 스스로 정함")
    p.add_argument("task")
    p.add_argument("-f", "--file", action="append", default=[])
    p.set_defaults(func=cmd_route)

    p = sub.add_parser("digest", help="큰 파일의 줄 번호 요약본(비싼 모델이 읽기 전에)")
    p.add_argument("-f", "--file", action="append", required=True)
    p.add_argument("--focus", default="")
    p.add_argument("--model", default=CHAT_MODEL)
    p.add_argument("--timeout", type=int, default=900)
    p.add_argument("--no-cache", action="store_true", help="같은 내용·질문의 이전 요약본을 쓰지 않음")
    p.set_defaults(func=cmd_digest)

    p = sub.add_parser("hook-read", help="Claude Code PreToolUse(Read) 훅: 큰 파일이면 요약본을 권함")
    p.set_defaults(func=cmd_hook_read)

    p = sub.add_parser("hook-shell", help="Codex PostToolUse(Bash) 훅: 큰 파일을 통째로 읽었으면 요약본을 권함")
    p.set_defaults(func=cmd_hook_shell)

    p = sub.add_parser("hook-plan", help="UserPromptSubmit 훅: 작업 시작 시 로컬 모델 분업을 먼저 정하게 함")
    p.set_defaults(func=cmd_hook_plan)

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
