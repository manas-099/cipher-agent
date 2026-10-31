# app/src/domain/tools/tool_factory.py
# Builds and wires all tool instances with their port dependencies.
# Application layer calls this once at startup.
# Nothing else ever imports concrete tool classes directly.

from __future__ import annotations
from typing import TYPE_CHECKING

from app.src.domain.tools.tool_registry import ToolRegistry
from app.src.domain.tools.file_tools import (
    ListFilesTool, ReadFileTool, CreateFileTool, EditFileTool,
    ReplaceInFileTool, DeleteFileTool, MoveFileTool, CopyFileTool,
    GetFileInfoTool, CreateFolderTool, DeleteFolderTool,
)
from app.src.domain.tools.search_tools import (
    GrepSearchTool, FileTreeTool, FindAndReplaceAllTool,
)
from app.src.domain.tools.execution_tools import (
    RunCodeTool, RunCommandTool, RunTestsTool, LintCodeTool, InstallPackageTool,
)
from app.src.domain.tools.web_tools import ReadUrlTool
from app.src.domain.tools.utility_tools import CountTokensTool

if TYPE_CHECKING:
    from app.src.ports.outbound.filesystem_port import FilesystemPort
    from app.src.ports.outbound.sandbox_port import SandboxPort
    from app.src.ports.outbound.llm_port import LLMPort


class ToolFactory:
    """
    Wires all tools with their port dependencies and registers them.

    Called once at application startup:
        factory  = ToolFactory(fs=fs_adapter, sandbox=sandbox_adapter, llm=llm_adapter)
        registry = factory.build()

    Returns a populated ToolRegistry ready for ToolNode and LLMNode.
    """

    def __init__(
        self,
        fs      : FilesystemPort,
        sandbox : SandboxPort,
        llm     : LLMPort,
    ) -> None:
        self._fs      = fs
        self._sandbox = sandbox
        self._llm     = llm

    def build(self) -> ToolRegistry:
        """
        Create every tool instance and register it.
        Order does not matter — registry is keyed by name.
        """
        registry = ToolRegistry()

        # ── file tools ────────────────────────────────────────────────────────
        registry.register(ListFilesTool(self._fs))
        registry.register(ReadFileTool(self._fs))
        registry.register(CreateFileTool(self._fs))
        registry.register(EditFileTool(self._fs))
        registry.register(ReplaceInFileTool(self._fs))
        registry.register(DeleteFileTool(self._fs))
        registry.register(MoveFileTool(self._fs))
        registry.register(CopyFileTool(self._fs))
        registry.register(GetFileInfoTool(self._fs))

        # ── folder tools ──────────────────────────────────────────────────────
        registry.register(CreateFolderTool(self._fs))
        registry.register(DeleteFolderTool(self._fs))

        # ── search tools ──────────────────────────────────────────────────────
        registry.register(GrepSearchTool(self._fs))
        registry.register(FileTreeTool(self._fs))
        registry.register(FindAndReplaceAllTool(self._fs))

        # ── execution tools ───────────────────────────────────────────────────
        registry.register(RunCodeTool(self._sandbox))
        registry.register(RunCommandTool(self._sandbox))
        registry.register(RunTestsTool(self._sandbox))
        registry.register(LintCodeTool(self._sandbox))
        registry.register(InstallPackageTool(self._sandbox))

        # ── web tools ─────────────────────────────────────────────────────────
        registry.register(ReadUrlTool())

        # ── utility tools ─────────────────────────────────────────────────────
        registry.register(CountTokensTool(self._llm))

        return registry