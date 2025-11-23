"""Pytest configuration and shared fixtures."""

import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to test fixtures directory.

    Returns:
        Path to fixtures directory
    """
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_vtt_path(fixtures_dir: Path) -> Path:
    """Path to sample VTT file.

    Args:
        fixtures_dir: Fixtures directory path

    Returns:
        Path to sample VTT file
    """
    return fixtures_dir / "sample_input.vtt"


@pytest.fixture
def test_jama_vtt_path(fixtures_dir: Path) -> Path:
    """Path to test_jama VTT file.

    Args:
        fixtures_dir: Fixtures directory path

    Returns:
        Path to test_jama VTT file
    """
    return fixtures_dir / "test_jama.vtt"


@pytest.fixture
def sample_transcript_text() -> str:
    """Sample transcript text for testing.

    Returns:
        Sample transcript as string
    """
    return """
    John Smith: Hi everyone, thanks for taking the time to meet with us today.
    I'm John Smith, CTO at Acme Corporation.
    Sarah Jameson: Thanks for having us, John. I'm Sarah Jameson, Solutions Architect.
    We're excited to learn more about your infrastructure challenges.
    John Smith: We've been struggling with scalability issues in our data pipeline.
    Our current system can't handle the volume we're processing.
    Sarah Jameson: I understand. How much data are you processing daily?
    John Smith: About 500 terabytes per day, and it's growing 20% month over month.
    """


@pytest.fixture
def sample_analysis() -> dict[str, Any]:
    """Sample analysis results.

    Returns:
        Dictionary with sample analysis data
    """
    return {
        "entities": ["John Smith", "Sarah Jameson", "Acme Corporation"],
        "topics": [
            "infrastructure challenges",
            "scalability issues",
            "data pipeline",
        ],
        "structure": {"meeting_type": "initial_consultation", "speaker_count": 2},
        "data_availability": {
            "Customer Information": 0.9,
            "Background": 0.7,
            "Solution": 0.5,
        },
    }


@pytest.fixture
def mock_llm_response() -> dict[str, Any]:
    """Mock LLM sampling response.

    Returns:
        Dictionary simulating LLM response
    """
    return {
        "content": "Generated content from LLM",
        "metadata": {
            "model": "claude-sonnet-4-20250514",
            "tokens_used": {"input": 500, "output": 200},
            "finish_reason": "stop",
        },
    }


@pytest.fixture
def mock_mcp_server() -> Mock:
    """Mock MCP server for testing.

    Returns:
        Mock MCP server instance
    """
    server = Mock()
    server.sample = AsyncMock()
    server.list_resources = AsyncMock()
    server.read_resource = AsyncMock()
    server.elicit_input = AsyncMock()
    return server


@pytest.fixture
def test_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up test environment variables.

    Args:
        monkeypatch: pytest monkeypatch fixture
    """
    monkeypatch.setenv("LLM_ANTHROPIC_API_KEY", "test-api-key-12345")
    monkeypatch.setenv("LLM_MODEL", "claude-sonnet-4-20250514")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.3")
    monkeypatch.setenv("MCP_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("WORKFLOW_ENABLE_ELICITATION", "true")
