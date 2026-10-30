# app/src/domain/models/chat_message.py
# Represents a single message in the conversation history.
# Role follows OpenAI convention: user | assistant | tool

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MessageRole(str, Enum):
    USER      = "user"
    ASSISTANT = "assistant"
    TOOL      = "tool"
    SYSTEM    = "system"


@dataclass
class ChatMessage:
    role    : MessageRole
    content : str
    
    # only populated for tool result messages
    tool_call_id : str | None = field(default=None)
    
    # raw provider response if needed for debugging
    raw : dict[str, Any] | None = field(default=None, repr=False)

    def is_user(self)      -> bool: return self.role == MessageRole.USER
    def is_assistant(self) -> bool: return self.role == MessageRole.ASSISTANT
    def is_tool(self)      -> bool: return self.role == MessageRole.TOOL
    def is_system(self)    -> bool: return self.role == MessageRole.SYSTEM

    @classmethod
    def user(cls, content: str) -> ChatMessage:
        return cls(role=MessageRole.USER, content=content)

    @classmethod
    def assistant(cls, content: str) -> ChatMessage:
        return cls(role=MessageRole.ASSISTANT, content=content)

    @classmethod
    def tool_result(cls, content: str, tool_call_id: str) -> ChatMessage:
        return cls(
            role         = MessageRole.TOOL,
            content      = content,
            tool_call_id = tool_call_id,
        )

    @classmethod
    def system(cls, content: str) -> ChatMessage:
        return cls(role=MessageRole.SYSTEM, content=content)