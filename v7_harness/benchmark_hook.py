"""
Lightweight A/B benchmark hook module for v7 harness.

Facilitates execution comparison between baseline and candidate approaches.
In accordance with global rules, cost and token savings are explicitly tracked as UNMEASURED
unless and until empirical, real-world comparison measurements are recorded.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Optional


@dataclass
class BenchmarkResult:
    benchmark_name: str
    baseline_duration_sec: float
    candidate_duration_sec: float
    baseline_success: bool
    candidate_success: bool
    cost_savings: str = "UNMEASURED"
    token_savings: str = "UNMEASURED"
    speedup_ratio: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BenchmarkHook:
    """Executes and records A/B comparisons with rigorous metric labeling."""

    def __init__(self, benchmark_name: str = "v7_vs_baseline"):
        self.benchmark_name = benchmark_name

    def run_comparison(
        self,
        baseline_fn: Callable[[], Any],
        candidate_fn: Callable[[], Any],
        metadata: Optional[dict[str, Any]] = None,
    ) -> BenchmarkResult:
        # Run baseline
        t0 = time.perf_counter()
        baseline_success = True
        try:
            baseline_fn()
        except Exception:
            baseline_success = False
        baseline_dur = time.perf_counter() - t0

        # Run candidate
        t1 = time.perf_counter()
        candidate_success = True
        try:
            candidate_fn()
        except Exception:
            candidate_success = False
        candidate_dur = time.perf_counter() - t1

        speedup = (baseline_dur / candidate_dur) if candidate_dur > 0 and candidate_success else None

        return BenchmarkResult(
            benchmark_name=self.benchmark_name,
            baseline_duration_sec=round(baseline_dur, 6),
            candidate_duration_sec=round(candidate_dur, 6),
            baseline_success=baseline_success,
            candidate_success=candidate_success,
            cost_savings="UNMEASURED",
            token_savings="UNMEASURED",
            speedup_ratio=round(speedup, 2) if speedup is not None else None,
            metadata=metadata or {},
        )
