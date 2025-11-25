"""Orchestration Agent for coordinating the complete snapshot generation workflow.

This agent manages the end-to-end process of generating a Customer Success
Snapshot from a VTT transcript file.
"""

import asyncio
from typing import cast

from mcp_snapshot_server.agents.analyzer import AnalysisAgent
from mcp_snapshot_server.agents.base import BaseAgent
from mcp_snapshot_server.agents.section_generator import SectionGeneratorAgent
from mcp_snapshot_server.agents.validator import ValidationAgent
from mcp_snapshot_server.models import (
    AnalysisInput,
    AnalysisResult,
    OrchestrationInput,
    SectionContent,
    SectionGeneratorInput,
    SectionResult,
    SnapshotMetadata,
    SnapshotOutput,
    TranscriptData,
    ValidationInput,
    ValidationResult,
)
from mcp_snapshot_server.prompts.section_prompts import SECTION_PROMPTS
from mcp_snapshot_server.prompts.system_prompts import SYSTEM_PROMPTS
from mcp_snapshot_server.tools.transcript_utils import parse_vtt_content
from mcp_snapshot_server.utils.config import get_settings
from mcp_snapshot_server.utils.errors import ErrorCode, MCPServerError
from mcp_snapshot_server.utils.logging_config import ContextLogger


