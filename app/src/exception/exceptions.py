# app/src/exception/exceptions.py
# Application-wide exception hierarchy.
# Every layer raises these; the API error handler maps them to HTTP responses.
# No imports from FastAPI, Docker, or any infrastructure library.

from __future__ import annotations

from typing import Any

__all__ = [
    "CipherAgentError",
    "ConfigurationError",
    "InvalidRequestError",
    "NotFoundError",
    "ToolNotFoundError",
    "PathNotFoundError",
    "ConflictError",
    "FileAlreadyExistsError",
    "PathOutsideWorkspaceError",
    "FilesystemError",
    "SandboxError",
    "SandboxUnavailableError",
    "SandboxTimeoutError",
    "LLMError",
    "LLMTimeoutError",
    "LLMResponseError",
    "AgentError",
    "AgentExecutionError",
    "AgentTimeoutError",
    "AgentIterationLimitError",
    "ServiceUnavailableError",
    "RateLimitError",
]


class CipherAgentError(Exception):
    """
    Base class for every expected application error.

    Subclasses override `code`, `status_code`, and `retryable`.
    The API layer reads `status_code` and returns `to_dict()` as the body.
    """

    code: str = "internal_error"
    status_code: int = 500
    retryable: bool = False

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = dict(details or {})
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
        }
        if self.details:
            payload["details"] = self.details
        return payload

    def __str__(self) -> str:
        return self.message


# ── configuration / request errors ────────────────────────────────────────────

class ConfigurationError(CipherAgentError):
    code = "configuration_error"
    status_code = 500


class InvalidRequestError(CipherAgentError):
    code = "invalid_request"
    status_code = 400


# ── not found ─────────────────────────────────────────────────────────────────

class NotFoundError(CipherAgentError):
    code = "not_found"
    status_code = 404


class ToolNotFoundError(NotFoundError):
    code = "tool_not_found"


class PathNotFoundError(NotFoundError):
    code = "path_not_found"


# ── conflicts / permissions ───────────────────────────────────────────────────

class ConflictError(CipherAgentError):
    code = "conflict"
    status_code = 409


class FileAlreadyExistsError(ConflictError):
    code = "file_already_exists"


class PathOutsideWorkspaceError(CipherAgentError):
    code = "path_outside_workspace"
    status_code = 403


# ── filesystem ────────────────────────────────────────────────────────────────

class FilesystemError(CipherAgentError):
    code = "filesystem_error"
    status_code = 500


# ── sandbox ───────────────────────────────────────────────────────────────────

class SandboxError(CipherAgentError):
    code = "sandbox_error"
    status_code = 500


class SandboxUnavailableError(SandboxError):
    code = "sandbox_unavailable"
    status_code = 503
    retryable = True


class SandboxTimeoutError(SandboxError):
    code = "sandbox_timeout"
    status_code = 504
    retryable = True


# ── LLM ───────────────────────────────────────────────────────────────────────

class LLMError(CipherAgentError):
    code = "llm_error"
    status_code = 502


class LLMTimeoutError(LLMError):
    code = "llm_timeout"
    status_code = 504
    retryable = True


class LLMResponseError(LLMError):
    code = "llm_response_error"
    status_code = 502


# ── agent ─────────────────────────────────────────────────────────────────────

class AgentError(CipherAgentError):
    code = "agent_error"
    status_code = 500


class AgentExecutionError(AgentError):
    code = "agent_execution_error"


class AgentTimeoutError(AgentError):
    code = "agent_timeout"
    status_code = 504
    retryable = True


class AgentIterationLimitError(AgentError):
    code = "agent_iteration_limit"


# ── service ───────────────────────────────────────────────────────────────────

class ServiceUnavailableError(CipherAgentError):
    code = "service_unavailable"
    status_code = 503
    retryable = True


class RateLimitError(CipherAgentError):
    code = "rate_limit_exceeded"
    status_code = 429
    retryable = True
