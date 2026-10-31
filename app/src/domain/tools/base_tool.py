# app/src/domain/tools/base_tool.py
# Abstract base class every tool must inherit.
# Defines the contract: name, description, schema, execute().
# ToolNode calls execute() — never the tool directly.

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ── what a tool returns after execution ───────────────────────────────────────

@dataclass
class ToolOutput:
    """
    Normalised output every tool must return.
    content → string sent back to LLM (must always be present)
    data    → structured data for internal use (optional)
    """
    content : str
    data    : dict[str, Any] | None = field(default=None)

    @classmethod
    def ok(cls, content: str, data: dict[str, Any] | None = None) -> ToolOutput:
        return cls(content=content, data=data)

    @classmethod
    def error(cls, message: str) -> ToolOutput:
        return cls(content=f"ERROR: {message}", data={"error": message})


# ── the base class ────────────────────────────────────────────────────────────

class BaseTool(ABC):
    """
    Every tool in the agent inherits this.

    Three things every tool must define:
      name        → string the LLM uses to call it
      description → what the LLM knows about this tool
      args_schema → JSON schema of what arguments it accepts

    One thing every tool must implement:
      execute()   → async method that does the actual work
    """

    # ── subclass defines these ────────────────────────────────────────────────
    name        : str
    description : str

    @property
    @abstractmethod
    def args_schema(self) -> dict[str, Any]:
        """
        JSON Schema describing the tool's input arguments.
        Sent to the LLM so it knows what to pass when calling this tool.

        Example:
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "file path to read"},
            },
            "required": ["path"]
        }
        """
        ...

    @abstractmethod
    async def execute(self, args: dict[str, Any]) -> ToolOutput:
        """
        Run the tool with the given arguments.
        Always async — ToolNode runs tools in parallel via asyncio.gather().
        Never raises — catch exceptions and return ToolOutput.error() instead.
        """
        ...

    def to_schema(self) -> dict[str, Any]:
        """
        Build the full tool schema sent to the LLM.
        LLMPort.get_tool_schemas() calls this on every registered tool.
        """
        return {
            "name"       : self.name,
            "description": self.description,
            "input_schema": self.args_schema,
        }

    def _validate_required(
        self,
        args     : dict[str, Any],
        required : list[str],
    ) -> str | None:
        """
        Check required args are present.
        Returns error message if missing, None if all present.
        """
        missing = [k for k in required if k not in args or args[k] is None]
        if missing:
            return f"Missing required arguments: {', '.join(missing)}"
        return None