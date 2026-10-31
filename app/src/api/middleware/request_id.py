# app/src/api/middleware/request_id.py
# Assigns every request a stable id, exposes it on request.state and in the
# X-Request-ID response header, and makes it available to logging.

from __future__ import annotations

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

__all__ = ["RequestIDMiddleware", "get_request_id", "request_id_var"]

request_id_var: ContextVar[str | None] = ContextVar(
    "request_id", default=None
)


def get_request_id() -> str | None:
    return request_id_var.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    header_name = "X-Request-ID"

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = (
            request.headers.get(self.header_name) or uuid.uuid4().hex
        )
        token = request_id_var.set(request_id)
        request.state.request_id = request_id

        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)

        response.headers[self.header_name] = request_id
        return response
