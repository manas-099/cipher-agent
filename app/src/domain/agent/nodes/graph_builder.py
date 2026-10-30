# app/src/domain/agent/graph_builder.py
# Wires llm_node and tool_node into a LangGraph StateGraph.
# The graph defines the loop: LLM → Tools → LLM → Tools → ... → END

from __future__ import annotations
from typing import TYPE_CHECKING

from langgraph.graph import StateGraph, END

from app.src.domain.models.agent_state import AgentState, AgentStatus
from app.src.domain.agent.nodes.llm_node import LLMNode
from app.src.domain.agent.nodes.tool_node import ToolNode

if TYPE_CHECKING:
    pass

# ── node name constants ────────────────────────────────────────────────────────
# string literals in graph edges are a footgun — define them once here
LLM_NODE  = "llm_node"
TOOL_NODE = "tool_node"


def _route_after_llm(state: AgentState) -> str:
    """
    Conditional edge function — called after every LLM node execution.
    Decides: keep looping or stop?

    LangGraph calls this with the current state and routes to whichever
    node name (or END) this function returns.

    Routing logic:
      COMPLETED → END   (LLM gave final answer, we are done)
      FAILED    → END   (something broke, surface the error)
      WAITING   → tools (LLM requested tool calls, go execute them)
      anything else → tools (default: keep going)
    """
    if state.status in (AgentStatus.COMPLETED, AgentStatus.FAILED):
        return END
    if state.status == AgentStatus.WAITING:
        return TOOL_NODE
    return TOOL_NODE


def _route_after_tools(state: AgentState) -> str:
    """
    Conditional edge after tool execution.
    Tools always hand back to LLM — LLM decides what to do with results.
    Only exit if something catastrophically failed.
    """
    if state.status == AgentStatus.FAILED:
        return END
    return LLM_NODE


def build_graph(
    llm_node  : LLMNode,
    tool_node : ToolNode,
) -> StateGraph:
    """
    Factory function — builds and compiles the LangGraph graph.

    Graph shape:
        START → llm_node
        llm_node → [tool_node | END]   (conditional)
        tool_node → [llm_node | END]   (conditional)

    StateGraph(AgentState) tells LangGraph what the state schema is.
    LangGraph uses it to know which keys to track and merge.
    """
    graph = StateGraph(AgentState)

    # ── register nodes ────────────────────────────────────────────────────────
    graph.add_node(LLM_NODE,  llm_node)
    graph.add_node(TOOL_NODE, tool_node)

    # ── entry point ───────────────────────────────────────────────────────────
    graph.set_entry_point(LLM_NODE)

    # ── conditional edges ─────────────────────────────────────────────────────
    graph.add_conditional_edges(
        source   = LLM_NODE,
        path     = _route_after_llm,
        path_map = {
            TOOL_NODE: TOOL_NODE,
            END      : END,
        },
    )

    graph.add_conditional_edges(
        source   = TOOL_NODE,
        path     = _route_after_tools,
        path_map = {
            LLM_NODE: LLM_NODE,
            END     : END,
        },
    )

    return graph.compile()