# app/src/domain/agent/nodes/tool_node.py
# Executes all pending tool calls in parallel using asyncio.
# Fans out to all tools simultaneously, collects results, feeds back to LLM.

from __future__ import annotations
import asyncio
import concurrent.futures
import time
from collections.abc import Coroutine
from typing import Any, TypeVar, TYPE_CHECKING

from app.src.domain.agent.nodes.base_node import BaseNode
from app.src.domain.models.agent_state import AgentState, AgentStatus
from app.src.domain.models.chat_message import ChatMessage
from app.src.domain.models.tool_call import ToolCall, ToolCallStatus
from app.src.domain.models.tool_result import ToolResult

if TYPE_CHECKING:
    from app.src.domain.tools.base_tool import BaseTool

T = TypeVar("T")


def _run_coroutine_sync(coro: Coroutine[Any, Any, T]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


class ToolNode(BaseNode):
    """
    Takes all PENDING tool calls from state and runs them in parallel.

    Parallel execution via asyncio.gather():
      - All tools fire simultaneously
      - Results collected once all complete (or fail)
      - Each result is appended to messages so LLM sees them next iteration

    Why asyncio and not threading?
      File I/O and HTTP calls (read_url) are I/O bound.
      asyncio handles I/O bound concurrency better than threads.
      Docker sandbox calls are also async-friendly.
    """

    def __init__(self, tools: dict[str, BaseTool]) -> None:
        # tool registry: name → tool instance
        # e.g. {"read_file": ReadFileTool(), "grep_search": GrepSearchTool()}
        self._tools = tools

    def _run(self, state: AgentState) -> dict[str, Any]:
        """
        Synchronous entry point required by LangGraph.
        Internally runs the async parallel execution via asyncio.run().
        """
        pending = state.pending_tool_calls()

        if not pending:
            # nothing to run, hand back to LLM
            return {"status": AgentStatus.RUNNING}

        # run all pending tool calls in parallel
        results = _run_coroutine_sync(self._execute_parallel(pending))

        # build tool result messages for LLM history
        tool_messages = [
            ChatMessage.tool_result(
                content      = result.content,
                tool_call_id = result.tool_call_id,
            )
            for result in results
        ]

        # track files the agent has touched
        files_read    = list(state.files_read)
        files_written = list(state.files_written)

        for result in results:
            if result.data:
                if path := result.data.get("path"):
                    if result.tool_name in ("read_file", "list_files", "grep_search", "file_tree"):
                        files_read.append(path)
                    elif result.tool_name in ("create_file", "edit_file", "replace_in_file", "delete_file", "move_file"):
                        files_written.append(path)

        return {
            "messages"     : state.messages + tool_messages,
            "tool_results" : state.tool_results + results,
            "files_read"   : files_read,
            "files_written": files_written,
            "status"       : AgentStatus.RUNNING,
        }

    async def _execute_parallel(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        """
        Fire all tool calls simultaneously with asyncio.gather.
        gather() waits for ALL of them before returning.
        return_exceptions=True means one failure does not cancel the others.
        """
        tasks = [self._execute_one(tc) for tc in tool_calls]
        results: list[ToolResult] = await asyncio.gather(
            *tasks,
            return_exceptions=False,
        )
        return results

    async def _execute_one(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a single tool call safely.
        Any exception becomes a ToolResult.fail() so the LLM
        can see the error and decide what to do next.
        """
        tool_call.mark_running()
        start = time.monotonic()

        tool = self._tools.get(tool_call.tool_name)

        if tool is None:
            tool_call.mark_failed()
            return ToolResult.fail(
                tool_call_id = tool_call.id,
                tool_name    = tool_call.tool_name,
                error        = f"Tool '{tool_call.tool_name}' not found in registry.",
                duration     = time.monotonic() - start,
            )

        try:
            result = await tool.execute(tool_call.arguments)
            tool_call.mark_completed()
            return ToolResult.ok(
                tool_call_id = tool_call.id,
                tool_name    = tool_call.tool_name,
                content      = result.content,
                data         = result.data,
                duration     = time.monotonic() - start,
            )

        except Exception as e:
            tool_call.mark_failed()
            return ToolResult.fail(
                tool_call_id = tool_call.id,
                tool_name    = tool_call.tool_name,
                error        = str(e),
                duration     = time.monotonic() - start,
            )