Create `src/util.py` and `tests/test_util.py`.

In `src/util.py`:
```python
"""CSV utility module."""
from __future__ import annotations
from typing import Any

def sort_csv_rows(rows: list[dict[str, Any]], key: str, reverse: bool = False) -> list[dict[str, Any]]:
    """Sort a list of dictionary rows by the specified column key."""
    return sorted(rows, key=lambda r: r.get(key, ""), reverse=reverse)
```

In `tests/test_util.py`:
```python
"""Tests for CSV utility module."""
import unittest
from src.util import sort_csv_rows

class TestCSVUtil(unittest.TestCase):
    def test_sort_ascending(self):
        rows = [{"name": "Bob", "age": "30"}, {"name": "Alice", "age": "25"}]
        sorted_rows = sort_csv_rows(rows, key="name")
        self.assertEqual([r["name"] for r in sorted_rows], ["Alice", "Bob"])

    def test_sort_descending(self):
        rows = [{"name": "Bob", "age": "30"}, {"name": "Alice", "age": "25"}]
        sorted_rows = sort_csv_rows(rows, key="age", reverse=True)
        self.assertEqual([r["age"] for r in sorted_rows], ["30", "25"])

    def test_sort_empty(self):
        self.assertEqual(sort_csv_rows([], key="any"), [])

if __name__ == "__main__":
    unittest.main()
```
