from __future__ import annotations

import re
from typing import Any


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _sentence_count(text: str) -> int:
    parts = re.split(r"[.!?]+", text.strip())
    return len([p for p in parts if p.strip()])


def _detect_format(text: str) -> str:
    if re.search(r"(?m)^\s*[-*•]\s+", text):
        return "bullets"
    if _sentence_count(text) <= 3:
        return "short_paragraphs"
    return "unknown"


def evaluate_instruction_adherence(assistant_text: str, spec: dict[str, Any] | None) -> dict[str, Any]:
    spec = spec or {}
    violations: list[str] = []

    word_count = _word_count(assistant_text)
    format_detected = _detect_format(assistant_text)

    max_words = spec.get("max_words")
    max_tokens = spec.get("max_tokens")
    required_format = spec.get("required_format")
    forbidden_phrases = spec.get("forbidden_phrases") or []

    if isinstance(max_words, int) and word_count > max_words:
        violations.append("max_words_exceeded")
    if isinstance(max_tokens, int) and word_count > max_tokens:
        violations.append("max_tokens_exceeded")

    if required_format in {"bullets", "short_paragraphs"} and format_detected != required_format:
        violations.append("format_mismatch")

    for phrase in forbidden_phrases:
        if phrase and phrase.lower() in assistant_text.lower():
            violations.append(f"forbidden_phrase:{phrase}")

    return {
        "passed": len(violations) == 0,
        "details": {
            "violations": violations,
            "word_count": word_count,
            "format_detected": format_detected,
        },
    }
