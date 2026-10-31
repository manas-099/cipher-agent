# app/src/infrastructure/llm/my_llm_adapter.py
# Concrete LLM adapter for self-hosted OpenAI-compatible endpoint.
# Inherits shared behaviour from BaseLLMAdapter.
# Implements: generate(), stream()

from __future__ import annotations

import json
import time
from typing import Any, Generator

import httpx

from app.src.config.settings import get_settings
from app.src.domain.models.chat_message import ChatMessage, MessageRole
from app.src.infrastructure.llm.base_llm_adapter import BaseLLMAdapter
from app.src.ports.outbound.llm_port import (
    LLMResponse,
    TokenUsage,
    ToolSchema,
)


# ── message format conversion ─────────────────────────────────────────────────

def _to_api_messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    """
    Convert domain ChatMessage list to OpenAI-compatible API format.
    """
    result = []
    for msg in messages:
        if msg.role == MessageRole.TOOL:
            result.append({
                "role"        : "tool",
                "content"     : msg.content,
                "tool_call_id": msg.tool_call_id,
            })
        elif msg.role == MessageRole.ASSISTANT and msg.tool_calls:
            result.append({
                "role"      : "assistant",
                "content"   : msg.content or None,
                "tool_calls": [
                    {
                        "id"      : tc["id"],
                        "type"    : "function",
                        "function": {
                            "name"     : tc["name"],
                            "arguments": json.dumps(tc["arguments"]),
                        },
                    }
                    for tc in msg.tool_calls
                ],
            })
        else:
            result.append({
                "role"   : msg.role.value,
                "content": msg.content,
            })
    return result


def _to_api_tools(tools: list[ToolSchema]) -> list[dict[str, Any]]:
    """
    Convert ToolSchema list to OpenAI-compatible function calling format.
    """
    return [
        {
            "type"    : "function",
            "function": {
                "name"       : tool.name,
                "description": tool.description,
                "parameters" : tool.parameters,
            },
        }
        for tool in tools
    ]


