import json
from pathlib import Path

from verbatim.experiments.run_conversations import (
    REQUIRED_RUN_FIELDS,
    build_run_metadata,
    is_mock_run,
    write_artifacts,
)


REQUESTED = {
    "run_id": "abc",
    "model": "claude-sonnet-4-20250514",
    "backend": "probekit-api",
    "intent_id": "concept_explanation",
    "condition": "budgeted",
    "temperature": 0.2,
    "token_budget": 120,
    "max_tokens": 512,
    "timestamp": "2026-10-16T00:00:00Z",
}

# Shape returned by the local backend's GET /api/conversations/{run_id}.
LOCAL_BACKEND_RUN = {
    "run_id": "abc",
    "condition": "budgeted",
    "model_id": "mock-echo",
    "backend": "mock",
    "intent_id": "concept_explanation",
    "parameters": {"backend": "mock", "temperature": 0.2},
    "error": None,
    "status": "completed",
    "created_at": "2026-10-16T00:00:01",
    "turns": [],
    "evaluator_results": [],
}

# Shape of the ProbeKit API responses behind the committed real runs.
PROBEKIT_RUN = {
    "id": "abc",
    "condition": "budgeted",
    "model": "claude-sonnet-4-20250514",
    "timestamp": "2026-10-16T00:00:01",
    "status": "completed",
    "turns": [],
    "evaluator_results": [],
}


def test_local_backend_response_is_labelled_mock():
    metadata = build_run_metadata(LOCAL_BACKEND_RUN, REQUESTED)
    assert metadata["model"] == "mock-echo"
    assert metadata["backend"] == "mock"
    assert is_mock_run(metadata)


def test_probekit_response_keeps_requested_metadata():
    metadata = build_run_metadata(PROBEKIT_RUN, REQUESTED)
    assert metadata["model"] == "claude-sonnet-4-20250514"
    assert metadata["backend"] == "probekit-api"
    assert metadata["intent_id"] == "concept_explanation"
    assert not is_mock_run(metadata)


def test_written_artifact_has_every_required_field(tmp_path: Path):
    metadata = build_run_metadata(PROBEKIT_RUN, REQUESTED)
    write_artifacts(PROBEKIT_RUN, tmp_path, metadata)
    payload = json.loads((tmp_path / "aggregate_metrics.json").read_text(encoding="utf-8"))
    for field in REQUIRED_RUN_FIELDS:
        assert field in payload, field
        if field != "error":
            assert payload[field] is not None, field


def test_length_unit_is_words_for_mock_and_provider_tokens_otherwise():
    assert build_run_metadata(LOCAL_BACKEND_RUN, REQUESTED)["length_unit"] == "words"
    assert build_run_metadata(PROBEKIT_RUN, REQUESTED)["length_unit"] == "provider_tokens"


def test_server_reported_length_unit_wins():
    run = {**PROBEKIT_RUN, "parameters": {"length_unit": "words"}}
    assert build_run_metadata(run, REQUESTED)["length_unit"] == "words"
