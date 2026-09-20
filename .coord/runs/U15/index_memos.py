"""U15 S8: 조율 메모 색인 생성기.

메모는 지우지 않는다. 대신 번호·날짜·작성자·제목을 한 줄씩 모아 어디에 무엇이 있는지 보이게 한다.
제목과 작성자는 파일 첫 제목 줄에서만 읽고, 추측하지 않는다.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]
MEMO_DIR = PROJECT / "docs" / "claude-assist"
INDEX = MEMO_DIR / "INDEX.md"

NUM_RE = re.compile(r"^(?P<num>\d+)[_-]")
DATE_RE = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})")
AUTHOR_RE = re.compile(r"^#\s*(?P<author>[^:0-9]+?)\s*(?:→|↔)\s*(?P<to>[^:0-9]+?)\s*\d+\s*:")


def _first_heading(path: Path) -> str:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def build() -> str:
    rows: list[tuple[int, str, str, str, str]] = []
    for path in sorted(MEMO_DIR.glob("*.md")):
        if path.name == "INDEX.md":
            continue
        heading = _first_heading(path)
        author_match = AUTHOR_RE.match("# " + heading)
        author = author_match.group("author").strip() if author_match else "미상"
        to = author_match.group("to").strip() if author_match else "-"
        num_match = NUM_RE.match(path.name)
        number = int(num_match.group("num")) if num_match else 0
        date_match = DATE_RE.search(path.name) or DATE_RE.search(heading)
        date = date_match.group("date") if date_match else "-"
        title = heading.split(":", 1)[-1].strip() if ":" in heading else heading
        rows.append((number, date, author, to, title))
        _ = path
    rows.sort()

    lines = [
        "# 조율 메모 색인",
        "",
        f"메모 {len(rows)}건. 본문은 지우지 않고 그대로 둔다. 이 색인은 `.coord/runs/U15/index_memos.py`가 만든다.",
        "",
        "| 번호 | 날짜 | 보낸 쪽 | 받는 쪽 | 제목 |",
        "|---|---|---|---|---|",
    ]
    for number, date, author, to, title in rows:
        lines.append(f"| {number:02d} | {date} | {author} | {to} | {title} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    text = build()
    INDEX.write_text(text, encoding="utf-8")
    print(f"{INDEX} {len(text.splitlines())} lines")
    sys.exit(0)
