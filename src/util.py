"""CSV utility module."""
from __future__ import annotations
from typing import Any

def sort_csv_rows(rows: list[dict[str, Any]], key: str, reverse: bool = False) -> list[dict[str, Any]]:
    """Sort a list of dictionary rows by the specified column key."""
    return sorted(rows, key=lambda r: r.get(key, ""), reverse=reverse)
