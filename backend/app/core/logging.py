"""Centralized logging configuration for the application."""

import logging
import sys
from contextvars import ContextVar
from typing import Any

from pythonjsonlogger import jsonlogger

# Context var for request ID tracking across async operations
request_id_ctx_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestIdFilter(logging.Filter):
    """Add request ID to log records from context variable."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx_var.get()  # type: ignore[attr-defined]
        return True


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)

        # Add standard fields
        log_record["timestamp"] = self.formatTime(record, self.datefmt)
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["module"] = record.module
        log_record["function"] = record.funcName

        # Add request ID if available
        request_id = getattr(record, "request_id", None)
        if request_id:
            log_record["request_id"] = request_id

        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)


def setup_logging(
    log_level: str = "INFO",
    json_format: bool = False,  # noqa: FBT001, FBT002
    log_file: str | None = None,
) -> None:
    """
    Configure application-wide logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: If True, use JSON formatter for structured logs
        log_file: Optional file path for log output
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))

    # Add request ID filter
    request_id_filter = RequestIdFilter()
    console_handler.addFilter(request_id_filter)

    # Configure formatter
    if json_format:
        # Production: JSON structured logs
        formatter = CustomJsonFormatter("%(timestamp)s %(level)s %(name)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
    else:
        # Development: Human-readable logs
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] [req:%(request_id)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.addFilter(request_id_filter)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def set_request_id(request_id: str) -> None:
    """Set request ID in context for current async task."""
    request_id_ctx_var.set(request_id)


def get_request_id() -> str | None:
    """Get current request ID from context."""
    return request_id_ctx_var.get()
