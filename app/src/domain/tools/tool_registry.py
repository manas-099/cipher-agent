# app/src/domain/tools/tool_registry.py
# Central store of all tool instances.
# ToolNode and LLMNode both read from here.
# Register a tool once — everything else picks it up automatically.

from __future__ import annotations
from app.src.domain.tools.base_tool import BaseTool


class ToolRegistry:
    """
    Holds all tool instances keyed by tool name.

    Why a registry and not just a dict?
      - single place to add/remove tools
      - validates no duplicate names
      - provides clean lookup with helpful errors
      - ToolFactory uses it to build instances
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """
        Register a tool instance.
        Raises if a tool with the same name is already registered.
        """
        if tool.name in self._tools:
            raise ValueError(
                f"Tool '{tool.name}' is already registered. "
                f"Each tool name must be unique."
            )
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        """Get tool by name. Raises if not found."""
        if name not in self._tools:
            raise KeyError(
                f"Tool '{name}' not found in registry. "
                f"Available tools: {self.list_names()}"
            )
        return self._tools[name]

    def get_all(self) -> dict[str, BaseTool]:
        """Return all registered tools. Used by ToolNode."""
        return dict(self._tools)

    def list_names(self) -> list[str]:
        """Return sorted list of all registered tool names."""
        return sorted(self._tools.keys())

    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def unregister(self, name: str) -> None:
        """Remove a tool from the registry."""
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found in registry.")
        del self._tools[name]

    def __len__(self) -> int:
        return len(self._tools)

    def __repr__(self) -> str:
        return f"ToolRegistry(tools={self.list_names()})"