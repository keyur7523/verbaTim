"""Conversation runner for Verbatim experiments."""
from __future__ import annotations

import argparse
import json
import ssl
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error as url_error
from urllib import request as url_request
from urllib.parse import urljoin

import yaml

from verbatim.models import MODEL_CATALOG


INTENTS_PATH = Path(__file__).resolve().parents[1] / "datasets" / "intents.yaml"
PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts" / "conditions"
DEFAULT_THRESHOLDS = {
    "max_drift_slope": 3.0,
    "max_growth_ratio": 1.2,
    "max_stddev_ratio": 0.35,
    "max_fallback_rate": 0.15,
}
ARTIFACT_SCHEMA_VERSION = 2
MOCK_BACKEND = "mock"
MOCK_MODEL_ID = "mock-echo"
REQUIRED_RUN_FIELDS = (
    "run_id",
    "model",
    "backend",
    "length_unit",
    "intent_id",
    "condition",
    "temperature",
    "token_budget",
    "max_tokens",
    "timestamp",
    "status",
    "error",
)
ALLOWED_MODEL_IDS = {*MODEL_CATALOG, MOCK_MODEL_ID}


def load_intents(path: Path = INTENTS_PATH) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_prompt_template(condition: str, token_budget: int | None = None) -> str:
    prompt_path = PROMPTS_DIR / f"{condition}.md"
    text = prompt_path.read_text(encoding="utf-8")
    if token_budget is not None:
        text = text.replace("{{token_budget}}", str(token_budget))
    return text


def build_turns(intent: dict[str, Any]) -> list[str]:
    turns = [intent["initial_user_prompt"]]
    turns.extend(f if isinstance(f, str) else f["text"] for f in intent.get("followups", []))
    return turns


def build_turn_specs(intent: dict[str, Any]) -> list[dict[str, Any] | None]:
    """Instruction-adherence spec per turn, aligned with build_turns (None = no check)."""
    specs: list[dict[str, Any] | None] = [None]
    specs.extend(None if isinstance(f, str) else f.get("spec") for f in intent.get("followups", []))
    return specs


def _http_json(
    method: str,
    url: str,
    payload: dict | None = None,
    timeout: int = 30,
    ssl_context: ssl.SSLContext | None = None,
    retries: int = 0,
    retry_delay_s: float = 1.0,
) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    req = url_request.Request(url, data=data, headers=headers, method=method)
    attempt = 0
    while True:
        try:
            with url_request.urlopen(req, timeout=timeout, context=ssl_context) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except url_error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            raise RuntimeError(f"HTTP {exc.code} for {url}: {body}") from exc
        except (url_error.URLError, TimeoutError) as exc:
            if attempt >= retries:
                raise
            attempt += 1
            time.sleep(retry_delay_s * attempt)


