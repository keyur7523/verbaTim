# Verbatim

Measuring and enforcing verbosity stability in multi-turn LLM conversations

---

## Overview

Verbatim is a behavioral case study focused on **verbosity drift** in multi-turn large language model (LLM) conversations.

Verbosity drift is the tendency for responses to grow longer across turns even when:
- user intent remains stable,
- task complexity does not increase, and
- explicit brevity instructions were provided earlier.

This project treats verbosity as a **product-quality invariant with safety implications**, not a stylistic preference. Excess verbosity increases hallucination risk, degrades semantic precision, inflates cost and latency, and expands policy surface area over time.

Verbatim evaluates this behavior, diagnoses failure modes, and demonstrates a prompt-level intervention that stabilizes verbosity across turns without truncation or hard clipping.

---

## What this repository contains

This repository is intentionally **evaluation-first**, not a hosted service.

### Core components
- Prompt interventions for different verbosity control strategies:
  - baseline
  - naive (“be concise”)
  - budgeted
  - verbatim (invariant + self-monitoring + fallback)
- Multi-turn experiment harness for fixed-intent conversations
- Verbosity stability evaluator (drift slope, variance, growth ratio)
- Reproducible artifacts (CSV/JSON summaries)
- Internal-style case study and reproducibility documentation

There is **no UI and no running backend** in this version by design.

---

## Why verbosity matters

Verbosity drift is not just a UX issue.

In production systems, it:
- reduces clarity and signal-to-noise ratio,
- increases the likelihood of unsupported claims,
- compounds cost and latency across long sessions,
- makes model behavior harder to reason about and test.

This project frames verbosity control as a **behavioral specification problem** and evaluates it accordingly.

---

## Experimental design (high level)

- Conversation length: fixed multi-turn (e.g., 12 turns)
- User intent fixed per run (no requests for “more detail”)
- Conditions tested:
  - baseline
  - naive
  - budgeted
  - verbatim
- What is held constant: intent, model, temperature, turn structure

Metrics are computed from per-turn token counts and aggregated at the conversation level.

---

## Metrics

Primary metrics:
- Mean tokens per turn
- Verbosity drift slope (tokens vs turn index)
- Growth ratio (early vs late turns)
- Length variance

Verbosity stability is evaluated quantitatively rather than qualitatively.

Verbosity reduction alone is insufficient without safety and adherence checks.

Safety-adjacent evaluators (instruction adherence, hallucination proxy, refusal behavior) are explicitly called out in the case study as **planned but not implemented** in this repo version.

---

## Results

All reported numbers are derived from committed artifacts.

- Aggregated metrics: `artifacts/summary.csv`
- Baseline → Verbatim deltas: `artifacts/summary_deltas.json`

A detailed analysis, including failure modes and tradeoffs, is documented in:

- `docs/case-study.md`

---

## Reproducibility

This project is designed to be reproducible without a running service.

Exact environment assumptions, execution commands, artifact descriptions, and variance caveats are documented in:

- `docs/reproducibility.md`

---

## What this project is (and is not)

**This project is:**
- A behavioral evaluation and prompt-engineering case study
- Focused on multi-turn behavior, not single responses
- Evidence-driven and artifact-based

**This project is not:**
- A hosted web service
- A UI or dashboard demo
- A claim that verbosity alone solves safety

These choices are intentional and aligned with the project’s goals.

---

## Repository structure

```
verbatim/
├─ prompts/
│  └─ conditions/
├─ datasets/
│  └─ intents.yaml
├─ evaluators/
│  └─ verbosity.py
├─ experiments/
│  └─ run_conversations.py
├─ analysis/
│  └─ summarize.py
├─ docs/
│  ├─ case-study.md
│  └─ reproducibility.md
└─ README.md
```

---

## Notes on scope

This repository represents **Route 2**: artifact-based evaluation without a backend or UI.

A Probekit-style API/dashboard integration is intentionally out of scope here to keep the focus on behavioral specification, measurement rigor, and reasoning about tradeoffs.

---
