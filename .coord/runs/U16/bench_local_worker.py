"""U16 실측: 로컬 모델 작업자가 어디까지 되는가.

"7B 모델이 쓸 만한가"는 의견으로 답할 수 없다. 난이도를 세 단계로 나눈 과제를 실제 파일럿으로
돌리고, 인수 검사 통과 여부와 걸린 시간을 기록한다. 판정은 파일럿 게이트가 한다.

난이도 구분(왜 이렇게 나눴나):
- easy   : 바꿀 값과 파일이 지시문에 그대로 있다. 로컬 모델의 주 용도.
- medium : 여러 파일을 같은 규칙으로 고쳐야 한다. 지시는 구체적이지만 옮길 곳이 여러 군데다.
- hard   : 무엇을 고칠지 코드를 읽고 판단해야 한다. 로컬 모델의 한계를 보려는 과제.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]
BENCH_ROOT = PROJECT / ".work" / "bench_local_worker"
RESULT = PROJECT / ".coord" / "runs" / "U16" / "bench_local_worker.json"
MODELS = ["qwen2.5-coder:7b", "qwen2.5-coder:3b", "qwen3.5:4b"]


def _big_file(count: int) -> str:
    """긴 파일. "파일 전체를 다시 쓰라"는 형식이 어디서 무너지는지 본다."""
    helpers = "".join(f"def helper_{i}(x):\n    return x + {i}\n\n\n" for i in range(count))
    return "TIMEOUT_S = 30\n\n\n" + helpers


CASES = [
    {
        "id": "easy",
        "files": {
            "config.py": 'TIMEOUT_S = 30\nRETRIES = 3\nNAME = "demo"\n',
        },
        "prompt": "In `config.py`, change TIMEOUT_S from 30 to 90. Change nothing else.",
        "accept": 'import pathlib,sys\n'
                  's=pathlib.Path("config.py").read_text(encoding="utf-8")\n'
                  'ok = "TIMEOUT_S = 90" in s and "RETRIES = 3" in s and \'NAME = "demo"\' in s\n'
                  'print("OK" if ok else "FAIL"); sys.exit(0 if ok else 1)\n',
    },
    {
        "id": "medium",
        "files": {
            "reader.py": 'def load(path):\n    return open(path).read()\n',
            "writer.py": 'def save(path, text):\n    open(path, "w").write(text)\n',
        },
        "prompt": (
            "Two files use `open()` without an encoding, which breaks on Windows for non-ASCII text.\n"
            "In `reader.py` and `writer.py`, add `encoding=\"utf-8\"` to every `open()` call.\n"
            "Keep the function names and signatures exactly as they are."
        ),
        "accept": 'import pathlib,sys\n'
                  'r=pathlib.Path("reader.py").read_text(encoding="utf-8")\n'
                  'w=pathlib.Path("writer.py").read_text(encoding="utf-8")\n'
                  'ok = r.count("encoding=") >= 1 and w.count("encoding=") >= 1 and "def load(path)" in r and "def save(path, text)" in w\n'
                  'print("OK" if ok else "FAIL"); sys.exit(0 if ok else 1)\n',
    },
    {
        "id": "hard",
        "files": {
            "stats.py": (
                "def mean(values):\n"
                "    return sum(values) / len(values)\n\n\n"
                "def median(values):\n"
                "    ordered = sorted(values)\n"
                "    return ordered[len(ordered) // 2]\n"
            ),
        },
        "prompt": (
            "`stats.py` has two defects found by tests:\n"
            "1. mean([]) raises ZeroDivisionError. It must raise ValueError('empty') instead.\n"
            "2. median() is wrong for an even number of values; it must average the two middle values.\n"
            "Fix both in `stats.py`. Keep the function names."
        ),
        "accept": 'import sys\n'
                  'sys.path.insert(0, ".")\n'
                  'import stats\n'
                  'ok = True\n'
                  'try:\n'
                  '    stats.mean([])\n'
                  '    ok = False\n'
                  'except ValueError:\n'
                  '    pass\n'
                  'except Exception:\n'
                  '    ok = False\n'
                  'ok = ok and stats.median([1, 2, 3, 4]) == 2.5 and stats.median([1, 3, 5]) == 3\n'
                  'ok = ok and stats.mean([2, 4]) == 3\n'
                  'print("OK" if ok else "FAIL"); sys.exit(0 if ok else 1)\n',
    },
    {
        "id": "large_file",
        "files": {"big.py": _big_file(120)},
        "prompt": "In `big.py`, change TIMEOUT_S from 30 to 90. Every other line must stay exactly as it is.",
        "accept": 'import pathlib,sys\n'
                  's=pathlib.Path("big.py").read_text(encoding="utf-8")\n'
                  'ok = "TIMEOUT_S = 90" in s and s.count("def helper_") == 120 and "def helper_119(x)" in s\n'
                  'print("OK" if ok else "FAIL"); sys.exit(0 if ok else 1)\n',
    },
    {
        # 일부러 모호하게 적는다. 판단을 요구하는 지시에서 어디까지 되는지 본다.
        "id": "ambiguous",
        "files": {
            "cache.py": "STORE = {}\n\n\ndef put(key, value):\n    STORE[key] = value\n\n\ndef get(key):\n    return STORE[key]\n",
        },
        "prompt": "Make `cache.py` more robust. Missing keys should not crash the caller.",
        "accept": 'import sys\n'
                  'sys.path.insert(0, ".")\n'
                  'import cache\n'
                  'ok = cache.get("nope") is None\n'
                  'cache.put("a", 1)\n'
                  'ok = ok and cache.get("a") == 1\n'
                  'print("OK" if ok else "FAIL"); sys.exit(0 if ok else 1)\n',
    },
    {
        "id": "multi_file_refactor",
        "files": {
            "api.py": "from util import fetch_data\n\n\ndef run():\n    return fetch_data('x')\n",
            "util.py": "def fetch_data(key):\n    return {'key': key}\n",
            "job.py": "from util import fetch_data\n\n\ndef nightly():\n    return fetch_data('y')\n",
        },
        "prompt": (
            "Rename `fetch_data` to `load_record` everywhere: its definition in `util.py` and every "
            "import and call in `api.py` and `job.py`. Behaviour must not change."
        ),
        "accept": 'import sys, pathlib\n'
                  'sys.path.insert(0, ".")\n'
                  'texts = {n: pathlib.Path(n).read_text(encoding="utf-8") for n in ("api.py", "util.py", "job.py")}\n'
                  'ok = all("fetch_data" not in t for t in texts.values())\n'
                  'import api, job\n'
                  'ok = ok and api.run() == {"key": "x"} and job.nightly() == {"key": "y"}\n'
                  'print("OK" if ok else "FAIL"); sys.exit(0 if ok else 1)\n',
    },
]


def run_case(case: dict, model: str) -> dict:
    slug = f"{model.replace(':', '-')}_{case['id']}"
    source = BENCH_ROOT / slug / "source"
    work = BENCH_ROOT / slug / "work"
    for path in (source, work):
        if path.exists():
            shutil.rmtree(path)
    source.mkdir(parents=True)
    for name, body in case["files"].items():
        (source / name).write_text(body, encoding="utf-8")

    accept_script = BENCH_ROOT / slug / "accept.py"
    accept_script.write_text(case["accept"], encoding="utf-8")
    prompt_file = BENCH_ROOT / slug / "prompt.md"
    prompt_file.write_text(case["prompt"], encoding="utf-8")

    started = time.monotonic()
    completed = subprocess.run(
        [
            sys.executable, "-m", "v7_harness.cli", "pilot", "run",
            "--task", f"B{abs(hash(slug)) % 100000}",
            "--source", str(source),
            "--prompt-file", str(prompt_file),
            "--work-dir", str(work),
            "--worker", "local",
            "--model", model,
            "--print-timeout", "900",
            "--accept-cmd", f'"{sys.executable}" "{accept_script}"',
        ],
        cwd=PROJECT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=1800,
    )
    elapsed = round(time.monotonic() - started, 1)

    summary: dict = {}
    for line in (completed.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                summary = json.loads((completed.stdout or "")[(completed.stdout or "").index(line):])
            except json.JSONDecodeError:
                pass
            break
    return {
        "case": case["id"],
        "model": model,
        "verdict": summary.get("verdict_hint", "UNKNOWN"),
        "state": summary.get("state", "UNKNOWN"),
        "error_class": summary.get("error_class", "UNKNOWN"),
        "acceptance_exit": summary.get("acceptance_exit"),
        "changed_files": summary.get("changed_files", []),
        "usage": summary.get("agy_usage", {}),
        "wall_s": elapsed,
    }


def main() -> int:
    BENCH_ROOT.mkdir(parents=True, exist_ok=True)
    models = sys.argv[1:] or MODELS
    rows = [run_case(case, model) for model in models for case in CASES]
    by_model = {
        model: {
            "passed": sum(1 for r in rows if r["model"] == model and r["verdict"] == "PASS"),
            "total": sum(1 for r in rows if r["model"] == model),
            "wall_s": round(sum(r["wall_s"] for r in rows if r["model"] == model), 1),
        }
        for model in models
    }
    by_case = {
        case["id"]: [r["model"] for r in rows if r["case"] == case["id"] and r["verdict"] == "PASS"]
        for case in CASES
    }
    report = {
        "schema": "u16-local-worker-bench-v2",
        "models": models,
        "cases": rows,
        "by_model": by_model,
        "passed_by_case": by_case,
        "note": "판정은 파일럿 인수 게이트가 한 것이며, 표본은 (모델, 과제)당 1회다.",
    }
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
