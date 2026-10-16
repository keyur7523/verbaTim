import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


@pytest.fixture
def session_factory():
    from app.database import Base

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture
def make_client(session_factory):
    """TestClient wired to the in-memory DB and an optional fake Anthropic client."""
    from fastapi.testclient import TestClient

    from app.api.conversations import get_client_factory
    from app.database import get_db, get_session_factory
    from app.main import app

    def _get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def _make(anthropic_client=None):
        app.dependency_overrides[get_db] = _get_db
        app.dependency_overrides[get_session_factory] = lambda: session_factory
        app.dependency_overrides[get_client_factory] = lambda: (lambda: anthropic_client)
        return TestClient(app)

    yield _make
    app.dependency_overrides.clear()


class FakeMessages:
    """Records each messages.create request and returns scripted responses."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    def create(self, **request):
        # Snapshot the history: the service keeps appending to the same list.
        self.requests.append({**request, "messages": list(request["messages"])})
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        return reply


def fake_response(text="A short answer.", input_tokens=100, output_tokens=20, stop_reason="end_turn", thinking=False):
    content = []
    if thinking:
        content.append(SimpleNamespace(type="thinking", thinking="", signature="sig"))
    content.append(SimpleNamespace(type="text", text=text))
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


@pytest.fixture
def fake_client():
    def _make(*replies):
        return SimpleNamespace(messages=FakeMessages(replies or [fake_response()]))

    return _make
