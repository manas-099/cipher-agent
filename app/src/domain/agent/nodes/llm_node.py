# app/src/domain/agent/nodes/llm_node.py
# The brain of the agent.
# Calls the LLM with current state, gets back either:
#   a) tool calls  → agent should keep going
#   b) text        → agent is done, return to user

from __future__ import annotations
from typing import Any, TYPE_CHECKING

from app.src.domain.agent.nodes.base_node import BaseNode
from app.src.domain.models.agent_state import AgentState, AgentStatus
from app.src.domain.models.chat_message import ChatMessage
from app.src.domain.models.tool_call import ToolCall

if TYPE_CHECKING:
    from app.src.ports.outbound.llm_port import LLMPort


class LLMNode(BaseNode):
    """
    Sends the current conversation + tool results to the LLM.
    
    Two possible outcomes:
      1. LLM returns tool_calls  → populate state.tool_calls, stay in loop
      2. LLM returns text only   → mark task completed, exit loop

    This node is intentionally thin. It delegates everything to LLMPort
    so the domain never touches the Anthropic SDK directly.
    """

    def __init__(self, llm: LLMPort) -> None:
        self._llm = llm

    def _run(self, state: AgentState) -> dict[str, Any]:

        # safety valve — never loop forever
        if state.has_reached_limit():
            return {
                "status": AgentStatus.FAILED,
                "error" : f"Reached max iterations ({state.max_iterations}). Stopping.",
            }

        # call the LLM with full message history
        response = self._llm.generate(
            messages=state.messages,
            tools   =self._llm.get_tool_schemas(),
        )

        # ── case 1: LLM wants to call tools ──────────────────────────────────
        if response.tool_calls:
            tool_calls = [
                ToolCall.create(
                    tool_name = tc["name"],
                    arguments = tc["arguments"],
                )
                for tc in response.tool_calls
            ]

            # add assistant message so history stays coherent
            assistant_msg = ChatMessage.assistant(
                content=response.content or ""
            )

            return {
                "messages"  : state.messages + [assistant_msg],
                "tool_calls": state.tool_calls + tool_calls,
                "status"    : AgentStatus.WAITING,
                "iteration" : state.iteration + 1,
            }

        # ── case 2: LLM is done, returning final answer ───────────────────────
        final_text = response.content or ""

        return {
            "messages"      : state.messages + [ChatMessage.assistant(final_text)],
            "status"        : AgentStatus.COMPLETED,
            "final_response": final_text,
            "iteration"     : state.iteration + 1,
        }