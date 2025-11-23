"""LLM sampling utilities for agent communication.

This module provides functions for requesting LLM completions
from the Anthropic API using MCP sampling patterns.
"""

import logging
from typing import Any, Optional

from anthropic import Anthropic

from mcp_snapshot_server.utils.config import get_settings
from mcp_snapshot_server.utils.errors import (
    ErrorCode,
    MCPServerError,
    retry_on_error,
)

logger = logging.getLogger(__name__)


@retry_on_error(max_retries=3, delay=1.0, backoff=2.0)
async def sample_llm(
    prompt: str,
    system_prompt: str,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
) -> dict[str, Any]:
    """Request LLM completion via Anthropic API.

    Args:
        prompt: User prompt/template filled with data
        system_prompt: System instructions for the agent role
        temperature: Sampling temperature (0.0-1.0), uses config default if None
        max_tokens: Maximum tokens in response, uses config default if None
        model: Model identifier, uses config default if None

    Returns:
        Dictionary with 'content' and 'metadata' keys

    Raises:
        MCPServerError: If API call fails
    """
    settings = get_settings()

    # Use provided values or fall back to config defaults
    temperature = temperature if temperature is not None else settings.llm.temperature
    max_tokens = (
        max_tokens if max_tokens is not None else settings.llm.max_tokens_analysis
    )
    model = model if model is not None else settings.llm.model

    logger.debug(
        "Requesting LLM sampling",
        extra={
            "prompt_length": len(prompt),
            "system_prompt_length": len(system_prompt),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "model": model,
        },
    )

    try:
        # Initialize Anthropic client
        client = Anthropic(api_key=settings.llm.anthropic_api_key)

        # Make API call
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract content
        content = ""
        if response.content:
            # Handle TextBlock response
            content = response.content[0].text

        logger.info(
            "LLM sampling completed",
            extra={
                "response_length": len(content),
                "model": model,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )

        return {
            "content": content,
            "metadata": {
                "model": model,
                "tokens_used": {
                    "input": response.usage.input_tokens,
                    "output": response.usage.output_tokens,
                },
                "finish_reason": response.stop_reason,
            },
        }

    except Exception as e:
        error_msg = f"LLM sampling failed: {str(e)}"
        logger.error(error_msg, extra={"error_type": type(e).__name__})

        # Classify error type
        if "api_key" in str(e).lower() or "authentication" in str(e).lower():
            error_code = ErrorCode.API_ERROR
        elif "rate" in str(e).lower() or "limit" in str(e).lower():
            error_code = ErrorCode.RATE_LIMIT
        elif "timeout" in str(e).lower():
            error_code = ErrorCode.TIMEOUT
        else:
            error_code = ErrorCode.INTERNAL_ERROR

        raise MCPServerError(
            message=error_msg, error_code=error_code, details={"error": str(e)}
        )
