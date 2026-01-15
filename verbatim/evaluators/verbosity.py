"""Verbosity stability evaluator stubs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass
class TurnMetrics:
    turn_index: int
    output_tokens: int


@dataclass
class VerbosityMetrics:
    mean_tokens_per_turn: float
    drift_slope: float
    length_stddev: float
    growth_ratio: float


def compute_verbosity_metrics(turns: Sequence[TurnMetrics]) -> VerbosityMetrics:
    """Compute verbosity metrics from per-turn token counts.

    This is a placeholder implementation that will be replaced with
    a Probekit-integrated evaluator.
    """
    if not turns:
        return VerbosityMetrics(0.0, 0.0, 0.0, 0.0)

    ordered = sorted(turns, key=lambda t: t.turn_index)
    outputs = [t.output_tokens for t in ordered]
    mean = sum(outputs) / len(outputs)

    # Simple variance/stddev without external deps.
    variance = sum((x - mean) ** 2 for x in outputs) / len(outputs)
    stddev = variance ** 0.5

    xs = [float(t.turn_index) for t in ordered]
    drift_slope = _linear_regression_slope(xs, [float(val) for val in outputs])

    # Growth ratio: last 3 turns vs first 3 turns.
    first_window = outputs[:3]
    last_window = outputs[-3:]
    first_avg = sum(first_window) / len(first_window)
    last_avg = sum(last_window) / len(last_window)
    growth_ratio = (last_avg / first_avg) if first_avg else 0.0

    return VerbosityMetrics(
        mean_tokens_per_turn=mean,
        drift_slope=drift_slope,
        length_stddev=stddev,
        growth_ratio=growth_ratio,
    )


def iter_turn_metrics(token_counts: Iterable[int]) -> list[TurnMetrics]:
    """Create per-turn metrics objects from token counts."""
    return [TurnMetrics(turn_index=i, output_tokens=val) for i, val in enumerate(token_counts)]


def _linear_regression_slope(xs: Sequence[float], ys: Sequence[float]) -> float:
    """
    Return least-squares slope for y = a + b*x.
    b = cov(x,y)/var(x)
    If var(x) == 0 or length < 2, return 0.0
    """
    if len(xs) < 2 or len(ys) < 2:
        return 0.0
    xs_float = [float(x) for x in xs]
    ys_float = [float(y) for y in ys]
    mx = sum(xs_float) / len(xs_float)
    my = sum(ys_float) / len(ys_float)
    var = sum((x - mx) ** 2 for x in xs_float)
    if var == 0:
        return 0.0
    cov = sum((x - mx) * (y - my) for x, y in zip(xs_float, ys_float))
    return cov / var
