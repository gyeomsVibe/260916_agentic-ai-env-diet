"""Hidden acceptance for P06: behavior checks independent of the agent's own tests."""
import math, sys
sys.path.insert(0, ".")
import stats as s

def raises(f, *a, **k):
    try: f(*a, **k)
    except ValueError: return True
    return False

assert s.mean([1, 2, 3, 4]) == 2.5
assert s.median([3, 1, 2]) == 2 and s.median([4, 1, 3, 2]) == 2.5
assert s.mode([1, 2, 2, 3, 3]) == [2, 3] and s.mode([5]) == [5]
assert math.isclose(s.variance([2, 4, 4, 4, 5, 5, 7, 9]), 4.0)
assert math.isclose(s.variance([2, 4, 4, 4, 5, 5, 7, 9], sample=True), 32 / 7)
assert math.isclose(s.stdev([2, 4, 4, 4, 5, 5, 7, 9]), 2.0)
assert math.isclose(s.percentile([1, 2, 3, 4], 50), 2.5)
assert s.percentile([10, 20, 30], 0) == 10 and s.percentile([10, 20, 30], 100) == 30
assert s.zscores([5, 5, 5]) == [0, 0, 0]
z = s.zscores([2, 4, 4, 4, 5, 5, 7, 9]); assert math.isclose(z[0], -1.5)
for f, a, k in ((s.mean, ([],), {}), (s.median, ([],), {}), (s.mode, ([],), {}),
                (s.variance, ([1],), {"sample": True}), (s.percentile, ([1, 2], 101), {}),
                (s.percentile, ([1, 2], -1), {})):
    assert raises(f, *a, **k), f.__name__
print("P06_ACCEPT_OK")
