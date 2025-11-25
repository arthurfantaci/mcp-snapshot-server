"""Pydantic models for mcp-snapshot-server."""

from mcp_snapshot_server.models.analysis import (
    AnalysisInput,
    AnalysisMetadata,
    AnalysisResult,
    LLMInsights,
    TranscriptStructure,
)
from mcp_snapshot_server.models.base import SnapshotBaseModel
from mcp_snapshot_server.models.llm import (
    LLMResponse,
    LLMResponseMetadata,
    LLMTokenUsage,
)
from mcp_snapshot_server.models.sections import (
    OrchestrationInput,
    SectionContent,
    SectionGeneratorInput,
    SectionMetadata,
    SectionResult,
    SnapshotMetadata,
    SnapshotOutput,
)
from mcp_snapshot_server.models.transcript import (
    SpeakerTurn,
    TranscriptData,
    TranscriptMetadata,
)
from mcp_snapshot_server.models.validation import (
    ValidationInput,
    ValidationResult,
)
from mcp_snapshot_server.models.zoom import (
    ZoomMeeting,
    ZoomMeetingRecordingsResponse,
    ZoomOAuthToken,
    ZoomRecordingFile,
    ZoomRecordingsListResponse,
)

# Rebuild models that have forward references now that all types are imported
SectionGeneratorInput.model_rebuild()

__all__ = [
    "AnalysisInput",
    "AnalysisMetadata",
    "AnalysisResult",
    "LLMInsights",
    "LLMResponse",
    "LLMResponseMetadata",
    "LLMTokenUsage",
    "OrchestrationInput",
    "SectionContent",
    "SectionGeneratorInput",
    "SectionMetadata",
    "SectionResult",
    "SnapshotBaseModel",
    "SnapshotMetadata",
    "SnapshotOutput",
    "SpeakerTurn",
    "TranscriptData",
    "TranscriptMetadata",
    "TranscriptStructure",
    "ValidationInput",
    "ValidationResult",
    "ZoomMeeting",
    "ZoomMeetingRecordingsResponse",
    "ZoomOAuthToken",
    "ZoomRecordingFile",
    "ZoomRecordingsListResponse",
]
