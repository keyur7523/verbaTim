"""Turn generators: the echo mock and a real Anthropic Messages API call.

Both take the system prompt, the conversation history so far, and the new user
text, and return one TurnResult. The conversation service owns the history.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from verbatim.models import cost_usd


ANTHROPIC_BACKEND = "anthropic"
MOCK_BACKEND = "mock"
MOCK_MODEL_ID = "mock-echo"
MOCK_FALLBACK_TEXT = "Clarify: which detail is most important?"


@dataclass
class TurnResult:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float
    stop_reason: str | None
    # True when the response carried thinking blocks: output_tokens then
    # includes reasoning tokens, not just the visible reply.
    thinking_used: bool
    fallback_used: bool
    # What to append to the history as the assistant turn.
    history_content: Any


class MockGenerator:
    """Echoes the system prompt and user text. Counts words, not tokens."""

    backend = MOCK_BACKEND
    model_id = MOCK_MODEL_ID

    def __init__(self, condition: str, token_budget: int | None):
        self.condition = condition
        self.token_budget = token_budget

    def generate(self, system_prompt: str, history: list[dict[str, Any]], user_text: str) -> TurnResult:
        text = f"{system_prompt}\n{user_text}".strip()
        fallback_used = False
        words = text.split()
        if self.token_budget is not None and len(words) > self.token_budget:
            fallback_used = True
            if self.condition == "budgeted":
                text = MOCK_FALLBACK_TEXT
            else:
                text = " ".join(words[: self.token_budget])
        return TurnResult(
            text=text,
            input_tokens=len(user_text.split()),
            output_tokens=len(text.split()),
            latency_ms=0,
            cost_usd=0.0,
            stop_reason=None,
            thinking_used=False,
            fallback_used=fallback_used,
            history_content=text,
        )


class AnthropicGenerator:
    """One Messages API call per turn, with the full history resent each time.

    No `thinking` parameter is sent: models where thinking is optional then run
    without it, and models where it is always on report thinking_used. No
    refusal fallbacks are configured: a fallback would silently answer with a
    different model and mix models within one run.
    """

    backend = ANTHROPIC_BACKEND

    def __init__(self, client: Any, model_id: str, max_tokens: int, temperature: float | None):
        self.client = client
        self.model_id = model_id
        self.max_tokens = max_tokens
        self.temperature = temperature

    def generate(self, system_prompt: str, history: list[dict[str, Any]], user_text: str) -> TurnResult:
        request: dict[str, Any] = {
            "model": self.model_id,
            "max_tokens": self.max_tokens,
            "system": system_prompt,
            "messages": [*history, {"role": "user", "content": user_text}],
        }
        if self.temperature is not None:
            request["temperature"] = self.temperature

        started = time.perf_counter()
        response = self.client.messages.create(**request)
        latency_ms = round((time.perf_counter() - started) * 1000)

        text = "".join(block.text for block in response.content if block.type == "text")
        usage = response.usage
        return TurnResult(
            text=text,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd(self.model_id, usage.input_tokens, usage.output_tokens),
            stop_reason=response.stop_reason,
            thinking_used=any(block.type in ("thinking", "redacted_thinking") for block in response.content),
            fallback_used=False,
            # Full content, so thinking blocks go back unchanged on the next turn.
            history_content=response.content,
        )
