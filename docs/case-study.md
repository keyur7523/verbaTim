# Verbatim case study

## 1) Problem Statement
Verbosity drift is the tendency for model responses to grow longer across turns even when user intent and task complexity are stable. This is a product quality issue with safety implications. Longer responses reduce clarity, increase semantic drift risk, and compound hallucination and policy exposure as redundant context accumulates.

## 2) Behavioral Hypothesis
Single-shot constraints decay across turns because the model optimizes for local helpfulness at each step. The model is rewarded for completeness in the current turn, which biases it toward elaboration. Without a persistent verbosity invariant, this leads to predictable increases in length and restatement across a multi-turn horizon.

## 3) Experimental Design
- 12 turns per conversation.
- Fixed intent templates with stable follow-ups.
- Identical user prompts across conditions; only system prompt changes.

Conditions:
- baseline: no verbosity control
- naive: single-shot "be concise"
- budgeted: explicit token budget with clarifying question fallback
- verbatim: verbosity invariant + self-monitoring + fallback

These conditions isolate how increasingly structured constraints affect drift while keeping intent constant.

## 4) Metrics and Evaluation
Core metrics:
- Mean tokens per turn: average output length per turn, in the provider's token counts; indicates overall verbosity.
- Drift slope: linear regression slope of output tokens vs turn index; captures trend across turns.
- Growth ratio: mean output of last 3 turns divided by first 3 turns; detects end-of-conversation inflation.
- Length stddev: variability in output length across turns; captures instability.

Turn 0 answers an open-ended prompt and every follow-up asks for something narrow, so turn 0
dominates all-turn metrics. The summary therefore also reports:
- Turn 0 length on its own, and follow-up metrics (mean, drift slope, growth ratio, pass rate) over turns 1–11.
- Length ratio vs baseline: each run's length at each follow-up turn divided by the baseline condition's mean
  length at that turn, for the same model, intent, and temperature, aggregated as a geometric mean. This removes
  the per-question demand that every condition shares. Baseline is about 1.0 by construction.
- Ratio drift (% per turn): the trend of that ratio across follow-ups. A positive value means the condition's
  length is creeping back toward baseline, i.e. the constraint is decaying across turns.

### Safety-adjacent checks (status)
- Instruction adherence: implemented with per-turn specs. Follow-ups with mechanically checkable wording ("in one sentence", "one-line", "two bullets", "bullets only", "10 words") carry a spec in `intents.yaml`; other turns are not checked. Counts are regex heuristics. Scored from transcripts in the summary: on the 22 evaluated real runs, all 66 checked turns passed. That says Sonnet 4 follows explicit format instructions; it says nothing yet about verbosity across conditions.
- Unsupported-claim proxy (regex): implemented. It flags numbers and capitalized phrases not found in the context, so false positives are common. It is a proxy, not hallucination detection.
- Refusal keyword proxy: implemented. It flags phrases like "cannot" or "won't" anywhere in a reply, so it also matches ordinary answers. It is a proxy, not refusal detection.
- The two proxies have not been applied to the real-model runs yet. They ran only on mock-generator runs, which are now excluded. Applying them to real runs is planned (not implemented).

Verbosity reduction alone is insufficient without safety and adherence checks.

## 5) Baseline Failure Modes
Observed patterns in baseline runs:
- Repetition and restatement across turns.
- Hedging and disclaimers that add length without new content.
- Unnecessary elaboration on stable intent.

Example (baseline, turn 0):
> "A **hash table** (also called a hash map) is a data structure that stores key-value pairs and provides very fast average-case lookup, insertion, and deletion operations. ... ## Collision Handling ... ## When to Use Hash Tables ..."

Excerpt with user and assistant turns (baseline):
> User: Explain what a hash table is and when to use it.
> Assistant: A **hash table** (also called a hash map) is a data structure that stores key-value pairs and provides very fast average-case lookup, insertion, and deletion operations.

