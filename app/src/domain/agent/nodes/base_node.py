# app/src/domain/agent/nodes/base_node.py
# Abstract base class for all nodes in the LangGraph graph.
# Every node must implement __call__ — that is the LangGraph contract.
# Nodes are pure domain logic — no FastAPI, no Anthropic SDK here.

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any

from app.src.domain.models.agent_state import AgentState


class BaseNode(ABC):
    """
    Every LangGraph node is a callable that receives state and returns
    a partial state update. This base class enforces that contract and
    provides shared utilities all nodes need.

    LangGraph calls nodes like this:
        result = node(state)
    
    result is a dict of keys to update on the state — not the full state.
    LangGraph merges it back automatically.
    """

    def __call__(self, state: AgentState) -> dict[str, Any]:
        """
        LangGraph entry point.
        Wraps _run() with iteration tracking and error safety.
        """
        try:
            return self._run(state)
        except Exception as e:
            return {
                "status": "failed",
                "error" : f"{self.__class__.__name__} failed: {str(e)}",
            }

    @abstractmethod
    def _run(self, state: AgentState) -> dict[str, Any]:
        """
        Implement the node logic here.
        Return only the keys you want to update on AgentState.
        LangGraph merges partial updates — you never return the full state.
        """
        ...

    @property
    def name(self) -> str:
        """Node name used in graph edges and logging."""
        return self.__class__.__name__