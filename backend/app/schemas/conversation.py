from datetime import datetime
from pydantic import BaseModel, Field


class ConversationRunRequest(BaseModel):
    model_id: str | None = None
    model: dict | None = None
    condition: str | None = None
    conditions: list[str] | None = None
    intent_name: str | None = None
    intent_id: str | None = None
    turns: list[str] | None = None
    system_prompt: str | None = None
    parameters: dict | None = None
    temperatures: list[float] | None = None
    budgets: list[int] | None = None
    max_turns: int = Field(12, ge=1)


class ConversationRunResponse(BaseModel):
    run_id: str
    status: str


class ConversationTurnResponse(BaseModel):
    turn_index: int
    user_text: str
    assistant_text: str | None
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int | None
    cost_usd: float | None
    fallback_used: bool


class EvaluatorResultResponse(BaseModel):
    evaluator_name: str
    passed: bool | None
    score: float | None
    details: dict | None
    reasoning: str | None


class ConversationDetailResponse(BaseModel):
    run_id: str
    condition: str
    model_id: str
    backend: str | None = None
    intent_id: str | None = None
    parameters: dict | None = None
    error: str | None = None
    status: str
    metrics: dict
    turns: list[ConversationTurnResponse]
    evaluator_results: list[EvaluatorResultResponse]
    created_at: datetime


class MetricsResponse(BaseModel):
    condition: str
    mean_slope: float
    mean_tokens: float
    stddev: float
    pass_rate: float


class CompareResponse(BaseModel):
    baseline_condition: str
    candidate_condition: str
    deltas: dict
    summary: dict
