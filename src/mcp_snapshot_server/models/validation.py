"""Validation-related Pydantic models."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from mcp_snapshot_server.models.base import SnapshotBaseModel


class ValidationResult(SnapshotBaseModel):
    """Results from section validation."""

    factual_consistency: bool = Field(
        True, description="Whether dates, names, numbers are consistent"
    )
    completeness: bool = Field(True, description="Whether critical info is present")
    quality: bool = Field(True, description="Whether tone, clarity are acceptable")
    issues: list[str] = Field(default_factory=list, description="Issues found")
    improvements: list[str] = Field(
        default_factory=list, description="Suggested improvements"
    )
    requires_improvements: bool = Field(False, description="Whether fixes are needed")
    missing_critical_info: list[str] = Field(
        default_factory=list, description="Critical fields missing"
    )

    @property
    def is_valid(self) -> bool:
        """Return True if all quality checks passed."""
        return self.factual_consistency and self.completeness and self.quality

    @property
    def issue_count(self) -> int:
        """Return total number of issues."""
        return len(self.issues)

    def merge(self, other: ValidationResult) -> ValidationResult:
        """Merge two validation results.

        Args:
            other: Another ValidationResult to merge with

        Returns:
            New ValidationResult with combined data
        """
        return ValidationResult(
            factual_consistency=self.factual_consistency and other.factual_consistency,
            completeness=self.completeness and other.completeness,
            quality=self.quality and other.quality,
            issues=self.issues + other.issues,
            improvements=self.improvements + other.improvements,
            requires_improvements=self.requires_improvements
            or other.requires_improvements,
            missing_critical_info=self.missing_critical_info
            + other.missing_critical_info,
        )


class ValidationInput(SnapshotBaseModel):
    """Input data for ValidationAgent.

    Note: sections is typed as dict[str, Any] to allow flexibility in what
    section data is passed. Will be refined when SectionResult is available.
    """

    sections: dict[str, Any] = Field(..., description="Sections to validate")
