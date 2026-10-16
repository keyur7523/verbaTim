"""Summarize Verbatim run metrics by (model, condition).

Only completed, evaluated, real-model runs are aggregated by default. Failed
runs, mock-backend runs (model null or "mock-echo", or backend "mock"), runs whose
transcript looks like mock output, and runs without a verbosity evaluation are
excluded and counted by reason.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from verbatim.analysis.contamination import run_dir_mock_reasons
from verbatim.evaluators.instruction_adherence import evaluate_transcript_adherence
from verbatim.experiments.run_conversations import build_turn_specs, load_intents


MOCK_MODELS = {None, "", "mock-echo"}
METRIC_KEYS = ("mean_tokens_per_turn", "drift_slope", "length_stddev", "growth_ratio")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _model_id(payload: dict[str, Any]) -> str | None:
    model = payload.get("model")
    if isinstance(model, dict):
        model = model.get("model_id")
    return model or None


def _extract_metrics(payload: dict[str, Any]) -> dict[str, float | None]:
    metrics = payload.get("metrics") or {}
    # Support nested shape: {"metrics": {...}} or flat.
    if isinstance(metrics.get("metrics"), dict):
        metrics = metrics["metrics"]
    return {
        "mean_tokens_per_turn": metrics.get("mean_tokens_per_turn"),
        "drift_slope": metrics.get("drift_slope"),
        "length_stddev": metrics.get("length_stddev"),
    }


def _format_float(value: float | None) -> str:
    return f"{value:.3f}" if isinstance(value, (int, float)) else "n/a"


def _load_evaluator_results(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "evaluator_results.json"
    if not path.exists():
        return []
    data = _load_json(path)
    return data if isinstance(data, list) else []


def load_turn_metrics(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValueError(f"Missing turn metrics file: {path}")
    data = _load_json(path)
    if not isinstance(data, list):
        raise ValueError(f"Unexpected turn metrics format: {path}")
    return data


def compute_growth_ratio_from_turn_metrics(turn_metrics: list[dict], n: int = 3) -> float:
    ordered = sorted(turn_metrics, key=lambda item: item.get("turn_index", 0))
    outputs = []
    for entry in ordered:
        if "output_tokens" in entry:
            outputs.append(entry.get("output_tokens"))
        elif "assistant_output_tokens" in entry:
            outputs.append(entry.get("assistant_output_tokens"))

    outputs = [val for val in outputs if isinstance(val, (int, float))]
    if len(outputs) < 2 * n:
        return 1.0

    early = sum(outputs[:n]) / n
    late = sum(outputs[-n:]) / n

    if early == 0:
        return 1.0 if late == 0 else float("inf")
    return late / early


def exclusion_reason(payload: dict[str, Any], include_mock: bool = False) -> str | None:
    """Return why a run must be excluded from aggregation, or None to keep it."""
    if payload.get("status") != "completed":
        return "failed"
    if not include_mock and (_model_id(payload) in MOCK_MODELS or payload.get("backend") == "mock"):
        return "mock"
    if payload.get("passed") is None or not any(
        isinstance(v, (int, float)) for v in _extract_metrics(payload).values()
    ):
        return "no_evaluation"
    return None


def _mean_sd(values: list[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    mean = sum(values) / len(values)
    if len(values) < 2:
        return mean, None
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return mean, math.sqrt(variance)


def _instruction_adherence(run_dir: Path, intent: dict[str, Any] | None) -> dict[str, Any] | None:
    """Score instruction adherence from the transcript, using the intent's per-turn specs."""
    path = run_dir / "transcript.json"
    if intent is None or not path.exists():
        return None
    transcript = _load_json(path)
    return evaluate_transcript_adherence(transcript if isinstance(transcript, list) else [], build_turn_specs(intent))


