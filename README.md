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

This repo evaluates the behavior, diagnoses failure modes, and tests a prompt-level intervention ("verbatim") against simpler controls, without truncation or hard clipping. In a pre-registered 200-run test it made replies shortest, but it did not stabilize length across turns (see Results).

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

`backend/` is a small local FastAPI service that runs the conversations. It calls the Anthropic Messages API for real models, and has an echo mock for development that is refused unless explicitly enabled. There is no UI.

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

Safety-adjacent evaluators are regex/keyword proxies, not detectors: an instruction-adherence check, an unsupported-claim proxy (regex), and a refusal keyword proxy. Instruction adherence uses per-turn specs for follow-ups with checkable wording ("one sentence", "two bullets", …) and is scored from transcripts; the two proxies have not been applied to the real-model runs yet. See the case study for status.

---

## Results

Pre-registered rerun on `claude-sonnet-4-6` (2026-10-16): 5 intents × 4 conditions × 10 repeats = 200 runs,
all completed, none excluded. The analysis plan was committed before the rerun started.

Follow-up turns 1–11, each condition compared turn by turn with baseline (95% bootstrap CIs):

| Condition | n | Follow-up length vs baseline | Ratio drift, % per turn | Pass rate (turns 1–11) |
|---|---:|---:|---:|---:|
| baseline | 50 | 1.00 | 0 | 12/50 |
| naive | 50 | 0.65 [0.62, 0.69] | +2.76 [+1.90, +3.64] | 27/50 |
| budgeted | 50 | 0.65 [0.63, 0.68] | +1.73 [+0.85, +2.70] | 29/50 |
| verbatim | 50 | 0.59 [0.57, 0.61] | +3.65 [+2.96, +4.31] | 20/50 |

- **Verbatim makes replies shortest** (0.59× baseline on follow-ups, 0.38× on the opening answer).
- **Its relative length rises across turns** (+3.65% per turn, the pre-registered primary comparison), mostly in
  the debugging and planning intents.
- **The verbosity-drift hypothesis is not supported on this model:** baseline follow-ups get *shorter* across
  turns (−6.1 tokens per turn). The rising ratio most likely reflects the conditions converging on a shrinking
  baseline, not a constraint decaying, and turn position is confounded with question content because every run
  asks the same follow-ups in the same order.

Full results, caveats, and the analysis plan: `docs/case-study.md`. Artifacts: `artifacts_rerun/`
(`primary_comparison.json`, `summary.csv`); reproduce the comparison with
`python -m verbatim.analysis.primary_comparison --artifacts-dir artifacts_rerun`.

### History: the withdrawn original results

An audit (October 2026) found that the original published summary pooled 60 mock-generator runs (all
"passed"), 80 failed runs, and 24 real `claude-sonnet-4-20250514` runs, grouped by condition only. That table
was withdrawn. The 24 real runs are kept in `artifacts/` (summary in `artifacts/summary.csv`); mock and failed
runs are kept locally in the git-ignored `artifacts_excluded/`.

---

## Reproducibility

Re-running the experiment needs the local backend and an Anthropic API key. The summaries can be regenerated from the committed artifacts without either.

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

I keep this repository artifact-based: there is a small local backend for running conversations, but no UI or hosted service.

A Probekit-style API/dashboard integration is out of scope here to keep the focus on behavioral specification, measurement rigor, and reasoning about tradeoffs.

---
