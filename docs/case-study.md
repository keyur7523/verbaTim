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
- Mean tokens per turn: average output length per turn; indicates overall verbosity.
- Drift slope: linear regression slope of output tokens vs turn index; captures trend across turns.
- Growth ratio: mean output of last 3 turns divided by first 3 turns; detects end-of-conversation inflation.
- Length stddev: variability in output length across turns; captures instability.

### Safety-adjacent checks (status)
- Instruction adherence: Implemented and measured in this repo version.
- Hallucination proxy: Implemented and measured in this repo version.
- Refusal/over-refusal: Implemented and measured in this repo version.
Planned checks are implemented in this repo version.

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
### Results (Summary)
| Condition | Mean tokens/turn | Drift slope (tokens/turn) | Growth ratio | Pass rate (verbosity) |
|---|---:|---:|---:|---:|
| baseline | 42.559 | -6.309 | 0.727 | 0.294 |
| naive | 27.872 | -2.500 | 0.835 | 0.345 |
| budgeted | 32.037 | -0.488 | 0.942 | 0.380 |
| verbatim | 71.667 | -0.764 | 0.945 | 0.455 |

### Deltas (baseline → verbatim)
- Drift slope delta: 5.544969267574531
- Mean tokens/turn delta: 29.107676900584792
- Pass rate delta: 0.160427807486631
- Growth ratio delta: 0.21821381471108503

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
