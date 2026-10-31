# app/src/api/middleware/timeout.py
# Caps how long a request may run and returns a 504 when the cap is exceeded.

from __future__ import annotations

import asyncio

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.src.api.middleware.request_id import get_request_id
from app.src.logger.logger import get_logger

__all__ = ["TimeoutMiddleware"]

logger = get_logger(__name__)


class TimeoutMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, timeout_seconds: float = 300.0) -> None:
        super().__init__(app)
        self._timeout_seconds = timeout_seconds

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=self._timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "api_request_timeout",
                path=request.url.path,
                timeout_seconds=self._timeout_seconds,
                request_id=get_request_id(),
            )
            return JSONResponse(
                status_code=504,
                content={
                    "error": {
                        "code": "request_timeout",
                        "message": "Request timed out",
                        "retryable": True,
                    },
                    "request_id": get_request_id(),
                },
            )
