"""Tests for configuration management."""

import pytest
from pydantic import ValidationError

from mcp_snapshot_server.utils.config import (
    LLMSettings,
    MCPServerSettings,
    NLPSettings,
    Settings,
    WorkflowSettings,
    ZoomSettings,
)


@pytest.mark.unit
class TestMCPServerSettings:
    """Tests for MCP Server settings."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        settings = MCPServerSettings()
        assert settings.server_name == "snapshot-server"
        assert settings.version == "0.1.0"
        assert settings.log_level == "INFO"
        assert settings.structured_logging is True

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test environment variable override."""
        monkeypatch.setenv("MCP_SERVER_NAME", "custom-server")
        monkeypatch.setenv("MCP_LOG_LEVEL", "DEBUG")

        settings = MCPServerSettings()
        assert settings.server_name == "custom-server"
        assert settings.log_level == "DEBUG"

    def test_log_level_validation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test log level validation."""
        # Valid levels should work (case insensitive)
        for level in ["DEBUG", "debug", "Info", "WARNING", "ERROR", "CRITICAL"]:
            monkeypatch.setenv("MCP_LOG_LEVEL", level)
            settings = MCPServerSettings()
            assert settings.log_level == level.upper()

    def test_log_level_invalid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test invalid log level raises error."""
        monkeypatch.setenv("MCP_LOG_LEVEL", "INVALID")
        with pytest.raises(ValidationError, match="Invalid log level"):
            MCPServerSettings()

    def test_server_name_validation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test server name cannot be empty."""
        monkeypatch.setenv("MCP_SERVER_NAME", "")
        with pytest.raises(ValidationError, match="Server name cannot be empty"):
            MCPServerSettings()

    def test_server_name_strips_whitespace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test server name whitespace is stripped."""
        monkeypatch.setenv("MCP_SERVER_NAME", "  my-server  ")
        settings = MCPServerSettings()
        assert settings.server_name == "my-server"


@pytest.mark.unit
class TestLLMSettings:
    """Tests for LLM settings."""

    def test_required_api_key(self, test_env_vars: None) -> None:
        """Test that API key can be set from environment."""
        settings = LLMSettings()
        assert settings.anthropic_api_key == "test-api-key-12345"

    def test_default_api_key_is_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that API key defaults to empty string when not in environment."""
        # Set to empty string to override any .env file values
        # (delenv doesn't work because .env file takes precedence after env vars)
        monkeypatch.setenv("LLM_ANTHROPIC_API_KEY", "")
        settings = LLMSettings()
        assert settings.anthropic_api_key == ""

    def test_default_values(self, test_env_vars: None) -> None:
        """Test default LLM configuration values."""
        settings = LLMSettings()
        assert settings.model == "claude-sonnet-4-20250514"
        assert settings.temperature == 0.3
        assert settings.max_tokens_per_section == 1500
        assert settings.max_tokens_analysis == 2000
        assert settings.timeout == 60
        assert settings.max_retries == 3

    def test_temperature_validation(
        self, test_env_vars: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test temperature value validation."""
        # Temperature too high
        monkeypatch.setenv("LLM_TEMPERATURE", "2.0")
        with pytest.raises(Exception):  # Pydantic ValidationError
            LLMSettings()

        # Temperature too low
        monkeypatch.setenv("LLM_TEMPERATURE", "-0.1")
        with pytest.raises(Exception):  # Pydantic ValidationError
            LLMSettings()


