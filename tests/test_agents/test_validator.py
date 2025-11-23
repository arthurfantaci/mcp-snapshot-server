"""Tests for Validation Agent."""

import pytest

from mcp_snapshot_server.agents.validator import ValidationAgent
from mcp_snapshot_server.utils.logging_config import ContextLogger


@pytest.fixture
def validator_agent():
    """Create a ValidationAgent instance."""
    logger = ContextLogger("test_validator")
    return ValidationAgent(logger=logger)


@pytest.fixture
def sample_sections():
    """Sample sections for validation testing."""
    return {
        "Customer Information": {
            "content": """Company Name: Acme Corporation
Industry: Financial Services
Location: San Francisco, California, USA
Primary Contact: John Smith
Position: Chief Technology Officer""",
            "confidence": 0.9,
            "missing_fields": [],
        },
        "Background": {
            "content": """The customer faced significant challenges with manual data processing,
which was consuming 40 hours per week of staff time and leading to frequent errors.""",
            "confidence": 0.8,
            "missing_fields": [],
        },
        "Solution": {
            "content": """Implemented Enterprise Cloud Platform with automated workflows,
reducing manual intervention by 90%.""",
            "confidence": 0.85,
            "missing_fields": [],
        },
    }


@pytest.fixture
def sections_with_issues():
    """Sample sections with validation issues."""
    return {
        "Customer Information": {
            "content": """Company Name: Not mentioned in transcript
Industry: Not specified""",
            "confidence": 0.3,
            "missing_fields": ["company_name", "industry"],
        },
        "Background": {
            "content": "Problem unclear from transcript.",
            "confidence": 0.2,
            "missing_fields": [],
        },
    }


