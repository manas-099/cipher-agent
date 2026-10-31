# app/src/api/dto/response.py
# HTTP response bodies. Built from inbound-port responses so the API surface
# stays independent of the domain models.

from __future__ import annotations

from pydantic import BaseModel, Field

from app.src.ports.inbound.chat_service_port import ChatResponse

__all__ = ["ChatResponseDTO", "HealthResponseDTO", "ErrorResponseDTO"]


class ChatResponseDTO(BaseModel):
    session_id: str
    success: bool
    response: str
    error: str | None = None
    iterations: int = 0
    files_read: list[str] = Field(default_factory=list)
    files_written: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0

    @classmethod
    def from_domain(cls, response: ChatResponse) -> "ChatResponseDTO":
        return cls(
            session_id=response.session_id,
            success=response.success,
            response=response.response,
            error=response.error,
            iterations=response.iterations,
            files_read=list(response.files_read),
            files_written=list(response.files_written),
            duration_seconds=response.duration_seconds,
        )


class HealthResponseDTO(BaseModel):
    status: str
    version: str
    uptime_seconds: float


class ErrorResponseDTO(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: dict | None = None
    request_id: str | None = None
