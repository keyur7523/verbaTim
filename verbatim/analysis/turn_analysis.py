"""Per-turn analysis: follow-up metrics and turn-by-turn ratios against baseline.

Turn 0 answers an open-ended prompt and every follow-up asks for something
narrow, so turn 0 dominates any metric computed over all 12 turns. These
helpers report turn 0 on its own and compute drift over the follow-ups.

Follow-up lengths also track what each question asks for. Every condition sees
the same questions, so comparing a run to the baseline condition at the same
turn removes that per-question demand: a ratio of 0.6 means "60% of baseline's
length at this turn", and a rising ratio means the intervention's effect is
fading over the conversation.
"""
from __future__ import annotations

import math
from typing import Any, Sequence

from verbatim.evaluators.verbosity import TurnMetrics, _linear_regression_slope, compute_verbosity_metrics


def followup_metrics(outputs: Sequence[float]) -> dict[str, float | None]:
    """Turn 0 length plus verbosity metrics over turns 1..n-1."""
    if len(outputs) < 2:
        return {"turn0_tokens": outputs[0] if outputs else None}
    metrics = compute_verbosity_metrics(
        [TurnMetrics(turn_index=i, output_tokens=v) for i, v in enumerate(outputs) if i > 0]
    )
    return {
        "turn0_tokens": outputs[0],
        "followup_mean_tokens": metrics.mean_tokens_per_turn,
        "followup_drift_slope": metrics.drift_slope,
        "followup_growth_ratio": metrics.growth_ratio,
        "followup_length_stddev": metrics.length_stddev,
    }


def followup_checks(metrics: dict[str, float | None], fallback_rate: float, thresholds: dict[str, float]) -> dict[str, bool]:
    """The verbosity-stability checks, applied to the follow-up turns only."""
    mean = metrics.get("followup_mean_tokens") or 0.0
    return {
        "drift_slope": metrics["followup_drift_slope"] <= thresholds["max_drift_slope"],
        "growth_ratio": metrics["followup_growth_ratio"] <= thresholds["max_growth_ratio"],
        "length_stddev": metrics["followup_length_stddev"] <= thresholds["max_stddev_ratio"] * mean,
        "fallback_rate": fallback_rate <= thresholds["max_fallback_rate"],
    }


def baseline_profiles(records: list[dict[str, Any]], key_fields: Sequence[str]) -> dict[tuple, list[float | None]]:
    """Mean output length at each turn index across baseline runs, per comparison key."""
    sums: dict[tuple, dict[int, list[float]]] = {}
    for record in records:
        if record["condition"] != "baseline":
            continue
        per_turn = sums.setdefault(tuple(record[f] for f in key_fields), {})
        for index, value in enumerate(record["outputs"]):
            per_turn.setdefault(index, []).append(value)
    profiles = {}
    for key, per_turn in sums.items():
        length = max(per_turn) + 1
        profiles[key] = [
            sum(per_turn[i]) / len(per_turn[i]) if i in per_turn else None for i in range(length)
        ]
    return profiles


def ratio_vs_baseline(outputs: Sequence[float], profile: Sequence[float | None]) -> dict[str, float | None]:
    """Geometric-mean length ratio to baseline over follow-ups, its trend, and the turn 0 ratio.

    Ratios are compared on a log scale so that 0.5x and 2x are symmetric.
    ratio_drift_pct_per_turn is the fitted % change in the ratio per turn.
    """
    pairs = [
        (i, math.log(value / profile[i]))
        for i, value in enumerate(outputs)
        if i > 0 and i < len(profile) and profile[i] and value > 0
    ]
    turn0 = (outputs[0] / profile[0]) if outputs and profile and profile[0] else None
    if not pairs:
        return {"length_ratio_vs_baseline": None, "ratio_drift_pct_per_turn": None, "turn0_ratio_vs_baseline": turn0}
    logs = [log_ratio for _, log_ratio in pairs]
    slope = _linear_regression_slope([float(i) for i, _ in pairs], logs)
    return {
        "length_ratio_vs_baseline": math.exp(sum(logs) / len(logs)),
        "ratio_drift_pct_per_turn": (math.exp(slope) - 1) * 100,
        "turn0_ratio_vs_baseline": turn0,
    }
