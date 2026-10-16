# Reproducibility

## 1) Environment
- Python: 3.11+ recommended
- OS: macOS or Linux (tested locally)
- Install dependencies:
  - `pip install -r requirements.txt`
  - `pip install -r backend/requirements.txt` (if running the backend)
- Required environment variables (name only):
  - ANTHROPIC_API_KEY (required only if backend is wired to real model calls)

## 2) Model Configuration
- Model name(s): set via `--model-id` in the runner (example: `claude-sonnet-4-20250514`)
- Temperatures used: `0.2`, `0.5`
- Token budgets used: `80`, `120`, `160` (budgeted condition only)
- Fixed parameters: `max_tokens=512` in the runner
- Not tuned: temperature, budget, and prompt wording were not optimized per intent

## 3) Dataset Description
- Intent templates: `verbatim/datasets/intents.yaml`
- Turns per conversation: 12
- Intent families: concept explanation, option comparison, step-by-step planning, debugging analysis, summarization
- Excluded: safety/refusal-specific prompts

## 4) Execution Steps (copy/paste commands)
Run all conditions locally against the backend:
```bash
python verbatim/experiments/run_conversations.py \
  --base-url http://127.0.0.1:8000 \
  --model-id claude-sonnet-4-20250514 \
  --conditions baseline,naive,budgeted,verbatim \
  --temperatures 0.2,0.5 \
  --budgets 80,120,160
```

Run a single baseline condition:
```bash
python verbatim/experiments/run_conversations.py \
  --base-url http://127.0.0.1:8000 \
  --model-id claude-sonnet-4-20250514 \
  --conditions baseline \
  --temperatures 0.2 \
  --budgets 120 \
  --intents concept_explanation
```

Run a single condition and intent:
```bash
python verbatim/experiments/run_conversations.py \
  --base-url http://127.0.0.1:8000 \
  --model-id claude-sonnet-4-20250514 \
  --conditions verbatim \
  --temperatures 0.2 \
  --budgets 120 \
  --intents concept_explanation
```

Artifacts are written under `artifacts/<run_id>/`.

Generate summaries:
```bash
python verbatim/analysis/summarize.py \
  --artifacts-dir artifacts \
  --output-csv artifacts/summary.csv \
  --output-html artifacts/summary.html \
  --compare-baseline baseline \
  --output-compare artifacts/summary_deltas.json
```

## 5) Artifacts
- `transcript.json`: ordered user/assistant turns
- `turn_metrics.json`: per-turn token and latency metadata
- `evaluator_results.json`: evaluator outputs per run
- `aggregate_metrics.json`: rollup metrics for the run
- `summary.csv`: aggregation per (model, condition) with `n` and standard deviations; failed, mock (model null or `mock-echo`), and unevaluated runs are excluded (pass `--include-mock` to keep mock runs)
- `summary.html`: HTML table view

Interpretation notes:
- Per-run metrics live in `aggregate_metrics.json`.
- Cross-condition deltas live in `summary_deltas.json`.
- Evaluator outputs are stored in `evaluator_results.json` if present.
- Drift slope is computed by the verbosity evaluator from per-turn output_tokens.
- Pass rate is derived from the verbosity evaluator passed/failed field.

## 6) Determinism & Variance
LLM outputs are stochastic even at fixed temperature. Results are aggregated by mean across multiple runs per condition
as reported in `summary.csv`. No fixed seed is enforced in the runner. Unless otherwise noted, these runs do not fully
characterize variance; for tighter estimates, run N replicates per condition and aggregate mean and standard deviation.

## 7) Known Limitations
- Sample size is limited to the runs executed locally.
- Model versions can change over time.
- API and inference behavior are non-deterministic.
- The local backend in `backend/` never calls a model: it echoes the system prompt plus the user text and counts words, not tokens. Runs it produces have `model: null` and are excluded from summaries. Real runs must go through an API that calls the model and reports provider token counts.
