# app/src/infrastructure/llm/base_llm_adapter.py
# Abstract base class all LLM adapters must inherit.
# Extends LLMPort with infrastructure-level shared behaviour:
#   - logger setup
#   - common retry config
#   - shared token counting heuristic

from __future__ import annotations
from abc import abstractmethod
from typing import Any, Generator

from app.src.domain.models.chat_message import ChatMessage
from app.src.logger.logger import get_logger
from app.src.ports.outbound.llm_port import (
    LLMPort,
    LLMResponse,
    ToolSchema,
)


class BaseLLMAdapter(LLMPort):
    """
    Abstract base for all LLM adapters.

    LLMPort  → defines what domain needs (the contract)
    BaseLLMAdapter → adds shared infrastructure behaviour
    MyLLMAdapter   → concrete implementation for our self-hosted model

    Why this extra layer?
    If you add a second LLM provider later (Groq, OpenRouter),
    they all inherit shared retry logic, logging, token counting
    from here — no code duplication.
    """

    def __init__(self, model_name: str, provider: str) -> None:
        self._model_name = model_name
        self._provider   = provider
        self._logger     = get_logger(self.__class__.__module__)
        self._tool_registry: dict[str, ToolSchema] = {}

    # ── shared across all adapters ────────────────────────────────────────────

    def get_tool_schemas(self) -> list[ToolSchema]:
        """Return all registered tool schemas."""
        return list(self._tool_registry.values())

    def register_tools(self, tools: list[ToolSchema]) -> None:
        """
        Register tool schemas so LLM knows what tools exist.
        Called by application layer at startup.
        """
        for tool in tools:
            self._tool_registry[tool.name] = tool

        self._logger.info(
            "llm_tools_registered",
            provider   = self._provider,
            model      = self._model_name,
            count      = len(tools),
            tool_names = [t.name for t in tools],
        )

    def count_tokens(self, messages: list[ChatMessage]) -> int:
        """
        Estimate token count using character heuristic.
        1 token ≈ 4 characters. No API call — instant.
        Good enough for deciding whether to chunk read a file.
        """
        total_chars = sum(len(msg.content) for msg in messages)
        estimated   = total_chars // 4

        self._logger.debug(
            "token_count_estimated",
            message_count = len(messages),
            total_chars   = total_chars,
            estimated     = estimated,
        )
        return estimated

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def provider(self) -> str:
        return self._provider

    # ── subclass must implement these ─────────────────────────────────────────

    @abstractmethod
    def generate(
        self,
        messages : list[ChatMessage],
        tools    : list[ToolSchema] | None = None,
    ) -> LLMResponse:
        """Send conversation to LLM, get response back."""
        ...

    @abstractmethod
    def stream(
        self,
        messages : list[ChatMessage],
        tools    : list[ToolSchema] | None = None,
    ) -> Generator[str, None, None]:
        """Stream response tokens as they arrive."""
        ...