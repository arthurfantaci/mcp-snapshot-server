"""Section-related Pydantic models."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import Field

from mcp_snapshot_server.models.base import SnapshotBaseModel
from mcp_snapshot_server.models.validation import ValidationResult

if TYPE_CHECKING:
    from mcp_snapshot_server.models.analysis import AnalysisResult


class SectionMetadata(SnapshotBaseModel):
    """Metadata about section generation from LLM."""

    model: str | None = Field(None, description="Model used for generation")
    tokens_used: dict[str, int] = Field(
        default_factory=dict, description="Token counts (input/output)"
    )
    finish_reason: str | None = Field(None, description="Why generation stopped")
    error: str | None = Field(None, description="Error message if generation failed")


class SectionResult(SnapshotBaseModel):
    """Result from SectionGeneratorAgent.process()."""

    section_name: str = Field(..., min_length=1, description="Name of the section")
    content: str = Field(..., description="Generated section content")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence score")
    missing_fields: list[str] = Field(
        default_factory=list, description="Fields that couldn't be populated"
    )
    metadata: SectionMetadata = Field(
        default_factory=SectionMetadata, description="Generation metadata"
    )

    @classmethod
    def error_placeholder(cls, section_name: str, error: str) -> SectionResult:
        """Create an error placeholder section.

        Args:
            section_name: Name of the section
            error: Error message

        Returns:
            SectionResult with error content
        """
        return cls(
            section_name=section_name,
            content=f"[Section generation failed: {error}]",
            confidence=0.0,
            missing_fields=[],
            metadata=SectionMetadata(error=error),
        )


class SectionContent(SnapshotBaseModel):
    """Section content in the final snapshot output."""

    content: str = Field(..., description="Section content")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence score")
    missing_fields: list[str] = Field(
        default_factory=list, description="Missing fields"
    )


class SnapshotMetadata(SnapshotBaseModel):
    """Metadata about the snapshot generation."""

    avg_confidence: float = Field(0.0, ge=0.0, le=1.0, description="Average confidence")
    total_sections: int = Field(0, ge=0, description="Number of sections")
    entities_extracted: dict[str, list[str]] = Field(
        default_factory=dict, description="Named entities found"
    )
    topics_identified: list[str] = Field(
        default_factory=list, description="Topics identified"
    )


class SnapshotOutput(SnapshotBaseModel):
    """Complete Customer Success Snapshot output."""

    sections: dict[str, SectionContent] = Field(
        default_factory=dict, description="All generated sections"
    )
    metadata: SnapshotMetadata = Field(
        default_factory=SnapshotMetadata, description="Snapshot metadata"
    )
    validation: ValidationResult = Field(
        default_factory=lambda: ValidationResult(),
        description="Validation results",
    )
    missing_fields: list[str] = Field(
        default_factory=list, description="Deduplicated list of all missing fields"
    )

    @property
    def section_count(self) -> int:
        """Return number of sections."""
        return len(self.sections)

    @property
    def avg_confidence(self) -> float:
        """Return average confidence across all sections."""
        if not self.sections:
            return 0.0
        confidences = [s.confidence for s in self.sections.values()]
        return sum(confidences) / len(confidences)


class SectionGeneratorInput(SnapshotBaseModel):
    """Input data for SectionGeneratorAgent."""

    transcript: str = Field(
        ..., description="Full transcript text (can be empty for Executive Summary)"
    )
    analysis: AnalysisResult | dict[str, Any] = Field(
        default_factory=dict, description="Analysis results"
    )
    context: dict[str, Any] = Field(
        default_factory=dict, description="Additional context"
    )


class OrchestrationInput(SnapshotBaseModel):
    """Input data for OrchestrationAgent."""

    vtt_content: str = Field(..., min_length=1, description="VTT transcript content")
    filename: str = Field("transcript.vtt", description="Filename for context")
