# app/src/domain/models/tool_call.py
# Represents a single tool call decision made by the LLM.
# LLM node produces these → tool node consumes these.

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import uuid


class ToolCallStatus(str, Enum):
    PENDING   = "pending"    # LLM requested it, not yet run
    RUNNING   = "running"    # currently executing
    COMPLETED = "completed"  # finished successfully
    FAILED    = "failed"     # raised an error


@dataclass
class ToolCall:
    tool_name : str
    arguments : dict[str, Any]

    # auto-generated unique ID ties this call to its result
    id     : str            = field(default_factory=lambda: str(uuid.uuid4()))
    status : ToolCallStatus = field(default=ToolCallStatus.PENDING)

    def mark_running(self)   -> None: self.status = ToolCallStatus.RUNNING
    def mark_completed(self) -> None: self.status = ToolCallStatus.COMPLETED
    def mark_failed(self)    -> None: self.status = ToolCallStatus.FAILED

    @property
    def is_pending(self)   -> bool: return self.status == ToolCallStatus.PENDING
    @property
    def is_running(self)   -> bool: return self.status == ToolCallStatus.RUNNING
    @property
    def is_completed(self) -> bool: return self.status == ToolCallStatus.COMPLETED
    @property
    def is_failed(self)    -> bool: return self.status == ToolCallStatus.FAILED

    @classmethod
    def create(
        cls,
        tool_name : str,
        arguments : dict[str, Any],
        id        : str | None = None,
    ) -> ToolCall:
        return cls(
            tool_name = tool_name,
            arguments = arguments,
            id        = id or str(uuid.uuid4()),
        )