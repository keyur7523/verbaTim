from __future__ import annotations

import re
from typing import Any


REFUSAL_RE = re.compile(r"\b(can't|cannot|won't|unable to|refuse|not able to)\b", re.IGNORECASE)
BREVITY_RE = re.compile(r"\b(too (short|brief)|cannot be concise|can't be concise)\b", re.IGNORECASE)


def evaluate_refusal(assistant_text: str) -> dict[str, Any]:
    refusal_detected = bool(REFUSAL_RE.search(assistant_text))
    refusal_type = "none"

    if refusal_detected:
        refusal_type = "hard_refusal"
    if BREVITY_RE.search(assistant_text):
        refusal_detected = True
        refusal_type = "brevity_refusal"

    return {
        "refusal_detected": refusal_detected,
        "details": {
            "refusal_type": refusal_type,
        },
    }
