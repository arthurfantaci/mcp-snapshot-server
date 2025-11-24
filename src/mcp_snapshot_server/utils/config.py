"""Configuration management for MCP Snapshot Server.

This module provides comprehensive configuration settings for the entire application,
organized into logical groups using Pydantic Settings.
"""

import logging
from typing import Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valid logging levels
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

# Valid Claude models
VALID_CLAUDE_MODELS = {
    "claude-sonnet-4-20250514",
    "claude-opus-4-20250514",
    "claude-3-5-sonnet-20241022",
}

# Valid output formats
VALID_OUTPUT_FORMATS = {"markdown", "json", "html"}


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

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is a valid Python logging level."""
        upper_v = v.upper()
        if upper_v not in VALID_LOG_LEVELS:
            raise ValueError(
                f"Invalid log level '{v}'. Must be one of: {sorted(VALID_LOG_LEVELS)}"
            )
        return upper_v

    @field_validator("server_name")
    @classmethod
    def validate_server_name(cls, v: str) -> str:
        """Validate server name is not empty."""
        if not v or not v.strip():
            raise ValueError("Server name cannot be empty")
        return v.strip()


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

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        """Validate model is a supported Claude model."""
        if v not in VALID_CLAUDE_MODELS:
            raise ValueError(
                f"Invalid model '{v}'. Must be one of: {sorted(VALID_CLAUDE_MODELS)}"
            )
        return v

    @field_validator("anthropic_api_key")
    @classmethod
    def validate_api_key_format(cls, v: str) -> str:
        """Validate API key format if provided."""
        if v and not v.startswith("sk-"):
            logging.getLogger(__name__).warning(
                "Anthropic API key format may be invalid (expected 'sk-' prefix)"
            )
        return v


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

    @field_validator("default_output_format")
    @classmethod
    def validate_output_format(cls, v: str) -> str:
        """Validate output format is supported."""
        lower_v = v.lower()
        if lower_v not in VALID_OUTPUT_FORMATS:
            raise ValueError(
                f"Invalid output format '{v}'. Must be one of: {sorted(VALID_OUTPUT_FORMATS)}"
            )
        return lower_v


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


class ZoomSettings(BaseSettings):
    """Zoom API configuration for Server-to-Server OAuth."""

    model_config = SettingsConfigDict(
        env_prefix="ZOOM_", env_file=".env", extra="ignore"
    )

    # OAuth credentials
    account_id: str = Field(
        default="", description="Zoom account ID for Server-to-Server OAuth"
    )

    client_id: str = Field(
        default="", description="Zoom OAuth client ID"
    )

    client_secret: str = Field(
        default="", description="Zoom OAuth client secret"
    )

    # API settings
    default_user_id: str = Field(
        default="me", description="Default user ID for API calls (me = authenticated user)"
    )

    api_timeout: int = Field(
        default=30, ge=10, le=120, description="API request timeout in seconds"
    )

    max_retries: int = Field(
        default=3, ge=1, le=5, description="Maximum API retry attempts"
    )

    # Caching settings
    cache_ttl_seconds: int = Field(
        default=900,  # 15 minutes
        ge=0,
        le=3600,
        description="Cache TTL for recordings list in seconds (0 = no cache)",
    )

    max_cache_size: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Maximum number of cached recordings list entries",
    )

    @model_validator(mode="after")
    def validate_zoom_credentials(self) -> Self:
        """Validate that if any Zoom credential is provided, all must be provided."""
        creds_provided = any([self.account_id, self.client_id, self.client_secret])
        creds_complete = all([self.account_id, self.client_id, self.client_secret])

        if creds_provided and not creds_complete:
            missing = []
            if not self.account_id:
                missing.append("ZOOM_ACCOUNT_ID")
            if not self.client_id:
                missing.append("ZOOM_CLIENT_ID")
            if not self.client_secret:
                missing.append("ZOOM_CLIENT_SECRET")
            raise ValueError(
                f"Incomplete Zoom credentials. Missing: {', '.join(missing)}"
            )
        return self

    @property
    def is_configured(self) -> bool:
        """Check if Zoom credentials are fully configured."""
        return all([self.account_id, self.client_id, self.client_secret])


class DemoSettings(BaseSettings):
    """Demo mode configuration."""

    model_config = SettingsConfigDict(
        env_prefix="DEMO_", env_file=".env", extra="ignore"
    )

    mode: bool = Field(
        default=False,
        description="Enable demo mode to preload Quest Enterprises demo transcript",
    )


class Settings:
    """Aggregated settings for the entire application."""

    def __init__(self) -> None:
        """Initialize all settings groups.

        Note: Individual settings groups perform their own validation via
        Pydantic field and model validators. This initialization will raise
        ValidationError if any settings are invalid.
        """
        self.server = MCPServerSettings()
        self.llm = LLMSettings()
        self.workflow = WorkflowSettings()
        self.nlp = NLPSettings()
        self.zoom = ZoomSettings()
        self.demo = DemoSettings()

    def validate(self) -> bool:
        """Validate all settings.

        This method performs additional cross-group validation that cannot
        be done at the individual settings level.

        Returns:
            bool: True if all settings are valid

        Raises:
            ValueError: If any settings are invalid
        """
        # Check required API keys (not validated at field level to allow empty default)
        if not self.llm.anthropic_api_key:
            raise ValueError(
                "LLM_ANTHROPIC_API_KEY (or ANTHROPIC_API_KEY) environment variable is required"
            )

        # Note: Model validation is now handled by LLMSettings.validate_model()
        # Note: Zoom credential validation is now handled by ZoomSettings.validate_zoom_credentials()

        return True

    @property
    def is_zoom_configured(self) -> bool:
        """Check if Zoom integration is fully configured."""
        return self.zoom.is_configured


def get_settings() -> Settings:
    """Get or create global settings instance.

    Returns:
        Settings instance
    """
    global _settings
    if "_settings" not in globals():
        _settings = Settings()
    return _settings
