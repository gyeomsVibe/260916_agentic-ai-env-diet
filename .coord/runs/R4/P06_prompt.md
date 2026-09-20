In this workspace, create two new files and do not modify existing files.

1. `stats.py` with these pure functions (type hints and a one-line docstring each; raise `ValueError` for empty input unless stated):
   - `mean(values)`, `median(values)` (average of the two middle values for even length),
   - `mode(values)` returning a sorted list of all most-frequent values,
   - `variance(values, sample=False)` (sample=True uses n-1 and needs at least 2 values),
   - `stdev(values, sample=False)`,
   - `percentile(values, p)` with linear interpolation between closest ranks, `0 <= p <= 100` else `ValueError`,
   - `zscores(values)` returning a list; if stdev is 0 return all zeros.
2. `test_stats.py` using `unittest` with at least 18 tests covering normal cases, edge cases and every error path.

Do not create, delete or rename other files. Run `python -m unittest -q` and reply with a one-line summary.
