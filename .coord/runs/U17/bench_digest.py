"""U17 실측: `olla digest` 요약본이 찾는 줄을 얼마나 맞히는가.

규칙은 "큰 읽기는 요약본 먼저, 그 줄만 연다"이다. 요약본이 엉뚱한 줄을 가리키면 비싼 모델이
헛걸음하거나, 더 나쁘게는 있는 코드를 없다고 판단한다. 그래서 적중률(recall)을 잰다.

방법: 실제 파일에서 정답 줄을 grep으로 먼저 정한다. 그 질문을 focus로 요약본을 만들고,
요약본의 `L시작-끝` 구간 중 하나라도 정답 줄을 포함하면 적중이다. 조각 크기(300/150줄)를 비교한다.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT))

from v7_harness import olla  # noqa: E402

RESULT = PROJECT / ".coord" / "runs" / "U17" / "bench_digest.json"
RANGE_RE = re.compile(r"L(\d+)\s*-\s*L?(\d+)")

# (파일, 질문, 정답 줄을 찾는 정규식) — 정답은 코드에서 기계적으로 정한다.
CASES = [
    ("v7_harness/pilot.py", "where is the approved bundle applied to the source", r"apply_promotion\("),
    ("v7_harness/pilot.py", "where is the acceptance command executed in staging", r"cwd=str\(workspace\.staging_dir\)"),
    ("v7_harness/pilot.py", "where does a run with no changed files become REWORK", r"if not changed_files and verdict_hint"),
    ("v7_harness/cli.py", "where is the pilot run command registered in the parser", r'add_parser\("run"\)'),
    ("v7_harness/cli.py", "where is the local worker command chosen", r"def resolve_worker_command"),
    ("v7_harness/cli.py", "where are pilot results written to the coordination stream", r"def record_pilot_in_stream"),
    ("v7_harness/coord/stream.py", "where are settled events moved to the archive", r"def archive_settled"),
    ("v7_harness/coord/stream.py", "where is the verdict actor restriction enforced", r"VERDICT_ACTOR_NOT_ALLOWED"),
]


def truth_lines(path: Path, pattern: str) -> list[int]:
    return [i for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1) if re.search(pattern, line)]


def hit_width(digest: str, targets: list[int]) -> int | None:
    """정답을 품은 가장 좁은 구간의 줄 수. 넓은 구간(L1-753)은 공짜 적중이므로 폭도 함께 본다."""
    widths = [int(e) - int(s) + 1 for s, e in RANGE_RE.findall(digest) if any(int(s) <= t <= int(e) for t in targets)]
    return min(widths) if widths else None


def run(chunk: int) -> dict:
    olla.CHUNK_LINES = chunk
    rows = []
    for rel, question, pattern in CASES:
        path = PROJECT / rel
        targets = truth_lines(path, pattern)
        started = time.monotonic()
        digest, usage = olla.digest_file(path, question, olla.CHAT_MODEL, 900)
        rows.append({
            "file": rel,
            "question": question,
            "truth": targets,
            "hit": (width := hit_width(digest, targets)) is not None,
            "hit_width_lines": width,
            "file_lines": len(path.read_text(encoding="utf-8").splitlines()),
            "digest": digest,
            "digest_tokens": round(len(digest.encode("utf-8")) / olla.BYTES_PER_TOKEN),
            "file_tokens": round(path.stat().st_size / olla.BYTES_PER_TOKEN),
            "wall_s": round(time.monotonic() - started, 1),
        })
    hits = sum(1 for r in rows if r["hit"])
    return {
        "chunk_lines": chunk,
        "recall": round(hits / len(rows), 3),
        "hits": hits,
        "total": len(rows),
        "avg_saved_pct": round(sum(1 - r["digest_tokens"] / r["file_tokens"] for r in rows) / len(rows) * 100, 1),
        "wall_s": round(sum(r["wall_s"] for r in rows), 1),
        "rows": rows,
    }


def main() -> int:
    chunks = [int(a) for a in sys.argv[1:]] or [300, 150]
    report = {"schema": "u17-digest-recall-v1", "model": olla.CHAT_MODEL, "runs": [run(c) for c in chunks]}
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for r in report["runs"]:
        print(f"chunk={r['chunk_lines']} recall={r['recall']} ({r['hits']}/{r['total']}) saved={r['avg_saved_pct']}% wall={r['wall_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
