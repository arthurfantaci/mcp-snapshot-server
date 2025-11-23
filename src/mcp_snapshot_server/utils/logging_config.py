"""Logging configuration for MCP Snapshot Server.

This module provides structured logging capabilities with JSON formatting
and contextual information for debugging and monitoring.
"""

import json
import logging
import sys
from datetime import datetime
from typing import Any


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging output.

    Outputs JSON for easy parsing by log aggregation systems.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON-formatted log string
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging(level: str = "INFO", structured: bool = True) -> None:
    """Configure logging for MCP server.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        structured: Whether to use structured JSON logging
    """
    # Create logger
    logger = logging.getLogger("mcp_snapshot_server")
    logger.setLevel(getattr(logging, level.upper()))

    # Create stderr handler (MCP requirement)
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(getattr(logging, level.upper()))

    # Set formatter
    if structured:
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Prevent propagation to root logger
    logger.propagate = False


class ContextLogger:
    """Logger wrapper that adds contextual information to all log messages."""

    def __init__(self, name: str, context: dict[str, Any] | None = None):
        """Initialize context logger.

        Args:
            name: Logger name
            context: Default context to add to all messages
        """
        self.logger = logging.getLogger(name)
        self.context = context or {}

    def _add_context(self, extra: dict[str, Any] | None) -> dict[str, Any]:
        """Merge context with extra fields.

        Args:
            extra: Additional fields to log

        Returns:
            Merged context dictionary
        """
        merged = self.context.copy()
        merged.update(extra or {})
        return merged

    def debug(self, msg: str, extra: dict[str, Any] | None = None) -> None:
        """Log debug message with context.

        Args:
            msg: Log message
            extra: Additional context fields
        """
        extra_fields = self._add_context(extra)
        self.logger.debug(msg, extra={"extra_fields": extra_fields})

    def info(self, msg: str, extra: dict[str, Any] | None = None) -> None:
        """Log info message with context.

        Args:
            msg: Log message
            extra: Additional context fields
        """
        extra_fields = self._add_context(extra)
        self.logger.info(msg, extra={"extra_fields": extra_fields})

    def warning(self, msg: str, extra: dict[str, Any] | None = None) -> None:
        """Log warning message with context.

        Args:
            msg: Log message
            extra: Additional context fields
        """
        extra_fields = self._add_context(extra)
        self.logger.warning(msg, extra={"extra_fields": extra_fields})

    def error(self, msg: str, extra: dict[str, Any] | None = None) -> None:
        """Log error message with context.

        Args:
            msg: Log message
            extra: Additional context fields
        """
        extra_fields = self._add_context(extra)
        self.logger.error(msg, extra={"extra_fields": extra_fields})
