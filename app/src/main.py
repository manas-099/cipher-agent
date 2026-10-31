# app/src/main.py
# Composition root. Builds adapters, wires services, mounts the HTTP layer.
# This is the only place that knows about every concrete implementation.

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.src.api.middleware.error_handler import register_exception_handlers
from app.src.api.middleware.request_id import RequestIDMiddleware
from app.src.api.middleware.timeout import TimeoutMiddleware
from app.src.api.routes import chat as chat_routes
from app.src.api.routes import health as health_routes
from app.src.application.agent_service import AgentService
from app.src.application.chat_service import ChatService
from app.src.config.api_config import API_ROUTES, APP_METADATA
from app.src.config.settings import Settings, get_settings
from app.src.domain.tools.tool_factory import ToolFactory
from app.src.infrastructure.filesystem.local_fs_adapter import LocalFSAdapter
from app.src.infrastructure.llm.llm_factory import LLMFactory
from app.src.infrastructure.sandbox.lazy_sandbox import LazySandbox
from app.src.infrastructure.sandbox.sandbox_factory import SandboxFactory
from app.src.logger.logger import get_logger
from app.src.ports.inbound.agent_service_port import AgentServicePort
from app.src.ports.inbound.chat_service_port import ChatServicePort

__all__ = ["AppContainer", "build_container", "create_app", "app", "main"]

logger = get_logger(__name__)

_PROMPT_DIR = Path(__file__).resolve().parent / "prompt_library"


@dataclass
class AppContainer:
    """Everything the HTTP layer needs, plus resources to release."""

    agent: AgentServicePort
    chat: ChatServicePort
    sandbox: LazySandbox | None = None

    def close(self) -> None:
        if self.sandbox is not None:
            self.sandbox.close()


def _load_system_prompt() -> str:
    path = _PROMPT_DIR / "system_prompt.txt"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        logger.warning("system_prompt_unavailable", path=str(path))
        return ""


def build_container(settings: Settings | None = None) -> AppContainer:
    """Wire the real adapters into the application services."""
    settings = settings or get_settings()
    workspace_root = settings.sandbox.WORKSPACE_ROOT or str(Path.cwd())

    filesystem = LocalFSAdapter(workspace_root)
    llm = LLMFactory.create()
    sandbox = LazySandbox(
        SandboxFactory(settings=settings.sandbox),
        workspace_root=workspace_root,
    )
    tools = ToolFactory(fs=filesystem, sandbox=sandbox, llm=llm).build()

    agent = AgentService(
        llm=llm,
        tools=tools,
        system_prompt=_load_system_prompt(),
    )
    chat = ChatService(agent)

    logger.info(
        "container_built",
        workspace_root=workspace_root,
        tool_count=len(tools.get_all()),
    )
    return AppContainer(agent=agent, chat=chat, sandbox=sandbox)


def create_app(container: AppContainer | None = None) -> FastAPI:
    settings = get_settings()
    owns_container = container is None

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        logger.info(
            "application_started",
            version=APP_METADATA.version,
            debug=settings.api.DEBUG,
        )
        try:
            yield
        finally:
            if owns_container:
                application.state.container.close()
            logger.info("application_stopped")

    application = FastAPI(
        title=APP_METADATA.title,
        description=APP_METADATA.description,
        version=APP_METADATA.version,
        docs_url=APP_METADATA.docs_url,
        redoc_url=APP_METADATA.redoc_url,
        openapi_url=APP_METADATA.openapi_url,
        lifespan=lifespan,
    )

    application.state.container = container or build_container(settings)
    application.state.started_at = time.monotonic()

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.CORS_ORIGINS,
        allow_methods=settings.api.CORS_METHODS,
        allow_headers=["*"],
    )
    application.add_middleware(
        TimeoutMiddleware,
        timeout_seconds=settings.api.REQUEST_TIMEOUT_SECONDS,
    )
    application.add_middleware(RequestIDMiddleware)

    register_exception_handlers(application)

    application.include_router(chat_routes.router, prefix=API_ROUTES.prefix)
    application.include_router(health_routes.router, prefix=API_ROUTES.prefix)

    return application


app = create_app()


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.src.main:app",
        host=settings.api.HOST,
        port=settings.api.PORT,
        reload=settings.api.RELOAD,
    )


if __name__ == "__main__":
    main()
