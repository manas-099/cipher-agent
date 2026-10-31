# app/src/logger/logger.py
# Single place that configures structlog for the entire application.
# Every other file imports get_logger() from here — nothing else.
#
# Development → colored, readable, human-friendly console output
# Production  → JSON, machine-parseable, ready for log aggregators

from __future__ import annotations

import logging
import logging.config
import sys
from functools import lru_cache
from typing import Any

import structlog

from app.src.config.settings import get_settings


# ─────────────────────────────────────────────────────────────────────────────
# PROCESSORS
# A processor is a function that receives a log event dict and returns it
# modified. structlog chains them in order — each one adds/transforms data.
# ─────────────────────────────────────────────────────────────────────────────

# shared processors that run in BOTH dev and prod
_SHARED_PROCESSORS: list[Any] = [
    # adds timestamp in ISO 8601 format
    structlog.processors.TimeStamper(fmt="iso", utc=True),

    # adds log level as string: "info", "warning", "error"
    structlog.stdlib.add_log_level,

    # adds logger name (the __name__ passed to get_logger)
    structlog.stdlib.add_logger_name,

    # adds file name + line number where log was called
    structlog.processors.CallsiteParameterAdder(
        parameters=[
            structlog.processors.CallsiteParameter.FILENAME,
            structlog.processors.CallsiteParameter.LINENO,
            structlog.processors.CallsiteParameter.FUNC_NAME,
        ]
    ),

    # renders exceptions as readable tracebacks
    structlog.processors.ExceptionRenderer(),

    # makes stdlib logging records structlog-compatible
    structlog.stdlib.PositionalArgumentsFormatter(),

    # cleans up extra whitespace in messages
    structlog.processors.UnicodeDecoder(),
]


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURE
# ─────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _configure_structlog() -> None:
    """
    Configure structlog once at startup.
    lru_cache ensures this runs exactly once — no matter how many
    files call get_logger().

    Dev  → ConsoleRenderer  (colored, human readable)
    Prod → JSONRenderer     (machine parseable, one JSON object per line)
    """
    settings = get_settings()
    is_dev   = settings.api.DEBUG

    if is_dev:
        # colored, readable output for local development
        renderer = structlog.dev.ConsoleRenderer(
            colors         = True,
            exception_formatter = structlog.dev.plain_traceback,
        )
    else:
        # one JSON object per log line — goes to your log aggregator
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *_SHARED_PROCESSORS,
            # must be last — renders the final output
            renderer,
        ],
        # use stdlib logging as the backend
        # means structlog respects log level filtering
        wrapper_class    = structlog.stdlib.BoundLogger,
        context_class    = dict,
        logger_factory   = structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use = True,
    )

    # configure stdlib logging so third-party libraries
    # (httpx, uvicorn, docker) also go through structlog
    _configure_stdlib_logging(is_dev=is_dev)


def _configure_stdlib_logging(is_dev: bool) -> None:
    """
    Wire standard Python logging into structlog.
    This means uvicorn, httpx, docker SDK logs all
    get the same format as our structlog output.
    """
    log_level = logging.DEBUG if is_dev else logging.INFO

    # foreign pre-chain handles stdlib log records
    # before they enter structlog processors
    foreign_pre_chain = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    logging.config.dictConfig({
        "version"                 : 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structlog": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processors": [
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.dev.ConsoleRenderer() if is_dev else structlog.processors.JSONRenderer(),
                ],
                "foreign_pre_chain": foreign_pre_chain,
            }
        },
        "handlers": {
            "console": {
                "class"    : "logging.StreamHandler",
                "formatter": "structlog",
                "stream"   : "ext://sys.stdout",
            }
        },
        "root": {
            "handlers": ["console"],
            "level"   : log_level,
        },
        # silence noisy third-party loggers in production
        "loggers": {
            "httpx"         : {"level": "WARNING"},
            "httpcore"      : {"level": "WARNING"},
            "docker"        : {"level": "WARNING"},
            "uvicorn.access": {"level": "WARNING" if not is_dev else "INFO"},
        },
    })


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API — this is the only thing other files import
# ─────────────────────────────────────────────────────────────────────────────

def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a named structlog logger.

    Usage in every file:
        from app.src.logger.logger import get_logger
        logger = get_logger(__name__)

        logger.info("tool_executed", tool="read_file", duration=0.023)
        logger.warning("llm_retry", attempt=2, reason="timeout")
        logger.error("agent_failed", error=str(e), iteration=3)

    Args:
        name: pass __name__ — gives you file-level logger naming

    Returns:
        Bound structlog logger configured for dev or prod
    """
    _configure_structlog()
    return structlog.get_logger(name)