"""Configuration management for MCP Snapshot Server.

This module provides comprehensive configuration settings for the entire application,
organized into logical groups using Pydantic Settings.
"""


from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MCPServerSettings(BaseSettings):
    """Main MCP Server configuration."""

    model_config = SettingsConfigDict(
        env_prefix="MCP_", env_file=".env", extra="ignore"
    )

    # Server settings
    server_name: str = Field(default="snapshot-server", description="MCP server name")

    version: str = Field(default="0.1.0", description="Server version")

    log_level: str = Field(default="INFO", description="Logging level")

    structured_logging: bool = Field(
        default=True, description="Enable structured JSON logging"
    )


class LLMSettings(BaseSettings):
    """LLM/Claude configuration."""

    model_config = SettingsConfigDict(
        env_prefix="LLM_", env_file=".env", extra="ignore"
    )

    # API settings
    anthropic_api_key: str = Field(
        default="",  # Empty by default, validated in Settings.validate()
        description="Anthropic API key",
    )

    model: str = Field(
        default="claude-sonnet-4-20250514", description="Claude model to use"
    )

    temperature: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Sampling temperature"
    )

    max_tokens_per_section: int = Field(
        default=1500,
        ge=100,
        le=4000,
        description="Maximum tokens per section",
    )

    max_tokens_analysis: int = Field(
        default=2000,
        ge=500,
        le=4000,
        description="Maximum tokens for analysis",
    )

    timeout: int = Field(
        default=60, ge=10, le=300, description="API timeout in seconds"
    )

    max_retries: int = Field(
        default=3, ge=1, le=5, description="Maximum retry attempts"
    )


class WorkflowSettings(BaseSettings):
    """Snapshot generation workflow configuration."""

    model_config = SettingsConfigDict(
        env_prefix="WORKFLOW_", env_file=".env", extra="ignore"
    )

    # Generation settings
    parallel_section_generation: bool = Field(
        default=False, description="Generate sections in parallel"
    )

    min_confidence_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum acceptable confidence score",
    )

    enable_elicitation: bool = Field(
        default=True,
        description="Enable user input elicitation for missing info",
    )

    enable_validation: bool = Field(
        default=True, description="Enable cross-section validation"
    )

    enable_improvements: bool = Field(
        default=True,
        description="Enable automatic improvements for low-confidence sections",
    )

    max_improvement_iterations: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Maximum iterations for section improvements",
    )

    # Output settings
    default_output_format: str = Field(
        default="markdown", description="Default output format"
    )

    include_metadata: bool = Field(
        default=True, description="Include generation metadata in output"
    )

    include_confidence_scores: bool = Field(
        default=False, description="Include confidence scores in output"
    )


class NLPSettings(BaseSettings):
    """NLP processing configuration."""

    model_config = SettingsConfigDict(
        env_prefix="NLP_", env_file=".env", extra="ignore"
    )

    spacy_model: str = Field(
        default="en_core_web_sm", description="spaCy model for entity extraction"
    )

    extract_entities: bool = Field(
        default=True, description="Extract named entities from transcript"
    )

    extract_topics: bool = Field(
        default=True, description="Extract key topics from transcript"
    )

    min_entity_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for entity extraction",
    )


class Settings:
    """Aggregated settings for the entire application."""

    def __init__(self) -> None:
        """Initialize all settings groups."""
        self.server = MCPServerSettings()
        self.llm = LLMSettings()
        self.workflow = WorkflowSettings()
        self.nlp = NLPSettings()

    def validate(self) -> bool:
        """Validate all settings.

        Returns:
            bool: True if all settings are valid

        Raises:
            ValueError: If any settings are invalid
        """
        # Check required API keys
        if not self.llm.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required")

        # Validate model name
        valid_models = [
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514",
            "claude-3-5-sonnet-20241022",
        ]
        if self.llm.model not in valid_models:
            raise ValueError(f"Invalid model. Must be one of: {valid_models}")

        return True


def get_settings() -> Settings:
    """Get or create global settings instance.

    Returns:
        Settings instance
    """
    global _settings
    if "_settings" not in globals():
        _settings = Settings()
    return _settings
