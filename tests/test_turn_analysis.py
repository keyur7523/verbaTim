import json
from pathlib import Path

import pytest

from verbatim.analysis.summarize import summarize
from verbatim.analysis.turn_analysis import (
    baseline_profiles,
    followup_checks,
    followup_metrics,
    ratio_vs_baseline,
)
from verbatim.experiments.run_conversations import DEFAULT_THRESHOLDS


def test_followup_metrics_exclude_turn0():
    # A long opening answer followed by flat follow-ups: all-turn slope would be strongly negative.
    metrics = followup_metrics([600, 40, 40, 40, 40, 40, 40])
    assert metrics["turn0_tokens"] == 600
    assert metrics["followup_mean_tokens"] == 40
    assert metrics["followup_drift_slope"] == 0
    assert metrics["followup_growth_ratio"] == 1


def test_followup_growth_detected():
    metrics = followup_metrics([600, 30, 35, 40, 45, 50, 55])
    assert metrics["followup_drift_slope"] == pytest.approx(5)
    assert metrics["followup_growth_ratio"] > 1.4


def test_followup_checks_pass_flat_and_fail_growing():
    flat = followup_metrics([600] + [40] * 11)
    assert all(followup_checks(flat, 0.0, DEFAULT_THRESHOLDS).values())
    growing = followup_metrics([600] + [20 + 5 * i for i in range(11)])
    checks = followup_checks(growing, 0.0, DEFAULT_THRESHOLDS)
    assert checks["drift_slope"] is False
    assert checks["growth_ratio"] is False


def test_baseline_profile_is_mean_per_turn_and_keyed():
    records = [
        {"condition": "baseline", "intent_id": "a", "outputs": [100, 10, 20]},
        {"condition": "baseline", "intent_id": "a", "outputs": [300, 30, 40]},
        {"condition": "baseline", "intent_id": "b", "outputs": [50, 5]},
        {"condition": "naive", "intent_id": "a", "outputs": [1, 1, 1]},
    ]
    profiles = baseline_profiles(records, ["intent_id"])
    assert profiles[("a",)] == [200, 20, 30]
    assert profiles[("b",)] == [50, 5]


def test_ratio_is_geometric_mean_over_followups():
    profile = [200, 20, 40]
    result = ratio_vs_baseline([50, 10, 20], profile)
    assert result["length_ratio_vs_baseline"] == pytest.approx(0.5)
    assert result["turn0_ratio_vs_baseline"] == pytest.approx(0.25)
    assert result["ratio_drift_pct_per_turn"] == pytest.approx(0)


def test_ratio_drift_detects_fading_effect():
    profile = [100] * 6
    # Starts at half of baseline and climbs back toward it: the constraint is decaying.
    result = ratio_vs_baseline([100, 50, 60, 70, 80, 90], profile)
    assert result["ratio_drift_pct_per_turn"] > 10


def test_summary_compares_only_runs_with_matching_baseline(tmp_path: Path):
    def write_run(name, condition, intent, outputs, temperature=0.2):
        run_dir = tmp_path / name
        run_dir.mkdir()
        payload = {
            "run_id": name, "model": "claude-sonnet-4-6", "length_unit": "provider_tokens",
            "condition": condition, "intent_id": intent, "temperature": temperature,
            "status": "completed", "passed": False,
            "metrics": {"metrics": {"mean_tokens_per_turn": 1.0, "drift_slope": 0.0, "length_stddev": 0.0}},
        }
        (run_dir / "aggregate_metrics.json").write_text(json.dumps(payload), encoding="utf-8")
        turns = [{"turn_index": i, "output_tokens": v} for i, v in enumerate(outputs)]
        (run_dir / "turn_metrics.json").write_text(json.dumps(turns), encoding="utf-8")

    write_run("b", "baseline", "concept_explanation", [400, 40, 40, 40, 40, 40, 40])
    write_run("v", "verbatim", "concept_explanation", [100, 20, 20, 20, 20, 20, 20])
    write_run("v_other_temp", "verbatim", "concept_explanation", [100, 20, 20, 20, 20, 20, 20], temperature=0.5)

    rows, _ = summarize(tmp_path)
    verbatim = next(r for r in rows if r["condition"] == "verbatim")
    assert verbatim["n"] == 2
    assert verbatim["n_compared"] == 1
    assert verbatim["length_ratio_vs_baseline"] == pytest.approx(0.5)
    assert verbatim["turn0_ratio_vs_baseline"] == pytest.approx(0.25)
    assert verbatim["turn0_tokens"] == 100
    assert verbatim["followup_mean_tokens"] == 20
