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
MODEL = "qwen2.5-coder:7b"

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
]


def run_case(case: dict) -> dict:
    source = BENCH_ROOT / case["id"] / "source"
    work = BENCH_ROOT / case["id"] / "work"
    for path in (source, work):
        if path.exists():
            shutil.rmtree(path)
    source.mkdir(parents=True)
    for name, body in case["files"].items():
        (source / name).write_text(body, encoding="utf-8")

    accept_script = BENCH_ROOT / case["id"] / "accept.py"
    accept_script.write_text(case["accept"], encoding="utf-8")
    prompt_file = BENCH_ROOT / case["id"] / "prompt.md"
    prompt_file.write_text(case["prompt"], encoding="utf-8")

    started = time.monotonic()
    completed = subprocess.run(
        [
            sys.executable, "-m", "v7_harness.cli", "pilot", "run",
            "--task", f"BENCH{case['id'].upper()}",
            "--source", str(source),
            "--prompt-file", str(prompt_file),
            "--work-dir", str(work),
            "--worker", "local",
            "--model", MODEL,
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
    rows = [run_case(case) for case in CASES]
    passed = [row for row in rows if row["verdict"] == "PASS"]
    report = {
        "schema": "u16-local-worker-bench-v1",
        "model": MODEL,
        "cases": rows,
        "passed": len(passed),
        "total": len(rows),
        "note": "판정은 파일럿 인수 게이트가 한 것이며, 표본은 난이도당 1회다.",
    }
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
