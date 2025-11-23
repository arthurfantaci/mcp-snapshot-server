"""Orchestration Agent for coordinating the complete snapshot generation workflow.

This agent manages the end-to-end process of generating a Customer Success
Snapshot from a VTT transcript file.
"""

import asyncio
from pathlib import Path
from typing import Any, Optional

from mcp_snapshot_server.agents.analyzer import AnalysisAgent
from mcp_snapshot_server.agents.base import BaseAgent
from mcp_snapshot_server.agents.section_generator import SectionGeneratorAgent
from mcp_snapshot_server.agents.validator import ValidationAgent
from mcp_snapshot_server.prompts.section_prompts import SECTION_PROMPTS
from mcp_snapshot_server.prompts.system_prompts import SYSTEM_PROMPTS
from mcp_snapshot_server.tools.transcript_utils import parse_vtt_transcript
from mcp_snapshot_server.utils.config import get_settings
from mcp_snapshot_server.utils.errors import ErrorCode, MCPServerError
from mcp_snapshot_server.utils.logging_config import ContextLogger


class OrchestrationAgent(BaseAgent):
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

    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Generate complete Customer Success Snapshot from VTT transcript.

        Args:
            input_data: Dictionary containing:
                - vtt_file_path: Path to VTT transcript file

        Returns:
            Dictionary containing:
                - sections: All generated sections
                - metadata: Generation metadata
                - validation: Validation results
                - missing_fields: Aggregated missing fields
        """
        vtt_file_path = input_data.get("vtt_file_path")
        if not vtt_file_path:
            raise MCPServerError(
                error_code=ErrorCode.INVALID_INPUT,
                message="vtt_file_path is required",
                details={"input_data": input_data},
            )

        self.logger.info(
            "Starting snapshot generation workflow",
            extra={"vtt_file": vtt_file_path},
        )

        try:
            # Step 1: Parse VTT transcript
            transcript_data = self._parse_transcript(vtt_file_path)

            # Step 2: Analyze transcript
            analysis_results = await self._analyze_transcript(transcript_data)

            # Step 3: Generate sections (10 sections, excluding Executive Summary)
            sections = await self._generate_sections(transcript_data, analysis_results)

            # Step 4: Validate sections
            validation_results = await self._validate_sections(sections)

            # Step 5: Handle improvements if needed
            if validation_results.get("requires_improvements", False):
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
                    "validation_passed": not final_validation.get(
                        "requires_improvements", False
                    ),
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
                details={"vtt_file": vtt_file_path, "error": str(e)},
            ) from e

    def _parse_transcript(self, vtt_file_path: str) -> dict[str, Any]:
        """Parse VTT transcript file.

        Args:
            vtt_file_path: Path to VTT file

        Returns:
            Parsed transcript data
        """
        self.logger.info("Parsing VTT transcript", extra={"file": vtt_file_path})

        try:
            transcript_data = parse_vtt_transcript(vtt_file_path)
            self.logger.info(
                "Transcript parsed successfully",
                extra={
                    "speaker_count": len(transcript_data.get("speakers", [])),
                    "turn_count": len(transcript_data.get("speaker_turns", [])),
                    "duration": transcript_data.get("duration", 0),
                },
            )
            return transcript_data
        except Exception as e:
            raise MCPServerError(
                error_code=ErrorCode.PARSE_ERROR,
                message=f"Failed to parse VTT file: {str(e)}",
                details={"file": vtt_file_path},
            ) from e

    async def _analyze_transcript(self, transcript_data: dict[str, Any]) -> dict[str, Any]:
        """Analyze transcript using Analysis Agent.

        Args:
            transcript_data: Parsed transcript data

        Returns:
            Analysis results
        """
        self.logger.info("Starting transcript analysis")

        analysis_results = await self.analysis_agent.process(
            {"transcript_data": transcript_data}
        )

        self.logger.info(
            "Transcript analysis complete",
            extra={
                "entities_count": sum(
                    len(v) for v in analysis_results.get("entities", {}).values()
                ),
                "topics_count": len(analysis_results.get("topics", [])),
            },
        )

        return analysis_results

    async def _generate_sections(
        self, transcript_data: dict[str, Any], analysis_results: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        """Generate all sections (excluding Executive Summary).

        Args:
            transcript_data: Parsed transcript data
            analysis_results: Analysis results

        Returns:
            Dictionary of generated sections
        """
        self.logger.info("Starting section generation", extra={"section_count": 10})

        sections = {}
        transcript_text = transcript_data.get("text", "")

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
                "avg_confidence": sum(
                    s.get("confidence", 0) for s in sections.values()
                )
                / len(sections)
                if sections
                else 0,
            },
        )

        return sections

    async def _generate_sections_parallel(
        self, transcript_text: str, analysis_results: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        """Generate sections in parallel.

        Args:
            transcript_text: Full transcript text
            analysis_results: Analysis results

        Returns:
            Dictionary of generated sections
        """
        tasks = []
        section_names = []

        # Create tasks for all sections except Executive Summary
        for section_name in self.SECTION_NAMES[:-1]:
            generator = self.section_generators[section_name]
            task = generator.process(
                {
                    "transcript": transcript_text,
                    "analysis": analysis_results,
                    "context": {},
                }
            )
            tasks.append(task)
            section_names.append(section_name)

        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build sections dictionary
        sections = {}
        for section_name, result in zip(section_names, results):
            if isinstance(result, Exception):
                self.logger.warning(
                    f"Section generation failed: {section_name}",
                    extra={"error": str(result)},
                )
                # Create placeholder section
                sections[section_name] = {
                    "section_name": section_name,
                    "content": f"[Section generation failed: {str(result)}]",
                    "confidence": 0.0,
                    "missing_fields": [],
                    "metadata": {"error": str(result)},
                }
            else:
                sections[section_name] = result

        return sections

    async def _generate_sections_sequential(
        self, transcript_text: str, analysis_results: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        """Generate sections sequentially.

        Args:
            transcript_text: Full transcript text
            analysis_results: Analysis results

        Returns:
            Dictionary of generated sections
        """
        sections = {}

        for section_name in self.SECTION_NAMES[:-1]:
            try:
                generator = self.section_generators[section_name]
                result = await generator.process(
                    {
                        "transcript": transcript_text,
                        "analysis": analysis_results,
                        "context": {},
                    }
                )
                sections[section_name] = result
            except Exception as e:
                self.logger.warning(
                    f"Section generation failed: {section_name}",
                    extra={"error": str(e)},
                )
                sections[section_name] = {
                    "section_name": section_name,
                    "content": f"[Section generation failed: {str(e)}]",
                    "confidence": 0.0,
                    "missing_fields": [],
                    "metadata": {"error": str(e)},
                }

        return sections

    async def _validate_sections(
        self, sections: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        """Validate generated sections.

        Args:
            sections: Generated sections

        Returns:
            Validation results
        """
        self.logger.info("Validating sections", extra={"section_count": len(sections)})

        validation_results = await self.validation_agent.process({"sections": sections})

        self.logger.info(
            "Validation complete",
            extra={
                "issues_found": len(validation_results.get("issues", [])),
                "requires_improvements": validation_results.get(
                    "requires_improvements", False
                ),
            },
        )

        return validation_results

    async def _improve_sections(
        self,
        sections: dict[str, dict[str, Any]],
        validation_results: dict[str, Any],
        transcript_data: dict[str, Any],
        analysis_results: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Improve sections based on validation results.

        Args:
            sections: Current sections
            validation_results: Validation results
            transcript_data: Original transcript data
            analysis_results: Analysis results

        Returns:
            Improved sections
        """
        self.logger.info(
            "Attempting to improve sections",
            extra={"issues": len(validation_results.get("issues", []))},
        )

        # For now, just log the issues and return sections as-is
        # In a production system, this would implement iterative improvement
        # by re-generating low-confidence sections with enhanced prompts

        issues = validation_results.get("issues", [])
        for issue in issues:
            self.logger.info(f"Validation issue: {issue}")

        # Identify low-confidence sections
        low_confidence_threshold = self.settings.workflow.min_confidence_threshold
        low_confidence_sections = [
            name
            for name, section in sections.items()
            if section.get("confidence", 1.0) < low_confidence_threshold
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
        self, sections: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        """Generate Executive Summary from all other sections.

        Args:
            sections: All generated sections (excluding Executive Summary)

        Returns:
            Executive Summary section
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
        result = await exec_summary_generator.process(
            {
                "transcript": "",  # Not needed for executive summary
                "analysis": {},
                "context": {"all_sections": all_sections_text},
            }
        )

        self.logger.info(
            "Executive Summary generated",
            extra={"confidence": result.get("confidence", 0)},
        )

        return result

    def _build_all_sections_text(self, sections: dict[str, dict[str, Any]]) -> str:
        """Build formatted text from all sections.

        Args:
            sections: All sections

        Returns:
            Formatted text
        """
        parts = []
        for name, section in sections.items():
            if name == "Executive Summary":
                continue  # Don't include executive summary in its own input
            content = section.get("content", "")
            parts.append(f"## {name}\n{content}")
        return "\n\n".join(parts)

    def _assemble_output(
        self,
        sections: dict[str, dict[str, Any]],
        analysis_results: dict[str, Any],
        validation_results: dict[str, Any],
    ) -> dict[str, Any]:
        """Assemble final output.

        Args:
            sections: All generated sections
            analysis_results: Analysis results
            validation_results: Final validation results

        Returns:
            Complete snapshot output
        """
        # Aggregate missing fields
        all_missing_fields = []
        for section in sections.values():
            all_missing_fields.extend(section.get("missing_fields", []))

        # Calculate overall confidence
        confidences = [s.get("confidence", 0) for s in sections.values()]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        return {
            "sections": {
                name: {
                    "content": section.get("content", ""),
                    "confidence": section.get("confidence", 0),
                    "missing_fields": section.get("missing_fields", []),
                }
                for name, section in sections.items()
            },
            "metadata": {
                "avg_confidence": avg_confidence,
                "total_sections": len(sections),
                "entities_extracted": analysis_results.get("entities", {}),
                "topics_identified": analysis_results.get("topics", []),
            },
            "validation": validation_results,
            "missing_fields": list(set(all_missing_fields)),  # Deduplicate
        }
