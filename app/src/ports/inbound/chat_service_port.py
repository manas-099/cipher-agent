# app/src/ports/inbound/chat_service_port.py
# Contract the API uses for conversational, multi-turn interaction.
# Sessions are keyed by an opaque session_id owned by this layer.

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "ChatServicePort",
]


@dataclass(frozen=True)
class ChatRequest:
    """One user message. Omit session_id to start a new conversation."""

    message: str
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChatResponse:
    """Response for one chat turn."""

    session_id: str
    success: bool
    response: str
    error: str | None = None
    iterations: int = 0
    files_read: list[str] = field(default_factory=list)
    files_written: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


class ChatServicePort(ABC):
    """Inbound port for conversational interaction with the agent."""

    @abstractmethod
    def send(self, request: ChatRequest) -> ChatResponse:
        """Send one user message and return the agent's reply."""
        ...

    @abstractmethod
    def reset(self, session_id: str) -> None:
        """Discard the stored history for a session."""
        ...
