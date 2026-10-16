"""Detect mock-generator output in run transcripts.

A model ID alone does not prove a run is real: earlier versions of the local
backend stored mock output under real model IDs. These checks look at the
assistant text itself for the shapes the mock generators produce:

- the condition's system prompt echoed back (optionally followed by the user text)
- "<prefix>: <user text>", e.g. "Answer: ..." or "Verbatim answer: ..."
- the fixed budget fallback "Clarify: which detail is most important?"
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts" / "conditions"
MOCK_FALLBACK_TEXT = "Clarify: which detail is most important?"
# Shorter user texts could plausibly end a real reply, so don't treat them as echoes.
MIN_ECHO_CHARS = 20


def _normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def _system_prompt_openings() -> set[str]:
    openings = set()
    for path in PROMPTS_DIR.glob("*.md"):
        first_line = next((line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()), "")
        if first_line:
            openings.add(_normalize(first_line))
    return openings


SYSTEM_PROMPT_OPENINGS = _system_prompt_openings()


def mock_echo_reason(assistant_text: str | None, user_text: str | None) -> str | None:
    """Return why a turn looks like mock output, or None if it doesn't."""
    assistant = _normalize(assistant_text or "")
    user = _normalize(user_text or "")
    if not assistant:
        return None
    if any(assistant.startswith(opening) for opening in SYSTEM_PROMPT_OPENINGS):
        return "echoes_system_prompt"
    if assistant == _normalize(MOCK_FALLBACK_TEXT):
        return "mock_fallback_text"
    if len(user) >= MIN_ECHO_CHARS and assistant.endswith(user):
        return "echoes_user_text"
    return None


def transcript_mock_reasons(transcript: list[dict[str, Any]]) -> list[tuple[int, str]]:
    """Return (turn_index, reason) for every turn that looks like mock output."""
    flagged = []
    for turn in transcript:
        reason = mock_echo_reason(turn.get("assistant_text"), turn.get("user_text"))
        if reason:
            flagged.append((turn.get("turn_index"), reason))
    return flagged


def run_dir_mock_reasons(run_dir: Path) -> list[tuple[int, str]]:
    path = run_dir / "transcript.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return transcript_mock_reasons(data if isinstance(data, list) else [])
