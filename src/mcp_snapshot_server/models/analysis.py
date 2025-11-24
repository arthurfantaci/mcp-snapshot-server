"""Analysis-related Pydantic models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator

from mcp_snapshot_server.models.base import SnapshotBaseModel
from mcp_snapshot_server.models.transcript import TranscriptData


class TranscriptStructure(SnapshotBaseModel):
    """Structural analysis of a transcript."""

    meeting_type: str = Field("discussion", description="Type of meeting detected")
    speaker_count: int = Field(0, ge=0, description="Number of unique speakers")
    total_turns: int = Field(0, ge=0, description="Total speaking turns")
    duration_seconds: float = Field(0.0, ge=0.0, description="Meeting duration in seconds")
    speaker_turns_count: dict[str, int] = Field(
        default_factory=dict, description="Turn count per speaker"
    )
    speaker_word_count: dict[str, int] = Field(
        default_factory=dict, description="Word count per speaker"
    )
    avg_turn_length: float = Field(0.0, ge=0.0, description="Average words per turn")


class LLMInsights(SnapshotBaseModel):
    """Insights extracted from LLM analysis."""

    entities: dict[str, list[str]] = Field(
        default_factory=dict, description="Additional entities from LLM"
    )
    topics: list[str] = Field(default_factory=list, description="LLM-identified topics")
    structure: dict[str, Any] = Field(
        default_factory=dict, description="LLM structure analysis"
    )
    data_availability: dict[str, float] = Field(
        default_factory=dict, description="Data availability scores per section"
    )

    @field_validator("data_availability")
    @classmethod
    def validate_availability_scores(cls, v: dict[str, float]) -> dict[str, float]:
        """Validate that availability scores are between 0.0 and 1.0."""
        for key, score in v.items():
            if not 0.0 <= score <= 1.0:
                raise ValueError(f"Score for '{key}' must be between 0.0 and 1.0, got {score}")
        return v


class AnalysisMetadata(SnapshotBaseModel):
    """Metadata about the analysis process."""

    analysis_method: Literal["hybrid_nlp_llm", "nlp_only", "llm_only"] = Field(
        "hybrid_nlp_llm", description="Method used for analysis"
    )
    nlp_enabled: bool = Field(True, description="Whether NLP extraction was enabled")


class AnalysisResult(SnapshotBaseModel):
    """Complete analysis results from AnalysisAgent."""

    entities: dict[str, list[str]] = Field(
        default_factory=dict, description="Named entities by type"
    )
    topics: list[str] = Field(default_factory=list, description="Key topics identified")
    key_phrases: list[str] = Field(
        default_factory=list, description="Important phrases extracted"
    )
    structure: TranscriptStructure = Field(
        default_factory=TranscriptStructure, description="Conversation structure analysis"
    )
    llm_insights: LLMInsights = Field(
        default_factory=LLMInsights, description="LLM-based analysis insights"
    )
    data_availability: dict[str, float] = Field(
        default_factory=dict, description="Data availability scores per section"
    )
    metadata: AnalysisMetadata = Field(
        default_factory=AnalysisMetadata, description="Analysis metadata"
    )

    @field_validator("data_availability")
    @classmethod
    def validate_availability_scores(cls, v: dict[str, float]) -> dict[str, float]:
        """Validate that availability scores are between 0.0 and 1.0."""
        for key, score in v.items():
            if not 0.0 <= score <= 1.0:
                raise ValueError(f"Score for '{key}' must be between 0.0 and 1.0, got {score}")
        return v

    @property
    def entity_count(self) -> int:
        """Return total number of entities extracted."""
        return sum(len(v) for v in self.entities.values())


class AnalysisInput(SnapshotBaseModel):
    """Input data for AnalysisAgent."""

    transcript: str = Field(..., min_length=1, description="Full transcript text")
    transcript_data: TranscriptData | None = Field(
        None, description="Parsed transcript data"
    )
    additional_context: str = Field("", description="Additional context for analysis")
