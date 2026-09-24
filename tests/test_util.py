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
