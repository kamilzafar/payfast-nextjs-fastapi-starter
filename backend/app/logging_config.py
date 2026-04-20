"""Structlog configuration.

- `ENV=production` → JSON-line output (one log per line, machine-parseable).
- otherwise         → pretty console renderer with colors for dev.

Processor chain is kept shared so every `structlog.get_logger()` call gets the
same context-aware output. Standard-library `logging` is routed through the
same chain so uvicorn / sqlalchemy logs render consistently.
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(env: str = "development", log_level: str = "INFO") -> None:
    """Configure structlog + stdlib logging.

    Call once at startup. Safe to call twice (idempotent reconfigure).
    """
    level = logging.getLevelName(log_level.upper())
    if not isinstance(level, int):
        level = logging.INFO

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if env == "production":
        renderer: structlog.typing.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Quiet noisy deps in production
    for noisy in ("uvicorn.access",):
        logging.getLogger(noisy).setLevel(logging.WARNING if env == "production" else level)
