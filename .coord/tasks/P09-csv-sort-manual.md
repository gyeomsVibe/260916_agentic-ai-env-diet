# P09 — CSV Sort Utility Implementation

## 1. Goal
Implement CSV row sorting function in `src/util.py` and unit tests in `tests/test_util.py`.

## 2. Specification
- `src/util.py`:
  Provide `sort_csv_rows(rows: list[dict[str, str]], key: str, reverse: bool = False) -> list[dict[str, str]]`:
  Sorts a list of dictionary rows by the specified column key.
- `tests/test_util.py`:
  Unit tests verifying:
  1. Ascending sort by string key
  2. Descending sort (`reverse=True`)
  3. Empty list handling

## 3. Acceptance Gate
`python -m unittest tests.test_util`

## 4. Constraints
- Only create/edit `src/util.py` and `tests/test_util.py`.
- Deterministic, exit code must be 0.
