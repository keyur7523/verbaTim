from __future__ import annotations

import re
from typing import Any


# Per-turn spec keys (all optional):
#   max_words, max_sentences, max_lines: upper bounds
#   required_format: "bullets" or "short_paragraphs"
#   bullet_count: exact number of top-level bullet or numbered items
#   bullets_only: every non-empty line must be a bullet or numbered item (any depth)
#   forbidden_phrases: case-insensitive substrings that must not appear
# Counts are regex heuristics: "e.g. " ends a sentence and markdown headings count as lines.
BULLET_RE = re.compile(r"^ ?(?:[-*•]|\d+[.)])\s+")
ANY_DEPTH_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
SENTENCE_END_RE = re.compile(r"[.!?]+(?=\s|$)")


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip()]


def _bullet_count(text: str) -> int:
    return sum(1 for line in _lines(text) if BULLET_RE.match(line))


def _sentence_count(text: str) -> int:
    parts = SENTENCE_END_RE.split(text.strip())
    return len([p for p in parts if p.strip()])


def _detect_format(text: str) -> str:
    if _bullet_count(text):
        return "bullets"
    if _sentence_count(text) <= 3:
        return "short_paragraphs"
    return "paragraphs"


def evaluate_instruction_adherence(assistant_text: str, spec: dict[str, Any] | None) -> dict[str, Any]:
    spec = spec or {}
    violations: list[str] = []

    word_count = _word_count(assistant_text)
    sentence_count = _sentence_count(assistant_text)
    line_count = len(_lines(assistant_text))
    bullet_count = _bullet_count(assistant_text)
    format_detected = _detect_format(assistant_text)

    max_words = spec.get("max_words")
    max_sentences = spec.get("max_sentences")
    max_lines = spec.get("max_lines")
    required_format = spec.get("required_format")
    required_bullets = spec.get("bullet_count")
    bullets_only = spec.get("bullets_only") is True
    forbidden_phrases = spec.get("forbidden_phrases") or []

    if isinstance(max_words, int) and word_count > max_words:
        violations.append("max_words_exceeded")
    if isinstance(max_sentences, int) and sentence_count > max_sentences:
        violations.append("max_sentences_exceeded")
    if isinstance(max_lines, int) and line_count > max_lines:
        violations.append("max_lines_exceeded")

    if required_format in {"bullets", "short_paragraphs"} and format_detected != required_format:
        violations.append("format_mismatch")
    if isinstance(required_bullets, int) and bullet_count != required_bullets:
        violations.append("bullet_count_mismatch")
    if bullets_only and any(not ANY_DEPTH_BULLET_RE.match(line) for line in _lines(assistant_text)):
        violations.append("non_bullet_lines")

    for phrase in forbidden_phrases:
        if phrase and phrase.lower() in assistant_text.lower():
            violations.append(f"forbidden_phrase:{phrase}")

    return {
        "passed": len(violations) == 0,
        "details": {
            "checked": bool(spec),
            "violations": violations,
            "word_count": word_count,
            "sentence_count": sentence_count,
            "line_count": line_count,
            "bullet_count": bullet_count,
            "format_detected": format_detected,
        },
    }


def evaluate_transcript_adherence(
    transcript: list[dict[str, Any]],
    turn_specs: list[dict[str, Any] | None],
) -> dict[str, Any]:
    """Evaluate every turn that has a spec; turns without one are skipped."""
    per_turn = []
    for turn in transcript:
        index = turn.get("turn_index")
        spec = turn_specs[index] if isinstance(index, int) and 0 <= index < len(turn_specs) else None
        if not spec:
            continue
        result = evaluate_instruction_adherence(turn.get("assistant_text") or "", spec)
        per_turn.append({"turn_index": index, **result})
    checked = len(per_turn)
    passed = sum(1 for result in per_turn if result["passed"])
    return {
        "checked_turns": checked,
        "passed_turns": passed,
        "passed": passed == checked,
        "per_turn": per_turn,
    }
