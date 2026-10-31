"""
Structured JSON logger using stdlib logging.
Usage:
    from app.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("User created", extra={"user_id": str(user.id)})
"""

import logging
import sys
from typing import Any

from app.core.config import settings


class _JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        import json
        import traceback

        log: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Extra fields injected via logger.xxx(..., extra={...})
        _skip = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
            "taskName",
        }
        for key, val in record.__dict__.items():
            if key not in _skip:
                log[key] = val

        if record.exc_info:
            log["exception"] = traceback.format_exception(*record.exc_info)

        return json.dumps(log, default=str)


class _TextFormatter(logging.Formatter):
    _FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    _DATE = "%Y-%m-%dT%H:%M:%S"

    def __init__(self) -> None:
        super().__init__(fmt=self._FMT, datefmt=self._DATE)


def _build_handler() -> logging.Handler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter() if settings.LOG_FORMAT == "json" else _TextFormatter())
    return handler


def configure_logging() -> None:
    """Call once at application startup."""
    root = logging.getLogger()
    root.setLevel(settings.LOG_LEVEL.upper())

    # Remove any handlers added by uvicorn / other libs before ours
    root.handlers.clear()
    root.addHandler(_build_handler())

    # Silence noisy third-party loggers
    for name in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
