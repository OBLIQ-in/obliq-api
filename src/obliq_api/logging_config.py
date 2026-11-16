"""structlog configuration for obliq-api.

Call ``configure_logging()`` once at application startup (before any
log calls are made).  After that, use:

    import structlog
    log = structlog.get_logger(__name__)
    log.info("event", key="value")

In development (LOG_FORMAT=text or DEBUG=true) logs are rendered as
coloured, human-readable lines.  In production they are emitted as JSON
one-object-per-line so log aggregators (Datadog, Loki, CloudWatch, etc.)
can parse them directly.
"""

from __future__ import annotations

import logging
import sys

import structlog

from obliq_api.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    use_json = settings.is_production

    # Shared processors applied to every log record regardless of origin.
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if use_json:
        # Production: structured JSON
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        # Development: coloured, human-readable
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)

    # Quieten noisy third-party loggers in production
    for noisy in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING if use_json else level)
