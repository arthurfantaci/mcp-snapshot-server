"""LLM-related Pydantic models."""

from __future__ import annotations

from pydantic import Field

from mcp_snapshot_server.models.base import SnapshotBaseModel


class LLMTokenUsage(SnapshotBaseModel):
    """Token usage from an LLM API call."""

    input: int = Field(0, ge=0, description="Input tokens used")
    output: int = Field(0, ge=0, description="Output tokens generated")

    @property
    def total(self) -> int:
        """Return total tokens used."""
        return self.input + self.output


class LLMResponseMetadata(SnapshotBaseModel):
    """Metadata from an LLM API response."""

    model: str | None = Field(None, description="Model used for generation")
    tokens_used: LLMTokenUsage = Field(
        default_factory=LLMTokenUsage, description="Token usage statistics"
    )
    finish_reason: str | None = Field(None, description="Why generation stopped")


class LLMResponse(SnapshotBaseModel):
    """Complete response from an LLM API call."""

    content: str = Field("", description="Generated text content")
    metadata: LLMResponseMetadata = Field(
        default_factory=LLMResponseMetadata, description="Response metadata"
    )

    @property
    def is_complete(self) -> bool:
        """Check if response completed normally (not truncated)."""
        return self.metadata.finish_reason in ("end_turn", "stop", None)

    @property
    def total_tokens(self) -> int:
        """Return total tokens used."""
        return self.metadata.tokens_used.total
