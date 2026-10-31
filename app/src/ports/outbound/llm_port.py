# app/src/ports/outbound/llm_port.py
# Contract that any LLM provider must fulfill.
# Domain calls this — never the Anthropic SDK directly.
# AnthropicAdapter, OpenAIAdapter both implement this.

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.src.domain.models.chat_message import ChatMessage


# ── what the LLM returns ──────────────────────────────────────────────────────

@dataclass
class LLMResponse:
    """
    Normalised response from any LLM provider.
    Adapter converts provider-specific response into this.
    Domain only ever sees LLMResponse — never raw Anthropic/OpenAI objects.
    """
    content    : str                    # text response from LLM
    tool_calls : list[dict[str, Any]]   # list of {name, arguments} dicts
    model      : str                    # which model actually ran
    usage      : TokenUsage | None = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    @property
    def is_final_answer(self) -> bool:
        return not self.has_tool_calls and bool(self.content)


@dataclass
class TokenUsage:
    """Token consumption for cost tracking."""
    input_tokens  : int = 0
    output_tokens : int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


# ── what a tool schema looks like when sent to LLM ───────────────────────────

@dataclass(frozen=True)
class ToolSchema:
    """
    JSON schema description of a tool sent to the LLM.
    LLM reads this to know what tools exist and what args they take.
    """
    name        : str
    description : str
    parameters  : dict[str, Any]   # JSON Schema object


# ── the port ──────────────────────────────────────────────────────────────────

class LLMPort(ABC):
    """
    Contract for any LLM provider.

    Two responsibilities:
      1. generate() — send messages + tools, get response back
      2. get_tool_schemas() — return schemas of all registered tools
    """

    @abstractmethod
    def generate(
        self,
        messages : list[ChatMessage],
        tools    : list[ToolSchema] | None = None,
    ) -> LLMResponse:
        """
        Send conversation history to LLM, get response.

        Args:
            messages : full conversation so far
            tools    : tool schemas LLM can choose from

        Returns:
            LLMResponse with either tool_calls or content
        """
        ...

    @abstractmethod
    def get_tool_schemas(self) -> list[ToolSchema]:
        """
        Return JSON schemas for all tools available to the LLM.
        Called by LLMNode before every generate() call.
        """
        ...

    @abstractmethod
    def count_tokens(self, messages: list[ChatMessage]) -> int:
        """
        Estimate token count for a list of messages.
        Used before generate() to check context window limits.
        """
        ...