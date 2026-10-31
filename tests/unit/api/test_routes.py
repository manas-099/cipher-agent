# tests/unit/api/test_routes.py

from __future__ import annotations

from fastapi.testclient import TestClient

from app.src.config.api_config import API_ROUTES
from app.src.exception.exceptions import InvalidRequestError
from app.src.main import AppContainer, create_app
from app.src.ports.inbound.agent_service_port import (
    AgentRequest,
    AgentResponse,
    AgentServicePort,
)
from app.src.ports.inbound.chat_service_port import (
    ChatRequest,
    ChatResponse,
    ChatServicePort,
)


class FakeAgent(AgentServicePort):
    def __init__(self, healthy: bool = True) -> None:
        self._healthy = healthy

    def run(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(
            success=True,
            response=f"done: {request.task}",
            iterations=1,
        )

    def health(self) -> bool:
        return self._healthy


class FakeChat(ChatServicePort):
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.reset_ids: list[str] = []

    def send(self, request: ChatRequest) -> ChatResponse:
        if request.message == "explode":
            raise InvalidRequestError("Message rejected.", details={"field": "message"})
        self.messages.append(request.message)
        return ChatResponse(
            session_id=request.session_id or "generated-session",
            success=True,
            response=f"echo: {request.message}",
            iterations=2,
            files_read=["a.py"],
            files_written=["b.py"],
            duration_seconds=0.5,
        )

    def reset(self, session_id: str) -> None:
        self.reset_ids.append(session_id)


def _client(agent: FakeAgent | None = None, chat: FakeChat | None = None) -> tuple[TestClient, FakeChat]:
    chat = chat or FakeChat()
    container = AppContainer(agent=agent or FakeAgent(), chat=chat)
    return TestClient(create_app(container)), chat


def test_health_ok() -> None:
    client, _ = _client()
    response = client.get(f"{API_ROUTES.prefix}{API_ROUTES.health}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]
    assert body["uptime_seconds"] >= 0


def test_health_degraded() -> None:
    client, _ = _client(agent=FakeAgent(healthy=False))
    response = client.get(f"{API_ROUTES.prefix}{API_ROUTES.health}")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


def test_chat_success() -> None:
    client, chat = _client()
    response = client.post(
        f"{API_ROUTES.prefix}{API_ROUTES.chat}",
        json={"message": "hi"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "generated-session"
    assert body["response"] == "echo: hi"
    assert body["files_read"] == ["a.py"]
    assert body["files_written"] == ["b.py"]
    assert chat.messages == ["hi"]


def test_chat_passes_session_id() -> None:
    client, _ = _client()
    response = client.post(
        f"{API_ROUTES.prefix}{API_ROUTES.chat}",
        json={"message": "hi", "session_id": "s-1"},
    )
    assert response.status_code == 200
    assert response.json()["session_id"] == "s-1"


def test_chat_empty_message_is_rejected() -> None:
    client, chat = _client()
    response = client.post(
        f"{API_ROUTES.prefix}{API_ROUTES.chat}",
        json={"message": ""},
    )
    assert response.status_code == 422
    assert chat.messages == []


def test_chat_missing_message_is_rejected() -> None:
    client, _ = _client()
    response = client.post(
        f"{API_ROUTES.prefix}{API_ROUTES.chat}",
        json={},
    )
    assert response.status_code == 422


def test_chat_maps_application_error() -> None:
    client, _ = _client()
    response = client.post(
        f"{API_ROUTES.prefix}{API_ROUTES.chat}",
        json={"message": "explode"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "invalid_request"
    assert body["error"]["message"] == "Message rejected."
    assert body["error"]["details"] == {"field": "message"}
    assert body["request_id"]


def test_chat_reset() -> None:
    client, chat = _client()
    response = client.post(
        f"{API_ROUTES.prefix}{API_ROUTES.chat}/reset",
        json={"session_id": "s-9"},
    )
    assert response.status_code == 204
    assert chat.reset_ids == ["s-9"]


def test_request_id_header_is_echoed() -> None:
    client, _ = _client()
    response = client.get(
        f"{API_ROUTES.prefix}{API_ROUTES.health}",
        headers={"X-Request-ID": "req-123"},
    )
    assert response.headers["X-Request-ID"] == "req-123"


def test_request_id_header_is_generated() -> None:
    client, _ = _client()
    response = client.get(f"{API_ROUTES.prefix}{API_ROUTES.health}")
    assert response.headers["X-Request-ID"]
