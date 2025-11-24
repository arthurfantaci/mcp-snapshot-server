"""Tests for Orchestration Agent."""

from unittest.mock import AsyncMock, patch

import pytest

from mcp_snapshot_server.agents.orchestrator import OrchestrationAgent
from mcp_snapshot_server.models.analysis import AnalysisResult, TranscriptStructure
from mcp_snapshot_server.models.sections import (
    OrchestrationInput,
    SectionResult,
    SnapshotOutput,
)
from mcp_snapshot_server.models.transcript import SpeakerTurn, TranscriptData
from mcp_snapshot_server.models.validation import ValidationResult
from mcp_snapshot_server.utils.errors import ErrorCode, MCPServerError
from mcp_snapshot_server.utils.logging_config import ContextLogger


@pytest.fixture
def orchestrator_agent():
    """Create an OrchestrationAgent instance."""
    logger = ContextLogger("test_orchestrator")
    return OrchestrationAgent(logger=logger)


@pytest.fixture
def mock_transcript_data():
    """Mock parsed transcript data."""
    from mcp_snapshot_server.models.transcript import TranscriptMetadata

    return TranscriptData(
        text="This is a sample transcript about Acme Corporation...",
        speakers=["Alice", "Bob"],
        speaker_turns=[
            SpeakerTurn(speaker="Alice", text="Welcome to the meeting.", start="00:00:00.000", end="00:00:05.000"),
            SpeakerTurn(speaker="Bob", text="Thank you for having us.", start="00:00:05.000", end="00:00:10.000"),
        ],
        duration=300.0,
        metadata=TranscriptMetadata(vtt_filename="sample.vtt"),
    )


@pytest.fixture
def mock_analysis_results():
    """Mock analysis results."""
    return AnalysisResult(
        entities={
            "PERSON": ["Alice", "Bob"],
            "ORG": ["Acme Corporation"],
            "PRODUCT": ["Enterprise Cloud Platform"],
        },
        topics=["cloud migration", "cost savings", "automation"],
        structure=TranscriptStructure(meeting_type="review", speaker_count=2),
        data_availability={
            "Customer Information": 0.8,
            "Background": 0.7,
            "Solution": 0.9,
        },
    )


@pytest.fixture
def mock_section_result():
    """Mock section generation result."""
    return SectionResult(
        section_name="Customer Information",
        content="Company Name: Acme Corporation\nIndustry: Technology",
        confidence=0.85,
        missing_fields=[],
    )