def _parse_tool_calls(raw_tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Parse raw tool_calls from API response into domain format.

    API returns:
    {
        "id": "call_abc",
        "type": "function",
        "function": {"name": "read_file", "arguments": "{\"path\": \"main.py\"}"}
    }

    We return:
    {"name": "read_file", "arguments": {"path": "main.py"}, "id": "call_abc"}
    """
    parsed = []
    for tc in raw_tool_calls:
        try:
            arguments = json.loads(tc["function"]["arguments"])
        except (json.JSONDecodeError, KeyError):
            arguments = {}

        parsed.append({
            "name"     : tc["function"]["name"],
            "arguments": arguments,
            "id"       : tc.get("id", ""),
        })
    return parsed


# ── health check state ────────────────────────────────────────────────────────

class _HealthState:
    """
    Tracks whether the LLM endpoint is reachable.
    Prevents hammering a down server on every request.
    Uses cooldown period before retrying after failure.
    """

    def __init__(self, cooldown_seconds: int) -> None:
        self._healthy          : bool  = True
        self._last_failed_at   : float = 0.0
        self._cooldown_seconds : int   = cooldown_seconds

    @property
    def is_available(self) -> bool:
        if self._healthy:
            return True
        # cooldown expired — try again
        if time.monotonic() - self._last_failed_at > self._cooldown_seconds:
            return True
        return False

    def mark_healthy(self) -> None:
        self._healthy = True

    def mark_failed(self) -> None:
        self._healthy        = False
        self._last_failed_at = time.monotonic()


# ── the adapter ───────────────────────────────────────────────────────────────

class LLMAdapter(BaseLLMAdapter):
    """
    Self-hosted OpenAI-compatible LLM adapter.

    Inherits from BaseLLMAdapter:
      - get_tool_schemas()
      - register_tools()
      - count_tokens()
      - self._logger
      - self._tool_registry

    Implements:
      - generate()  → full response with tool calling support
      - stream()    → streaming tokens
    """

    def __init__(self) -> None:
        settings = get_settings()

        # initialise BaseLLMAdapter with model info
        super().__init__(
            model_name = settings.my_llm.MODEL_NAME,
            provider   = "my_llm",
        )

        self._settings = settings.my_llm
        self._health   = _HealthState(
            cooldown_seconds=self._settings.HEALTH_CHECK_COOLDOWN_SECONDS,
        )

        self._logger.info(
            "llm_adapter_initialized",
            model       = self._model_name,
            provider    = self._provider,
            api_url     = self._settings.API_URL,
            max_retries = self._settings.MAX_RETRIES,
        )

    # ── LLMPort interface ─────────────────────────────────────────────────────

    def generate(
        self,
        messages : list[ChatMessage],
        tools    : list[ToolSchema] | None = None,
    ) -> LLMResponse:
        """
        Send conversation to LLM, get full response back.
        Retries on server errors, stops on client errors.
        Raises LLMAdapterError after all retries exhausted.
        """
        if not self._health.is_available:
            self._logger.error("llm_skipped_unhealthy_endpoint")
            raise LLMAdapterError(
                "LLM endpoint is unavailable (in cooldown). Try again shortly."
            )

        payload = self._build_payload(messages, tools, stream=False)
        headers = self._build_headers()

        self._logger.info(
            "llm_generate_started",
            model         = self._model_name,
            message_count = len(messages),
            has_tools     = tools is not None,
            tool_count    = len(tools) if tools else 0,
        )

        last_error : str | None = None
        start                   = time.monotonic()

        for attempt in range(1, self._settings.MAX_RETRIES + 1):
            try:
                self._logger.debug(
                    "llm_attempt",
                    attempt     = attempt,
                    max_retries = self._settings.MAX_RETRIES,
                )

                with httpx.Client(timeout=self._settings.TIMEOUT_SECONDS) as client:
                    resp = client.post(
                        self._settings.API_URL,
                        headers = headers,
                        json    = payload,
                    )

                if resp.status_code >= 400:
                    last_error = f"http_{resp.status_code}: {resp.text[:500]}"
                    self._logger.warning(
                        "llm_error_response",
                        status_code = resp.status_code,
                        attempt     = attempt,
                        error       = last_error,
                    )

                    # 4xx = client error — retrying won't help
                    if 400 <= resp.status_code < 500:
                        self._health.mark_failed()
                        break

                    # 5xx = server error — retry after delay
                    if attempt < self._settings.MAX_RETRIES:
                        time.sleep(self._settings.RETRY_DELAY_SECONDS)
                    continue

                resp.raise_for_status()
                self._health.mark_healthy()

                response = self._parse_response(resp.json())
                duration = time.monotonic() - start

                self._logger.info(
                    "llm_generate_completed",
                    duration_seconds = round(duration, 3),
                    has_tool_calls   = response.has_tool_calls,
                    tool_call_count  = len(response.tool_calls),
                    input_tokens     = response.usage.input_tokens if response.usage else None,
                    output_tokens    = response.usage.output_tokens if response.usage else None,
                    model            = response.model,
                )
                return response

            except httpx.TimeoutException as e:
                last_error = f"timeout: {e}"
                self._logger.warning(
                    "llm_timeout",
                    attempt         = attempt,
                    timeout_seconds = self._settings.TIMEOUT_SECONDS,
                )
                self._health.mark_failed()
                if attempt < self._settings.MAX_RETRIES:
                    time.sleep(self._settings.RETRY_DELAY_SECONDS)

            except httpx.RequestError as e:
                last_error = f"request_failed: {e}"
                self._logger.warning(
                    "llm_request_error",
                    attempt = attempt,
                    error   = str(e),
                )
                self._health.mark_failed()
                if attempt < self._settings.MAX_RETRIES:
                    time.sleep(self._settings.RETRY_DELAY_SECONDS)

            except (KeyError, IndexError, ValueError) as e:
                last_error = f"unexpected_response_shape: {e}"
                self._logger.error(
                    "llm_parse_error",
                    attempt = attempt,
                    error   = str(e),
                )
                if attempt < self._settings.MAX_RETRIES:
                    time.sleep(self._settings.RETRY_DELAY_SECONDS)

        self._logger.error(
            "llm_generate_failed",
            attempts   = self._settings.MAX_RETRIES,
            last_error = last_error,
            duration   = round(time.monotonic() - start, 3),
        )
        raise LLMAdapterError(f"LLMAdapter failed after retries: {last_error}")

    def stream(
        self,
        messages : list[ChatMessage],
        tools    : list[ToolSchema] | None = None,
    ) -> Generator[str, None, None]:
        """
        Stream response tokens as they arrive.
        Yields text chunks — caller prints or sends each chunk immediately.
        Tool calls are NOT supported in stream mode — use generate() for that.
        """
        payload = self._build_payload(messages, tools, stream=True)
        headers = self._build_headers()

        self._logger.info(
            "llm_stream_started",
            model         = self._model_name,
            message_count = len(messages),
        )

        start       = time.monotonic()
        chunk_count = 0

        try:
            with httpx.Client(timeout=self._settings.TIMEOUT_SECONDS) as client:
                with client.stream(
                    "POST",
                    self._settings.API_URL,
                    headers = headers,
                    json    = payload,
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        chunk = self._parse_stream_chunk(line)
                        if chunk:
                            chunk_count += 1
                            yield chunk

            self._logger.info(
                "llm_stream_completed",
                chunk_count      = chunk_count,
                duration_seconds = round(time.monotonic() - start, 3),
            )

        except httpx.TimeoutException as e:
            self._logger.error("llm_stream_timeout", error=str(e))
            raise LLMAdapterError(f"Stream timed out: {e}")

        except httpx.RequestError as e:
            self._logger.error("llm_stream_request_error", error=str(e))
            raise LLMAdapterError(f"Stream request failed: {e}")

    # ── private helpers ───────────────────────────────────────────────────────

    def _build_payload(
        self,
        messages : list[ChatMessage],
        tools    : list[ToolSchema] | None,
        stream   : bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model"      : self._model_name,
            "messages"   : _to_api_messages(messages),
            "temperature": 0.0,
            "max_tokens" : 4096,
            "stream"     : stream,
        }
        if tools:
            payload["tools"]       = _to_api_tools(tools)
            payload["tool_choice"] = "auto"
        return payload

    def _build_headers(self) -> dict[str, str]:
        return {
            "Content-Type" : "application/json",
            "Authorization": f"Bearer {self._settings.AUTH_TOKEN}",
        }

    def _parse_response(self, data: dict[str, Any]) -> LLMResponse:
        """Parse raw API response into LLMResponse."""
        choice  = data["choices"][0]
        message = choice["message"]

        content    = message.get("content") or ""
        tool_calls = []

        if raw_tools := message.get("tool_calls"):
            tool_calls = _parse_tool_calls(raw_tools)
            self._logger.debug(
                "llm_tool_calls_parsed",
                count      = len(tool_calls),
                tool_names = [tc["name"] for tc in tool_calls],
            )

        usage = None
        if raw_usage := data.get("usage"):
            usage = TokenUsage(
                input_tokens  = raw_usage.get("prompt_tokens", 0),
                output_tokens = raw_usage.get("completion_tokens", 0),
            )

        return LLMResponse(
            content    = content,
            tool_calls = tool_calls,
            model      = data.get("model", self._model_name),
            usage      = usage,
        )

    def _parse_stream_chunk(self, line: str) -> str | None:
        """Parse one SSE line from a streaming response."""
        line = line.strip()
        if not line or not line.startswith("data:"):
            return None

        data_str = line[len("data:"):].strip()
        if data_str == "[DONE]":
            return None

        try:
            data  = json.loads(data_str)
            delta = data["choices"][0]["delta"]
            return delta.get("content") or None
        except (json.JSONDecodeError, KeyError, IndexError):
            return None


# ── custom exception ──────────────────────────────────────────────────────────

class LLMAdapterError(Exception):
    """Raised when LLMAdapter fails after all retries."""