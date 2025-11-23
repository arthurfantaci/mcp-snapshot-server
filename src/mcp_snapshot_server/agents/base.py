"""Base agent class for all MCP agents.

This module provides the abstract base class that all specialized agents inherit from.
"""

from abc import ABC, abstractmethod
from typing import Any

from mcp_snapshot_server.utils.logging_config import ContextLogger


class BaseAgent(ABC):
    """Abstract base class for all agents in the system."""

    def __init__(self, name: str, system_prompt: str, logger: ContextLogger):
        """Initialize base agent.

        Args:
            name: Agent name for logging and identification
            system_prompt: System prompt defining agent's role and behavior
            logger: Context logger for structured logging
        """
        self.name = name
        self.system_prompt = system_prompt
        self.logger = logger

    @abstractmethod
    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Process input and return results.

        This method must be implemented by all concrete agent classes.

        Args:
            input_data: Input data for processing

        Returns:
            Processing results with metadata
        """
        pass
