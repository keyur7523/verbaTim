import random

import pytest

from verbatim.analysis.primary_comparison import compare


def _runs(condition, intent, make, n=10, seed=0):
    rng = random.Random(f"{condition}-{intent}-{seed}")
    return [{"model": "m", "condition": condition, "intent_id": intent, "outputs": make(rng)} for _ in range(n)]


def test_constant_half_length_has_no_drift_and_ratio_half():
    baseline = lambda rng: [400] + [40 + rng.gauss(0, 2) for _ in range(11)]
    half = lambda rng: [100] + [20 + rng.gauss(0, 1) for _ in range(11)]
    runs = []
    for intent in ("a", "b"):
        runs += _runs("baseline", intent, baseline) + _runs("verbatim", intent, half)
    result = compare(runs, "verbatim", resamples=300, seed=1)
    assert result["n_runs"] == 20
    assert result["length_ratio_vs_baseline"] == pytest.approx(0.5, abs=0.03)
    lo, hi = result["ratio_drift_ci95_bootstrap"]
    assert lo < 0 < hi


def test_fading_constraint_has_positive_drift_ci():
    baseline = lambda rng: [400] + [40 + rng.gauss(0, 2) for _ in range(11)]
    # Starts at half of baseline and climbs back toward it.
    fading = lambda rng: [100] + [20 + 2 * i + rng.gauss(0, 1) for i in range(11)]
    runs = _runs("baseline", "a", baseline) + _runs("verbatim", "a", fading)
    result = compare(runs, "verbatim", resamples=300, seed=1)
    lo, hi = result["ratio_drift_ci95_bootstrap"]
    assert lo > 3
    t_lo, _ = result["ratio_drift_ci95_t"]
    assert t_lo > 3
