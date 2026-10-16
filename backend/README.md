# Verbatim Backend

## Install
```bash
pip install -r backend/requirements.txt
```

## Run
```bash
uvicorn app.main:app --reload --app-dir backend
```

## Note on responses
This backend never calls a model. Its only generator is a deterministic mock that echoes the system prompt plus
the user text (with an optional budget fallback), and it counts words, not tokens. It exists for development
and schema wiring.

To keep mock output out of experiment results:
- Runs are refused with HTTP 503 unless the server is started with `VERBATIM_ALLOW_MOCK=1`.
- Every run it records has model `mock-echo` and backend `mock`; the requested model is kept in
  `parameters.requested_model_id`.
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
    "model_id": "claude-sonnet-4-20250514",
    "condition": "baseline",
    "intent_name": "concept_explanation",
    "max_turns": 12
  }'

curl -s http://127.0.0.1:8000/api/conversations/{run_id}

curl -s http://127.0.0.1:8000/api/conversations/metrics

curl -s "http://127.0.0.1:8000/api/conversations/compare?baseline=baseline&candidate=verbatim"
```
