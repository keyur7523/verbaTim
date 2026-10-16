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
- Instruction adherence: implemented with per-turn specs. Follow-ups with mechanically checkable wording ("in one sentence", "one-line", "two bullets", "bullets only", "10 words") carry a spec in `intents.yaml`; other turns are not checked. Counts are regex heuristics. Scored from transcripts in the summary: on the 22 evaluated Sonnet 4 runs, all 66 checked turns passed; on the 200-run Sonnet 4.6 rerun, 98.8–100% per condition. That says these models follow explicit format instructions; it says nothing about verbosity across conditions.
- Unsupported-claim proxy (regex): implemented. It flags numbers and capitalized phrases not found in the context, so false positives are common. It is a proxy, not hallucination detection.
- Refusal keyword proxy: implemented. It flags phrases like "cannot" or "won't" anywhere in a reply, so it also matches ordinary answers. It is a proxy, not refusal detection.
- The two proxies ran on the 200 rerun runs (the backend applies them per turn). They flag 4–100% of runs per condition, mostly known false positives, so their rates are reported but not interpreted.

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

**Pre-registered result (rerun, 2026-10-16).** 200 runs on `claude-sonnet-4-6`: 5 intents × 4 conditions × 10
repeats, temperature 0.2, `max_tokens` 4096, budget 120. All 200 completed; none were excluded and no turn hit
`max_tokens`. Computed cost: $8.75. Artifacts: `artifacts_rerun/` (`primary_comparison.json`, `summary.csv`).
The analysis plan below was committed before the rerun started.

### Results (Summary)
Follow-up turns 1–11, each condition compared turn by turn with baseline on the same intent (50 runs per
condition, 50 baseline runs). 95% CIs from a stratified bootstrap (2,000 resamples, baseline runs resampled too);
t-intervals agree in sign.

| Condition | n | Follow-up length vs baseline [95% CI] | Ratio drift, % per turn [95% CI] | Pass rate (verbosity, turns 1–11) |
|---|---:|---:|---:|---:|
| baseline | 50 | 1.00 (reference) | 0 (reference) | 12/50 |
| naive | 50 | 0.65 [0.62, 0.69] | +2.76 [+1.90, +3.64] | 27/50 |
| budgeted | 50 | 0.65 [0.63, 0.68] | +1.73 [+0.85, +2.70] | 29/50 |
| verbatim | 50 | 0.59 [0.57, 0.61] | +3.65 [+2.96, +4.31] | 20/50 |

| Condition | Turn 0, tokens | Turn 0 vs baseline | Follow-up mean, tokens | Follow-up drift slope, tokens/turn (mean ± SD) |
|---|---:|---:|---:|---:|
| baseline | 923 | 1.00 | 70.8 | −6.09 ± 7.20 |
| naive | 436 | 0.49 | 42.1 | −2.00 ± 3.56 |
| budgeted | 187 | 0.22 | 40.3 | −1.80 ± 2.70 |
| verbatim | 352 | 0.38 | 36.6 | −0.81 ± 1.37 |

What this shows:
- Verbatim produces the shortest follow-ups (0.59× baseline) and a much shorter opening answer (0.38×).
- On the primary comparison, verbatim's length relative to baseline rises by +3.65% per turn, and the CI excludes
  zero. The other two conditions rise too, more slowly.
- The effect is concentrated in two intents: `debugging_analysis` (+10.7% per turn) and `step_by_step_planning`
  (+6.3%). `concept_explanation` (−0.6%) and `summarization` (0.0%) show essentially none.
- Instruction adherence on checked turns is 98.8–100% in every condition.

What it does not show:
- **The original hypothesis is not supported on this model.** Baseline follow-ups get shorter across turns
  (slope −6.1 tokens/turn; last-3/first-3 growth 0.70×), not longer. Every condition shrinks.
- **The rising ratio is probably convergence, not a constraint decaying.** Baseline shrinks fastest, so the
  conditions close in on it as the follow-ups get narrower and leave less to trim (a floor effect).
- **Turn position and question content are confounded.** Every run asks the same follow-ups in the same order,
  so a per-turn trend can't be separated from what each later question asks for. Shuffling follow-up order per
  run would separate them.
- One model, one temperature, 10 repeats per cell. The unsupported-claim and refusal keyword proxies flag
  4–100% of runs, mostly known false positives, and are not interpreted.

Earlier data (claude-sonnet-4-20250514, 22 evaluated runs, unbalanced, `artifacts/`): the original summary
pooled mock, failed, and real runs and was withdrawn (see the README). On those runs turn 0 dominated every
all-turn metric (5 of 9 baseline runs hit the old 512-token cap), and follow-ups drifted upward
(+1.5 to +2.9 tokens per turn). The rerun does not reproduce that upward drift on Sonnet 4.6; whether the
difference is the model or the small sample is open.

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
Follow-up turns 1–11 on `claude-sonnet-4-6` (n = 50 each): length 0.59× baseline [0.57, 0.61]; ratio drift
+3.65% per turn [+2.96, +4.31]; turn 0 length 0.38× baseline. All-turn deltas per model are in
`artifacts_rerun/summary_deltas.json`, but turn 0 dominates them.

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