def start_conversation_run(
    base_url: str,
    condition: str,
    model_id: str,
    temperature: float,
    max_tokens: int,
    turns: list[str],
    system_prompt: str,
    intent_id: str | None,
    parameters: dict[str, Any],
    ssl_context: ssl.SSLContext | None,
    request_timeout_s: int,
    request_retries: int,
) -> str:
    payload = {
        "condition": condition,
        "model": {
            "model_id": model_id,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        "turns": turns,
        "system_prompt": system_prompt,
        "intent_id": intent_id,
        "parameters": parameters,
    }
    url = urljoin(base_url, "/api/conversations/run")
    response = _http_json(
        "POST",
        url,
        payload=payload,
        timeout=request_timeout_s,
        ssl_context=ssl_context,
        retries=request_retries,
    )
    return response["run_id"]


def fetch_conversation_run(
    base_url: str,
    run_id: str,
    ssl_context: ssl.SSLContext | None,
    request_timeout_s: int,
    request_retries: int,
) -> dict:
    url = urljoin(base_url, f"/api/conversations/{run_id}")
    return _http_json(
        "GET",
        url,
        timeout=request_timeout_s,
        ssl_context=ssl_context,
        retries=request_retries,
    )


def poll_run(
    base_url: str,
    run_id: str,
    timeout_s: int,
    poll_interval_s: float,
    ssl_context: ssl.SSLContext | None,
    request_timeout_s: int,
    request_retries: int,
) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        run = fetch_conversation_run(
            base_url,
            run_id,
            ssl_context,
            request_timeout_s,
            request_retries,
        )
        status = run.get("status")
        if status in ("completed", "failed"):
            return run
        time.sleep(poll_interval_s)
    raise TimeoutError(f"Run {run_id} did not complete within {timeout_s}s")


class MockRunError(RuntimeError):
    pass


def _response_model_id(run: dict) -> str | None:
    model = run.get("model_id") or run.get("model")
    if isinstance(model, dict):
        model = model.get("model_id")
    return model or None


def build_run_metadata(run: dict, requested: dict[str, Any]) -> dict[str, Any]:
    """Merge what the runner requested with what the server reports.

    The server's backend and model win when present: a mock backend reports
    backend "mock" and model "mock-echo" regardless of the requested model.
    Both response shapes are accepted (local backend: run_id/model_id/created_at;
    ProbeKit API: id/model/timestamp).
    """
    run_parameters = run.get("parameters") or {}
    backend = run.get("backend") or run_parameters.get("backend") or requested["backend"]
    return {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "run_id": str(run.get("run_id") or run.get("id") or requested["run_id"]),
        "model": _response_model_id(run) or requested["model"],
        "backend": backend,
        "length_unit": _length_unit(run, backend),
        "intent_id": run.get("intent_id") or requested["intent_id"],
        "condition": run.get("condition") or requested["condition"],
        "temperature": requested["temperature"],
        "token_budget": requested["token_budget"],
        "max_tokens": requested["max_tokens"],
        "timestamp": run.get("timestamp") or run.get("created_at") or requested["timestamp"],
        "status": run.get("status"),
        "error": run.get("error") or run.get("error_message"),
    }


def _length_unit(run: dict, backend: str) -> str:
    """Unit of the per-turn input_tokens/output_tokens counts.

    The mock backend counts words and says so. A real model API reports the
    provider's token counts.
    """
    reported = run.get("length_unit") or (run.get("parameters") or {}).get("length_unit")
    if reported:
        return reported
    return "words" if backend == MOCK_BACKEND else "provider_tokens"


def is_mock_run(metadata: dict[str, Any]) -> bool:
    return metadata.get("backend") == MOCK_BACKEND or metadata.get("model") == MOCK_MODEL_ID


def write_artifacts(run: dict, output_dir: Path, metadata: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    turns = sorted(run.get("turns", []), key=lambda item: item.get("turn_index", 0))
    evaluator_results = run.get("evaluator_results", [])

    transcript = [
        {
            "turn_index": t.get("turn_index"),
            "user_text": t.get("user_text"),
            "assistant_text": t.get("assistant_text"),
        }
        for t in turns
    ]
    turn_metrics = [
        {
            "turn_index": t.get("turn_index"),
            "input_tokens": t.get("input_tokens"),
            "output_tokens": t.get("output_tokens"),
            "latency_ms": t.get("latency_ms"),
            "cost_usd": t.get("cost_usd"),
            "fallback_used": t.get("fallback_used"),
        }
        for t in turns
    ]

    verbosity_eval = next(
        (res for res in evaluator_results if res.get("evaluator_name") == "verbosity_stability"),
        None,
    )

    aggregate_metrics = {
        **metadata,
        "metrics": verbosity_eval.get("details") if verbosity_eval else {},
        "passed": verbosity_eval.get("passed") if verbosity_eval else None,
        "parameters": run.get("parameters"),
    }

    (output_dir / "transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
    (output_dir / "turn_metrics.json").write_text(json.dumps(turn_metrics, indent=2), encoding="utf-8")
    (output_dir / "evaluator_results.json").write_text(json.dumps(evaluator_results, indent=2), encoding="utf-8")
    (output_dir / "aggregate_metrics.json").write_text(json.dumps(aggregate_metrics, indent=2), encoding="utf-8")


def build_run_plan(
    intents: list[dict[str, Any]],
    conditions: list[str],
    budgets: list[int],
    temperatures: list[float | None],
    repeats: int,
) -> list[dict[str, Any]]:
    """Every (intent, condition, budget, temperature) combination, once per repeat.

    The repeat is the outer loop, so each pass covers every combination before
    the next starts: if the run stops early or the API drifts over time, the
    conditions stay balanced.
    """
    plan = []
    for repeat in range(1, repeats + 1):
        for intent in intents:
            for condition in conditions:
                for budget in (budgets if condition == "budgeted" else [None]):
                    for temperature in temperatures:
                        plan.append({
                            "repeat": repeat,
                            "intent": intent,
                            "condition": condition,
                            "budget": budget,
                            "temperature": temperature,
                        })
    return plan


def run_cost_usd(run: dict) -> float:
    return sum(t.get("cost_usd") or 0.0 for t in run.get("turns", []))


def parse_temperatures(value: str) -> list[float | None]:
    if value.strip().lower() in ("", "none"):
        return [None]
    return [float(val) for val in value.split(",") if val.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Verbatim multi-turn experiments.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Probekit API base URL")
    parser.add_argument("--model-id", default="claude-sonnet-4-20250514", help="Model identifier")
    parser.add_argument(
        "--temperatures",
        default="0.2,0.5",
        help="Comma-separated temperatures, or 'none' to send no temperature (required for models that reject it)",
    )
    parser.add_argument("--budgets", default="80,120,160", help="Comma-separated token budgets")
    parser.add_argument("--conditions", default="baseline,naive,budgeted,verbatim", help="Comma-separated conditions")
    parser.add_argument("--intents", default="", help="Comma-separated intent ids (default: all)")
    parser.add_argument("--max-tokens", type=int, default=4096, help="Max tokens per response")
    parser.add_argument("--output-dir", default="artifacts", help="Directory for run artifacts")
    parser.add_argument("--timeout-s", type=int, default=600, help="Timeout per run")
    parser.add_argument("--poll-interval-s", type=float, default=2.0, help="Polling interval")
    parser.add_argument("--request-timeout-s", type=int, default=60, help="HTTP request timeout")
    parser.add_argument("--request-retries", type=int, default=2, help="HTTP request retries")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification")
    parser.add_argument("--ca-bundle", default="", help="Path to custom CA bundle for TLS verification")
    parser.add_argument(
        "--backend",
        default="probekit-api",
        help="Backend label recorded when the server does not report one",
    )
    parser.add_argument("--repeats", type=int, default=1, help="Runs per combination")
    parser.add_argument(
        "--max-cost-usd",
        type=float,
        default=None,
        help="Stop before starting a run once total spend reaches this amount",
    )
    parser.add_argument(
        "--allow-mock",
        action="store_true",
        help="Write artifacts for mock-backend runs instead of failing",
    )
    args = parser.parse_args()

    if args.model_id not in ALLOWED_MODEL_IDS:
        allowed = ", ".join(sorted(ALLOWED_MODEL_IDS))
        raise ValueError(f"Model id '{args.model_id}' is not allowed. Allowed: {allowed}")

    if args.insecure:
        ssl_context = ssl._create_unverified_context()
    elif args.ca_bundle:
        ssl_context = ssl.create_default_context(cafile=args.ca_bundle)
    else:
        ssl_context = ssl.create_default_context()

    intents_data = load_intents()
    intents = intents_data.get("intents", [])

    selected_intents = {i.strip() for i in args.intents.split(",") if i.strip()}
    if selected_intents:
        intents = [i for i in intents if i.get("id") in selected_intents]

    temperatures = parse_temperatures(args.temperatures)
    budgets = [int(val) for val in args.budgets.split(",") if val.strip()]
    conditions = [val.strip() for val in args.conditions.split(",") if val.strip()]

    output_root = Path(args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    plan = build_run_plan(intents, conditions, budgets, temperatures, args.repeats)
    total_cost = 0.0
    for position, item in enumerate(plan, start=1):
        if args.max_cost_usd is not None and total_cost >= args.max_cost_usd:
            print(f"Stopping: spent ${total_cost:.4f}, cap is ${args.max_cost_usd:.2f}. "
                  f"{len(plan) - position + 1} of {len(plan)} runs not started.", flush=True)
            return 1
        intent, condition, budget, temperature = item["intent"], item["condition"], item["budget"], item["temperature"]
        intent_id = intent.get("id")
        system_prompt = load_prompt_template(condition, token_budget=budget)
        parameters = {
            "temperature": temperature,
            "max_tokens": args.max_tokens,
            "token_budget": budget,
            "thresholds": DEFAULT_THRESHOLDS,
            "created_at": datetime.utcnow().isoformat() + "Z",
        }

        run_id = start_conversation_run(
            base_url=args.base_url,
            condition=condition,
            model_id=args.model_id,
            temperature=temperature,
            max_tokens=args.max_tokens,
            turns=build_turns(intent),
            system_prompt=system_prompt,
            intent_id=intent_id,
            parameters=parameters,
            ssl_context=ssl_context,
            request_timeout_s=args.request_timeout_s,
            request_retries=args.request_retries,
        )

        run = poll_run(
            base_url=args.base_url,
            run_id=run_id,
            timeout_s=args.timeout_s,
            poll_interval_s=args.poll_interval_s,
            ssl_context=ssl_context,
            request_timeout_s=args.request_timeout_s,
            request_retries=args.request_retries,
        )

        metadata = build_run_metadata(run, {
            "run_id": run_id,
            "model": args.model_id,
            "backend": args.backend,
            "intent_id": intent_id,
            "condition": condition,
            "temperature": temperature,
            "token_budget": budget,
            "max_tokens": args.max_tokens,
            "timestamp": parameters["created_at"],
        })
        if is_mock_run(metadata) and not args.allow_mock:
            raise MockRunError(
                f"Run {run_id} came from a mock backend (model '{metadata['model']}'). "
                "Point --base-url at a real model API, or pass --allow-mock to keep mock runs."
            )

        artifact_dir = output_root / str(run_id)
        write_artifacts(run, artifact_dir, metadata)
        total_cost += run_cost_usd(run)
        print(
            f"[{position}/{len(plan)}] repeat {item['repeat']} {intent_id} {condition} -> {metadata['status']} "
            f"(total ${total_cost:.4f}) {artifact_dir}",
            flush=True,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
