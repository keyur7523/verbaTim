import pytest
from conftest import fake_response

from app.services.conversation_service import RunConfigError, run_conversation


MODEL = "claude-sonnet-4-6"


def _run(session_factory, client, **overrides):
    kwargs = {
        "model_id": MODEL,
        "condition": "baseline",
        "intent_name": "concept_explanation",
        "max_tokens": 1024,
        "client_factory": lambda: client,
        **overrides,
    }
    return run_conversation(db=session_factory(), **kwargs)


def test_resends_growing_history_with_system_prompt(session_factory, fake_client):
    client = fake_client()
    run = _run(session_factory, client)
    requests = client.messages.requests
    assert run.status.value == "completed"
    assert len(requests) == 12
    assert requests[0]["system"].startswith("You are a helpful assistant.")
    assert [len(r["messages"]) for r in requests] == [1 + 2 * i for i in range(12)]
    assert requests[1]["messages"][0] == {"role": "user", "content": "Explain what a hash table is and when to use it."}
    assert requests[1]["messages"][1]["role"] == "assistant"
    assert all(r["model"] == MODEL and r["max_tokens"] == 1024 for r in requests)


def test_temperature_sent_only_when_given(session_factory, fake_client):
    with_temp = fake_client()
    _run(session_factory, with_temp, temperature=0.2)
    assert with_temp.messages.requests[0]["temperature"] == 0.2

    without = fake_client()
    _run(session_factory, without)
    assert "temperature" not in without.messages.requests[0]


def test_records_provider_tokens_cost_and_backend(session_factory, fake_client):
    client = fake_client(fake_response(input_tokens=1000, output_tokens=200))
    run = _run(session_factory, client)
    turn = run.turns[0]
    assert (turn.input_tokens, turn.output_tokens) == (1000, 200)
    # Sonnet 4.6: $3 / $15 per million input / output tokens.
    assert turn.cost_usd == pytest.approx(1000 * 3e-6 + 200 * 15e-6)
    assert run.total_cost_usd == pytest.approx(12 * turn.cost_usd)
    assert run.model == MODEL
    assert run.parameters["backend"] == "anthropic"
    assert run.parameters["length_unit"] == "provider_tokens"


def test_thinking_responses_are_labelled_so_they_are_never_pooled(session_factory, fake_client):
    client = fake_client(fake_response(thinking=True))
    run = _run(session_factory, client, model_id="claude-opus-5-5")
    assert run.parameters["length_unit"] == "provider_tokens_incl_thinking"
    # Thinking blocks go back unchanged in the history.
    assistant = client.messages.requests[1]["messages"][1]["content"]
    assert [block.type for block in assistant] == ["thinking", "text"]


def test_truncated_turns_are_recorded(session_factory, fake_client):
    client = fake_client(fake_response(stop_reason="max_tokens"), fake_response())
    run = _run(session_factory, client)
    verbosity = next(r for r in run.evaluator_results if r.evaluator_name == "verbosity_stability")
    assert verbosity.details["truncated_turns"] == [0]
    assert verbosity.details["turn_stop_reasons"][1] == "end_turn"


def test_api_error_marks_run_failed_with_message(session_factory, fake_client):
    client = fake_client(fake_response(), RuntimeError("rate limited"))
    run = _run(session_factory, client)
    assert run.status.value == "failed"
    assert run.error_message == "RuntimeError: rate limited"
    assert run.completed_count == 1


def test_unknown_model_rejected(session_factory, fake_client):
    with pytest.raises(RunConfigError, match="Unknown model"):
        _run(session_factory, fake_client(), model_id="claude-3-5-sonnet-20241022")


def test_temperature_rejected_for_models_that_do_not_accept_it(session_factory, fake_client):
    with pytest.raises(RunConfigError, match="rejects the temperature"):
        _run(session_factory, fake_client(), model_id="claude-opus-5-5", temperature=0.2)


def test_api_runs_in_background_and_reports_completion(make_client, fake_client):
    client = make_client(fake_client())
    response = client.post("/api/conversations/run", json={
        "condition": "naive",
        "model": {"model_id": MODEL, "max_tokens": 1024},
        "intent_id": "concept_explanation",
        "max_turns": 12,
    })
    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    detail = client.get(f"/api/conversations/{response.json()['run_id']}").json()
    assert detail["status"] == "completed"
    assert detail["backend"] == "anthropic"
    assert len(detail["turns"]) == 12


def test_api_returns_422_for_unsupported_temperature(make_client, fake_client):
    response = make_client(fake_client()).post("/api/conversations/run", json={
        "condition": "naive",
        "model": {"model_id": "claude-opus-5-5", "temperature": 0.2},
        "intent_id": "concept_explanation",
        "max_turns": 12,
    })
    assert response.status_code == 422
