"""Section Generator Agent for creating individual snapshot sections.

This agent generates content for specific sections of the Customer Success
Snapshot using specialized prompts and system instructions.
"""

import re
from typing import Any

from mcp_snapshot_server.agents.base import BaseAgent
from mcp_snapshot_server.models.analysis import AnalysisResult
from mcp_snapshot_server.models.sections import (
    SectionGeneratorInput,
    SectionMetadata,
    SectionResult,
)
from mcp_snapshot_server.utils.config import get_settings
from mcp_snapshot_server.utils.logging_config import ContextLogger
from mcp_snapshot_server.utils.sampling import sample_llm


class SectionGeneratorAgent(BaseAgent[SectionGeneratorInput, SectionResult]):
    """Agent responsible for generating individual sections."""

    def __init__(
        self,
        section_name: str,
        system_prompt: str,
        prompt_template: str,
        logger: ContextLogger,
    ):
        """Initialize Section Generator Agent.

        Args:
            section_name: Name of the section to generate
            system_prompt: System prompt for this section's agent
            prompt_template: Prompt template for this section
            logger: Context logger for structured logging
        """
        super().__init__(
            name=f"SectionGenerator_{section_name.replace(' ', '_')}",
            system_prompt=system_prompt,
            logger=logger,
        )
        self.section_name = section_name
        self.prompt_template = prompt_template

    async def process(self, input_data: SectionGeneratorInput) -> SectionResult:
        """Generate section content.

        Args:
            input_data: SectionGeneratorInput containing transcript, analysis, and context

        Returns:
            SectionResult with generated content, confidence, and metadata
        """
        transcript = input_data.transcript
        # Handle analysis as either AnalysisResult model or dict
        analysis = input_data.analysis
        if isinstance(analysis, AnalysisResult):
            analysis_dict = analysis.model_dump()
        else:
            analysis_dict = analysis if analysis else {}
        context = input_data.context

        self.logger.info(
            f"Generating section: {self.section_name}",
            extra={
                "section": self.section_name,
                "entities_available": len(analysis_dict.get("entities", {})),
                "topics_available": len(analysis_dict.get("topics", [])),
            },
        )

        # Build section prompt
        prompt = self._build_prompt(transcript, analysis_dict, context)

        # Sample LLM
        settings = get_settings()
        response = await sample_llm(
            prompt=prompt,
            system_prompt=self.system_prompt,
            temperature=0.3,  # Moderate creativity
            max_tokens=settings.llm.max_tokens_per_section,
        )

        content = response.content

        # Calculate confidence
        confidence = self._calculate_confidence(content, analysis_dict)

        # Identify missing fields
        missing_fields = self._identify_missing_fields(content)

        self.logger.info(
            f"Section generated: {self.section_name}",
            extra={
                "section": self.section_name,
                "confidence": confidence,
                "missing_fields_count": len(missing_fields),
                "content_length": len(content),
            },
        )

        # Build metadata from response
        metadata = SectionMetadata(
            model=response.metadata.model,
            tokens_used=response.metadata.tokens_used.model_dump(),
            finish_reason=response.metadata.finish_reason,
        )

        return SectionResult(
            section_name=self.section_name,
            content=content,
            confidence=confidence,
            missing_fields=missing_fields,
            metadata=metadata,
        )

    def _build_prompt(
        self,
        transcript: str,
        analysis: dict[str, Any],
        context: dict[str, Any],
    ) -> str:
        """Build the prompt for section generation.

        Args:
            transcript: Full transcript text
            analysis: Analysis results
            context: Additional context

        Returns:
            Formatted prompt string
        """
        # Format entities for prompt
        entities_str = self._format_entities(analysis.get("entities", {}))

        # Format topics for prompt
        topics_str = self._format_topics(analysis.get("topics", []))

        # Prepare template variables
        template_vars = {
            "transcript": transcript[:5000] + ("..." if len(transcript) > 5000 else ""),
            "entities": entities_str,
            "topics": topics_str,
        }

        # Add any additional context variables
        template_vars.update(context)

        # Format the prompt template
        try:
            prompt = self.prompt_template.format(**template_vars)
        except KeyError as e:
            # If a required variable is missing, use partial formatting
            self.logger.warning(
                f"Missing template variable: {e}", extra={"section": self.section_name}
            )
            # Use what we have
            prompt = self.prompt_template.format_map(
                {**template_vars, "all_sections": ""}
            )

        return prompt

    def _calculate_confidence(self, content: str, analysis: dict[str, Any]) -> float:
        """Calculate confidence score for generated section.

        Args:
            content: Generated content
            analysis: Analysis results

        Returns:
            Confidence score between 0.0 and 1.0
        """
        score = 1.0
        content_lower = content.lower()

        # Reduce score for common placeholder phrases
        placeholders = [
            "not mentioned",
            "not specified",
            "not available",
            "not stated",
            "unclear from transcript",
            "no information provided",
        ]

        for placeholder in placeholders:
            if placeholder in content_lower:
                score -= 0.1

        # Check for [INFERRED] tags (lower confidence but acceptable)
        inferred_count = content.count("[INFERRED]")
        if inferred_count > 0:
            score -= 0.05 * inferred_count

        # Section-specific confidence checks
        if self.section_name == "Customer Information":
            if "company name:" in content_lower:
                # Check if actually has a value
                if "not mentioned" not in content_lower.split("company name:")[1][:50]:
                    score += 0.1
            else:
                score -= 0.2

            if "industry:" not in content_lower:
                score -= 0.1

        elif self.section_name == "Background":
            if "problem" in content_lower or "challenge" in content_lower:
                score += 0.05

        elif self.section_name == "Solution":
            if "product" in content_lower or "service" in content_lower:
                score += 0.05

        elif self.section_name == "Results and Achievements":
            # Look for quantifiable metrics
            has_numbers = bool(re.search(r"\d+%|\d+\s*hours?|\$\d+", content))
            if has_numbers:
                score += 0.1

        elif self.section_name == "Financial Impact":
            # Financial sections need numbers
            has_financial = bool(re.search(r"\$\d+|\d+%\s*roi|savings", content_lower))
            if has_financial:
                score += 0.15
            else:
                score -= 0.2

        # Check content length (too short suggests lack of information)
        if len(content) < 100:
            score -= 0.2
        elif len(content) < 200:
            score -= 0.1

        # Ensure score stays within bounds
        return max(0.0, min(1.0, score))

    def _identify_missing_fields(self, content: str) -> list[str]:
        """Identify fields that are missing or incomplete.

        Args:
            content: Generated content

        Returns:
            List of missing field identifiers
        """
        missing = []
        content_lower = content.lower()

        # Section-specific field checks
        if self.section_name == "Customer Information":
            if self._is_field_missing(content_lower, "company name"):
                missing.append("company_name")
            if self._is_field_missing(content_lower, "industry"):
                missing.append("industry")
            if self._is_field_missing(content_lower, "location"):
                missing.append("location")
            if self._is_field_missing(content_lower, "primary contact"):
                missing.append("primary_contact")

        elif self.section_name == "Engagement Details":
            if self._is_field_missing(content_lower, "start date"):
                missing.append("start_date")
            if self._is_field_missing(content_lower, "completion date"):
                missing.append("completion_date")

        elif self.section_name == "Financial Impact":
            if not re.search(r"\$\d+|cost savings", content_lower):
                missing.append("cost_savings")
            if (
                "roi" not in content_lower
                and "return on investment" not in content_lower
            ):
                missing.append("roi_percentage")

        elif self.section_name == "Adoption and Usage":
            if "users" not in content_lower and "adoption" not in content_lower:
                missing.append("user_count")
                missing.append("adoption_rate")

        return missing

    def _is_field_missing(self, content: str, field_label: str) -> bool:
        """Check if a field is missing or has no value.

        Args:
            content: Content to check (lowercase)
            field_label: Field label to look for

        Returns:
            True if field is missing or has no value
        """
        if field_label not in content:
            return True

        # Check if the field has an actual value or just placeholder
        field_index = content.index(field_label)
        following_text = content[field_index : field_index + 100].lower()

        placeholders = [
            "not mentioned",
            "not specified",
            "not available",
            "not stated",
            "unclear",
        ]

        return any(placeholder in following_text for placeholder in placeholders)

    def _format_entities(self, entities: dict[str, list[str]]) -> str:
        """Format entities for prompt.

        Args:
            entities: Dictionary of entities by type

        Returns:
            Formatted entity string
        """
        if not entities:
            return "No entities extracted"

        formatted = []
        for entity_type, entity_list in entities.items():
            if entity_list:
                formatted.append(f"{entity_type}: {', '.join(entity_list[:5])}")

        return "; ".join(formatted) if formatted else "No entities extracted"

    def _format_topics(self, topics: list[str]) -> str:
        """Format topics for prompt.

        Args:
            topics: List of topics

        Returns:
            Formatted topic string
        """
        if not topics:
            return "No specific topics identified"

        return ", ".join(topics[:10])
