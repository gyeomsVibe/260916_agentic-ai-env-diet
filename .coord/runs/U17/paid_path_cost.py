"""U17: 요약본 경로의 유료 토큰 — 요약본 + 적중한 가장 좁은 구간 열기 vs 파일 통째 읽기.

bench_digest.json(7b, 300줄 조각)의 요약본을 그대로 쓴다. 한 번 읽기 기준이며, 이후 턴 재전송은 뺐다
(재전송까지 넣으면 두 경로 모두 비례해 커지므로 비율은 같다). 실제 에이전트 세션의 절감은 여전히 UNMEASURED.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]
SOURCE = PROJECT / ".coord" / "runs" / "U17" / "bench_digest.json"
RESULT = PROJECT / ".coord" / "runs" / "U17" / "paid_path_cost.json"
RANGE_RE = re.compile(r"L(\d+)\s*-\s*L?(\d+)")
BYTES_PER_TOKEN = 3.0  # olla.BYTES_PER_TOKEN 과 같은 근사


def main() -> int:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    rows = []
    for row in data["runs"][0]["rows"]:
        lines = (PROJECT / row["file"]).read_text(encoding="utf-8").splitlines()
        spans = [(int(a), int(b)) for a, b in RANGE_RE.findall(row["digest"]) if any(int(a) <= t <= int(b) for t in row["truth"])]
        lo, hi = min(spans, key=lambda s: s[1] - s[0])
        opened = round(len("\n".join(lines[lo - 1:hi]).encode("utf-8")) / BYTES_PER_TOKEN)
        path_cost = row["digest_tokens"] + opened
        rows.append({"file": row["file"], "question": row["question"], "full_read": row["file_tokens"],
                     "digest": row["digest_tokens"], "opened_window": opened, "digest_path": path_cost,
                     "saved_pct": round((1 - path_cost / row["file_tokens"]) * 100, 1)})
    full = sum(r["full_read"] for r in rows)
    path = sum(r["digest_path"] for r in rows)
    report = {"schema": "u17-paid-path-v1", "model": data["model"], "full_read_tokens": full, "digest_path_tokens": path,
              "saved_pct": round((1 - path / full) * 100, 1), "rows": rows}
    RESULT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"full={full} digest_path={path} saved={report['saved_pct']}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
