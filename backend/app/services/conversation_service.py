from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import ConversationRun, ConversationTurn, ConversationEvaluatorResult, RunStatus
from verbatim.evaluators.verbosity import TurnMetrics, compute_verbosity_metrics
from verbatim.evaluators.instruction_adherence import evaluate_instruction_adherence
from verbatim.evaluators.hallucination_proxy import evaluate_hallucination_proxy
from verbatim.evaluators.refusal import evaluate_refusal
from verbatim.experiments.run_conversations import (
    DEFAULT_THRESHOLDS,
    build_turns,
    load_intents,
    load_prompt_template,
)


def _select_intent(intent_name: str) -> dict[str, Any]:
    intents = load_intents().get("intents", [])
    for intent in intents:
        if intent.get("id") == intent_name:
            return intent
    raise ValueError(f"Intent not found: {intent_name}")


def _generate_response(
    system_prompt: str,
    user_text: str,
    condition: str,
    token_budget: int | None,
) -> tuple[str, bool]:
    base = f"{system_prompt}\n{user_text}".strip()
    words = base.split()
    if token_budget is None:
        return base, False

    if len(words) <= token_budget:
        return base, False

    if condition == "budgeted":
        return "Clarify: which detail is most important?", True

    truncated = " ".join(words[:token_budget])
    return truncated, True


def _token_count(text: str | None) -> int:
    if not text:
        return 0
    return len(text.split())


def run_conversation(
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
) -> ConversationRun:
    intent = _select_intent(intent_name) if intent_name else {}
    system_prompt = system_prompt_override or load_prompt_template(condition, token_budget=budget)
    if turns_override is not None:
        turns = turns_override[:max_turns]
    else:
        turns = build_turns(intent)[:max_turns]

    run = ConversationRun(
        condition=condition,
        model=model_id,
        status=RunStatus.PENDING,
        intent_id=intent_id_override or intent_name,
        system_prompt=system_prompt,
        parameters={
            "temperature": temperature,
            "token_budget": budget,
            "max_turns": max_turns,
        },
        turn_count=len(turns),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    run.status = RunStatus.RUNNING
    db.commit()

    output_metrics: list[TurnMetrics] = []
    total_cost = 0.0
    total_latency = 0
    fallback_count = 0
    instruction_results = []
    hallucination_results = []
    refusal_results = []
    instruction_spec = intent.get("instruction_spec") if isinstance(intent, dict) else None
    context = intent.get("context") if isinstance(intent, dict) else None

    for index, user_text in enumerate(turns):
        assistant_text, fallback_used = _generate_response(system_prompt, user_text, condition, budget)
        input_tokens = _token_count(user_text)
        output_tokens = _token_count(assistant_text)
        latency_ms = 0
        cost_usd = 0.0

        turn = ConversationTurn(
            run_id=run.id,
            turn_index=index,
            user_text=user_text,
            assistant_text=assistant_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            fallback_used=fallback_used,
        )
        db.add(turn)
        if fallback_used:
            fallback_count += 1
        output_metrics.append(TurnMetrics(turn_index=index, output_tokens=output_tokens))
        total_cost += cost_usd
        total_latency += latency_ms

        instruction_results.append(evaluate_instruction_adherence(assistant_text, instruction_spec))
        hallucination_results.append(evaluate_hallucination_proxy(assistant_text, context))
        refusal_results.append(evaluate_refusal(assistant_text))

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
            "thresholds": DEFAULT_THRESHOLDS,
            "checks": checks,
        },
        reasoning="All verbosity thresholds satisfied" if passed else "One or more verbosity thresholds failed",
    )
    db.add(eval_result)

    instruction_pass = all(result["passed"] for result in instruction_results) if instruction_results else True
    db.add(ConversationEvaluatorResult(
        run_id=run.id,
        evaluator_name="instruction_adherence",
        passed=instruction_pass,
        score=1.0 if instruction_pass else 0.0,
        details={
            "per_turn": [result["details"] for result in instruction_results],
        },
        reasoning="All turns passed instruction adherence" if instruction_pass else "Instruction adherence failures",
    ))

    hallucination_pass = all(result["passed"] for result in hallucination_results) if hallucination_results else True
    db.add(ConversationEvaluatorResult(
        run_id=run.id,
        evaluator_name="hallucination_proxy",
        passed=hallucination_pass,
        score=1.0 if hallucination_pass else 0.0,
        details={
            "per_turn": [result["details"] for result in hallucination_results],
        },
        reasoning="No hallucination flags" if hallucination_pass else "Hallucination flags detected",
    ))

    refusal_detected = any(result["refusal_detected"] for result in refusal_results) if refusal_results else False
    db.add(ConversationEvaluatorResult(
        run_id=run.id,
        evaluator_name="refusal_proxy",
        passed=not refusal_detected,
        score=0.0 if refusal_detected else 1.0,
        details={
            "per_turn": [result["details"] for result in refusal_results],
        },
        reasoning="No refusals detected" if not refusal_detected else "Refusal detected",
    ))

    run.status = RunStatus.COMPLETED
    run.total_cost_usd = total_cost
    run.total_duration_ms = total_latency
    run.completed_count = len(turns)
    run.timestamp = datetime.utcnow()
    db.commit()
    db.refresh(run)

    return run
