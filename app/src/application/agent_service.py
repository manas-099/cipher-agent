# app/src/application/agent_service.py
# Use case: build the agent once, then run tasks against it.
# Owns the composition of LLM + tools -> CipherAgent.
# Knows nothing about FastAPI, HTTP, or concrete adapters.

from __future__ import annotations

import time

from app.src.domain.agent.agent import CipherAgent
from app.src.domain.tools.base_tool import BaseTool
from app.src.domain.tools.tool_registry import ToolRegistry
from app.src.exception.exceptions import (
    AgentExecutionError,
    CipherAgentError,
    ConfigurationError,
    InvalidRequestError,
)
from app.src.logger.logger import get_logger
from app.src.ports.inbound.agent_service_port import (
    AgentRequest,
    AgentResponse,
    AgentServicePort,
)
from app.src.ports.outbound.llm_port import LLMPort, ToolSchema

__all__ = ["AgentService"]


class AgentService(AgentServicePort):
    """
    Application use case for a single agent run.

    Usage:
        service = AgentService(llm=llm_adapter, tools=tool_registry)
        result  = service.run(AgentRequest(task="Fix the failing test"))
    """

    def __init__(
        self,
        llm: LLMPort,
        tools: ToolRegistry | dict[str, BaseTool],
        *,
        system_prompt: str = "",
        max_iterations: int = 10,
    ) -> None:
        if max_iterations < 1:
            raise ConfigurationError("max_iterations must be >= 1")

        self._llm = llm
        self._tools = self._normalise_tools(tools)
        self._system_prompt = system_prompt
        self._max_iterations = max_iterations
        self._logger = get_logger(__name__)

        if not self._tools:
            raise ConfigurationError(
                "AgentService requires at least one registered tool."
            )

        invalid = [
            name for name, tool in self._tools.items()
            if not isinstance(tool, BaseTool)
        ]
        if invalid:
            raise ConfigurationError(
                "Invalid tool objects registered: " + ", ".join(sorted(invalid))
            )

        self._register_tool_schemas()

        self._agent = CipherAgent(
            llm=llm,
            tools=self._tools,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
        )

        self._logger.info(
            "agent_service_ready",
            tool_count=len(self._tools),
            tools=sorted(self._tools),
            max_iterations=max_iterations,
        )

    # ── AgentServicePort ──────────────────────────────────────────────────────

    def run(self, request: AgentRequest) -> AgentResponse:
        task = (request.task or "").strip()
        if not task:
            raise InvalidRequestError("Task must not be empty.")

        started = time.monotonic()
        self._logger.info(
            "agent_run_started",
            task_chars=len(task),
            metadata_keys=sorted(request.metadata),
            max_iterations=self._max_iterations,
        )

        try:
            result = self._agent.run(task)
        except CipherAgentError:
            raise
        except Exception as exc:
            self._logger.exception("agent_run_crashed", error=str(exc))
            raise AgentExecutionError(
                f"Agent execution failed: {exc}"
            ) from exc

        duration = time.monotonic() - started

        self._logger.info(
            "agent_run_finished",
            success=result.success,
            iterations=result.iterations,
            duration_seconds=round(duration, 3),
            files_read=len(result.files_read),
            files_written=len(result.files_written),
        )

        return AgentResponse(
            success=result.success,
            response=result.response,
            error=result.error,
            iterations=result.iterations,
            files_read=list(result.files_read),
            files_written=list(result.files_written),
            duration_seconds=duration,
        )

    def health(self) -> bool:
        return self._agent is not None and bool(self._tools)

    # ── helpers ───────────────────────────────────────────────────────────────

    @property
    def tool_names(self) -> list[str]:
        return sorted(self._tools)

    @property
    def max_iterations(self) -> int:
        return self._max_iterations

    @staticmethod
    def _normalise_tools(
        tools: ToolRegistry | dict[str, BaseTool],
    ) -> dict[str, BaseTool]:
        if isinstance(tools, ToolRegistry):
            return tools.get_all()
        return dict(tools)

    def _register_tool_schemas(self) -> None:
        schemas = [
            ToolSchema(
                name=tool.name,
                description=tool.description,
                parameters=tool.args_schema,
            )
            for tool in self._tools.values()
        ]

        register = getattr(self._llm, "register_tools", None)
        if not callable(register):
            self._logger.warning(
                "llm_adapter_cannot_register_tools",
                adapter=type(self._llm).__name__,
                tool_count=len(schemas),
            )
            return

        register(schemas)
