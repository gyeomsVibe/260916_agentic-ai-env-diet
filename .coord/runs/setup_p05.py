"""Set up clean P05 sample directories for apples-to-apples A/B benchmark."""

from pathlib import Path

CALC_CODE = '''"""Tiny calculator module used as the live pilot target."""


def mul(a: float, b: float) -> float:
    """Return a multiplied by b."""
    return a * b


def clamp(value: float, low: float, high: float) -> float:
    """Clamp value to the inclusive range [low, high]."""
    if low > high:
        raise ValueError("low cannot be greater than high")
    if value < low:
        return low
    if value > high:
        return high
    return value
'''

TEST_CODE = '''import unittest

import calc


class CalcTests(unittest.TestCase):
    def test_mul(self) -> None:
        self.assertEqual(6, calc.mul(2, 3))

    def test_clamp_inside(self) -> None:
        self.assertEqual(5, calc.clamp(5, 1, 10))

    def test_clamp_below(self) -> None:
        self.assertEqual(1, calc.clamp(-5, 1, 10))

    def test_clamp_above(self) -> None:
        self.assertEqual(10, calc.clamp(15, 1, 10))

    def test_clamp_at_bounds(self) -> None:
        self.assertEqual(1, calc.clamp(1, 1, 10))
        self.assertEqual(10, calc.clamp(10, 1, 10))

    def test_clamp_invalid_bounds(self) -> None:
        with self.assertRaises(ValueError):
            calc.clamp(5, 10, 1)


if __name__ == "__main__":
    unittest.main()
'''


def main() -> None:
    root = Path(__file__).resolve().parents[2].parent
    for name in ("260916_pilot_sample_P05_A", "260916_pilot_sample_P05_B"):
        target_dir = root / name
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "calc.py").write_text(CALC_CODE, encoding="utf-8")
        (target_dir / "test_calc.py").write_text(TEST_CODE, encoding="utf-8")
    print("Setup P05 samples complete.")


if __name__ == "__main__":
    main()
