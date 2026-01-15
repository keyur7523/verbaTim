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
This backend uses a deterministic mock generator (system prompt + user text, with optional budget fallback).
It does not call external LLM services. This keeps the backend local-only but means assistant responses are
mocked for development and schema wiring.

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
