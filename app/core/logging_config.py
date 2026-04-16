"""
Structlog configuration — call configure_logging() once at app startup.

In development:  pretty console renderer with colours.
In production:   JSON renderer compatible with Railway / Datadog / CloudWatch.
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(environment: str = "development") -> None:
    """
    Wire structlog to stdlib logging and configure the processor pipeline.

    Args:
        environment: "development" | "production" | "test"
    """
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
    ]

    if environment == "production":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(
        logging.DEBUG if environment == "development" else logging.INFO
    )

    # Silence noisy third-party loggers (always, not just production)
    for name in ("httpx", "httpcore", "hpack", "uvicorn.access"):
        logging.getLogger(name).setLevel(logging.WARNING)