class OrchestrationAgent(BaseAgent[OrchestrationInput, SnapshotOutput]):
    """Agent responsible for orchestrating the complete snapshot generation workflow."""

    # Define the 11 section names in order
    SECTION_NAMES = [
        "Customer Information",
        "Background",
        "Solution",
        "Engagement Details",
        "Results and Achievements",
        "Adoption and Usage",
        "Financial Impact",
        "Long-Term Impact",
        "Visuals",
        "Additional Commentary",
        "Executive Summary",
    ]

    # Map section names to prompt keys
    SECTION_PROMPT_KEYS = {
        "Customer Information": "customer_information",
        "Background": "background",
        "Solution": "solution",
        "Engagement Details": "engagement_details",
        "Results and Achievements": "results_achievements",
        "Adoption and Usage": "adoption_usage",
        "Financial Impact": "financial_impact",
        "Long-Term Impact": "long_term_impact",
        "Visuals": "visuals",
        "Additional Commentary": "additional_commentary",
        "Executive Summary": "executive_summary",
    }

    def __init__(self, logger: ContextLogger):
        """Initialize Orchestration Agent.

        Args:
            logger: Context logger for structured logging
        """
        super().__init__(
            name="OrchestrationAgent",
            system_prompt=SYSTEM_PROMPTS["orchestrator"],
            logger=logger,
        )
        self.settings = get_settings()

        # Initialize sub-agents
        self.analysis_agent = AnalysisAgent(logger=logger)
        self.validation_agent = ValidationAgent(logger=logger)
        self.section_generators: dict[str, SectionGeneratorAgent] = {}

        # Initialize section generators (excluding Executive Summary for now)
        for section_name in self.SECTION_NAMES[:-1]:  # Exclude Executive Summary
            prompt_key = self.SECTION_PROMPT_KEYS[section_name]
            system_prompt_key = prompt_key + "_agent"

            self.section_generators[section_name] = SectionGeneratorAgent(
                section_name=section_name,
                system_prompt=SYSTEM_PROMPTS.get(
                    system_prompt_key, SYSTEM_PROMPTS["section_generator"]
                ),
                prompt_template=SECTION_PROMPTS[prompt_key]["template"],
                logger=logger,
            )

    async def process(self, input_data: OrchestrationInput) -> SnapshotOutput:
        """Generate complete Customer Success Snapshot from VTT transcript content.

        Args:
            input_data: OrchestrationInput containing VTT content and filename

        Returns:
            SnapshotOutput with all generated sections, metadata, and validation
        """
        vtt_content = input_data.vtt_content
        filename = input_data.filename

        if not vtt_content:
            raise MCPServerError(
                error_code=ErrorCode.INVALID_INPUT,
                message="vtt_content is required",
                details={"filename": filename},
            )

        self.logger.info(
            "Starting snapshot generation workflow",
            extra={"filename": filename, "content_length": len(vtt_content)},
        )

        try:
            # Step 1: Parse VTT transcript
            transcript_data = self._parse_transcript(vtt_content, filename)

            # Step 2: Analyze transcript
            analysis_results = await self._analyze_transcript(transcript_data)

            # Step 3: Generate sections (10 sections, excluding Executive Summary)
            sections = await self._generate_sections(transcript_data, analysis_results)

            # Step 4: Validate sections
            validation_results = await self._validate_sections(sections)

            # Step 5: Handle improvements if needed
            if validation_results.requires_improvements:
                sections = await self._improve_sections(
                    sections, validation_results, transcript_data, analysis_results
                )

            # Step 6: Generate Executive Summary
            sections["Executive Summary"] = await self._generate_executive_summary(
                sections
            )

            # Step 7: Final validation
            final_validation = await self._validate_sections(sections)

            # Step 8: Assemble output
            output = self._assemble_output(sections, analysis_results, final_validation)

            self.logger.info(
                "Snapshot generation complete",
                extra={
                    "sections_count": len(sections),
                    "validation_passed": not final_validation.requires_improvements,
                },
            )

            return output

        except Exception as e:
            self.logger.error(
                f"Snapshot generation failed: {e}",
                extra={"error_type": type(e).__name__},
            )
            raise MCPServerError(
                error_code=ErrorCode.INTERNAL_ERROR,
                message=f"Failed to generate snapshot: {str(e)}",
                details={"filename": filename, "error": str(e)},
            ) from e

    def _parse_transcript(
        self, vtt_content: str, filename: str = "transcript.vtt"
    ) -> TranscriptData:
        """Parse VTT transcript content.

        Args:
            vtt_content: VTT transcript content as string
            filename: Optional filename for context

        Returns:
            Parsed TranscriptData model
        """
        self.logger.info(
            "Parsing VTT transcript",
            extra={"filename": filename, "content_length": len(vtt_content)},
        )

        try:
            transcript_data = parse_vtt_content(vtt_content, filename)
            self.logger.info(
                "Transcript parsed successfully",
                extra={
                    "speaker_count": transcript_data.speaker_count,
                    "turn_count": transcript_data.turn_count,
                    "duration": transcript_data.duration,
                },
            )
            return transcript_data
        except Exception as e:
            raise MCPServerError(
                error_code=ErrorCode.PARSE_ERROR,
                message=f"Failed to parse VTT content: {str(e)}",
                details={"filename": filename},
            ) from e

    async def _analyze_transcript(
        self, transcript_data: TranscriptData
    ) -> AnalysisResult:
        """Analyze transcript using Analysis Agent.

        Args:
            transcript_data: Parsed TranscriptData model

        Returns:
            AnalysisResult model
        """
        self.logger.info("Starting transcript analysis")

        analysis_input = AnalysisInput(
            transcript=transcript_data.text,
            transcript_data=transcript_data,
        )
        analysis_results = await self.analysis_agent.process(analysis_input)

        self.logger.info(
            "Transcript analysis complete",
            extra={
                "entities_count": analysis_results.entity_count,
                "topics_count": len(analysis_results.topics),
            },
        )

        return analysis_results

    async def _generate_sections(
        self, transcript_data: TranscriptData, analysis_results: AnalysisResult
    ) -> dict[str, SectionResult]:
        """Generate all sections (excluding Executive Summary).

        Args:
            transcript_data: Parsed TranscriptData model
            analysis_results: AnalysisResult model

        Returns:
            Dictionary mapping section names to SectionResult models
        """
        self.logger.info("Starting section generation", extra={"section_count": 10})

        sections: dict[str, SectionResult] = {}
        transcript_text = transcript_data.text

        # Determine if we should generate sections in parallel or sequential
        if self.settings.workflow.parallel_section_generation:
            sections = await self._generate_sections_parallel(
                transcript_text, analysis_results
            )
        else:
            sections = await self._generate_sections_sequential(
                transcript_text, analysis_results
            )

        self.logger.info(
            "Section generation complete",
            extra={
                "sections_generated": len(sections),
                "avg_confidence": sum(s.confidence for s in sections.values())
                / len(sections)
                if sections
                else 0,
            },
        )

        return sections

    async def _generate_sections_parallel(
        self, transcript_text: str, analysis_results: AnalysisResult
    ) -> dict[str, SectionResult]:
        """Generate sections in parallel.

        Args:
            transcript_text: Full transcript text
            analysis_results: AnalysisResult model

        Returns:
            Dictionary mapping section names to SectionResult models
        """
        tasks = []
        section_names = []

        # Create tasks for all sections except Executive Summary
        for section_name in self.SECTION_NAMES[:-1]:
            generator = self.section_generators[section_name]
            input_data = SectionGeneratorInput(
                transcript=transcript_text,
                analysis=analysis_results,
                context={},
            )
            task = generator.process(input_data)
            tasks.append(task)
            section_names.append(section_name)

        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build sections dictionary
        sections: dict[str, SectionResult] = {}
        for section_name, result in zip(section_names, results, strict=False):
            if isinstance(result, Exception):
                self.logger.warning(
                    f"Section generation failed: {section_name}",
                    extra={"error": str(result)},
                )
                # Create placeholder section using error_placeholder method
                sections[section_name] = SectionResult.error_placeholder(
                    section_name=section_name,
                    error=str(result),
                )
            else:
                sections[section_name] = cast("SectionResult", result)

        return sections

    async def _generate_sections_sequential(
        self, transcript_text: str, analysis_results: AnalysisResult
    ) -> dict[str, SectionResult]:
        """Generate sections sequentially.

        Args:
            transcript_text: Full transcript text
            analysis_results: AnalysisResult model

        Returns:
            Dictionary mapping section names to SectionResult models
        """
        sections: dict[str, SectionResult] = {}

        for section_name in self.SECTION_NAMES[:-1]:
            try:
                generator = self.section_generators[section_name]
                input_data = SectionGeneratorInput(
                    transcript=transcript_text,
                    analysis=analysis_results,
                    context={},
                )
                result = await generator.process(input_data)
                sections[section_name] = result
            except Exception as e:
                self.logger.warning(
                    f"Section generation failed: {section_name}",
                    extra={"error": str(e)},
                )
                sections[section_name] = SectionResult.error_placeholder(
                    section_name=section_name,
                    error=str(e),
                )

        return sections

    async def _validate_sections(
        self, sections: dict[str, SectionResult]
    ) -> ValidationResult:
        """Validate generated sections.

        Args:
            sections: Dictionary mapping section names to SectionResult models

        Returns:
            ValidationResult model
        """
        self.logger.info("Validating sections", extra={"section_count": len(sections)})

        # Convert SectionResult models to dict for validation
        sections_dict = {name: result.model_dump() for name, result in sections.items()}
        validation_input = ValidationInput(sections=sections_dict)
        validation_results = await self.validation_agent.process(validation_input)

        self.logger.info(
            "Validation complete",
            extra={
                "issues_found": validation_results.issue_count,
                "requires_improvements": validation_results.requires_improvements,
            },
        )

        return validation_results

    async def _improve_sections(
        self,
        sections: dict[str, SectionResult],
        validation_results: ValidationResult,
        transcript_data: TranscriptData,
        analysis_results: AnalysisResult,
    ) -> dict[str, SectionResult]:
        """Improve sections based on validation results.

        Args:
            sections: Dictionary mapping section names to SectionResult models
            validation_results: ValidationResult model
            transcript_data: Original TranscriptData model
            analysis_results: AnalysisResult model

        Returns:
            Improved sections dictionary
        """
        self.logger.info(
            "Attempting to improve sections",
            extra={"issues": validation_results.issue_count},
        )

        # For now, just log the issues and return sections as-is
        # In a production system, this would implement iterative improvement
        # by re-generating low-confidence sections with enhanced prompts

        for issue in validation_results.issues:
            self.logger.info(f"Validation issue: {issue}")

        # Identify low-confidence sections
        low_confidence_threshold = self.settings.workflow.min_confidence_threshold
        low_confidence_sections = [
            name
            for name, section in sections.items()
            if section.confidence < low_confidence_threshold
        ]

        if low_confidence_sections:
            self.logger.info(
                "Low confidence sections identified",
                extra={
                    "sections": low_confidence_sections,
                    "threshold": low_confidence_threshold,
                },
            )

        # TODO: Implement iterative improvement logic
        # For Phase 4, we'll accept the sections as-is

        return sections

    async def _generate_executive_summary(
        self, sections: dict[str, SectionResult]
    ) -> SectionResult:
        """Generate Executive Summary from all other sections.

        Args:
            sections: Dictionary mapping section names to SectionResult models

        Returns:
            Executive Summary SectionResult
        """
        self.logger.info("Generating Executive Summary")

        # Build combined sections text
        all_sections_text = self._build_all_sections_text(sections)

        # Create Executive Summary generator
        exec_summary_generator = SectionGeneratorAgent(
            section_name="Executive Summary",
            system_prompt=SYSTEM_PROMPTS.get(
                "executive_summary_agent", SYSTEM_PROMPTS["section_generator"]
            ),
            prompt_template=SECTION_PROMPTS["executive_summary"]["template"],
            logger=self.logger,
        )

        # Generate with all sections as context
        input_data = SectionGeneratorInput(
            transcript="",  # Not needed for executive summary
            analysis={},
            context={"all_sections": all_sections_text},
        )
        result = await exec_summary_generator.process(input_data)

        self.logger.info(
            "Executive Summary generated",
            extra={"confidence": result.confidence},
        )

        return result

    def _build_all_sections_text(self, sections: dict[str, SectionResult]) -> str:
        """Build formatted text from all sections.

        Args:
            sections: Dictionary mapping section names to SectionResult models

        Returns:
            Formatted text
        """
        parts = []
        for name, section in sections.items():
            if name == "Executive Summary":
                continue  # Don't include executive summary in its own input
            parts.append(f"## {name}\n{section.content}")
        return "\n\n".join(parts)

    def _assemble_output(
        self,
        sections: dict[str, SectionResult],
        analysis_results: AnalysisResult,
        validation_results: ValidationResult,
    ) -> SnapshotOutput:
        """Assemble final output.

        Args:
            sections: Dictionary mapping section names to SectionResult models
            analysis_results: AnalysisResult model
            validation_results: ValidationResult model

        Returns:
            SnapshotOutput model
        """
        # Aggregate missing fields
        all_missing_fields: list[str] = []
        for section in sections.values():
            all_missing_fields.extend(section.missing_fields)

        # Calculate overall confidence
        confidences = [s.confidence for s in sections.values()]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Build SectionContent models for each section
        section_contents = {
            name: SectionContent(
                content=section.content,
                confidence=section.confidence,
                missing_fields=section.missing_fields,
            )
            for name, section in sections.items()
        }

        # Build metadata
        metadata = SnapshotMetadata(
            avg_confidence=avg_confidence,
            total_sections=len(sections),
            entities_extracted=analysis_results.entities,
            topics_identified=analysis_results.topics,
        )

        return SnapshotOutput(
            sections=section_contents,
            metadata=metadata,
            validation=validation_results,
            missing_fields=list(set(all_missing_fields)),  # Deduplicate
        )