@pytest.mark.unit
class TestWorkflowSettings:
    """Tests for workflow settings."""

    def test_default_values(self) -> None:
        """Test default workflow configuration values."""
        settings = WorkflowSettings()
        assert settings.parallel_section_generation is False
        assert settings.min_confidence_threshold == 0.5
        assert settings.enable_elicitation is True
        assert settings.enable_validation is True
        assert settings.enable_improvements is True
        assert settings.max_improvement_iterations == 2
        assert settings.default_output_format == "markdown"
        assert settings.include_metadata is True
        assert settings.include_confidence_scores is False

    def test_confidence_threshold_validation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test confidence threshold validation."""
        # Threshold too high
        monkeypatch.setenv("WORKFLOW_MIN_CONFIDENCE_THRESHOLD", "1.5")
        with pytest.raises(Exception):  # Pydantic ValidationError
            WorkflowSettings()

    def test_output_format_validation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test output format validation."""
        # Valid formats (case insensitive)
        for fmt in ["markdown", "json", "html", "MARKDOWN", "Json"]:
            monkeypatch.setenv("WORKFLOW_DEFAULT_OUTPUT_FORMAT", fmt)
            settings = WorkflowSettings()
            assert settings.default_output_format == fmt.lower()

    def test_output_format_invalid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test invalid output format raises error."""
        monkeypatch.setenv("WORKFLOW_DEFAULT_OUTPUT_FORMAT", "pdf")
        with pytest.raises(ValidationError, match="Invalid output format"):
            WorkflowSettings()


@pytest.mark.unit
class TestNLPSettings:
    """Tests for NLP settings."""

    def test_default_values(self) -> None:
        """Test default NLP configuration values."""
        settings = NLPSettings()
        assert settings.spacy_model == "en_core_web_sm"
        assert settings.extract_entities is True
        assert settings.extract_topics is True
        assert settings.min_entity_confidence == 0.5


@pytest.mark.unit
class TestSettings:
    """Tests for aggregated settings."""

    def test_settings_initialization(self, test_env_vars: None) -> None:
        """Test settings initialization."""
        settings = Settings()
        assert isinstance(settings.server, MCPServerSettings)
        assert isinstance(settings.llm, LLMSettings)
        assert isinstance(settings.workflow, WorkflowSettings)
        assert isinstance(settings.nlp, NLPSettings)

    def test_validate_success(self, test_env_vars: None) -> None:
        """Test successful validation."""
        settings = Settings()
        assert settings.validate() is True

    def test_validate_missing_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test validation fails with missing API key."""
        monkeypatch.setenv("LLM_ANTHROPIC_API_KEY", "")
        settings = Settings()
        settings.llm.anthropic_api_key = ""

        with pytest.raises(ValueError, match="LLM_ANTHROPIC_API_KEY"):
            settings.validate()

    def test_validate_invalid_model(
        self, test_env_vars: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test validation fails with invalid model at instantiation time."""
        # Model validation now happens at field level via @field_validator
        monkeypatch.setenv("LLM_MODEL", "invalid-model")

        with pytest.raises(Exception, match="Invalid model"):
            LLMSettings()

    def test_validate_valid_models(
        self, test_env_vars: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test validation succeeds with valid models."""
        valid_models = [
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514",
            "claude-3-5-sonnet-20241022",
        ]

        for model in valid_models:
            # Model validation happens at instantiation time via @field_validator
            monkeypatch.setenv("LLM_MODEL", model)
            settings = LLMSettings()
            assert settings.model == model


@pytest.mark.unit
class TestZoomSettings:
    """Tests for Zoom settings validation."""

    def test_default_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test default Zoom settings when environment is clear."""
        # Set to empty strings to override any .env file values
        monkeypatch.setenv("ZOOM_ACCOUNT_ID", "")
        monkeypatch.setenv("ZOOM_CLIENT_ID", "")
        monkeypatch.setenv("ZOOM_CLIENT_SECRET", "")
        settings = ZoomSettings()
        assert settings.account_id == ""
        assert settings.client_id == ""
        assert settings.client_secret == ""
        assert settings.default_user_id == "me"
        assert settings.api_timeout == 30
        assert settings.max_retries == 3

    def test_complete_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that complete credentials are valid."""
        monkeypatch.setenv("ZOOM_ACCOUNT_ID", "test-account")
        monkeypatch.setenv("ZOOM_CLIENT_ID", "test-client")
        monkeypatch.setenv("ZOOM_CLIENT_SECRET", "test-secret")

        settings = ZoomSettings()
        assert settings.is_configured is True

    def test_incomplete_credentials_raises_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that partial credentials raise validation error."""
        # Only account_id provided
        monkeypatch.setenv("ZOOM_ACCOUNT_ID", "test-account")
        monkeypatch.setenv("ZOOM_CLIENT_ID", "")
        monkeypatch.setenv("ZOOM_CLIENT_SECRET", "")

        with pytest.raises(ValidationError, match="Incomplete Zoom credentials"):
            ZoomSettings()

    def test_no_credentials_is_valid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that no credentials at all is valid (Zoom is optional)."""
        monkeypatch.setenv("ZOOM_ACCOUNT_ID", "")
        monkeypatch.setenv("ZOOM_CLIENT_ID", "")
        monkeypatch.setenv("ZOOM_CLIENT_SECRET", "")

        settings = ZoomSettings()
        assert settings.is_configured is False

    def test_is_zoom_configured_property(
        self, test_env_vars: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test Settings.is_zoom_configured property."""
        # Set to empty strings to override any .env file values
        monkeypatch.setenv("ZOOM_ACCOUNT_ID", "")
        monkeypatch.setenv("ZOOM_CLIENT_ID", "")
        monkeypatch.setenv("ZOOM_CLIENT_SECRET", "")
        settings = Settings()
        assert settings.is_zoom_configured is False