## 6) Prompt Intervention (Verbatim)
The intervention treats verbosity as a correctness constraint rather than stylistic preference. It introduces:
- A verbosity invariant that prohibits restating known context and encourages compact structure.
- A self-monitoring loop that checks whether each sentence adds new information.
- A failure-aware fallback that asks for clarification or provides a compressed answer with an offer to expand.

Truncation and hard clipping were avoided to preserve coherence and to diagnose behavior rather than mask it.

## 7) Results

**Withdrawn pending rerun.** The previous results table mixed mock-generator
runs, failed runs, and real model runs, and grouped them only by condition.
See the README "Results" section for the audit. Real-run data so far
(claude-sonnet-4-20250514, 22 evaluated runs, unbalanced) is insufficient to
compare conditions. This section will be replaced with per-condition means,
standard deviations, and sample sizes from the balanced rerun.

### Results (Summary)
Status: withdrawn. The current filtered summary, with `n` and standard deviation per
(model, condition) cell, is in `artifacts/summary.csv`. It is not a basis for comparing conditions:

| Condition | n | Pass rate (verbosity) |
|---|---:|---:|
| baseline | 9 | 0/9 |
| naive | 5 | 0/5 |
| budgeted | 6 | 0/6 |
| verbatim | 2 | 0/2 |

Observation, not a conclusion: in every real run the first answer is much longer than the
rest (5 of 9 baseline runs hit the 512-token `max_tokens` cap on turn 0). The negative all-turn
drift slopes therefore mostly reflect the opening answer's length. Over turns 1–11 the same runs
drift upward in every condition (+1.5 to +2.9 tokens per turn; last-3/first-3 growth 1.25–1.53×).
With 22 unbalanced runs this is a hint worth testing in the rerun, not a finding.

### Analysis plan for the rerun (confirmed 2026-10-16, before the rerun started)
Fixed before any rerun data existed. Only the 5 pilot runs (`artifacts_pilot/`, used to check cost and
truncation) had been seen; they are excluded from the analysis.

Design:
- Model `claude-sonnet-4-6`, temperature 0.2, `max_tokens` 4096, token budget 120 (budgeted condition only).
- All 5 intents × 4 conditions × 10 repeats = 200 runs, written to `artifacts_rerun/`. Each repeat covers every
  combination before the next starts; spending is capped at $25.

Analysis:
- Primary comparison: verbatim vs baseline on ratio drift (% per turn) over turns 1–11, with a 95% CI.
- Secondary: length ratio vs baseline over turns 1–11, turn 0 ratio, and follow-up drift slope per condition.
- Pass/fail thresholds, applied to turns 1–11: drift slope ≤ 3.0 tokens/turn, growth ≤ 1.2×,
  stddev ≤ 0.35 × mean, fallback rate ≤ 0.15.
- Failed, mock, and unevaluated runs are excluded and reported with counts. No other runs are dropped.

### Deltas (baseline → verbatim)
Withdrawn. With n = 2 for verbatim, no delta is reported. Per-model deltas with sample
sizes are written to `artifacts/summary_deltas.json` for reference only.

## 8) Tradeoffs and Failure Cases
Observed or expected tradeoffs:
- Over-compression can omit nuance needed for correctness.
- Budgeted fallback can increase clarification frequency and user friction.
- Strict brevity can suppress helpful context.

Failure example:
TODO: Add a verbatim-run example where fallback triggers.

## 9) Prompt-Level vs Model-Level Responsibility
Prompt-level scaffolding can enforce:
- Output length constraints and format hints.
- Self-monitoring reminders.
- Explicit fallback behavior.

Model-level changes are likely required when:
- The model repeatedly violates constraints despite explicit instructions.
- Safety failures persist without a clear instruction path.
- Brevity requires internal uncertainty calibration beyond promptable checks.

## 10) Open Questions
- When is verbosity increase legitimately required for correctness?
- How should brevity constraints interact with tone requirements?
- How can brevity avoid hiding uncertainty or risk?
- What is the minimum clarification rate that preserves task success?
