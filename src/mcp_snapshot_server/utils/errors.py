"""Error handling for MCP Snapshot Server.

This module provides standardized error codes, custom exceptions,
and retry logic for handling various failure scenarios.
"""

import asyncio
import logging
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ErrorCode(Enum):
    """Standard error codes for MCP server."""

    INVALID_INPUT = "INVALID_INPUT"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    PARSE_ERROR = "PARSE_ERROR"
    API_ERROR = "API_ERROR"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class MCPServerError(Exception):
    """Base exception for MCP server errors."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        details: Optional[dict[str, Any]] = None,
    ):
        """Initialize MCP server error.

        Args:
            message: Human-readable error message
            error_code: Standard error code
            details: Additional error details
        """
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the error
        """
        return {
            "error": self.error_code.value,
            "message": self.message,
            "details": self.details,
        }


def retry_on_error(
    max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for retrying on transient errors.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Backoff multiplier for subsequent retries

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[Exception] = None

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)

                except (MCPServerError, Exception) as e:
                    last_exception = e

                    if attempt < max_retries - 1:
                        wait_time = delay * (backoff**attempt)
                        logger.warning(
                            f"Attempt {attempt + 1} failed, retrying in {wait_time}s",
                            extra={
                                "function": func.__name__,
                                "error": str(e),
                                "attempt": attempt + 1,
                            },
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(
                            f"All {max_retries} attempts failed",
                            extra={"function": func.__name__, "error": str(e)},
                        )

            if last_exception:
                raise last_exception

        return wrapper

    return decorator
