from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.models import ConversationRun, ConversationTurn, ConversationEvaluatorResult, RunStatus
from app.services.generators import MOCK_BACKEND, MOCK_MODEL_ID, AnthropicGenerator, MockGenerator
from verbatim.evaluators.verbosity import TurnMetrics, compute_verbosity_metrics
from verbatim.evaluators.instruction_adherence import evaluate_instruction_adherence
from verbatim.evaluators.refusal_keyword_proxy import evaluate_refusal_keyword_proxy
from verbatim.evaluators.unsupported_claim_proxy import evaluate_unsupported_claim_proxy
from verbatim.experiments.run_conversations import (
    DEFAULT_THRESHOLDS,
    build_turn_specs,
    build_turns,
    load_intents,
    load_prompt_template,
)
from verbatim.models import MODEL_CATALOG

# Runs on a model from verbatim.models.MODEL_CATALOG call the Anthropic API.
# Runs on "mock-echo" use the echo mock, which requires an explicit opt-in and
# is always stamped as mock.
MOCK_LENGTH_UNIT = "words"
ALLOW_MOCK_ENV = "VERBATIM_ALLOW_MOCK"
DEFAULT_MAX_TOKENS = 4096


class MockNotAllowedError(RuntimeError):
    pass


class RunConfigError(ValueError):
    """The request can't be run as asked (unknown model or intent, unsupported parameter)."""


def mock_allowed() -> bool:
    return os.getenv(ALLOW_MOCK_ENV) == "1"


def _select_intent(intent_name: str) -> dict[str, Any]:
    intents = load_intents().get("intents", [])
    for intent in intents:
        if intent.get("id") == intent_name:
            return intent
    raise RunConfigError(f"Intent not found: {intent_name}")


def _default_client_factory():
    import anthropic

    return anthropic.Anthropic()


def _make_generator(
    model_id: str,
    condition: str,
    budget: int | None,
    temperature: float | None,
    max_tokens: int,
    client_factory: Callable[[], Any] | None,
):
    if model_id == MOCK_MODEL_ID:
        if not mock_allowed():
            raise MockNotAllowedError(
                f"Model '{MOCK_MODEL_ID}' is the echo mock (no model is called). "
                f"Set {ALLOW_MOCK_ENV}=1 to run it anyway."
            )
        return MockGenerator(condition=condition, token_budget=budget)

    info = MODEL_CATALOG.get(model_id)
    if info is None:
        known = ", ".join(sorted([*MODEL_CATALOG, MOCK_MODEL_ID]))
        raise RunConfigError(f"Unknown model '{model_id}'. Known: {known}")
    if temperature is not None and not info.accepts_temperature:
        raise RunConfigError(
            f"Model '{model_id}' rejects the temperature parameter. "
            "Run it without a temperature, or pick a model that accepts one."
        )
    client = (client_factory or _default_client_factory)()
    return AnthropicGenerator(client=client, model_id=model_id, max_tokens=max_tokens, temperature=temperature)


@dataclass
class PreparedRun:
    run_id: Any
    generator: Any
    condition: str
    system_prompt: str
    turns: list[str]
    turn_specs: list[dict[str, Any] | None]
    context: str | None