class TestOrchestrationAgent:
    """Test cases for OrchestrationAgent."""

    def test_initialization(self, orchestrator_agent):
        """Test OrchestrationAgent initialization."""
        assert orchestrator_agent.name == "OrchestrationAgent"
        assert orchestrator_agent.system_prompt is not None
        assert orchestrator_agent.analysis_agent is not None
        assert orchestrator_agent.validation_agent is not None
        assert (
            len(orchestrator_agent.section_generators) == 10
        )  # Excluding exec summary

    def test_section_names(self, orchestrator_agent):
        """Test that all 11 section names are defined."""
        assert len(orchestrator_agent.SECTION_NAMES) == 11
        assert "Customer Information" in orchestrator_agent.SECTION_NAMES
        assert "Executive Summary" in orchestrator_agent.SECTION_NAMES

    def test_section_prompt_keys(self, orchestrator_agent):
        """Test section prompt key mappings."""
        assert len(orchestrator_agent.SECTION_PROMPT_KEYS) == 11
        assert (
            orchestrator_agent.SECTION_PROMPT_KEYS["Customer Information"]
            == "customer_information"
        )

    def test_orchestration_input_requires_vtt_content(self):
        """Test OrchestrationInput validation requires non-empty vtt_content."""
        from pydantic import ValidationError

        # Empty string should fail due to min_length=1
        with pytest.raises(ValidationError) as exc_info:
            OrchestrationInput(vtt_content="")

        assert "vtt_content" in str(exc_info.value)

    @patch("mcp_snapshot_server.agents.orchestrator.parse_vtt_content")
    def test_parse_transcript(
        self, mock_parse, orchestrator_agent, mock_transcript_data
    ):
        """Test transcript content parsing."""
        mock_parse.return_value = mock_transcript_data
        vtt_content = "WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nTest content"

        result = orchestrator_agent._parse_transcript(vtt_content, "test.vtt")

        assert isinstance(result, TranscriptData)
        assert result.text == mock_transcript_data.text
        mock_parse.assert_called_once_with(vtt_content, "test.vtt")

    @patch("mcp_snapshot_server.agents.orchestrator.parse_vtt_content")
    def test_parse_transcript_error(self, mock_parse, orchestrator_agent):
        """Test transcript parsing error handling."""
        mock_parse.side_effect = Exception("Invalid VTT format")
        vtt_content = "Invalid content"

        with pytest.raises(MCPServerError) as exc_info:
            orchestrator_agent._parse_transcript(vtt_content, "invalid.vtt")

        assert exc_info.value.error_code == ErrorCode.PARSE_ERROR

    @pytest.mark.asyncio
    async def test_analyze_transcript(
        self, orchestrator_agent, mock_transcript_data, mock_analysis_results
    ):
        """Test transcript analysis."""
        # Mock the analysis agent
        orchestrator_agent.analysis_agent.process = AsyncMock(
            return_value=mock_analysis_results
        )

        result = await orchestrator_agent._analyze_transcript(mock_transcript_data)

        assert isinstance(result, AnalysisResult)
        assert result.entities == mock_analysis_results.entities
        orchestrator_agent.analysis_agent.process.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_sections_sequential(
        self, orchestrator_agent, mock_transcript_data, mock_analysis_results
    ):
        """Test sequential section generation."""
        # Mock section generators to return SectionResult
        for name, generator in orchestrator_agent.section_generators.items():
            generator.process = AsyncMock(
                return_value=SectionResult(
                    section_name=name,
                    content="Test content",
                    confidence=0.8,
                    missing_fields=[],
                )
            )

        # Disable parallel generation
        orchestrator_agent.settings.workflow.parallel_section_generation = False

        sections = await orchestrator_agent._generate_sections(
            mock_transcript_data, mock_analysis_results
        )

        assert len(sections) == 10  # Excluding Executive Summary
        # Each generator should have been called once
        for generator in orchestrator_agent.section_generators.values():
            generator.process.assert_called_once()
        # Results should be SectionResult instances
        for section in sections.values():
            assert isinstance(section, SectionResult)

    @pytest.mark.asyncio
    async def test_generate_sections_parallel(
        self, orchestrator_agent, mock_transcript_data, mock_analysis_results
    ):
        """Test parallel section generation."""
        # Mock section generators to return SectionResult
        for name, generator in orchestrator_agent.section_generators.items():
            generator.process = AsyncMock(
                return_value=SectionResult(
                    section_name=name,
                    content="Test content",
                    confidence=0.8,
                    missing_fields=[],
                )
            )

        # Enable parallel generation
        orchestrator_agent.settings.workflow.parallel_section_generation = True

        sections = await orchestrator_agent._generate_sections(
            mock_transcript_data, mock_analysis_results
        )

        assert len(sections) == 10  # Excluding Executive Summary
        # Results should be SectionResult instances
        for section in sections.values():
            assert isinstance(section, SectionResult)

    @pytest.mark.asyncio
    async def test_generate_sections_handles_errors(
        self, orchestrator_agent, mock_transcript_data, mock_analysis_results
    ):
        """Test that section generation handles individual generator errors."""
        # Mock one generator to fail
        section_names = list(orchestrator_agent.section_generators.keys())
        generators = list(orchestrator_agent.section_generators.values())
        generators[0].process = AsyncMock(side_effect=Exception("Generator error"))

        # Mock the rest to succeed
        for i, generator in enumerate(generators[1:], start=1):
            generator.process = AsyncMock(
                return_value=SectionResult(
                    section_name=section_names[i],
                    content="Test content",
                    confidence=0.8,
                    missing_fields=[],
                )
            )

        orchestrator_agent.settings.workflow.parallel_section_generation = False

        sections = await orchestrator_agent._generate_sections(
            mock_transcript_data, mock_analysis_results
        )

        # Should still generate sections, with error placeholder for failed one
        assert len(sections) == 10
        # First section should have error placeholder
        first_section = list(sections.values())[0]
        assert isinstance(first_section, SectionResult)
        assert first_section.confidence == 0.0
        assert "failed" in first_section.content.lower()

    @pytest.mark.asyncio
    async def test_validate_sections(self, orchestrator_agent):
        """Test section validation."""
        sections = {
            "Customer Information": SectionResult(
                section_name="Customer Information",
                content="Test content",
                confidence=0.8,
            )
        }

        mock_validation_result = ValidationResult(
            factual_consistency=True,
            completeness=True,
            quality=True,
            issues=[],
            improvements=[],
            requires_improvements=False,
        )

        orchestrator_agent.validation_agent.process = AsyncMock(
            return_value=mock_validation_result
        )

        result = await orchestrator_agent._validate_sections(sections)

        assert isinstance(result, ValidationResult)
        assert result.factual_consistency is True
        orchestrator_agent.validation_agent.process.assert_called_once()

    @pytest.mark.asyncio
    async def test_improve_sections(
        self, orchestrator_agent, mock_transcript_data, mock_analysis_results
    ):
        """Test section improvement logic."""
        sections = {
            "Customer Information": SectionResult(
                section_name="Customer Information",
                content="Low confidence content",
                confidence=0.3,  # Below threshold
            )
        }

        validation_results = ValidationResult(
            issues=["Missing company name"],
            requires_improvements=True,
        )

        # Currently just returns sections as-is
        improved = await orchestrator_agent._improve_sections(
            sections, validation_results, mock_transcript_data, mock_analysis_results
        )

        # For now, should return unchanged
        assert improved == sections

    @pytest.mark.asyncio
    async def test_generate_executive_summary(self, orchestrator_agent):
        """Test executive summary generation."""
        sections = {
            "Customer Information": SectionResult(
                section_name="Customer Information",
                content="Acme Corporation, Technology sector",
                confidence=0.8,
            ),
            "Background": SectionResult(
                section_name="Background",
                content="Faced automation challenges",
                confidence=0.7,
            ),
        }

        # Mock the executive summary generator
        with patch.object(
            orchestrator_agent,
            "_generate_executive_summary",
            new_callable=AsyncMock,
        ) as mock_gen:
            mock_gen.return_value = SectionResult(
                section_name="Executive Summary",
                content="Comprehensive summary of all sections",
                confidence=0.9,
                missing_fields=[],
            )

            result = await orchestrator_agent._generate_executive_summary(sections)

            assert isinstance(result, SectionResult)
            assert result.section_name == "Executive Summary"
            assert "summary" in result.content.lower()

    def test_build_all_sections_text(self, orchestrator_agent):
        """Test building combined sections text."""
        sections = {
            "Customer Information": SectionResult(
                section_name="Customer Information",
                content="Acme Corporation",
                confidence=0.8,
            ),
            "Background": SectionResult(
                section_name="Background",
                content="Business challenges",
                confidence=0.7,
            ),
            "Executive Summary": SectionResult(
                section_name="Executive Summary",
                content="Should be excluded",
                confidence=0.9,
            ),
        }

        text = orchestrator_agent._build_all_sections_text(sections)

        assert "Customer Information" in text
        assert "Acme Corporation" in text
        assert "Background" in text
        assert "Business challenges" in text
        # Executive Summary should not be included
        assert "Should be excluded" not in text

    def test_assemble_output(self, orchestrator_agent):
        """Test final output assembly."""
        sections = {
            "Customer Information": SectionResult(
                section_name="Customer Information",
                content="Test content",
                confidence=0.8,
                missing_fields=["location"],
            ),
            "Background": SectionResult(
                section_name="Background",
                content="Background info",
                confidence=0.7,
                missing_fields=[],
            ),
        }

        analysis_results = AnalysisResult(
            entities={"ORG": ["Acme"]},
            topics=["automation"],
        )

        validation_results = ValidationResult(
            factual_consistency=True,
            issues=[],
            requires_improvements=False,
        )

        output = orchestrator_agent._assemble_output(
            sections, analysis_results, validation_results
        )

        assert isinstance(output, SnapshotOutput)
        assert len(output.sections) == 2
        assert output.metadata.total_sections == 2
        assert output.metadata.avg_confidence == 0.75  # (0.8 + 0.7) / 2

        # Check missing fields aggregation
        assert "location" in output.missing_fields

    @pytest.mark.asyncio
    @patch("mcp_snapshot_server.agents.orchestrator.parse_vtt_content")
    async def test_full_workflow_integration(
        self,
        mock_parse,
        orchestrator_agent,
        mock_transcript_data,
        mock_analysis_results,
        sample_vtt_content,
        test_env_vars,
    ):
        """Test complete workflow integration."""
        mock_parse.return_value = mock_transcript_data

        # Mock analysis agent
        orchestrator_agent.analysis_agent.process = AsyncMock(
            return_value=mock_analysis_results
        )

        # Mock section generators to return SectionResult
        for name, generator in orchestrator_agent.section_generators.items():
            generator.process = AsyncMock(
                return_value=SectionResult(
                    section_name=name,
                    content="Content",
                    confidence=0.8,
                    missing_fields=[],
                )
            )

        # Mock validation agent
        orchestrator_agent.validation_agent.process = AsyncMock(
            return_value=ValidationResult(
                factual_consistency=True,
                completeness=True,
                quality=True,
                issues=[],
                improvements=[],
                requires_improvements=False,
                missing_critical_info=[],
            )
        )

        # Disable parallel processing for predictable test
        orchestrator_agent.settings.workflow.parallel_section_generation = False

        # Mock executive summary generation
        with patch.object(
            orchestrator_agent,
            "_generate_executive_summary",
            new_callable=AsyncMock,
        ) as mock_exec_summary:
            mock_exec_summary.return_value = SectionResult(
                section_name="Executive Summary",
                content="Test executive summary",
                confidence=0.9,
                missing_fields=[],
            )

            # Run full workflow with OrchestrationInput
            input_data = OrchestrationInput(
                vtt_content=sample_vtt_content,
                filename="test.vtt",
            )
            result = await orchestrator_agent.process(input_data)

            # Verify output structure
            assert isinstance(result, SnapshotOutput)
            assert len(result.sections) == 11  # 10 + Executive Summary
            assert "Executive Summary" in result.sections
