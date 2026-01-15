"""Summarize Verbatim run metrics by condition."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def summarize(artifacts_dir: Path) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for run_dir in artifacts_dir.iterdir():
        if not run_dir.is_dir():
            continue
        metrics_path = run_dir / "aggregate_metrics.json"
        if not metrics_path.exists():
            continue
        payload = _load_json(metrics_path)
        condition = payload.get("condition", "unknown")
        row = rows.setdefault(
            condition,
            {
                "condition": condition,
                "count": 0,
                "passed": 0,
                "mean_tokens_per_turn": [],
                "drift_slope": [],
                "length_stddev": [],
                "instruction_passed": 0,
                "instruction_total": 0,
                "hallucination_passed": 0,
                "hallucination_total": 0,
                "refusal_detected": 0,
                "refusal_total": 0,
            },
        )
        row["count"] += 1
        if payload.get("passed") is True:
            row["passed"] += 1

        extracted = _extract_metrics(payload)
        for key in ("mean_tokens_per_turn", "drift_slope", "length_stddev"):
            value = extracted.get(key)
            if isinstance(value, (int, float)):
                row[key].append(float(value))

        for result in _load_evaluator_results(run_dir):
            name = result.get("evaluator_name")
            passed = result.get("passed")
            if name == "instruction_adherence":
                row["instruction_total"] += 1
                if passed:
                    row["instruction_passed"] += 1
            elif name == "hallucination_proxy":
                row["hallucination_total"] += 1
                if passed:
                    row["hallucination_passed"] += 1
            elif name == "refusal_proxy":
                row["refusal_total"] += 1
                if not passed:
                    row["refusal_detected"] += 1

    output = []
    for condition, row in rows.items():
        count = row["count"] or 1
        passed = row["passed"]
        instruction_rate = (row["instruction_passed"] / row["instruction_total"]) if row["instruction_total"] else None
        hallucination_pass_rate = (
            row["hallucination_passed"] / row["hallucination_total"]
        ) if row["hallucination_total"] else None
        refusal_rate = (row["refusal_detected"] / row["refusal_total"]) if row["refusal_total"] else None
        output.append(
            {
                "condition": condition,
                "runs": row["count"],
                "pass_rate": (passed / row["count"]) if row["count"] else 0.0,
                "mean_tokens_per_turn": sum(row["mean_tokens_per_turn"]) / len(row["mean_tokens_per_turn"])
                if row["mean_tokens_per_turn"] else None,
                "drift_slope": sum(row["drift_slope"]) / len(row["drift_slope"])
                if row["drift_slope"] else None,
                "length_stddev": sum(row["length_stddev"]) / len(row["length_stddev"])
                if row["length_stddev"] else None,
                "instruction_pass_rate": instruction_rate,
                "hallucination_flag_rate": (1.0 - hallucination_pass_rate) if hallucination_pass_rate is not None else None,
                "refusal_rate": refusal_rate,
            }
        )

    output.sort(key=lambda item: item["condition"])
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize Verbatim artifacts by condition.")
    parser.add_argument("--artifacts-dir", default="artifacts", help="Directory containing run artifacts")
    parser.add_argument("--output", default="", help="Optional output JSON path")
    parser.add_argument("--output-csv", default="", help="Optional output CSV path")
    parser.add_argument("--output-html", default="", help="Optional output HTML path")
    parser.add_argument("--compare-baseline", default="", help="Baseline condition for delta comparison")
    parser.add_argument("--output-compare", default="", help="Optional output JSON for deltas")
    args = parser.parse_args()

    artifacts_dir = Path(args.artifacts_dir)
    rows = summarize(artifacts_dir)

    header = [
        "condition",
        "runs",
        "pass_rate",
        "mean_tokens",
        "drift_slope",
        "length_stddev",
        "instruction_pass_rate",
        "hallucination_flag_rate",
        "refusal_rate",
    ]
    print("\t".join(header))
    for row in rows:
        print("\t".join([
            row["condition"],
            str(row["runs"]),
            _format_float(row["pass_rate"]),
            _format_float(row["mean_tokens_per_turn"]),
            _format_float(row["drift_slope"]),
            _format_float(row["length_stddev"]),
            _format_float(row["instruction_pass_rate"]),
            _format_float(row["hallucination_flag_rate"]),
            _format_float(row["refusal_rate"]),
        ]))

    if args.output:
        Path(args.output).write_text(json.dumps(rows, indent=2), encoding="utf-8")

    if args.output_csv:
        lines = [
            "condition,runs,pass_rate,mean_tokens,drift_slope,length_stddev,instruction_pass_rate,hallucination_flag_rate,refusal_rate"
        ]
        for row in rows:
            lines.append(",".join([
                row["condition"],
                str(row["runs"]),
                _format_float(row["pass_rate"]),
                _format_float(row["mean_tokens_per_turn"]),
                _format_float(row["drift_slope"]),
                _format_float(row["length_stddev"]),
                _format_float(row["instruction_pass_rate"]),
                _format_float(row["hallucination_flag_rate"]),
                _format_float(row["refusal_rate"]),
            ]))
        Path(args.output_csv).write_text("\n".join(lines) + "\n", encoding="utf-8")

    if args.output_html:
        def _num(value: float | None) -> float:
            return float(value) if isinstance(value, (int, float)) else 0.0

        max_mean = max((_num(row["mean_tokens_per_turn"]) for row in rows), default=1.0)
        max_stddev = max((_num(row["length_stddev"]) for row in rows), default=1.0)

        html_rows = []
        for row in rows:
            mean_val = _num(row["mean_tokens_per_turn"])
            stddev_val = _num(row["length_stddev"])
            mean_pct = (mean_val / max_mean * 100) if max_mean else 0.0
            stddev_pct = (stddev_val / max_stddev * 100) if max_stddev else 0.0
            html_rows.append(
                "<tr>"
                f"<td>{row['condition']}</td>"
                f"<td>{row['runs']}</td>"
                f"<td>{_format_float(row['pass_rate'])}</td>"
                f"<td>{_format_float(row['mean_tokens_per_turn'])}</td>"
                f"<td>{_format_float(row['drift_slope'])}</td>"
                f"<td>{_format_float(row['length_stddev'])}</td>"
                f"<td>{_format_float(row['instruction_pass_rate'])}</td>"
                f"<td>{_format_float(row['hallucination_flag_rate'])}</td>"
                f"<td>{_format_float(row['refusal_rate'])}</td>"
                f"<td><div class='bar' style='width:{mean_pct:.1f}%;'></div></td>"
                f"<td><div class='bar bar-alt' style='width:{stddev_pct:.1f}%;'></div></td>"
                "</tr>"
            )

        html = "\n".join([
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
            ".bar { height: 10px; background: #2a7f62; }",
            ".bar-alt { background: #2a4f7f; }",
            "</style>",
            "</head>",
            "<body>",
            "<h1>Verbatim Summary</h1>",
            "<table>",
            "<thead>",
            "<tr>",
            "<th>condition</th>",
            "<th>runs</th>",
            "<th>pass_rate</th>",
            "<th>mean_tokens</th>",
            "<th>drift_slope</th>",
            "<th>length_stddev</th>",
            "<th>instruction_pass_rate</th>",
            "<th>hallucination_flag_rate</th>",
            "<th>refusal_rate</th>",
            "<th>mean_tokens_bar</th>",
            "<th>stddev_bar</th>",
            "</tr>",
            "</thead>",
            "<tbody>",
            *html_rows,
            "</tbody>",
            "</table>",
            "</body>",
            "</html>",
        ])
        Path(args.output_html).write_text(html, encoding="utf-8")

    if args.compare_baseline:
        baseline = next((row for row in rows if row["condition"] == args.compare_baseline), None)
        if baseline:
            deltas = []
            for row in rows:
                if row["condition"] == args.compare_baseline:
                    continue
                deltas.append({
                    "baseline": args.compare_baseline,
                    "candidate": row["condition"],
                    "deltas": {
                        "mean_tokens_delta": (
                            row["mean_tokens_per_turn"] - baseline["mean_tokens_per_turn"]
                            if row["mean_tokens_per_turn"] is not None and baseline["mean_tokens_per_turn"] is not None
                            else None
                        ),
                        "drift_slope_delta": (
                            row["drift_slope"] - baseline["drift_slope"]
                            if row["drift_slope"] is not None and baseline["drift_slope"] is not None
                            else None
                        ),
                        "pass_rate_delta": (
                            row["pass_rate"] - baseline["pass_rate"]
                            if row["pass_rate"] is not None and baseline["pass_rate"] is not None
                            else None
                        ),
                        "instruction_pass_rate_delta": (
                            row["instruction_pass_rate"] - baseline["instruction_pass_rate"]
                            if row["instruction_pass_rate"] is not None and baseline["instruction_pass_rate"] is not None
                            else None
                        ),
                        "hallucination_flag_rate_delta": (
                            row["hallucination_flag_rate"] - baseline["hallucination_flag_rate"]
                            if row["hallucination_flag_rate"] is not None and baseline["hallucination_flag_rate"] is not None
                            else None
                        ),
                        "refusal_rate_delta": (
                            row["refusal_rate"] - baseline["refusal_rate"]
                            if row["refusal_rate"] is not None and baseline["refusal_rate"] is not None
                            else None
                        ),
                    },
                })
            if args.output_compare:
                Path(args.output_compare).write_text(json.dumps(deltas, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
