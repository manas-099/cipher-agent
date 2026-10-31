# app/src/domain/tools/web_tools.py
# Web tools — 1 tool.
# read_url uses httpx directly — no port needed, httpx is lightweight enough.
# If you later need to mock HTTP calls in tests, extract a WebPort.

from __future__ import annotations
from typing import Any

import httpx

from app.src.domain.tools.base_tool import BaseTool, ToolOutput


class ReadUrlTool(BaseTool):
    name        = "read_url"
    description = (
        "Fetch the content of a URL and return it as clean text. "
        "Use to read documentation, README files, GitHub sources, or Stack Overflow answers. "
        "Content is truncated at max_chars to avoid flooding context."
    )

    @property
    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url"      : {"type": "string",  "description": "URL to fetch"},
                "timeout"  : {"type": "integer", "description": "Seconds before giving up (default: 15)"},
                "max_chars": {"type": "integer", "description": "Truncate response at this length (default: 10000)"},
            },
            "required": ["url"],
        }

    async def execute(self, args: dict[str, Any]) -> ToolOutput:
        if err := self._validate_required(args, ["url"]):
            return ToolOutput.error(err)

        url       = args["url"]
        timeout   = args.get("timeout", 15)
        max_chars = args.get("max_chars", 10_000)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    url,
                    follow_redirects = True,
                    headers          = {"User-Agent": "CipherAgent/1.0"},
                )
                response.raise_for_status()

            text = response.text

            # strip excess whitespace
            lines   = [line.strip() for line in text.splitlines() if line.strip()]
            cleaned = "\n".join(lines)

            # truncate if too long
            truncated = False
            if len(cleaned) > max_chars:
                cleaned   = cleaned[:max_chars]
                truncated = True

            content = (
                f"URL: {url}\n"
                f"Status: {response.status_code}\n"
                + (f"[TRUNCATED at {max_chars} chars]\n" if truncated else "")
                + f"\n{cleaned}"
            )

            return ToolOutput.ok(
                content = content,
                data    = {
                    "url"        : url,
                    "status_code": response.status_code,
                    "truncated"  : truncated,
                    "char_count" : len(cleaned),
                },
            )

        except httpx.TimeoutException:
            return ToolOutput.error(f"Request timed out after {timeout}s: {url}")
        except httpx.HTTPStatusError as e:
            return ToolOutput.error(f"HTTP {e.response.status_code}: {url}")
        except Exception as e:
            return ToolOutput.error(str(e))