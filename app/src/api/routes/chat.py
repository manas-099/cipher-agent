# app/src/api/routes/chat.py
# HTTP adapter for conversational agent interaction.

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from app.src.api.dto.request import ChatRequestDTO, ChatResetRequestDTO
from app.src.api.dto.response import ChatResponseDTO
from app.src.config.api_config import API_ROUTES
from app.src.exception.exceptions import ConfigurationError
from app.src.ports.inbound.chat_service_port import ChatServicePort

__all__ = ["router"]

router = APIRouter(tags=["chat"])


def _chat_service(request: Request) -> ChatServicePort:
    container = getattr(request.app.state, "container", None)
    service = getattr(container, "chat", None)
    if service is None:
        raise ConfigurationError("Chat service is not configured.")
    return service


@router.post(
    API_ROUTES.chat,
    response_model=ChatResponseDTO,
    summary="Send a message to the agent",
)
def chat(body: ChatRequestDTO, request: Request) -> ChatResponseDTO:
    response = _chat_service(request).send(body.to_domain())
    return ChatResponseDTO.from_domain(response)


@router.post(
    f"{API_ROUTES.chat}/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Discard a session's conversation history",
)
def reset_chat(body: ChatResetRequestDTO, request: Request) -> Response:
    _chat_service(request).reset(body.session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
