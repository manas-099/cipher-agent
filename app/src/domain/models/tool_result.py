# app/src/domain/models/tool_result.py
# Represents the output of a single tool execution.
# Tool node produces these → LLM node reads these next iteration.

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    tool_call_id : str           # ties back to ToolCall.id
    tool_name    : str
    content      : str           # string output sent back to LLM
    success      : bool

    # structured data if tool returns more than a string
    data         : dict[str, Any] | None = field(default=None)

    # error message if success=False
    error        : str | None = field(default=None)

    # execution time in seconds
    duration_seconds : float = field(default=0.0)

    @classmethod
    def ok(
        cls,
        tool_call_id : str,
        tool_name    : str,
        content      : str,
        data         : dict[str, Any] | None = None,
        duration     : float = 0.0,
    ) -> ToolResult:
        return cls(
            tool_call_id     = tool_call_id,
            tool_name        = tool_name,
            content          = content,
            success          = True,
            data             = data,
            duration_seconds = duration,
        )

    @classmethod
    def fail(
        cls,
        tool_call_id : str,
        tool_name    : str,
        error        : str,
        duration     : float = 0.0,
    ) -> ToolResult:
        return cls(
            tool_call_id     = tool_call_id,
            tool_name        = tool_name,
            content          = f"ERROR: {error}",
            success          = False,
            error            = error,
            duration_seconds = duration,
        )

    @property
    def failed(self) -> bool:
        return not self.success