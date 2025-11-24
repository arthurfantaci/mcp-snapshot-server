"""Base agent class for all MCP agents.

This module provides the abstract base class that all specialized agents inherit from.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel

from mcp_snapshot_server.utils.logging_config import ContextLogger

# Type variables for generic agent input/output
InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class BaseAgent(ABC, Generic[InputT, OutputT]):
    """Abstract base class for all agents in the system.

    This class is generic over input and output types, allowing concrete
    implementations to specify their exact input/output Pydantic models.

    Type Parameters:
        InputT: The Pydantic model type for input data
        OutputT: The Pydantic model type for output data
    """

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
    async def process(self, input_data: InputT) -> OutputT:
        """Process input and return results.

        This method must be implemented by all concrete agent classes.

        Args:
            input_data: Pydantic model containing input data for processing

        Returns:
            Pydantic model containing processing results with metadata
        """
        pass
