import json
import uuid

from sqlalchemy.orm import Session
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.database import get_db, get_session_factory
from app.models import ConversationRun, ConversationTurn, ConversationEvaluatorResult, RunStatus
from app.schemas.conversation import (
    ConversationRunRequest,
    ConversationRunResponse,
    ConversationDetailResponse,
    ConversationTurnResponse,
    MetricsResponse,
    CompareResponse,
    EvaluatorResultResponse,
)
from app.services.conversation_service import (
    MockNotAllowedError,
    PreparedRun,
    RunConfigError,
    execute_run,
    prepare_run,
)

router = APIRouter()


def get_client_factory():
    """Anthropic client factory; None means the default client. Tests override this."""
    return None


def _execute_in_background(session_factory, prepared: PreparedRun) -> None:
    db = session_factory()
    try:
        execute_run(db, prepared)
    finally:
        db.close()


def _resolve_condition(request: ConversationRunRequest) -> str:
    if request.condition:
        return request.condition
    if request.conditions:
        if len(request.conditions) == 1:
            return request.conditions[0]
        raise HTTPException(status_code=400, detail="Only one condition is supported per request")
    raise HTTPException(status_code=400, detail="Condition is required")


def _coerce_details(details):
    if details is None:
        return {}
    if isinstance(details, dict):
        return details
    if isinstance(details, str):
        try:
            return json.loads(details)
        except json.JSONDecodeError:
            return {}
    return {}


@router.post("/conversations/run", response_model=ConversationRunResponse)
def start_run(
    request: ConversationRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    session_factory=Depends(get_session_factory),
    client_factory=Depends(get_client_factory),
):
    condition = _resolve_condition(request)
    temperatures = request.temperatures or []
    budgets = request.budgets or []
    parameters = request.parameters or {}
    if not temperatures and "temperature" in parameters:
        temperatures = [parameters.get("temperature")]
    if not temperatures and isinstance(request.model, dict) and "temperature" in request.model:
        temperatures = [request.model.get("temperature")]
    if not budgets and "token_budget" in parameters:
        budgets = [parameters.get("token_budget")]
    if not temperatures:
        temperatures = [None]
    if not budgets:
        budgets = [None]

    model_id = request.model_id
    max_tokens = parameters.get("max_tokens")
    if request.model and isinstance(request.model, dict):
        model_id = model_id or request.model.get("model_id")
        max_tokens = request.model.get("max_tokens", max_tokens)
    if not model_id:
        raise HTTPException(status_code=422, detail="model_id is required")

    intent_name = request.intent_name or request.intent_id
    turns_override = request.turns
    system_prompt_override = request.system_prompt

    if turns_override is not None:
        if len(turns_override) != 12:
            raise HTTPException(status_code=400, detail="Conversation must contain exactly 12 turns")
    elif request.max_turns != 12:
        raise HTTPException(status_code=400, detail="Conversation must contain exactly 12 turns")
    if not intent_name and turns_override is None:
        raise HTTPException(status_code=422, detail="intent_name is required when turns are not provided")

    try:
        prepared = prepare_run(
            db=db,
            model_id=model_id,
            condition=condition,
            intent_name=intent_name or "",
            temperature=temperatures[0],
            budget=budgets[0],
            max_turns=request.max_turns,
            turns_override=turns_override,
            system_prompt_override=system_prompt_override,
            intent_id_override=request.intent_id or intent_name,
            max_tokens=max_tokens,
            client_factory=client_factory,
        )
    except MockNotAllowedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RunConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # A real 12-turn run takes minutes; the runner polls GET /conversations/{run_id}.
    background_tasks.add_task(_execute_in_background, session_factory, prepared)
    return ConversationRunResponse(run_id=str(prepared.run_id), status="pending")


