import pytest

from app.models import ConversationRun
from app.services.conversation_service import (
    ALLOW_MOCK_ENV,
    MOCK_MODEL_ID,
    MockNotAllowedError,
    run_conversation,
)


MOCK_REQUEST = {
    "condition": "baseline",
    "model": {"model_id": MOCK_MODEL_ID, "max_tokens": 512},
    "intent_id": "concept_explanation",
    "max_turns": 12,
}


def test_service_refuses_mock_without_flag(session_factory, monkeypatch):
    monkeypatch.delenv(ALLOW_MOCK_ENV, raising=False)
    db = session_factory()
    with pytest.raises(MockNotAllowedError):
        run_conversation(db=db, model_id=MOCK_MODEL_ID, condition="baseline", intent_name="concept_explanation")
    assert db.query(ConversationRun).count() == 0


def test_service_stamps_mock_run_with_flag(session_factory, monkeypatch):
    monkeypatch.setenv(ALLOW_MOCK_ENV, "1")
    run = run_conversation(db=session_factory(), model_id=MOCK_MODEL_ID, condition="baseline",
                           intent_name="concept_explanation", max_tokens=512)
    assert run.model == MOCK_MODEL_ID
    assert run.parameters["backend"] == "mock"
    assert run.parameters["max_tokens"] == 512
    assert run.parameters["length_unit"] == "words"


def test_api_returns_503_for_mock_without_flag(make_client, monkeypatch):
    monkeypatch.delenv(ALLOW_MOCK_ENV, raising=False)
    response = make_client().post("/api/conversations/run", json=MOCK_REQUEST)
    assert response.status_code == 503
    assert ALLOW_MOCK_ENV in response.json()["detail"]


def test_api_detail_reports_mock_backend_with_flag(make_client, monkeypatch):
    monkeypatch.setenv(ALLOW_MOCK_ENV, "1")
    client = make_client()
    run_id = client.post("/api/conversations/run", json=MOCK_REQUEST).json()["run_id"]
    detail = client.get(f"/api/conversations/{run_id}").json()
    assert detail["status"] == "completed"
    assert detail["model_id"] == MOCK_MODEL_ID
    assert detail["backend"] == "mock"
    assert detail["intent_id"] == "concept_explanation"


def test_service_checks_instruction_specs_per_turn(session_factory, monkeypatch):
    monkeypatch.setenv(ALLOW_MOCK_ENV, "1")
    run = run_conversation(db=session_factory(), model_id=MOCK_MODEL_ID, condition="naive",
                           intent_name="concept_explanation")
    adherence = next(r for r in run.evaluator_results if r.evaluator_name == "instruction_adherence")
    # concept_explanation has 3 checkable turns; the multi-line mock echo fails the one-line recap.
    assert adherence.details["checked_turns"] == 3
    assert adherence.passed is False
    names = {r.evaluator_name for r in run.evaluator_results}
    assert {"unsupported_claim_proxy", "refusal_keyword_proxy"} <= names
    assert not names & {"hallucination_proxy", "refusal_proxy"}
