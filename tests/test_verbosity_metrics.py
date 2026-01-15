import pytest

from verbatim.evaluators.verbosity import compute_verbosity_metrics, iter_turn_metrics, TurnMetrics


def test_compute_verbosity_metrics_basic():
    turns = iter_turn_metrics([10, 12, 14, 16])
    metrics = compute_verbosity_metrics(turns)

    assert metrics.mean_tokens_per_turn == pytest.approx(13.0)
    assert metrics.drift_slope == pytest.approx(2.0)
    assert metrics.length_stddev > 0
    assert metrics.growth_ratio > 1.0


def test_regression_differs_from_endpoint_slope():
    turns = iter_turn_metrics([0, 100, 0, 0])
    metrics = compute_verbosity_metrics(turns)
    assert metrics.drift_slope == pytest.approx(-10.0)


def test_sorted_turns_compute_same_slope():
    turns = [
        TurnMetrics(turn_index=2, output_tokens=0),
        TurnMetrics(turn_index=0, output_tokens=0),
        TurnMetrics(turn_index=3, output_tokens=0),
        TurnMetrics(turn_index=1, output_tokens=100),
    ]
    metrics = compute_verbosity_metrics(turns)
    assert metrics.drift_slope == pytest.approx(-10.0)


def test_single_turn_slope_zero():
    turns = iter_turn_metrics([42])
    metrics = compute_verbosity_metrics(turns)
    assert metrics.drift_slope == 0.0


def test_constant_turn_index_slope_zero():
    turns = [
        TurnMetrics(turn_index=5, output_tokens=10),
        TurnMetrics(turn_index=5, output_tokens=20),
        TurnMetrics(turn_index=5, output_tokens=30),
    ]
    metrics = compute_verbosity_metrics(turns)
    assert metrics.drift_slope == 0.0
