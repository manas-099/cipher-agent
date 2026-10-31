# app/src/domain/tools/utility_tools.py
# Utility tools — 1 tool.
# count_tokens uses LLMPort to estimate tokens without an API call.

from __future__ import annotations
from typing import Any, TYPE_CHECKING

from app.src.domain.tools.base_tool import BaseTool, ToolOutput

if TYPE_CHECKING:
    from app.src.ports.outbound.llm_port import LLMPort


class CountTokensTool(BaseTool):
    name        = "count_tokens"
    description = (
        "Estimate token count for a string or file without making an API call. "
        "Use before reading a large file to check if it fits in context. "
        "Check fits_in_context — if False, use read_file with offset and limit."
    )

    def __init__(self, llm: LLMPort) -> None:
        self._llm = llm

    @property
    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content"  : {"type": "string", "description": "Raw text to count tokens for"},
                "file_path": {"type": "string", "description": "Path to file to count tokens for"},
                "model"    : {"type": "string", "description": "Model name for context window comparison (default: current model)"},
            },
        }

    async def execute(self, args: dict[str, Any]) -> ToolOutput:
        content   = args.get("content")
        file_path = args.get("file_path")

        if not content and not file_path:
            return ToolOutput.error("Provide either 'content' or 'file_path'.")

        try:
            # read file if path given
            if file_path and not content:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

            # heuristic: 1 token ≈ 4 characters
            token_count     = len(content) // 4
            context_window  = 200_000       # claude sonnet default
            percentage_used = (token_count / context_window) * 100
            fits            = token_count < context_window

            content_out = (
                f"Token estimate: {token_count:,}\n"
                f"Context window: {context_window:,}\n"
                f"Usage: {percentage_used:.1f}%\n"
                f"Fits in context: {'Yes' if fits else 'No — use chunked reading'}"
            )

            return ToolOutput.ok(
                content = content_out,
                data    = {
                    "token_count"     : token_count,
                    "context_window"  : context_window,
                    "fits_in_context" : fits,
                    "percentage_used" : round(percentage_used, 2),
                    "file_path"       : file_path,
                },
            )
        except Exception as e:
            return ToolOutput.error(str(e))