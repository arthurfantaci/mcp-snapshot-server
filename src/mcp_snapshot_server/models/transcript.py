"""Transcript-related Pydantic models."""

from pydantic import Field, field_validator

from mcp_snapshot_server.models.base import SnapshotBaseModel


class SpeakerTurn(SnapshotBaseModel):
    """A single speaker turn in the transcript."""

    speaker: str = Field(..., min_length=1, description="Speaker name")
    text: str = Field(..., description="Spoken text content")
    start: str = Field(..., description="Start timestamp (HH:MM:SS.mmm)")
    end: str = Field(..., description="End timestamp (HH:MM:SS.mmm)")

    @field_validator("speaker")
    @classmethod
    def normalize_speaker(cls, v: str) -> str:
        """Normalize speaker name, defaulting to 'Unknown' if empty."""
        return v.strip() or "Unknown"


class TranscriptMetadata(SnapshotBaseModel):
    """Metadata about a parsed transcript."""

    vtt_filename: str | None = Field(None, description="Original VTT filename")
    file_path: str | None = Field(None, description="Original file path if from file")
    caption_count: int = Field(0, ge=0, description="Number of captions parsed")
    speaker_count: int = Field(0, ge=0, description="Number of unique speakers")


class TranscriptData(SnapshotBaseModel):
    """Parsed transcript data from VTT file or content."""

    text: str = Field(..., description="Full transcript text with speaker labels")
    speakers: list[str] = Field(default_factory=list, description="Unique speakers")
    speaker_turns: list[SpeakerTurn] = Field(
        default_factory=list, description="List of individual speaking turns"
    )
    duration: float = Field(0.0, ge=0.0, description="Duration in seconds")
    metadata: TranscriptMetadata = Field(default_factory=TranscriptMetadata)

    @property
    def speaker_count(self) -> int:
        """Return the number of unique speakers."""
        return len(self.speakers)

    @property
    def turn_count(self) -> int:
        """Return the number of speaking turns."""
        return len(self.speaker_turns)

    def get_summary(self) -> str:
        """Generate a brief summary of transcript data."""
        minutes = int(self.duration // 60)
        seconds = int(self.duration % 60)
        speakers_preview = ", ".join(self.speakers[:3])
        if len(self.speakers) > 3:
            speakers_preview += "..."

        return f"""Transcript Summary:
- Speakers: {self.speaker_count} ({speakers_preview})
- Duration: {minutes}m {seconds}s
- Speaking turns: {self.turn_count}
- Total text length: {len(self.text):,} characters
"""