def prepare_run(
    db: Session,
    model_id: str,
    condition: str,
    intent_name: str,
    temperature: float | None = None,
    budget: int | None = None,
    max_turns: int = 12,
    turns_override: list[str] | None = None,
    system_prompt_override: str | None = None,
    intent_id_override: str | None = None,
    max_tokens: int | None = None,
    client_factory: Callable[[], Any] | None = None,
) -> PreparedRun:
    """Validate the request and record a pending run. Raises before anything is stored."""
    max_tokens = max_tokens or DEFAULT_MAX_TOKENS
    generator = _make_generator(model_id, condition, budget, temperature, max_tokens, client_factory)
    intent = _select_intent(intent_name) if intent_name else {}
    system_prompt = system_prompt_override or load_prompt_template(condition, token_budget=budget)
    turns = (turns_override if turns_override is not None else build_turns(intent))[:max_turns]
    # Per-turn specs only apply when the turns come from the intent itself.
    turn_specs = build_turn_specs(intent) if intent and turns_override is None else []

    is_mock = generator.backend == MOCK_BACKEND
    run = ConversationRun(
        condition=condition,
        model=generator.model_id,
        status=RunStatus.PENDING,
        intent_id=intent_id_override or intent_name,
        system_prompt=system_prompt,
        parameters={
            "backend": generator.backend,
            "length_unit": MOCK_LENGTH_UNIT if is_mock else "provider_tokens",
            "requested_model_id": model_id,
            "temperature": temperature,
            "token_budget": budget,
            "max_tokens": max_tokens,
            "max_turns": max_turns,
        },
        turn_count=len(turns),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return PreparedRun(
        run_id=run.id,
        generator=generator,
        condition=condition,
        system_prompt=system_prompt,
        turns=turns,
        turn_specs=turn_specs,
        context=intent.get("context") if isinstance(intent, dict) else None,
    )


def run_conversation(db: Session, **kwargs) -> ConversationRun:
    """Prepare and execute a run in one call (used by tests and scripts)."""
    return execute_run(db, prepare_run(db, **kwargs))


def execute_run(db: Session, prepared: PreparedRun) -> ConversationRun:
    run = db.query(ConversationRun).filter(ConversationRun.id == prepared.run_id).one()
    run.status = RunStatus.RUNNING
    db.commit()
    try:
        return _execute(db, run, prepared)
    except Exception as exc:  # noqa: BLE001 - any failure must end the run as failed, not stuck running
        db.rollback()
        run = db.query(ConversationRun).filter(ConversationRun.id == prepared.run_id).one()
        run.status = RunStatus.FAILED
        run.error_message = f"{type(exc).__name__}: {exc}"
        run.timestamp = datetime.utcnow()
        db.commit()
        db.refresh(run)
        return run


def _execute(db: Session, run: ConversationRun, prepared: PreparedRun) -> ConversationRun:
    condition = prepared.condition
    turns = prepared.turns
    turn_specs = prepared.turn_specs
    context = prepared.context

    output_metrics: list[TurnMetrics] = []
    total_cost = 0.0
    total_latency = 0
    fallback_count = 0
    instruction_results = []
    unsupported_claim_results = []
    refusal_keyword_results = []
    stop_reasons: list[str | None] = []
    thinking_used = False
    history: list[dict[str, Any]] = []

    for index, user_text in enumerate(turns):
        result = prepared.generator.generate(prepared.system_prompt, history, user_text)
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": result.history_content})
        assistant_text = result.text

        db.add(ConversationTurn(
            run_id=run.id,
            turn_index=index,
            user_text=user_text,
            assistant_text=assistant_text,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            cost_usd=result.cost_usd,
            fallback_used=result.fallback_used,
        ))
        run.completed_count = index + 1
        db.commit()

        if result.fallback_used:
            fallback_count += 1
        stop_reasons.append(result.stop_reason)
        thinking_used = thinking_used or result.thinking_used
        output_metrics.append(TurnMetrics(turn_index=index, output_tokens=result.output_tokens))
        total_cost += result.cost_usd
        total_latency += result.latency_ms

        turn_spec = turn_specs[index] if index < len(turn_specs) else None
        if turn_spec:
            instruction_results.append(evaluate_instruction_adherence(assistant_text, turn_spec))
        unsupported_claim_results.append(evaluate_unsupported_claim_proxy(assistant_text, context))
        refusal_keyword_results.append(evaluate_refusal_keyword_proxy(assistant_text))

    if thinking_used:
        # Reasoning tokens are inside output_tokens; never pool these with visible-only counts.
        run.parameters = {**run.parameters, "length_unit": "provider_tokens_incl_thinking"}

    metrics = compute_verbosity_metrics(output_metrics)

    stddev_limit = DEFAULT_THRESHOLDS["max_stddev_ratio"] * metrics.mean_tokens_per_turn
    fallback_rate = (fallback_count / len(turns)) if turns else 0.0
    checks = {
        "drift_slope": metrics.drift_slope <= DEFAULT_THRESHOLDS["max_drift_slope"],
        "growth_ratio": metrics.growth_ratio <= DEFAULT_THRESHOLDS["max_growth_ratio"],
        "length_stddev": metrics.length_stddev <= stddev_limit,
        "fallback_rate": fallback_rate <= DEFAULT_THRESHOLDS["max_fallback_rate"],
    }
    passed = all(checks.values())
    score = sum(1 for value in checks.values() if value) / len(checks)

    eval_result = ConversationEvaluatorResult(
        run_id=run.id,
        evaluator_name="verbosity_stability",
        passed=passed,
        score=score,
        details={
            "metrics": {
                "mean_tokens_per_turn": metrics.mean_tokens_per_turn,
                "drift_slope": metrics.drift_slope,
                "length_stddev": metrics.length_stddev,
                "growth_ratio": metrics.growth_ratio,
            },
            "fallback_rate": fallback_rate,
            "turn_stop_reasons": stop_reasons,
            "truncated_turns": [i for i, reason in enumerate(stop_reasons) if reason == "max_tokens"],
            "thinking_used": thinking_used,
            "thresholds": DEFAULT_THRESHOLDS,
            "checks": checks,
        },
        reasoning="All verbosity thresholds satisfied" if passed else "One or more verbosity thresholds failed",
    )
    db.add(eval_result)

    # None (not checked) when no turn had a spec, so an unchecked run never counts as a pass.
    instruction_passed_turns = sum(1 for result in instruction_results if result["passed"])
    instruction_pass = (instruction_passed_turns == len(instruction_results)) if instruction_results else None
    db.add(ConversationEvaluatorResult(
        run_id=run.id,
        evaluator_name="instruction_adherence",
        passed=instruction_pass,
        score=(instruction_passed_turns / len(instruction_results)) if instruction_results else None,
        details={
            "checked_turns": len(instruction_results),
            "passed_turns": instruction_passed_turns,
            "per_turn": [result["details"] for result in instruction_results],
        },
        reasoning=(
            "No turn has an instruction spec" if instruction_pass is None
            else "All checked turns passed instruction adherence" if instruction_pass
            else "Instruction adherence failures"
        ),
    ))

    unsupported_claim_pass = (
        all(result["passed"] for result in unsupported_claim_results) if unsupported_claim_results else True
    )
    db.add(ConversationEvaluatorResult(
        run_id=run.id,
        evaluator_name="unsupported_claim_proxy",
        passed=unsupported_claim_pass,
        score=1.0 if unsupported_claim_pass else 0.0,
        details={
            "per_turn": [result["details"] for result in unsupported_claim_results],
        },
        reasoning="No unsupported-claim proxy flags" if unsupported_claim_pass else "Unsupported-claim proxy flags",
    ))

    refusal_keyword_flagged = (
        any(result["flagged"] for result in refusal_keyword_results) if refusal_keyword_results else False
    )
    db.add(ConversationEvaluatorResult(
        run_id=run.id,
        evaluator_name="refusal_keyword_proxy",
        passed=not refusal_keyword_flagged,
        score=0.0 if refusal_keyword_flagged else 1.0,
        details={
            "per_turn": [result["details"] for result in refusal_keyword_results],
        },
        reasoning="Refusal keywords matched" if refusal_keyword_flagged else "No refusal keywords matched",
    ))

    run.status = RunStatus.COMPLETED
    run.total_cost_usd = total_cost
    run.total_duration_ms = total_latency
    run.timestamp = datetime.utcnow()
    db.commit()
    db.refresh(run)

    return run
