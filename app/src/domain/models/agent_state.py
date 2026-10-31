# app/src/domain/models/agent_state.py
# The state object that flows through the LangGraph graph.
# Every node reads from it and writes back to it.
# This IS the working memory for the duration of one task.

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.src.domain.models.chat_message import ChatMessage
from app.src.domain.models.tool_call import ToolCall
from app.src.domain.models.tool_result import ToolResult


class AgentStatus(str, Enum):
    IDLE       = "idle"        # not started
    RUNNING    = "running"     # llm_node or tool_node active
    WAITING    = "waiting"     # waiting for tool results
    COMPLETED  = "completed"   # task finished successfully
    FAILED     = "failed"      # unrecoverable error


@dataclass
class AgentState:
    # ── core conversation ─────────────────────────────────────────────────────
    messages      : list[ChatMessage] = field(default_factory=list)

    # ── tool execution ────────────────────────────────────────────────────────
    tool_calls    : list[ToolCall]   = field(default_factory=list)
    tool_results  : list[ToolResult] = field(default_factory=list)

    # ── task context ──────────────────────────────────────────────────────────
    task          : str = ""           # original user task
    status        : AgentStatus = field(default=AgentStatus.IDLE)
    iteration     : int = 0            # how many llm→tool loops so far
    max_iterations: int = 10           # safety cap to prevent infinite loops

    # ── files touched this session ────────────────────────────────────────────
    files_read    : list[str] = field(default_factory=list)
    files_written : list[str] = field(default_factory=list)

    # ── final response ────────────────────────────────────────────────────────
    final_response: str | None = None
    error         : str | None = None

    # ── metadata ──────────────────────────────────────────────────────────────
    metadata      : dict[str, Any] = field(default_factory=dict)

    # ─────────────────────────────────────────────────────────────────────────
    # helpers
    # ─────────────────────────────────────────────────────────────────────────

    def add_message(self, message: ChatMessage) -> None:
        self.messages.append(message)

    def add_tool_call(self, tool_call: ToolCall) -> None:
        self.tool_calls.append(tool_call)

    def add_tool_result(self, result: ToolResult) -> None:
        self.tool_results.append(result)

    def pending_tool_calls(self) -> list[ToolCall]:
        return [tc for tc in self.tool_calls if tc.is_pending]

    def increment_iteration(self) -> None:
        self.iteration += 1

    def has_reached_limit(self) -> bool:
        return self.iteration >= self.max_iterations

    def mark_completed(self, response: str) -> None:
        self.status         = AgentStatus.COMPLETED
        self.final_response = response

    def mark_failed(self, error: str) -> None:
        self.status = AgentStatus.FAILED
        self.error  = error

    @property
    def is_done(self) -> bool:
        return self.status in (AgentStatus.COMPLETED, AgentStatus.FAILED)

    @classmethod
    def create(cls, task: str, system_prompt: str | None = None) -> AgentState:
        state = cls(task=task, status=AgentStatus.RUNNING)
        if system_prompt:
            state.messages.append(ChatMessage.system(system_prompt))
        state.messages.append(ChatMessage.user(task))
        return state