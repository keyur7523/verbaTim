# Reproducibility

## 1) Environment
- Python: 3.11+ recommended
- OS: macOS or Linux (tested locally)
- Install dependencies:
  - `pip install -r requirements.txt`
  - `pip install -r backend/requirements.txt` (if running the backend)
- Required environment variables (name only):
  - ANTHROPIC_API_KEY (required for real-model runs through the local backend; an `ant auth login` profile also works)

## 2) Model Configuration
- Model name(s): set via `--model-id` in the runner (example: `claude-sonnet-4-20250514`)
- Temperatures used: `0.2`, `0.5`
- Token budgets used: `80`, `120`, `160` (budgeted condition only)
- Fixed parameters: `max_tokens` defaults to 4096 in the runner. The committed runs used 512, which truncated several opening answers; truncated turns are now listed in `truncated_turns`.
- Models in `verbatim/models.py` that reject `temperature` (Opus 4.7+, Sonnet 5+, Haiku 5.5) must be run with `--temperatures none`.
- Not tuned: temperature, budget, and prompt wording were not optimized per intent

## 3) Dataset Description
- Intent templates: `verbatim/datasets/intents.yaml`
- Turns per conversation: 12
- Intent families: concept explanation, option comparison, step-by-step planning, debugging analysis, summarization
- Excluded: safety/refusal-specific prompts

## 4) Execution Steps (copy/paste commands)
Start the backend (calls the Anthropic API):
```bash
export ANTHROPIC_API_KEY=...
uvicorn app.main:app --app-dir backend --port 8000
```

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
- `aggregate_metrics.json`: rollup metrics for the run, plus run metadata (`artifact_schema_version` 2 and later): `run_id`, `model`, `backend` (`anthropic`, `probekit-api`, or `mock`), `length_unit` (`provider_tokens`, `provider_tokens_incl_thinking`, or `words`), `intent_id`, `condition`, `temperature`, `token_budget`, `max_tokens`, `timestamp`, `status`, `error`
- `summary.csv`: aggregation per (model, condition, length unit) with `n` and standard deviations; word counts and token counts are never pooled; failed, mock (model null or `mock-echo`), and unevaluated runs are excluded (pass `--include-mock` to keep mock runs)
- `summary.html`: HTML table view

Interpretation notes:
- Per-run metrics live in `aggregate_metrics.json`.
- Cross-condition deltas live in `summary_deltas.json`.
- Evaluator outputs are stored in `evaluator_results.json` if present.
- Drift slope is computed by the verbosity evaluator from per-turn output_tokens. For real runs these are the provider's token counts (the committed runs' counts reproduce their recorded `cost_usd` at $3/$15 per million input/output tokens); for mock runs the same fields hold word counts, labelled `length_unit: words`.
- Pass rate is derived from the verbosity evaluator passed/failed field.

## 6) Determinism & Variance
LLM outputs are stochastic even at fixed temperature. Results are aggregated by mean across multiple runs per condition
as reported in `summary.csv`. No fixed seed is enforced in the runner. Unless otherwise noted, these runs do not fully
characterize variance; for tighter estimates, run N replicates per condition and aggregate mean and standard deviation.

## 7) Known Limitations
- Sample size is limited to the runs executed locally.
- Model versions can change over time.
- API and inference behavior are non-deterministic.
- The local backend calls the Anthropic API for models in `verbatim/models.py`. Its `mock-echo` model echoes the system prompt plus the user text and counts words, not tokens; older mock runs had `model: null` and are excluded from summaries. The backend refuses mock runs unless `VERBATIM_ALLOW_MOCK=1` is set, and the runner refuses to save mock runs unless `--allow-mock` is passed. Because older mock runs were stored under real model IDs, the summary also excludes runs whose transcript looks like mock output (`mock_content`), and a test fails if any committed transcript does.
