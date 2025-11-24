"""Analysis Agent for transcript analysis and entity extraction.

This agent performs comprehensive analysis of meeting transcripts,
extracting entities, topics, and structural information.
"""

import json
from typing import Any

from mcp_snapshot_server.agents.base import BaseAgent
from mcp_snapshot_server.models.analysis import (
    AnalysisInput,
    AnalysisMetadata,
    AnalysisResult,
    LLMInsights,
    TranscriptStructure,
)
from mcp_snapshot_server.prompts.system_prompts import SYSTEM_PROMPTS
from mcp_snapshot_server.tools.nlp_utils import (
    analyze_transcript_structure,
    extract_entities,
    extract_key_phrases,
    extract_topics,
)
from mcp_snapshot_server.utils.config import get_settings
from mcp_snapshot_server.utils.logging_config import ContextLogger
from mcp_snapshot_server.utils.sampling import sample_llm


class AnalysisAgent(BaseAgent[AnalysisInput, AnalysisResult]):
    """Agent responsible for initial transcript analysis."""

    def __init__(self, logger: ContextLogger):
        """Initialize Analysis Agent.

        Args:
            logger: Context logger for structured logging
        """
        super().__init__(
            name="AnalysisAgent",
            system_prompt=SYSTEM_PROMPTS["analyzer"],
            logger=logger,
        )

    async def process(self, input_data: AnalysisInput) -> AnalysisResult:
        """Analyze transcript and extract structured information.

        Args:
            input_data: AnalysisInput model containing transcript and context

        Returns:
            AnalysisResult model with extracted information
        """
        transcript = input_data.transcript
        transcript_data = input_data.transcript_data
        additional_context = input_data.additional_context

        self.logger.info(
            "Starting transcript analysis",
            extra={"transcript_length": len(transcript)},
        )

        settings = get_settings()

        # Step 1: Extract entities using NLP
        entities = {}
        if settings.nlp.extract_entities:
            try:
                self.logger.debug("Extracting entities with spaCy")
                entities = extract_entities(transcript)
            except Exception as e:
                self.logger.warning(f"Entity extraction failed: {str(e)}")
                entities = {}

        # Step 2: Extract topics using NLP
        topics = []
        if settings.nlp.extract_topics:
            try:
                self.logger.debug("Extracting topics with NLTK")
                topics = extract_topics(transcript, top_n=15)
            except Exception as e:
                self.logger.warning(f"Topic extraction failed: {str(e)}")
                topics = []

        # Step 3: Extract key phrases
        try:
            self.logger.debug("Extracting key phrases")
            key_phrases = extract_key_phrases(transcript, top_n=15)
        except Exception as e:
            self.logger.warning(f"Key phrase extraction failed: {str(e)}")
            key_phrases = []

        # Step 4: Analyze structure
        structure = TranscriptStructure()
        if transcript_data is not None:
            structure = analyze_transcript_structure(transcript_data)

        # Step 5: LLM-based deep analysis
        llm_analysis = await self._llm_analysis(
            transcript, entities, topics, additional_context
        )

        # Step 6: Assess data availability for each section
        data_availability = self._assess_data_availability(
            transcript, entities, llm_analysis
        )

        self.logger.info(
            "Transcript analysis complete",
            extra={
                "entities_found": sum(len(v) for v in entities.values()),
                "topics_found": len(topics),
                "key_phrases_found": len(key_phrases),
            },
        )

        # Convert llm_analysis dict to LLMInsights model
        llm_insights = LLMInsights(
            entities=llm_analysis.get("entities", {}),
            topics=llm_analysis.get("topics", []),
            structure=llm_analysis.get("structure", {}),
            data_availability=llm_analysis.get("data_availability", {}),
        )

        return AnalysisResult(
            entities=entities,
            topics=topics,
            key_phrases=key_phrases,
            structure=structure,
            llm_insights=llm_insights,
            data_availability=data_availability,
            metadata=AnalysisMetadata(
                analysis_method="hybrid_nlp_llm",
                nlp_enabled=settings.nlp.extract_entities,
            ),
        )

    async def _llm_analysis(
        self,
        transcript: str,
        entities: dict[str, list[str]],
        topics: list[str],
        additional_context: str,
    ) -> dict[str, Any]:
        """Perform LLM-based deep analysis of the transcript.

        Args:
            transcript: Full transcript text
            entities: Extracted entities
            topics: Extracted topics
            additional_context: Additional context

        Returns:
            Dictionary with LLM analysis results
        """
        # Build analysis prompt
        additional_context_section = ""
        if additional_context:
            additional_context_section = f"ADDITIONAL CONTEXT:\n{additional_context}\n\n"

        prompt = f"""Analyze this meeting transcript and extract structured information:

TRANSCRIPT:
{transcript[:3000]}{"..." if len(transcript) > 3000 else ""}

ALREADY EXTRACTED ENTITIES:
{json.dumps(entities, indent=2)}

ALREADY EXTRACTED TOPICS:
{", ".join(topics)}

{additional_context_section}Extract and structure the following information in JSON format:

1. NAMED ENTITIES (supplement the above with any missing):
   - People (names and roles)
   - Companies/Organizations
   - Products/Services
   - Locations
   - Technologies

2. KEY TOPICS:
   - Main discussion themes
   - Problems/challenges discussed
   - Solutions mentioned
   - Metrics and results discussed

3. CONVERSATION STRUCTURE:
   - Meeting type (kickoff, review, planning, consultation, etc.)
   - Number of speakers
   - Discussion flow and phases
   - Key decision points

4. DATA AVAILABILITY ASSESSMENT:
   For each of these sections, rate data availability (0.0 to 1.0):
   - Customer Information
   - Background (problems/challenges)
   - Solution (products/services)
   - Engagement Details (timeline, team)
   - Results and Achievements
   - Adoption and Usage
   - Financial Impact
   - Long-Term Impact
   - Additional Commentary

OUTPUT: Valid JSON only, no additional text.
"""

        try:
            response = await sample_llm(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.2,  # Lower for factual extraction
                max_tokens=2000,
            )

            content = response.content

            # Try to parse as JSON
            try:
                analysis_data = json.loads(content)
            except json.JSONDecodeError:
                # Fallback: extract JSON from response
                self.logger.warning("LLM response not valid JSON, using fallback")
                analysis_data = self._parse_analysis_text(content)

            return analysis_data

        except Exception as e:
            self.logger.warning(f"LLM analysis failed: {str(e)}")
            return {}

    def _parse_analysis_text(self, text: str) -> dict[str, Any]:
        """Fallback parser for non-JSON analysis responses.

        Args:
            text: LLM response text

        Returns:
            Parsed analysis dictionary
        """
        # Basic fallback structure
        return {
            "entities": {},
            "topics": [],
            "structure": {"meeting_type": "unknown"},
            "data_availability": {},
        }

    def _assess_data_availability(
        self,
        transcript: str,
        entities: dict[str, list[str]],
        llm_analysis: dict[str, Any],
    ) -> dict[str, float]:
        """Assess data availability for each snapshot section.

        Args:
            transcript: Full transcript text
            entities: Extracted entities
            llm_analysis: LLM analysis results

        Returns:
            Dictionary mapping section names to confidence scores (0.0-1.0)
        """
        text_lower = transcript.lower()

        # Start with LLM assessment if available
        availability = llm_analysis.get("data_availability", {})

        # Supplement with heuristic checks
        if not availability:
            availability = {}

            # Customer Information
            has_company = bool(entities.get("ORG", []))
            has_person = bool(entities.get("PERSON", []))
            availability["Customer Information"] = (
                0.9 if (has_company and has_person) else 0.5
            )

            # Background
            has_problem_keywords = any(
                keyword in text_lower
                for keyword in ["problem", "challenge", "issue", "pain"]
            )
            availability["Background"] = 0.8 if has_problem_keywords else 0.3

            # Solution
            has_solution_keywords = any(
                keyword in text_lower
                for keyword in ["solution", "implement", "deploy", "product"]
            )
            availability["Solution"] = 0.7 if has_solution_keywords else 0.3

            # Results
            has_results_keywords = any(
                keyword in text_lower
                for keyword in ["result", "improvement", "saved", "increased"]
            )
            availability["Results and Achievements"] = (
                0.7 if has_results_keywords else 0.2
            )

            # Financial Impact
            has_money = bool(entities.get("MONEY", []))
            has_percent = bool(entities.get("PERCENT", []))
            availability["Financial Impact"] = (
                0.7 if (has_money or has_percent) else 0.2
            )

            # Default for others
            for section in [
                "Engagement Details",
                "Adoption and Usage",
                "Long-Term Impact",
            ]:
                if section not in availability:
                    availability[section] = 0.4

        return availability
