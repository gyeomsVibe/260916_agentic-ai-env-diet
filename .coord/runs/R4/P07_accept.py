"""Hidden acceptance for P07: behavior checks independent of the agent's own tests."""
import math, sys
sys.path.insert(0, ".")
from inventory import Inventory

inv = Inventory()
inv.add("b", 10, 2.0); inv.add("a", 5, 1.0); inv.add("b", 10, 4.0)
assert inv.quantity("b") == 20 and math.isclose(inv.total_value(), 20 * 3.0 + 5 * 1.0)
assert inv.skus() == ["a", "b"] and inv.quantity("zzz") == 0
assert inv.low_stock(10) == ["a"]
inv.remove("a", 5); assert inv.skus() == ["b"]
for bad in (lambda: inv.add("x", 0, 1.0), lambda: inv.add("x", 1, -1.0), lambda: inv.remove("b", 0),
            lambda: inv.remove("b", 999)):
    try: bad(); raise AssertionError("expected ValueError")
    except ValueError: pass
try: inv.remove("nope", 1); raise AssertionError("expected KeyError")
except KeyError: pass
csv = inv.to_csv(); assert csv.splitlines()[0] == "sku,qty,unit_price" and "b,20,3.00" in csv
back = Inventory.from_csv(csv); assert back.quantity("b") == 20 and math.isclose(back.total_value(), 60.0)
for bad in ("wrong,header\nb,1,1.00", "sku,qty,unit_price\nb,notint,1.00"):
    try: Inventory.from_csv(bad); raise AssertionError("expected ValueError")
    except ValueError: pass
print("P07_ACCEPT_OK")
