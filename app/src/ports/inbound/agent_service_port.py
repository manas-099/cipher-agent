# app/src/ports/inbound/agent_service_port.py
# Contract the API uses to trigger one agent run.
# The application layer implements it; adapters never see CipherAgent directly.

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "AgentRequest",
    "AgentResponse",
    "AgentServicePort",
]


@dataclass(frozen=True)
class AgentRequest:
    """A single task for the agent."""

    task: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentResponse:
    """Normalised result of one agent run."""

    success: bool
    response: str
    error: str | None = None
    iterations: int = 0
    files_read: list[str] = field(default_factory=list)
    files_written: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


class AgentServicePort(ABC):
    """Inbound port for running the agent."""

    @abstractmethod
    def run(self, request: AgentRequest) -> AgentResponse:
        """Execute a task to completion and return the final response."""
        ...

    @abstractmethod
    def health(self) -> bool:
        """Return True when the service is ready to accept tasks."""
        ...
