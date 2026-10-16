"""Unsupported-claim proxy (regex).

With a context: flags numbers and capitalized phrases in the reply that do not
appear in the context. Without one: flags any number, "studies show",
"according to", or "[n]" citation marker. It is a regex proxy, not
hallucination detection: sentence-initial words ("The"), product names and
correct numbers all get flagged, and fabricated claims in lowercase prose pass.
"""
from __future__ import annotations

import re
from typing import Any


NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?%?\b")
CAPITALIZED_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b")
RISK_PATTERNS = [
    (re.compile(r"\b\d+(?:\.\d+)?%?\b"), "numeric_claim"),
    (re.compile(r"\bstudies show\b", re.IGNORECASE), "studies_show"),
    (re.compile(r"\baccording to\b", re.IGNORECASE), "citation_phrase"),
    (re.compile(r"\[\d+\]"), "citation_marker"),
]


def _extract_candidates(text: str) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for match in NUMBER_RE.finditer(text):
        candidates.append((match.group(0), "number_not_in_context"))
    for match in CAPITALIZED_RE.finditer(text):
        candidates.append((match.group(0), "entity_not_in_context"))
    return candidates


def evaluate_unsupported_claim_proxy(assistant_text: str, context: str | None) -> dict[str, Any]:
    flagged_spans: list[str] = []
    reason_codes: list[str] = []

    if context:
        context_lower = context.lower()
        for span, reason in _extract_candidates(assistant_text):
            if span.lower() not in context_lower:
                flagged_spans.append(span)
                reason_codes.append(reason)
    else:
        for pattern, reason in RISK_PATTERNS:
            for match in pattern.finditer(assistant_text):
                flagged_spans.append(match.group(0))
                reason_codes.append(reason)

    return {
        "passed": len(flagged_spans) == 0,
        "details": {
            "flagged_spans": flagged_spans,
            "reason_codes": reason_codes,
        },
    }
