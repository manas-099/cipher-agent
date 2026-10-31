# app/src/application/chat_service.py
# Use case: conversational interaction on top of AgentService.
# Keeps a bounded in-memory history per session and turns it into agent tasks.
# Session storage is local to this process; swap it for Redis later without
# changing the inbound port.

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.src.exception.exceptions import (
    AgentExecutionError,
    CipherAgentError,
    ConfigurationError,
    InvalidRequestError,
)
from app.src.logger.logger import get_logger
from app.src.ports.inbound.agent_service_port import (
    AgentRequest,
    AgentServicePort,
)
from app.src.ports.inbound.chat_service_port import (
    ChatRequest,
    ChatResponse,
    ChatServicePort,
)

__all__ = ["ChatService"]

Turn = tuple[str, str]


@dataclass
class _Session:
    turns: list[Turn] = field(default_factory=list)
    lock: Any = field(default_factory=threading.Lock, repr=False)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class ChatService(ChatServicePort):
    """
    Multi-turn chat over a stateless agent.

    Each turn is sent to the agent as one task string. Recent turns are
    included as context because CipherAgent currently accepts a single task.

    Usage:
        chat = ChatService(agent_service)
        reply = chat.send(ChatRequest(message="Create a calculator"))
        reply = chat.send(ChatRequest(message="Add tests", session_id=reply.session_id))
    """

    def __init__(
        self,
        agent: AgentServicePort,
        *,
        max_history_turns: int = 20,
        max_sessions: int = 1_000,
    ) -> None:
        if max_history_turns < 0:
            raise ConfigurationError("max_history_turns must be >= 0")
        if max_sessions < 1:
            raise ConfigurationError("max_sessions must be >= 1")

        self._agent = agent
        self._max_history_turns = max_history_turns
        self._max_sessions = max_sessions
        self._sessions: dict[str, _Session] = {}
        self._lock = threading.Lock()
        self._logger = get_logger(__name__)

    # ── ChatServicePort ───────────────────────────────────────────────────────

    def send(self, request: ChatRequest) -> ChatResponse:
        message = (request.message or "").strip()
        if not message:
            raise InvalidRequestError("Message must not be empty.")

        session_id, session = self._get_or_create_session(request.session_id)

        with session.lock:
            history = list(session.turns)
            task = self._build_task(message, history)
            started = time.monotonic()

            self._logger.info(
                "chat_message_received",
                session_id=session_id,
                message_chars=len(message),
                history_turns=len(history),
            )

            try:
                result = self._agent.run(
                    AgentRequest(
                        task=task,
                        metadata={
                            **request.metadata,
                            "session_id": session_id,
                        },
                    )
                )
            except CipherAgentError:
                self._logger.warning(
                    "chat_agent_error",
                    session_id=session_id,
                )
                raise
            except Exception as exc:
                self._logger.exception(
                    "chat_agent_crashed",
                    session_id=session_id,
                    error=str(exc),
                )
                raise AgentExecutionError(
                    f"Chat agent execution failed: {exc}"
                ) from exc

            duration = time.monotonic() - started
            self._append_turns(session, message, result.response)
            turn_count = len(session.turns)

        self._logger.info(
            "chat_message_handled",
            session_id=session_id,
            success=result.success,
            iterations=result.iterations,
            turns=turn_count,
            duration_seconds=round(duration, 3),
        )

        return ChatResponse(
            session_id=session_id,
            success=result.success,
            response=result.response,
            error=result.error,
            iterations=result.iterations,
            files_read=list(result.files_read),
            files_written=list(result.files_written),
            duration_seconds=duration,
        )

    def reset(self, session_id: str) -> None:
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is not None:
            self._logger.info("chat_session_reset", session_id=session_id)

    # ── session storage ───────────────────────────────────────────────────────

    def _get_or_create_session(
        self, session_id: str | None
    ) -> tuple[str, _Session]:
        with self._lock:
            if session_id:
                session = self._sessions.get(session_id)
                if session is None:
                    session = _Session()
                    self._sessions[session_id] = session
                    self._evict_locked()
                return session_id, session

            new_id = uuid.uuid4().hex
            session = _Session()
            self._sessions[new_id] = session
            self._evict_locked()
            return new_id, session

    def _evict_locked(self) -> None:
        while len(self._sessions) > self._max_sessions:
            oldest = min(
                self._sessions,
                key=lambda sid: self._sessions[sid].updated_at,
            )
            self._sessions.pop(oldest, None)
            self._logger.info("chat_session_evicted", session_id=oldest)

    def _append_turns(
        self,
        session: _Session,
        message: str,
        response: str,
    ) -> None:
        session.turns.append(("user", message))
        if response:
            session.turns.append(("assistant", response))

        if self._max_history_turns > 0:
            session.turns = session.turns[-self._max_history_turns:]
        else:
            session.turns = []

        session.updated_at = time.time()

    @staticmethod
    def _build_task(message: str, history: list[Turn]) -> str:
        if not history:
            return message

        lines = ["Previous conversation:"]
        for role, content in history:
            lines.append(f"{role.capitalize()}: {content}")
        lines.append("")
        lines.append("New user message:")
        lines.append(message)
        return "\n".join(lines)