class TestValidationAgent:
    """Test cases for ValidationAgent."""

    def test_initialization(self, validator_agent):
        """Test ValidationAgent initialization."""
        assert validator_agent.name == "ValidationAgent"
        assert validator_agent.system_prompt is not None

    @pytest.mark.asyncio
    async def test_process_valid_sections(self, validator_agent, sample_sections):
        """Test validation of valid sections."""
        result = await validator_agent.process({"sections": sample_sections})

        assert isinstance(result, dict)
        assert "issues" in result
        assert "factual_consistency" in result
        assert "completeness" in result
        assert "quality" in result
        assert "requires_improvements" in result
        assert isinstance(result["issues"], list)

    @pytest.mark.asyncio
    async def test_process_sections_with_issues(
        self, validator_agent, sections_with_issues
    ):
        """Test validation of sections with issues."""
        result = await validator_agent.process({"sections": sections_with_issues})

        assert isinstance(result, dict)
        assert "issues" in result
        # Should detect issues from heuristic validation
        assert len(result["issues"]) > 0
        # Should require improvements
        assert result.get("requires_improvements", False) is True

    def test_build_sections_text(self, validator_agent, sample_sections):
        """Test building sections text."""
        sections_text = validator_agent._build_sections_text(sample_sections)

        assert isinstance(sections_text, str)
        assert "Customer Information" in sections_text
        assert "Acme Corporation" in sections_text
        assert "Background" in sections_text

    def test_heuristic_validate_missing_sections(self, validator_agent):
        """Test heuristic validation for missing critical sections."""
        sections = {
            "Background": {"content": "Some background information"},
            "Solution": {"content": "Some solution description"},
        }

        result = validator_agent._heuristic_validate(sections)

        assert "issues" in result
        issues = result["issues"]
        # Should flag missing Customer Information
        assert any("Customer Information" in issue for issue in issues)

    def test_heuristic_validate_short_sections(self, validator_agent):
        """Test heuristic validation for very short sections."""
        sections = {
            "Customer Information": {"content": "Short"},  # Less than 50 chars
            "Background": {"content": "Also very short"},
        }

        result = validator_agent._heuristic_validate(sections)

        assert "issues" in result
        issues = result["issues"]
        # Should flag short sections
        assert len(issues) >= 2  # Both sections are too short

    def test_extract_dates(self, validator_agent):
        """Test date extraction from sections."""
        sections = {
            "Engagement Details": {
                "content": "Start Date: 2024-07-14, Completion: 2024-12-15"
            },
            "Background": {"content": "Project began on 2024-01-01"},
        }

        dates = validator_agent._extract_dates(sections)

        assert isinstance(dates, list)
        assert "2024-07-14" in dates
        assert "2024-12-15" in dates
        assert "2024-01-01" in dates

    def test_extract_issues(self, validator_agent):
        """Test issue extraction from LLM response."""
        response = """FACTUAL CONSISTENCY:
- Contradictory dates mentioned
- Company name differs between sections

COMPLETENESS:
All fields present
"""

        issues = validator_agent._extract_issues(response)

        assert isinstance(issues, list)
        assert len(issues) >= 2
        assert any("date" in issue.lower() for issue in issues)

    def test_extract_improvements(self, validator_agent):
        """Test improvement extraction from LLM response."""
        response = """IMPROVEMENTS:
- Add more specific metrics in Results section
- Include customer testimonial quote
- Clarify timeline in Engagement Details

QUALITY ISSUES:
None found
"""

        improvements = validator_agent._extract_improvements(response)

        assert isinstance(improvements, list)
        assert len(improvements) >= 3
        assert any("metric" in imp.lower() for imp in improvements)

    def test_parse_validation_response_with_contradictions(self, validator_agent):
        """Test parsing response with contradictions."""
        response = """FACTUAL CONSISTENCY:
Found contradiction in dates

COMPLETENESS:
Missing critical customer information

QUALITY ISSUES:
Unprofessional tone in several sections

IMPROVEMENTS:
Need improvement in timeline section
"""

        result = validator_agent._parse_validation_response(response)

        assert result["factual_consistency"] is False  # Has "contradiction"
        assert result["completeness"] is False  # Has "missing"
        assert result["quality"] is False  # Has "unprofessional" quality keyword
        assert result["requires_improvements"] is True  # Has "improvement" keyword

    def test_parse_validation_response_clean(self, validator_agent):
        """Test parsing clean validation response."""
        response = """FACTUAL CONSISTENCY:
All facts are consistent

COMPLETENESS:
All required information present

QUALITY ISSUES:
No problems found
"""

        result = validator_agent._parse_validation_response(response)

        # These should be True since negative keywords are absent
        assert result["factual_consistency"] is True
        assert result["completeness"] is True
        # Quality should be True because "No problems found" doesn't contain quality keywords
        assert result["quality"] is True

    def test_merge_validation_results(self, validator_agent):
        """Test merging LLM and heuristic validation results."""
        llm_results = {
            "factual_consistency": True,
            "completeness": False,
            "quality": True,
            "issues": ["Missing date in timeline"],
            "improvements": ["Add more details"],
            "requires_improvements": True,
        }

        heuristic_results = {
            "issues": ["Section X is too short", "Missing critical section Y"],
            "heuristic": True,
        }

        merged = validator_agent._merge_validation_results(
            llm_results, heuristic_results
        )

        assert merged["factual_consistency"] is True
        assert merged["completeness"] is False
        assert merged["quality"] is True
        # Issues should be combined
        assert len(merged["issues"]) == 3  # 1 from LLM + 2 from heuristic
        assert merged["requires_improvements"] is True

    def test_merge_validation_results_heuristic_triggers_improvement(
        self, validator_agent
    ):
        """Test that heuristic issues trigger improvement flag."""
        llm_results = {
            "factual_consistency": True,
            "completeness": True,
            "quality": True,
            "issues": [],
            "improvements": [],
            "requires_improvements": False,  # LLM says all good
        }

        heuristic_results = {
            "issues": ["Section is too short"],  # But heuristic finds issue
            "heuristic": True,
        }

        merged = validator_agent._merge_validation_results(
            llm_results, heuristic_results
        )

        # Should require improvements because heuristic found issues
        assert merged["requires_improvements"] is True
