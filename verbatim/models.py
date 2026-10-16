"""Models the experiment can run on, with pricing and sampling support.

Prices are first-party Claude API rates in USD per million tokens (checked
2026-10-16). claude-sonnet-4-20250514 is deprecated but kept so the committed
runs stay reproducible; its rates match their recorded cost_usd exactly.

accepts_temperature: Opus 4.7+, Sonnet 5+, and Haiku 5.5 reject non-default
sampling parameters with a 400, so a temperature sweep only works on the
older models marked True.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    input_usd_per_mtok: float
    output_usd_per_mtok: float
    accepts_temperature: bool


MODEL_CATALOG: dict[str, ModelInfo] = {
    "claude-opus-5-5": ModelInfo(4.00, 20.00, accepts_temperature=False),
    "claude-opus-5": ModelInfo(5.00, 25.00, accepts_temperature=False),
    "claude-opus-4-8": ModelInfo(5.00, 25.00, accepts_temperature=False),
    "claude-opus-4-7": ModelInfo(5.00, 25.00, accepts_temperature=False),
    "claude-opus-4-6": ModelInfo(5.00, 25.00, accepts_temperature=True),
    "claude-sonnet-5-5": ModelInfo(2.00, 10.00, accepts_temperature=False),
    "claude-sonnet-5": ModelInfo(2.00, 10.00, accepts_temperature=False),
    "claude-sonnet-4-6": ModelInfo(3.00, 15.00, accepts_temperature=True),
    "claude-sonnet-4-20250514": ModelInfo(3.00, 15.00, accepts_temperature=True),
    "claude-haiku-5-5": ModelInfo(0.10, 0.50, accepts_temperature=False),
    "claude-haiku-4-5": ModelInfo(1.00, 5.00, accepts_temperature=True),
}


def cost_usd(model_id: str, input_tokens: int, output_tokens: int) -> float:
    info = MODEL_CATALOG[model_id]
    return (input_tokens * info.input_usd_per_mtok + output_tokens * info.output_usd_per_mtok) / 1_000_000
