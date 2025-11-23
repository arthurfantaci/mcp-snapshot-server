"""Tests for error handling."""


import pytest

from mcp_snapshot_server.utils.errors import (
    ErrorCode,
    MCPServerError,
    retry_on_error,
)


@pytest.mark.unit
class TestErrorCode:
    """Tests for ErrorCode enum."""

    def test_error_codes_exist(self) -> None:
        """Test that all expected error codes exist."""
        assert ErrorCode.INVALID_INPUT
        assert ErrorCode.FILE_NOT_FOUND
        assert ErrorCode.PARSE_ERROR
        assert ErrorCode.API_ERROR
        assert ErrorCode.RATE_LIMIT
        assert ErrorCode.TIMEOUT
        assert ErrorCode.RESOURCE_NOT_FOUND
        assert ErrorCode.INTERNAL_ERROR

    def test_error_code_values(self) -> None:
        """Test error code values."""
        assert ErrorCode.INVALID_INPUT.value == "INVALID_INPUT"
        assert ErrorCode.FILE_NOT_FOUND.value == "FILE_NOT_FOUND"
        assert ErrorCode.API_ERROR.value == "API_ERROR"


@pytest.mark.unit
class TestMCPServerError:
    """Tests for MCPServerError exception."""

    def test_error_creation(self) -> None:
        """Test creating an error."""
        error = MCPServerError(
            message="Test error",
            error_code=ErrorCode.INVALID_INPUT,
            details={"field": "test_field"},
        )

        assert error.message == "Test error"
        assert error.error_code == ErrorCode.INVALID_INPUT
        assert error.details == {"field": "test_field"}
        assert str(error) == "Test error"

    def test_error_without_details(self) -> None:
        """Test creating error without details."""
        error = MCPServerError(
            message="Simple error", error_code=ErrorCode.INTERNAL_ERROR
        )

        assert error.details == {}

    def test_to_dict(self) -> None:
        """Test converting error to dictionary."""
        error = MCPServerError(
            message="Test error",
            error_code=ErrorCode.PARSE_ERROR,
            details={"line": 42, "column": 10},
        )

        error_dict = error.to_dict()

        assert error_dict == {
            "error": "PARSE_ERROR",
            "message": "Test error",
            "details": {"line": 42, "column": 10},
        }

    def test_error_inheritance(self) -> None:
        """Test that MCPServerError is an Exception."""
        error = MCPServerError(message="Test", error_code=ErrorCode.INVALID_INPUT)
        assert isinstance(error, Exception)


@pytest.mark.unit
class TestRetryDecorator:
    """Tests for retry_on_error decorator."""

    @pytest.mark.asyncio
    async def test_retry_success_first_attempt(self) -> None:
        """Test successful execution on first attempt."""
        call_count = 0

        @retry_on_error(max_retries=3, delay=0.01)
        async def successful_function() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_function()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self) -> None:
        """Test successful execution after some failures."""
        call_count = 0

        @retry_on_error(max_retries=3, delay=0.01, backoff=1.5)
        async def flaky_function() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise MCPServerError("Temporary error", ErrorCode.API_ERROR)
            return "success"

        result = await flaky_function()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_all_attempts_fail(self) -> None:
        """Test that error is raised after all retries fail."""
        call_count = 0

        @retry_on_error(max_retries=3, delay=0.01)
        async def always_fails() -> None:
            nonlocal call_count
            call_count += 1
            raise MCPServerError("Permanent error", ErrorCode.INTERNAL_ERROR)

        with pytest.raises(MCPServerError) as exc_info:
            await always_fails()

        assert exc_info.value.message == "Permanent error"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_with_standard_exception(self) -> None:
        """Test retry with standard Python exception."""
        call_count = 0

        @retry_on_error(max_retries=2, delay=0.01)
        async def raises_value_error() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("Standard error")

        with pytest.raises(ValueError):
            await raises_value_error()

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_delay_backoff(self) -> None:
        """Test that retry delays follow backoff pattern."""
        import time

        call_times = []

        @retry_on_error(max_retries=3, delay=0.1, backoff=2.0)
        async def timed_failure() -> None:
            call_times.append(time.time())
            raise MCPServerError("Error", ErrorCode.API_ERROR)

        with pytest.raises(MCPServerError):
            await timed_failure()

        # Verify we had 3 attempts
        assert len(call_times) == 3

        # Verify delays increase (within tolerance for timing variations)
        # First delay: ~0.1s, Second delay: ~0.2s
        if len(call_times) >= 2:
            delay1 = call_times[1] - call_times[0]
            assert 0.08 < delay1 < 0.15  # First delay ~0.1s

        if len(call_times) >= 3:
            delay2 = call_times[2] - call_times[1]
            assert 0.18 < delay2 < 0.25  # Second delay ~0.2s
