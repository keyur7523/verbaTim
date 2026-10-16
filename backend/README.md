# Verbatim Backend

## Install
```bash
pip install -r backend/requirements.txt
```

## Run
```bash
export ANTHROPIC_API_KEY=...   # or sign in with `ant auth login`
uvicorn app.main:app --reload --app-dir backend
```

## Models
Runs on a model in `verbatim/models.py` (`MODEL_CATALOG`) call the Anthropic Messages API: one request per
turn, with the condition's system prompt and the full conversation history resent each time. Each turn records
the provider's input/output token counts, latency, cost (from the catalog's per-model prices), and stop reason.

- **Temperature:** sent only when the request gives one. Opus 4.7+, Sonnet 5+, and Haiku 5.5 reject it, so a
  request that sets a temperature on those models gets HTTP 422 before anything runs.
- **Thinking:** no `thinking` parameter is sent. On models where thinking is always on (Opus 5.x, Sonnet 5.x,
  Haiku 5.5), `output_tokens` includes reasoning tokens, so those runs are labelled
  `length_unit: provider_tokens_incl_thinking` and are never pooled with visible-only counts.
- **Truncation:** turns that stop on `max_tokens` are listed in the verbosity result's `truncated_turns`.
- **No refusal fallbacks:** a fallback would answer with a different model mid-run, so a refusal is recorded as
  `stop_reason: refusal` instead.
- **Background runs:** `POST /api/conversations/run` validates the request, returns the run ID with status
  `pending`, and runs the conversation in the background. Poll `GET /api/conversations/{run_id}`. API errors
  end the run as `failed` with the error message.

## Mock model
Model `mock-echo` is a deterministic mock for development: it echoes the system prompt plus the user text (with
an optional budget fallback) and counts words, not tokens.

To keep mock output out of experiment results:
- Mock runs are refused with HTTP 503 unless the server is started with `VERBATIM_ALLOW_MOCK=1`.
- Every mock run is recorded with model `mock-echo`, backend `mock`, and `length_unit: words`.
- The experiment runner refuses to write artifacts for mock runs unless it is given `--allow-mock`, and
  the summary script excludes them unless it is given `--include-mock`.

```bash
VERBATIM_ALLOW_MOCK=1 uvicorn app.main:app --reload --app-dir backend
```

## Example requests
```bash
curl -s -X POST http://127.0.0.1:8000/api/conversations/run \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "claude-sonnet-4-6",
    "condition": "baseline",
    "intent_name": "concept_explanation",
    "max_turns": 12
  }'

curl -s http://127.0.0.1:8000/api/conversations/{run_id}

curl -s http://127.0.0.1:8000/api/conversations/metrics

curl -s "http://127.0.0.1:8000/api/conversations/compare?baseline=baseline&candidate=verbatim"
```
