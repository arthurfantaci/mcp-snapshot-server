"""Zoom API-related Pydantic models."""

from __future__ import annotations

from pydantic import ConfigDict, Field

from mcp_snapshot_server.models.base import SnapshotBaseModel


class ZoomBaseModel(SnapshotBaseModel):
    """Base model for Zoom API responses.

    Allows extra fields since Zoom API may return fields we don't explicitly model.
    """

    model_config = ConfigDict(
        extra="ignore",  # Allow extra fields from Zoom API
    )


class ZoomRecordingFile(ZoomBaseModel):
    """A single Zoom recording file."""

    id: str = Field(..., description="Recording file ID")
    recording_start: str | None = Field(None, description="Recording start time")
    recording_end: str | None = Field(None, description="Recording end time")
    file_type: str = Field(..., description="Type of recording file")
    file_extension: str | None = Field(None, description="File extension")
    file_size: int | None = Field(None, ge=0, description="File size in bytes")
    download_url: str | None = Field(None, description="URL to download the file")
    status: str | None = Field(None, description="Processing status")
    recording_type: str | None = Field(None, description="Recording type")

    @property
    def is_vtt_transcript(self) -> bool:
        """Check if this file is a VTT transcript."""
        return self.file_type == "TRANSCRIPT" and self.file_extension == "VTT"


class ZoomMeeting(ZoomBaseModel):
    """A Zoom meeting recording."""

    uuid: str = Field(..., description="Meeting UUID")
    id: int = Field(..., description="Meeting ID")
    topic: str = Field("", description="Meeting topic")
    start_time: str | None = Field(None, description="Meeting start time")
    duration: int = Field(0, ge=0, description="Meeting duration in minutes")
    recording_count: int = Field(0, ge=0, description="Number of recordings")
    recording_files: list[ZoomRecordingFile] = Field(
        default_factory=list, description="Recording files"
    )
    host_id: str | None = Field(None, description="Host user ID")
    host_email: str | None = Field(None, description="Host email")

    @property
    def has_vtt_transcript(self) -> bool:
        """Check if this meeting has a VTT transcript."""
        return any(f.is_vtt_transcript for f in self.recording_files)

    def get_transcript_file(self) -> ZoomRecordingFile | None:
        """Get the VTT transcript file if available."""
        for file in self.recording_files:
            if file.is_vtt_transcript:
                return file
        return None


class ZoomRecordingsListResponse(ZoomBaseModel):
    """Response from listing Zoom recordings."""

    meetings: list[ZoomMeeting] = Field(
        default_factory=list, description="List of meeting recordings"
    )
    from_date: str | None = Field(None, description="Start date of query")
    to_date: str | None = Field(None, description="End date of query")
    total_count: int = Field(0, ge=0, description="Total number of meetings")
    has_transcript_filter: bool = Field(
        False, description="Whether filtered for transcripts"
    )


class ZoomOAuthToken(ZoomBaseModel):
    """Zoom OAuth token response."""

    access_token: str = Field(..., description="OAuth access token")
    token_type: str = Field("Bearer", description="Token type")
    expires_in: int = Field(3600, ge=0, description="Token expiry in seconds")
    scope: str = Field("", description="Token scopes")


class ZoomMeetingRecordingsResponse(ZoomBaseModel):
    """Response from getting specific meeting recordings."""

    uuid: str = Field(..., description="Meeting UUID")
    id: int = Field(..., description="Meeting ID")
    topic: str = Field("", description="Meeting topic")
    start_time: str | None = Field(None, description="Meeting start time")
    duration: int = Field(0, ge=0, description="Meeting duration in minutes")
    total_size: int = Field(0, ge=0, description="Total recording size in bytes")
    recording_count: int = Field(0, ge=0, description="Number of recordings")
    recording_files: list[ZoomRecordingFile] = Field(
        default_factory=list, description="Recording files"
    )
    host_id: str | None = Field(None, description="Host user ID")
    host_email: str | None = Field(None, description="Host email")

    def get_transcript_file(self) -> ZoomRecordingFile | None:
        """Get the VTT transcript file if available."""
        for file in self.recording_files:
            if file.is_vtt_transcript:
                return file
        return None