@router.get("/conversations/metrics", response_model=list[MetricsResponse])
def metrics(db: Session = Depends(get_db)):
    runs = db.query(ConversationRun).all()
    response = []
    conditions = {run.condition for run in runs}

    for condition in conditions:
        condition_runs = [run for run in runs if run.condition == condition]
        evaluator_results = (
            db.query(ConversationEvaluatorResult)
            .filter(ConversationEvaluatorResult.run_id.in_([run.id for run in condition_runs]))
            .all()
        )

        slopes = []
        means = []
        stddevs = []
        passed = 0
        total = 0

        for evaluator in evaluator_results:
            details = _coerce_details(evaluator.details)
            metrics_data = details.get("metrics") or {}
            if "drift_slope" in metrics_data:
                value = metrics_data.get("drift_slope")
                if isinstance(value, (int, float)):
                    slopes.append(value)
            if "mean_tokens_per_turn" in metrics_data:
                value = metrics_data.get("mean_tokens_per_turn")
                if isinstance(value, (int, float)):
                    means.append(value)
            if "length_stddev" in metrics_data:
                value = metrics_data.get("length_stddev")
                if isinstance(value, (int, float)):
                    stddevs.append(value)

            if evaluator.passed is not None:
                total += 1
                if evaluator.passed:
                    passed += 1

        if not condition_runs:
            continue

        response.append(MetricsResponse(
            condition=condition,
            mean_slope=sum(slopes) / len(slopes) if slopes else 0.0,
            mean_tokens=sum(means) / len(means) if means else 0.0,
            stddev=sum(stddevs) / len(stddevs) if stddevs else 0.0,
            pass_rate=(passed / total) if total else 0.0,
        ))

    return response


@router.get("/conversations/compare", response_model=CompareResponse)
def compare(
    baseline: str = Query(...),
    candidate: str = Query(...),
    db: Session = Depends(get_db),
):
    summaries = {entry.condition: entry for entry in metrics(db)}
    base = summaries.get(baseline)
    cand = summaries.get(candidate)

    if not base or not cand:
        raise HTTPException(status_code=404, detail="Conditions not found")

    deltas = {
        "slope_delta": cand.mean_slope - base.mean_slope,
        "mean_tokens_delta": cand.mean_tokens - base.mean_tokens,
        "pass_rate_delta": cand.pass_rate - base.pass_rate,
    }
    summary = {
        "baseline": base.dict(),
        "candidate": cand.dict(),
    }

    return CompareResponse(
        baseline_condition=baseline,
        candidate_condition=candidate,
        deltas=deltas,
        summary=summary,
    )


@router.get("/conversations/{run_id}", response_model=ConversationDetailResponse)
def get_run(run_id: str, db: Session = Depends(get_db)):
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid run_id") from exc

    run = db.query(ConversationRun).filter(ConversationRun.id == run_uuid).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    turns = (
        db.query(ConversationTurn)
        .filter(ConversationTurn.run_id == run.id)
        .order_by(ConversationTurn.turn_index.asc())
        .all()
    )
    evaluator = (
        db.query(ConversationEvaluatorResult)
        .filter(ConversationEvaluatorResult.run_id == run.id)
        .all()
    )

    turn_responses = [
        ConversationTurnResponse(
            turn_index=turn.turn_index,
            user_text=turn.user_text,
            assistant_text=turn.assistant_text,
            input_tokens=turn.input_tokens,
            output_tokens=turn.output_tokens,
            latency_ms=turn.latency_ms,
            cost_usd=turn.cost_usd,
            fallback_used=bool(turn.fallback_used),
        )
        for turn in turns
    ]

    metrics = {}
    evaluator_responses = []
    for result in evaluator:
        details = _coerce_details(result.details)
        if result.evaluator_name == "verbosity_stability":
            metrics = details.get("metrics", {})
        evaluator_responses.append(EvaluatorResultResponse(
            evaluator_name=result.evaluator_name,
            passed=result.passed,
            score=result.score,
            details=details,
            reasoning=result.reasoning,
        ))

    parameters = run.parameters or {}
    return ConversationDetailResponse(
        run_id=str(run.id),
        condition=run.condition,
        model_id=run.model,
        backend=parameters.get("backend"),
        intent_id=run.intent_id,
        parameters=parameters,
        error=run.error_message,
        status=run.status.value,
        metrics=metrics,
        turns=turn_responses,
        evaluator_results=evaluator_responses,
        created_at=run.timestamp,
    )
