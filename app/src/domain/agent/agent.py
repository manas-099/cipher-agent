# app/src/domain/agent/agent.py
# Entry point for running the agent.
# Wires together: LLMNode + ToolNode + Graph → one run() call.
# Application layer calls agent.run(task) and gets back a string.

from __future__ import annotations
from dataclasses import dataclass, fields
from typing import TYPE_CHECKING

from app.src.domain.agent.nodes.graph_builder import build_graph
from app.src.domain.agent.nodes.llm_node import LLMNode
from app.src.domain.agent.nodes.tool_node import ToolNode
from app.src.domain.models.agent_state import AgentState, AgentStatus

if TYPE_CHECKING:
    from app.src.ports.outbound.llm_port import LLMPort
    from app.src.domain.tools.base_tool import BaseTool


class CipherAgent:
    """
    The agent. One instance per application lifecycle.

    Responsibilities:
      - build the LangGraph graph once at startup
      - accept a task string
      - initialize AgentState
      - invoke the graph
      - return the final response string

    It does NOT know about FastAPI, HTTP, or Anthropic.
    It only knows about ports and domain models.
    """

    def __init__(
        self,
        llm          : LLMPort,
        tools        : dict[str, BaseTool],
        system_prompt: str = "",
        max_iterations: int = 10,
    ) -> None:
        self._llm           = llm
        self._tools         = tools
        self._system_prompt = system_prompt
        self._max_iterations = max_iterations

        # build graph once — reused for every task
        llm_node  = LLMNode(llm=llm)
        tool_node = ToolNode(tools=tools)
        self._graph = build_graph(llm_node, tool_node)

    def run(self, task: str) -> AgentResult:
        """
        Run the agent on a single task.
        Blocks until the agent completes or fails.
        Returns AgentResult — caller never touches AgentState directly.
        """
        initial_state = AgentState.create(
            task          = task,
            system_prompt = self._system_prompt,
        )
        initial_state.max_iterations = self._max_iterations

        # LangGraph .invoke() runs the graph to completion.
        # It returns a plain dict for dataclass schemas, so normalise it back.
        raw_state = self._graph.invoke(initial_state)
        final_state = self._as_agent_state(raw_state)

        return AgentResult.from_state(final_state)

    @staticmethod
    def _as_agent_state(raw_state: object) -> AgentState:
        if isinstance(raw_state, AgentState):
            return raw_state
        if not isinstance(raw_state, dict):
            raise TypeError(
                f"Unexpected graph output type: {type(raw_state).__name__}"
            )
        allowed = {field.name for field in fields(AgentState)}
        return AgentState(
            **{key: value for key, value in raw_state.items() if key in allowed}
        )


# ── result object returned to caller ──────────────────────────────────────────
# keeps application layer decoupled from AgentState internals

@dataclass
class AgentResult:
    success       : bool
    response      : str
    error         : str | None
    iterations    : int
    files_read    : list[str]
    files_written : list[str]

    @classmethod
    def from_state(cls, state: AgentState) -> AgentResult:
        return cls(
            success       = state.status == AgentStatus.COMPLETED,
            response      = state.final_response or "",
            error         = state.error,
            iterations    = state.iteration,
            files_read    = state.files_read,
            files_written = state.files_written,
        )

    @property
    def failed(self) -> bool:
        return not self.success