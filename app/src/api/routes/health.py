# app/src/api/routes/health.py
# Liveness/readiness endpoint. Does not touch Docker or the LLM endpoint.

from __future__ import annotations

import time

from fastapi import APIRouter, Request

from app.src.api.dto.response import HealthResponseDTO
from app.src.config.api_config import APP_METADATA, API_ROUTES

__all__ = ["router"]

router = APIRouter(tags=["health"])


@router.get(
    API_ROUTES.health,
    response_model=HealthResponseDTO,
    summary="Service health",
)
def health(request: Request) -> HealthResponseDTO:
    container = getattr(request.app.state, "container", None)
    started_at = getattr(request.app.state, "started_at", time.monotonic())

    healthy = bool(container is not None and container.agent.health())

    return HealthResponseDTO(
        status="ok" if healthy else "degraded",
        version=APP_METADATA.version,
        uptime_seconds=round(time.monotonic() - started_at, 3),
    )
