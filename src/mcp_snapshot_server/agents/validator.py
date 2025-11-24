"""Validation Agent for cross-section consistency checking."""

import re
from typing import Any

from mcp_snapshot_server.agents.base import BaseAgent
from mcp_snapshot_server.models.validation import ValidationInput, ValidationResult
from mcp_snapshot_server.prompts.system_prompts import SYSTEM_PROMPTS
from mcp_snapshot_server.utils.logging_config import ContextLogger
from mcp_snapshot_server.utils.sampling import sample_llm


class ValidationAgent(BaseAgent[ValidationInput, ValidationResult]):
    """Agent responsible for validating section consistency and quality."""

    def __init__(self, logger: ContextLogger):
        """Initialize Validation Agent."""
        super().__init__(
            name="ValidationAgent",
            system_prompt=SYSTEM_PROMPTS["validator"],
            logger=logger,
        )

    async def process(self, input_data: ValidationInput) -> ValidationResult:
        """Validate sections for consistency and quality.

        Args:
            input_data: ValidationInput model containing sections to validate

        Returns:
            ValidationResult model with issues and suggestions
        """
        sections = input_data.sections

        self.logger.info(
            "Starting section validation", extra={"sections_count": len(sections)}
        )

        # Build sections text for validation
        sections_text = self._build_sections_text(sections)

        # LLM-based validation
        validation_results = await self._llm_validate(sections_text)

        # Heuristic validation
        heuristic_results = self._heuristic_validate(sections)

        # Merge results
        merged_results = self._merge_validation_results(
            validation_results, heuristic_results
        )

        self.logger.info(
            "Validation complete",
            extra={
                "issues_found": merged_results.issue_count,
                "requires_improvements": merged_results.requires_improvements,
            },
        )

        return merged_results

    def _build_sections_text(self, sections: dict[str, Any]) -> str:
        """Build formatted text from sections."""
        parts = []
        for name, section in sections.items():
            content = (
                section.get("content", "") if isinstance(section, dict) else section
            )
            parts.append(f"## {name}\n{content}")
        return "\n\n".join(parts)

    async def _llm_validate(self, sections_text: str) -> dict[str, Any]:
        """Perform LLM-based validation."""
        prompt = f"""Review these Customer Success Snapshot sections for consistency and quality:

{sections_text[:4000]}

Provide validation feedback in this format:

FACTUAL CONSISTENCY:
[List any contradictions in dates, names, numbers, or facts]

COMPLETENESS:
[Note any critical missing information]

QUALITY ISSUES:
[Flag tone, clarity, or professionalism problems]

IMPROVEMENTS:
[Suggest specific enhancements]

OUTPUT: Structured feedback as shown above
"""

        try:
            response = await sample_llm(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.2,
                max_tokens=1500,
            )
            return self._parse_validation_response(response.content)
        except Exception as e:
            self.logger.warning(f"LLM validation failed: {e}")
            return {}

    def _heuristic_validate(self, sections: dict[str, Any]) -> dict[str, Any]:
        """Perform heuristic validation checks."""
        issues = []

        # Check for contradictory dates
        dates = self._extract_dates(sections)
        if len(dates) > 1:
            # Simple check: start should be before completion
            pass  # Could add more sophisticated date logic

        # Check for missing critical sections
        critical_sections = ["Customer Information", "Background", "Solution"]
        for critical in critical_sections:
            if critical not in sections:
                issues.append(f"Missing critical section: {critical}")

        # Check for very short sections (likely low quality)
        for name, section in sections.items():
            content = (
                section.get("content", "") if isinstance(section, dict) else section
            )
            if len(content) < 50:
                issues.append(f"Section '{name}' is very short (< 50 chars)")

        return {"issues": issues, "heuristic": True}

    def _extract_dates(self, sections: dict[str, Any]) -> list[str]:
        """Extract dates from sections."""
        dates = []
        date_pattern = r"\d{4}-\d{2}-\d{2}"

        for section in sections.values():
            content = (
                section.get("content", "") if isinstance(section, dict) else section
            )
            found_dates = re.findall(date_pattern, content)
            dates.extend(found_dates)

        return dates

    def _parse_validation_response(self, response: str) -> dict[str, Any]:
        """Parse LLM validation response."""
        # Extract quality issues section to check for actual problems
        quality_issues = self._extract_quality_issues(response)

        # Check if there are actual quality problems (not "no problems")
        has_quality_issues = False
        if quality_issues:
            for issue in quality_issues:
                issue_lower = issue.lower()
                # Skip lines that explicitly say "no" problems
                if (
                    issue_lower.startswith("no ")
                    or "no problems" in issue_lower
                    or "none" in issue_lower
                ):
                    continue
                # Check for actual problem keywords
                if any(
                    keyword in issue_lower
                    for keyword in [
                        "problem",
                        "concern",
                        "poor",
                        "unclear",
                        "unprofessional",
                        "issue",
                    ]
                ):
                    has_quality_issues = True
                    break

        return {
            "factual_consistency": "contradiction" not in response.lower(),
            "completeness": "missing" not in response.lower(),
            "quality": not has_quality_issues,
            "issues": self._extract_issues(response),
            "improvements": self._extract_improvements(response),
            "requires_improvements": "improvement" in response.lower(),
            "missing_critical_info": [],
        }

    def _extract_issues(self, response: str) -> list[str]:
        """Extract issues from response."""
        issues = []
        if "FACTUAL CONSISTENCY:" in response:
            section = response.split("FACTUAL CONSISTENCY:")[1].split("\n\n")[0]
            issues.extend(
                [line.strip() for line in section.split("\n") if line.strip()]
            )
        return issues

    def _extract_improvements(self, response: str) -> list[str]:
        """Extract improvement suggestions."""
        improvements = []
        if "IMPROVEMENTS:" in response:
            section = response.split("IMPROVEMENTS:")[1].split("\n\n")[0]
            improvements.extend(
                [line.strip() for line in section.split("\n") if line.strip()]
            )
        return improvements

    def _extract_quality_issues(self, response: str) -> list[str]:
        """Extract quality issues from response."""
        issues = []
        if "QUALITY ISSUES:" in response:
            section = response.split("QUALITY ISSUES:")[1].split("\n\n")[0]
            issues.extend(
                [line.strip() for line in section.split("\n") if line.strip()]
            )
        return issues

    def _merge_validation_results(
        self, llm_results: dict[str, Any], heuristic_results: dict[str, Any]
    ) -> ValidationResult:
        """Merge LLM and heuristic validation results."""
        return ValidationResult(
            factual_consistency=llm_results.get("factual_consistency", True),
            completeness=llm_results.get("completeness", True),
            quality=llm_results.get("quality", True),
            issues=llm_results.get("issues", []) + heuristic_results.get("issues", []),
            improvements=llm_results.get("improvements", []),
            requires_improvements=(
                llm_results.get("requires_improvements", False)
                or len(heuristic_results.get("issues", [])) > 0
            ),
            missing_critical_info=llm_results.get("missing_critical_info", []),
        )
