# app/src/api/dto/request.py
# HTTP request bodies. These are transport objects only — they are converted
# into inbound-port requests before reaching the application layer.

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.src.ports.inbound.chat_service_port import ChatRequest

__all__ = ["ChatRequestDTO", "ChatResetRequestDTO"]


class ChatRequestDTO(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=100_000,
        description="User message for the agent.",
    )
    session_id: str | None = Field(
        default=None,
        max_length=128,
        description="Omit to start a new conversation.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_domain(self) -> ChatRequest:
        return ChatRequest(
            message=self.message,
            session_id=self.session_id,
            metadata=dict(self.metadata),
        )


class ChatResetRequestDTO(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
