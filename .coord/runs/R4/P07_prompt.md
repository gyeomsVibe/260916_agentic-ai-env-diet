In this workspace, create two new files and do not modify existing files.

1. `inventory.py` implementing class `Inventory` (type hints, one-line docstrings):
   - `add(sku: str, qty: int, unit_price: float)`: qty > 0 and unit_price >= 0 else `ValueError`; adding an existing sku increases qty and keeps a quantity-weighted average unit price.
   - `remove(sku: str, qty: int)`: `KeyError` for unknown sku, `ValueError` if qty <= 0 or exceeds stock; remove the sku when qty reaches 0.
   - `quantity(sku) -> int` (0 if unknown), `total_value() -> float`, `skus() -> list[str]` sorted.
   - `low_stock(threshold: int) -> list[str]` sorted skus with qty < threshold.
   - `to_csv() -> str` with header `sku,qty,unit_price` and rows sorted by sku, unit_price formatted with 2 decimals.
   - `classmethod from_csv(text: str) -> Inventory` that parses the same format and raises `ValueError` on a bad header or malformed row.
2. `test_inventory.py` using `unittest` with at least 20 tests covering every method, the weighted average, round-trip CSV and every error path.

Do not create, delete or rename other files. Run `python -m unittest -q` and reply with a one-line summary.
