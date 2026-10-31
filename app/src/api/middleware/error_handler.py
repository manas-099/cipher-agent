# app/src/api/middleware/error_handler.py
# Maps application errors to HTTP responses without leaking internals.

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.src.api.middleware.request_id import get_request_id
from app.src.exception.exceptions import CipherAgentError
from app.src.logger.logger import get_logger

__all__ = ["register_exception_handlers"]

logger = get_logger(__name__)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None) or get_request_id()


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    retryable: bool = False,
    details: dict | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "retryable": retryable,
                **({"details": details} if details else {}),
            },
            "request_id": _request_id(request),
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(CipherAgentError)
    async def handle_cipher_error(
        request: Request,
        exc: CipherAgentError,
    ) -> JSONResponse:
        logger.warning(
            "api_cipher_error",
            code=exc.code,
            status_code=exc.status_code,
            error=str(exc),
            request_id=_request_id(request),
        )
        return _error_response(
            request,
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            retryable=exc.retryable,
            details=exc.details or None,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception(
            "api_unhandled_error",
            error=str(exc),
            request_id=_request_id(request),
        )
        return _error_response(
            request,
            status_code=500,
            code="internal_error",
            message="An internal error occurred",
        )
