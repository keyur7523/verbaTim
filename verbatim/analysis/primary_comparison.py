"""Pre-registered comparison: each condition vs baseline over follow-up turns 1-11.

For every non-baseline condition, reports with 95% CIs:
- ratio drift (% per turn): the trend of the condition's length relative to
  baseline across follow-ups (primary for verbatim; >0 means the constraint fades);
- length ratio vs baseline: geometric-mean follow-up length relative to baseline.

CI method (chosen before the rerun's results were seen): a stratified bootstrap
that resamples, within each intent, both the baseline runs (rebuilding the
per-turn baseline profile) and the condition's runs, so uncertainty in the
baseline is included. A t-interval over run-level values is printed alongside
as a cross-check; it treats the baseline profile as fixed.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev
from typing import Any

from verbatim.analysis.contamination import run_dir_mock_reasons
from verbatim.analysis.summarize import _load_json, _model_id, _ordered_outputs, exclusion_reason, load_turn_metrics
from verbatim.analysis.turn_analysis import ratio_vs_baseline

T_975 = {9: 2.262, 19: 2.093, 29: 2.045, 39: 2.023, 49: 2.010}


def load_runs(artifacts_dir: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    runs, excluded = [], defaultdict(int)
    for run_dir in sorted(p for p in artifacts_dir.iterdir() if p.is_dir()):
        metrics_path = run_dir / "aggregate_metrics.json"
        if not metrics_path.exists():
            continue
        payload = _load_json(metrics_path)
        reason = exclusion_reason(payload) or ("mock_content" if run_dir_mock_reasons(run_dir) else None)
        if reason:
            excluded[reason] += 1
            continue
        runs.append({
            "model": _model_id(payload),
            "condition": payload["condition"],
            "intent_id": payload["intent_id"],
            "outputs": _ordered_outputs(load_turn_metrics(run_dir / "turn_metrics.json")),
        })
    return runs, dict(excluded)


def _profile(baseline_runs: list[dict[str, Any]]) -> list[float]:
    length = max(len(r["outputs"]) for r in baseline_runs)
    return [mean(r["outputs"][i] for r in baseline_runs if len(r["outputs"]) > i) for i in range(length)]


def _run_values(candidate_runs, baseline_runs):
    profile = _profile(baseline_runs)
    values = [ratio_vs_baseline(r["outputs"], profile) for r in candidate_runs]
    return (
        [v["ratio_drift_pct_per_turn"] for v in values if v["ratio_drift_pct_per_turn"] is not None],
        [math.log(v["length_ratio_vs_baseline"]) for v in values if v["length_ratio_vs_baseline"]],
    )


def _statistics(by_intent: dict[str, tuple[list, list]]) -> tuple[float, float]:
    drifts, log_ratios = [], []
    for candidate_runs, baseline_runs in by_intent.values():
        d, lr = _run_values(candidate_runs, baseline_runs)
        drifts += d
        log_ratios += lr
    return mean(drifts), math.exp(mean(log_ratios))


def _t_interval(values: list[float]) -> tuple[float, float]:
    t = T_975.get(len(values) - 1, 1.96)
    half = t * stdev(values) / math.sqrt(len(values))
    return mean(values) - half, mean(values) + half


def compare(runs: list[dict[str, Any]], condition: str, resamples: int, seed: int) -> dict[str, Any]:
    by_intent = {}
    for intent in sorted({r["intent_id"] for r in runs}):
        baseline = [r for r in runs if r["intent_id"] == intent and r["condition"] == "baseline"]
        candidate = [r for r in runs if r["intent_id"] == intent and r["condition"] == condition]
        if baseline and candidate:
            by_intent[intent] = (candidate, baseline)

    drift, ratio = _statistics(by_intent)
    rng = random.Random(seed)
    boot_drift, boot_ratio = [], []
    for _ in range(resamples):
        sample = {
            intent: ([rng.choice(c) for _ in c], [rng.choice(b) for _ in b])
            for intent, (c, b) in by_intent.items()
        }
        d, r = _statistics(sample)
        boot_drift.append(d)
        boot_ratio.append(r)
    boot_drift.sort()
    boot_ratio.sort()
    lo, hi = int(0.025 * resamples), int(0.975 * resamples) - 1

    run_drifts = [v for c, b in by_intent.values() for v in _run_values(c, b)[0]]
    per_intent = {}
    for intent, (c, b) in by_intent.items():
        d, lr = _run_values(c, b)
        per_intent[intent] = {"n": len(c), "ratio_drift_pct_per_turn": mean(d), "length_ratio": math.exp(mean(lr))}
    return {
        "condition": condition,
        "n_runs": sum(len(c) for c, _ in by_intent.values()),
        "n_baseline_runs": sum(len(b) for _, b in by_intent.values()),
        "ratio_drift_pct_per_turn": drift,
        "ratio_drift_ci95_bootstrap": [boot_drift[lo], boot_drift[hi]],
        "ratio_drift_ci95_t": list(_t_interval(run_drifts)),
        "length_ratio_vs_baseline": ratio,
        "length_ratio_ci95_bootstrap": [boot_ratio[lo], boot_ratio[hi]],
        "per_intent": per_intent,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--artifacts-dir", default="artifacts_rerun")
    parser.add_argument("--resamples", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20261016)
    parser.add_argument("--output", default="", help="Optional JSON output path")
    args = parser.parse_args()

    runs, excluded = load_runs(Path(args.artifacts_dir))
    models = sorted({r["model"] for r in runs})
    if len(models) != 1:
        raise SystemExit(f"Expected one model, found {models}")
    print(f"model {models[0]}; included {len(runs)} runs; excluded {excluded or 'none'}")

    results = []
    for condition in ("verbatim", "budgeted", "naive"):
        result = compare(runs, condition, args.resamples, args.seed)
        results.append(result)
        d_lo, d_hi = result["ratio_drift_ci95_bootstrap"]
        t_lo, t_hi = result["ratio_drift_ci95_t"]
        r_lo, r_hi = result["length_ratio_ci95_bootstrap"]
        print(
            f"{condition:9} n={result['n_runs']:3}  ratio drift {result['ratio_drift_pct_per_turn']:+.2f}%/turn "
            f"[bootstrap {d_lo:+.2f}, {d_hi:+.2f}; t {t_lo:+.2f}, {t_hi:+.2f}]  "
            f"length ratio {result['length_ratio_vs_baseline']:.3f} [{r_lo:.3f}, {r_hi:.3f}]"
        )
        for intent, values in result["per_intent"].items():
            print(f"    {intent:22} n={values['n']:2}  drift {values['ratio_drift_pct_per_turn']:+.2f}%/turn  "
                  f"ratio {values['length_ratio']:.3f}")

    if args.output:
        Path(args.output).write_text(
            json.dumps({"model": models[0], "excluded": excluded, "results": results}, indent=2), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
