"""Tests for configuration management."""

import pytest

from mcp_snapshot_server.utils.config import (
    LLMSettings,
    MCPServerSettings,
    NLPSettings,
    Settings,
    WorkflowSettings,
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


@pytest.mark.unit
class TestLLMSettings:
    """Tests for LLM settings."""

    def test_required_api_key(self, test_env_vars: None) -> None:
        """Test that API key can be set from environment."""
        settings = LLMSettings()
        assert settings.anthropic_api_key == "test-api-key-12345"

    def test_default_api_key_is_empty(self) -> None:
        """Test that API key defaults to empty string."""
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

        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY is required"):
            settings.validate()

    def test_validate_invalid_model(self, test_env_vars: None) -> None:
        """Test validation fails with invalid model."""
        settings = Settings()
        settings.llm.model = "invalid-model"

        with pytest.raises(ValueError, match="Invalid model"):
            settings.validate()

    def test_validate_valid_models(self, test_env_vars: None) -> None:
        """Test validation succeeds with valid models."""
        settings = Settings()

        valid_models = [
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514",
            "claude-3-5-sonnet-20241022",
        ]

        for model in valid_models:
            settings.llm.model = model
            assert settings.validate() is True
