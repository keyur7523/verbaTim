import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ConversationRun  # noqa: E402
from app.services.conversation_service import (  # noqa: E402
    ALLOW_MOCK_ENV,
    MOCK_MODEL_ID,
    MockNotAllowedError,
    run_conversation,
)


RUN_REQUEST = {
    "condition": "baseline",
    "model": {"model_id": "claude-sonnet-4-20250514", "temperature": 0.2, "max_tokens": 512},
    "intent_id": "concept_explanation",
    "max_turns": 12,
}


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture
def client(session_factory):
    def _get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_service_refuses_without_flag(session_factory, monkeypatch):
    monkeypatch.delenv(ALLOW_MOCK_ENV, raising=False)
    db = session_factory()
    with pytest.raises(MockNotAllowedError):
        run_conversation(db=db, model_id="claude-sonnet-4-20250514", condition="baseline",
                         intent_name="concept_explanation")
    assert db.query(ConversationRun).count() == 0


def test_service_stamps_mock_model_with_flag(session_factory, monkeypatch):
    monkeypatch.setenv(ALLOW_MOCK_ENV, "1")
    run = run_conversation(db=session_factory(), model_id="claude-sonnet-4-20250514",
                           condition="baseline", intent_name="concept_explanation", max_tokens=512)
    assert run.model == MOCK_MODEL_ID
    assert run.parameters["backend"] == "mock"
    assert run.parameters["requested_model_id"] == "claude-sonnet-4-20250514"
    assert run.parameters["max_tokens"] == 512


def test_api_returns_503_without_flag(client, monkeypatch):
    monkeypatch.delenv(ALLOW_MOCK_ENV, raising=False)
    response = client.post("/api/conversations/run", json=RUN_REQUEST)
    assert response.status_code == 503
    assert ALLOW_MOCK_ENV in response.json()["detail"]


def test_api_detail_reports_mock_backend_with_flag(client, monkeypatch):
    monkeypatch.setenv(ALLOW_MOCK_ENV, "1")
    run_id = client.post("/api/conversations/run", json=RUN_REQUEST).json()["run_id"]
    detail = client.get(f"/api/conversations/{run_id}").json()
    assert detail["model_id"] == MOCK_MODEL_ID
    assert detail["backend"] == "mock"
    assert detail["intent_id"] == "concept_explanation"
    assert detail["parameters"]["temperature"] == 0.2


def test_service_checks_instruction_specs_per_turn(session_factory, monkeypatch):
    monkeypatch.setenv(ALLOW_MOCK_ENV, "1")
    db = session_factory()
    run = run_conversation(db=db, model_id="claude-sonnet-4-20250514", condition="naive",
                           intent_name="concept_explanation")
    adherence = next(r for r in run.evaluator_results if r.evaluator_name == "instruction_adherence")
    # concept_explanation has 3 checkable turns; the multi-line mock echo fails the one-line recap.
    assert adherence.details["checked_turns"] == 3
    assert adherence.passed is False
