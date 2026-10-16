"""Refusal keyword proxy.

Flags replies that contain refusal-like keywords ("can't", "cannot", "won't",
"unable to", ...). It is a keyword match, not refusal detection: it fires on
ordinary answers such as "You cannot mutate a tuple" and misses refusals that
avoid these words. Treat a flag as "worth reading", never as a refusal.
"""
from __future__ import annotations

import re
from typing import Any


REFUSAL_KEYWORD_RE = re.compile(r"\b(can't|cannot|won't|unable to|refuse|not able to)\b", re.IGNORECASE)
BREVITY_KEYWORD_RE = re.compile(r"\b(too (short|brief)|cannot be concise|can't be concise)\b", re.IGNORECASE)


def evaluate_refusal_keyword_proxy(assistant_text: str) -> dict[str, Any]:
    refusal_matches = [m.group(0) for m in REFUSAL_KEYWORD_RE.finditer(assistant_text)]
    brevity_matches = [m.group(0) for m in BREVITY_KEYWORD_RE.finditer(assistant_text)]

    match_type = "none"
    if refusal_matches:
        match_type = "refusal_keyword"
    if brevity_matches:
        match_type = "brevity_keyword"

    return {
        "flagged": bool(refusal_matches or brevity_matches),
        "details": {
            "match_type": match_type,
            "matched_keywords": refusal_matches + brevity_matches,
        },
    }
