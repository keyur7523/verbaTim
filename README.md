# Verbatim

Measuring and enforcing verbosity stability in multi-turn LLM conversations

---

## Overview

I built Verbatim as a behavioral case study focused on **verbosity drift** in multi-turn large language model (LLM) conversations.

Verbosity drift is the tendency for responses to grow longer across turns even when:
- user intent remains stable,
- task complexity does not increase, and
- explicit brevity instructions were provided earlier.

I treat verbosity as a **product-quality invariant with safety implications**, not a stylistic preference. Excess verbosity increases hallucination risk, degrades semantic precision, inflates cost and latency, and expands policy surface area over time.

This repo evaluates the behavior, diagnoses failure modes, and demonstrates a prompt-level intervention that stabilizes verbosity across turns without truncation or hard clipping.

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
- Run artifacts and CSV/JSON summaries (real-model runs only; see Results)
- Internal-style case study and reproducibility documentation

I include **no UI and no running backend** in this version by design.

---

## Why verbosity matters

Verbosity drift is not just a UX issue.

In production systems, it:
- reduces clarity and signal-to-noise ratio,
- increases the likelihood of unsupported claims,
- compounds cost and latency across long sessions,
- makes model behavior harder to reason about and test.

I frame verbosity control as a **behavioral specification problem** and evaluate it accordingly.

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

I evaluate verbosity stability quantitatively rather than qualitatively.

Verbosity reduction alone is insufficient without safety and adherence checks.

Safety-adjacent evaluators are regex/keyword proxies, not detectors: an instruction-adherence check, an unsupported-claim proxy (regex), and a refusal keyword proxy. None of them has been applied to the real-model runs yet, and instruction adherence passes unconditionally until intents define an instruction spec. See the case study for status.

---

## Results — status: invalidated, rerun pending

An audit of the original artifacts (October 2026) found that the published
summary pooled three kinds of runs:

- 60 runs from the local backend's mock generator, which echoes the prompt
  instead of calling a model (all "passed");
- 80 runs on claude-3-5-sonnet-20241022 that failed with no output;
- 24 real runs on claude-sonnet-4-20250514 (baseline 10, budgeted 7,
  naive 5, verbatim 2). 22 of them failed the verbosity check; the other 2
  completed without a verbosity evaluation.

The earlier table and deltas are withdrawn. The real runs are too few and
too unbalanced to support a conclusion, so **the verbosity-drift hypothesis
is currently untested**. The aggregation now excludes failed, mock, and
unevaluated runs and reports results per model with sample sizes and standard
deviations; a balanced rerun (4 conditions × 4 intents × 10 runs, one model)
is planned.

- Committed artifacts: the 24 real claude-sonnet-4-20250514 runs only. Mock and failed runs are kept locally in the git-ignored `artifacts_excluded/`.
- Current summary (22 evaluated real runs, n and SD per cell): `artifacts/summary.csv`
- Per-model deltas against baseline, with sample sizes: `artifacts/summary_deltas.json`

A detailed analysis, including failure modes and tradeoffs, is documented in:

- `docs/case-study.md`

---

## Reproducibility

I designed this project to be reproducible without a running service.

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

I keep this repository artifact-based without a backend or UI.

A Probekit-style API/dashboard integration is out of scope here to keep the focus on behavioral specification, measurement rigor, and reasoning about tradeoffs.

---