def summarize(artifacts_dir: Path, include_mock: bool = False) -> tuple[list[dict[str, Any]], Counter]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    excluded: Counter = Counter()
    intents = {intent.get("id"): intent for intent in load_intents().get("intents", [])}

    for run_dir in sorted(artifacts_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        metrics_path = run_dir / "aggregate_metrics.json"
        if not metrics_path.exists():
            continue
        payload = _load_json(metrics_path)

        reason = exclusion_reason(payload, include_mock=include_mock)
        if not reason and not include_mock and run_dir_mock_reasons(run_dir):
            reason = "mock_content"
        if reason:
            excluded[reason] += 1
            continue

        model = _model_id(payload) or "mock-echo"
        condition = payload.get("condition", "unknown")
        row = rows.setdefault(
            (model, condition),
            {
                "model": model,
                "condition": condition,
                "n": 0,
                "passed": 0,
                **{key: [] for key in METRIC_KEYS},
                "instruction_checked_turns": 0,
                "instruction_passed_turns": 0,
                "unsupported_claim_flagged": 0,
                "unsupported_claim_total": 0,
                "refusal_keyword_flagged": 0,
                "refusal_keyword_total": 0,
            },
        )
        row["n"] += 1
        if payload.get("passed") is True:
            row["passed"] += 1

        extracted = _extract_metrics(payload)
        for key in ("mean_tokens_per_turn", "drift_slope", "length_stddev"):
            value = extracted.get(key)
            if isinstance(value, (int, float)):
                row[key].append(float(value))

        turn_metrics_path = run_dir / "turn_metrics.json"
        if turn_metrics_path.exists():
            turn_metrics = load_turn_metrics(turn_metrics_path)
            row["growth_ratio"].append(compute_growth_ratio_from_turn_metrics(turn_metrics, n=3))

        adherence = _instruction_adherence(run_dir, intents.get(payload.get("intent_id")))
        if adherence:
            row["instruction_checked_turns"] += adherence["checked_turns"]
            row["instruction_passed_turns"] += adherence["passed_turns"]

        for result in _load_evaluator_results(run_dir):
            name = result.get("evaluator_name")
            passed = result.get("passed")
            # Older artifacts used "hallucination_proxy" and "refusal_proxy".
            if name in ("unsupported_claim_proxy", "hallucination_proxy"):
                row["unsupported_claim_total"] += 1
                if not passed:
                    row["unsupported_claim_flagged"] += 1
            elif name in ("refusal_keyword_proxy", "refusal_proxy"):
                row["refusal_keyword_total"] += 1
                if not passed:
                    row["refusal_keyword_flagged"] += 1

    output = []
    for row in rows.values():
        out: dict[str, Any] = {
            "model": row["model"],
            "condition": row["condition"],
            "n": row["n"],
            "passed": row["passed"],
            "pass_rate": row["passed"] / row["n"],
        }
        for key in METRIC_KEYS:
            mean, sd = _mean_sd(row[key])
            out[key] = mean
            out[f"{key}_sd"] = sd
        out["instruction_checked_turns"] = row["instruction_checked_turns"]
        out["instruction_turn_pass_rate"] = (
            row["instruction_passed_turns"] / row["instruction_checked_turns"]
            if row["instruction_checked_turns"] else None
        )
        out["unsupported_claim_proxy_rate"] = (
            row["unsupported_claim_flagged"] / row["unsupported_claim_total"]
            if row["unsupported_claim_total"] else None
        )
        out["refusal_keyword_proxy_rate"] = (
            row["refusal_keyword_flagged"] / row["refusal_keyword_total"]
            if row["refusal_keyword_total"] else None
        )
        output.append(out)

    output.sort(key=lambda item: (item["model"], item["condition"]))
    return output, excluded


CSV_HEADER = [
    "model",
    "condition",
    "n",
    "passed",
    "pass_rate",
    "mean_tokens",
    "mean_tokens_sd",
    "drift_slope",
    "drift_slope_sd",
    "length_stddev",
    "length_stddev_sd",
    "growth_ratio",
    "growth_ratio_sd",
    "instruction_checked_turns",
    "instruction_turn_pass_rate",
    "unsupported_claim_proxy_rate",
    "refusal_keyword_proxy_rate",
]


def _row_cells(row: dict[str, Any]) -> list[str]:
    return [
        row["model"],
        row["condition"],
        str(row["n"]),
        str(row["passed"]),
        _format_float(row["pass_rate"]),
        _format_float(row["mean_tokens_per_turn"]),
        _format_float(row["mean_tokens_per_turn_sd"]),
        _format_float(row["drift_slope"]),
        _format_float(row["drift_slope_sd"]),
        _format_float(row["length_stddev"]),
        _format_float(row["length_stddev_sd"]),
        _format_float(row["growth_ratio"]),
        _format_float(row["growth_ratio_sd"]),
        str(row["instruction_checked_turns"]),
        _format_float(row["instruction_turn_pass_rate"]),
        _format_float(row["unsupported_claim_proxy_rate"]),
        _format_float(row["refusal_keyword_proxy_rate"]),
    ]


def _format_excluded(excluded: Counter) -> str:
    if not excluded:
        return "excluded: none"
    parts = [f"{count} {reason}" for reason, count in sorted(excluded.items(), key=lambda kv: (-kv[1], kv[0]))]
    return "excluded: " + ", ".join(parts)


def _delta(row: dict[str, Any], baseline: dict[str, Any], key: str) -> float | None:
    if row[key] is None or baseline[key] is None:
        return None
    return row[key] - baseline[key]


def compute_deltas(rows: list[dict[str, Any]], baseline_condition: str) -> list[dict[str, Any]]:
    """Deltas against the baseline condition, computed within each model only."""
    deltas = []
    for baseline in (r for r in rows if r["condition"] == baseline_condition):
        for row in rows:
            if row["model"] != baseline["model"] or row["condition"] == baseline_condition:
                continue
            deltas.append({
                "model": row["model"],
                "baseline": baseline_condition,
                "candidate": row["condition"],
                "n_baseline": baseline["n"],
                "n_candidate": row["n"],
                "deltas": {
                    "mean_tokens_delta": _delta(row, baseline, "mean_tokens_per_turn"),
                    "drift_slope_delta": _delta(row, baseline, "drift_slope"),
                    "pass_rate_delta": _delta(row, baseline, "pass_rate"),
                    "growth_ratio_delta": _delta(row, baseline, "growth_ratio"),
                },
            })
    return deltas


def _render_html(rows: list[dict[str, Any]], excluded: Counter) -> str:
    html_rows = [
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in _row_cells(row)) + "</tr>"
        for row in rows
    ]
    return "\n".join([
        "<!doctype html>",
        "<html>",
        "<head>",
        "<meta charset='utf-8'/>",
        "<title>Verbatim Summary</title>",
        "<style>",
        "body { font-family: Arial, sans-serif; padding: 16px; }",
        "table { border-collapse: collapse; width: 100%; }",
        "th, td { border: 1px solid #ccc; padding: 6px 8px; text-align: left; }",
        "th { background: #f3f3f3; }",
        "</style>",
        "</head>",
        "<body>",
        "<h1>Verbatim Summary</h1>",
        f"<p>{_format_excluded(excluded)}</p>",
        "<table>",
        "<thead>",
        "<tr>" + "".join(f"<th>{name}</th>" for name in CSV_HEADER) + "</tr>",
        "</thead>",
        "<tbody>",
        *html_rows,
        "</tbody>",
        "</table>",
        "</body>",
        "</html>",
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize Verbatim artifacts by model and condition.")
    parser.add_argument("--artifacts-dir", default="artifacts", help="Directory containing run artifacts")
    parser.add_argument("--include-mock", action="store_true", help="Include mock-backend runs (model null or mock-echo)")
    parser.add_argument("--output", default="", help="Optional output JSON path")
    parser.add_argument("--output-csv", default="", help="Optional output CSV path")
    parser.add_argument("--output-html", default="", help="Optional output HTML path")
    parser.add_argument("--compare-baseline", default="", help="Baseline condition for delta comparison")
    parser.add_argument("--output-compare", default="", help="Optional output JSON for deltas")
    args = parser.parse_args()

    rows, excluded = summarize(Path(args.artifacts_dir), include_mock=args.include_mock)

    print(_format_excluded(excluded))
    print("\t".join(CSV_HEADER))
    for row in rows:
        print("\t".join(_row_cells(row)))

    if args.output:
        Path(args.output).write_text(
            json.dumps({"excluded": dict(excluded), "rows": rows}, indent=2), encoding="utf-8"
        )

    if args.output_csv:
        lines = [",".join(CSV_HEADER)] + [",".join(_row_cells(row)) for row in rows]
        Path(args.output_csv).write_text("\n".join(lines) + "\n", encoding="utf-8")

    if args.output_html:
        Path(args.output_html).write_text(_render_html(rows, excluded), encoding="utf-8")

    if args.compare_baseline:
        deltas = compute_deltas(rows, args.compare_baseline)
        if args.output_compare:
            Path(args.output_compare).write_text(json.dumps(deltas, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
