"""MCP Server for Customer Success Snapshot Generation.

This module implements the Model Context Protocol (MCP) server with all 6 primitives:
- Tools: generate_customer_snapshot, upload_transcript
- Resources: transcript, snapshot, section, field URIs
- Prompts: section generation prompts
- Sampling: LLM integration for content generation
- Elicitation: Missing field collection from users
- Logging: Structured logging throughout
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    Resource,
    TextContent,
    Tool,
)

from mcp_snapshot_server.agents.orchestrator import OrchestrationAgent
from mcp_snapshot_server.models import OrchestrationInput, SnapshotOutput
from mcp_snapshot_server.prompts.field_definitions import (
    FIELD_DEFINITIONS,
    get_field_info,
)
from mcp_snapshot_server.prompts.section_prompts import SECTION_PROMPTS
from mcp_snapshot_server.utils.config import get_settings
from mcp_snapshot_server.utils.errors import ErrorCode, MCPServerError
from mcp_snapshot_server.utils.logging_config import ContextLogger


class SnapshotMCPServer:
    """MCP Server for Customer Success Snapshot generation."""

    def __init__(self) -> None:
        """Initialize the MCP server."""
        self.server = Server("mcp-snapshot-server")
        self.settings = get_settings()
        self.logger = ContextLogger("mcp_server")

        # Initialize orchestrator
        self.orchestrator = OrchestrationAgent(logger=self.logger)

        # Storage for generated snapshots (in-memory for now)
        # Values are SnapshotOutput models serialized to dict for JSON compatibility
        self.snapshots: dict[str, dict[str, Any]] = {}

        # Storage for uploaded transcripts (in-memory cache)
        # Key: transcript_id (hash of content), Value: {content, filename, parsed_data}
        self.transcripts: dict[str, dict[str, Any]] = {}

        # Register handlers
        self._register_handlers()

        # Load demo transcript if enabled
        self.logger.info(
            "Checking demo mode configuration",
            extra={"demo_mode": self.settings.demo.mode},
        )
        if self.settings.demo.mode:
            self.logger.info("Demo mode enabled, loading demo transcript")
            self._load_demo_transcript()
        else:
            self.logger.info("Demo mode disabled")

        self.logger.info(
            "MCP Snapshot Server initialized",
            extra={"transcripts_loaded": len(self.transcripts)},
        )

    def _register_handlers(self) -> None:
        """Register all MCP primitive handlers."""
        # Tools primitive
        self.server.list_tools()(self._list_tools)
        self.server.call_tool()(self._call_tool)

        # Resources primitive
        self.server.list_resources()(self._list_resources)
        self.server.read_resource()(self._read_resource)

        # Prompts primitive
        self.server.list_prompts()(self._list_prompts)
        self.server.get_prompt()(self._get_prompt)

        self.logger.info("MCP handlers registered")

    def _load_demo_transcript(self) -> None:
        """Load Quest Enterprises demo transcript for demonstrations.

        This method loads the Quest Enterprises fixture transcript into memory
        when DEMO_MODE is enabled, making it available as transcript://quest-enterprises-demo
        for testing, demonstrations, and training purposes.
        """
        from mcp_snapshot_server.tools.transcript_utils import parse_vtt_content

        # Path to demo transcript fixture
        fixture_path = (
            Path(__file__).parent.parent.parent
            / "tests"
            / "fixtures"
            / "quest_enterprises_project_kickoff_transcript.vtt"
        )

        if not fixture_path.exists():
            self.logger.warning(
                "Demo transcript file not found", extra={"path": str(fixture_path)}
            )
            return

        try:
            # Read VTT content
            with open(fixture_path, encoding="utf-8") as f:
                vtt_content = f.read()

            # Parse VTT content
            filename = "quest_enterprises_project_kickoff_transcript.vtt"
            parsed_data = parse_vtt_content(vtt_content, filename)

            # Use fixed ID for demo transcript (not hash-based)
            transcript_id = "quest-enterprises-demo"
            transcript_uri = f"transcript://{transcript_id}"

            # Store with demo metadata
            self.transcripts[transcript_id] = {
                "content": vtt_content,
                "filename": filename,
                "parsed_data": parsed_data,
                "uri": transcript_uri,
                "source": "demo",
                "demo_metadata": {
                    "meeting_id": "demo",
                    "topic": "Quest Enterprises - Quiznos Analytics Professional Services Engagement Kickoff",
                    "start_time": "2024-07-14T09:00:00Z",
                    "duration": 4113,  # ~68 minutes
                    "description": "Demo transcript for testing and demonstrations",
                },
            }

            self.logger.info(
                "Demo transcript loaded successfully",
                extra={
                    "transcript_id": transcript_id,
                    "uri": transcript_uri,
                    "speakers": len(parsed_data.speakers),
                    "vtt_filename": filename,
                },
            )

        except Exception as e:
            self.logger.error(
                "Failed to load demo transcript",
                extra={"error": str(e), "path": str(fixture_path)},
            )

    # ==================== Tools Primitive ====================

    async def _list_tools(self) -> list[Tool]:
        """List available tools.

        Returns:
            List of available tools
        """
        return [
            Tool(
                name="list_cached_transcripts",
                description="List all transcripts currently cached in server memory. This includes demo transcripts (when DEMO_MODE is enabled) and any transcripts previously fetched from Zoom. Returns transcript URIs that can be used with generate_customer_snapshot.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="list_all_transcripts",
                description="List all available transcripts from both cached memory and Zoom cloud storage. Provides a unified view combining cached transcripts (including demo) and Zoom recordings with transcripts. Shows which Zoom recordings are already cached. If Zoom credentials are not configured, only cached transcripts are returned with a note.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "from_date": {
                            "type": "string",
                            "description": "Start date for Zoom recordings (YYYY-MM-DD). Defaults to 30 days ago.",
                        },
                        "to_date": {
                            "type": "string",
                            "description": "End date for Zoom recordings (YYYY-MM-DD). Defaults to today.",
                        },
                        "search_query": {
                            "type": "string",
                            "description": "Search query to filter Zoom recordings by topic (case-insensitive).",
                        },
                    },
                },
            ),
            Tool(
                name="list_zoom_recordings",
                description="List Zoom cloud recordings with available transcripts from Zoom's cloud storage. Use list_cached_transcripts to see transcripts already loaded in memory (including demo transcripts). Requires Zoom API credentials to be configured (ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "from_date": {
                            "type": "string",
                            "description": "Start date for recordings (YYYY-MM-DD format). Defaults to 30 days ago.",
                        },
                        "to_date": {
                            "type": "string",
                            "description": "End date for recordings (YYYY-MM-DD format). Defaults to today.",
                        },
                        "search_query": {
                            "type": "string",
                            "description": "Search query to filter recordings by topic/title (case-insensitive substring match).",
                        },
                        "page_size": {
                            "type": "integer",
                            "description": "Number of recordings to return per page (max 300). Default: 30.",
                            "default": 30,
                        },
                    },
                },
            ),
            Tool(
                name="fetch_zoom_transcript",
                description="Fetch and cache a VTT transcript from a specific Zoom meeting. Returns a transcript URI (e.g., transcript://abc123) that can be used with generate_customer_snapshot or referenced directly in your conversations to ask questions about the transcript.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "meeting_id": {
                            "type": "string",
                            "description": "Zoom meeting ID (obtain from list_zoom_recordings).",
                        },
                    },
                    "required": ["meeting_id"],
                },
            ),
            Tool(
                name="generate_snapshot_from_zoom",
                description="Fetch Zoom transcript and generate Customer Success Snapshot in a single step. Convenience tool that combines fetch_zoom_transcript and generate_customer_snapshot.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "meeting_id": {
                            "type": "string",
                            "description": "Zoom meeting ID (obtain from list_zoom_recordings).",
                        },
                        "output_format": {
                            "type": "string",
                            "enum": ["json", "markdown"],
                            "description": "Output format for the snapshot",
                            "default": "json",
                        },
                    },
                    "required": ["meeting_id"],
                },
            ),
            Tool(
                name="generate_customer_snapshot",
                description="Generate a comprehensive Customer Success Snapshot from a cached transcript URI. Use list_cached_transcripts to see available transcript URIs (including preloaded demo transcripts). You can also fetch new transcripts from Zoom using fetch_zoom_transcript.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "transcript_uri": {
                            "type": "string",
                            "description": "URI of a cached transcript (e.g., 'transcript://abc123'). Obtain this from fetch_zoom_transcript tool.",
                        },
                        "output_format": {
                            "type": "string",
                            "enum": ["json", "markdown"],
                            "description": "Output format for the snapshot",
                            "default": "json",
                        },
                    },
                    "required": ["transcript_uri"],
                },
            ),
            Tool(
                name="read_transcript_content",
                description="Read raw transcript content from a cached transcript without generating a snapshot. Useful for ad-hoc queries, summarization, or inspecting transcript dialogue. Use list_cached_transcripts to see available transcript URIs.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "transcript_uri": {
                            "type": "string",
                            "description": "URI of a cached transcript (e.g., 'transcript://quest-enterprises-demo'). Obtain from list_cached_transcripts.",
                        },
                        "include_timestamps": {
                            "type": "boolean",
                            "description": "Include VTT timestamps in output. Default: false.",
                            "default": False,
                        },
                        "max_turns": {
                            "type": "integer",
                            "description": "Limit number of speaker turns returned. Useful for previewing long transcripts. Returns all if not specified.",
                        },
                    },
                    "required": ["transcript_uri"],
                },
            ),
        ]

    async def _call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> list[TextContent]:
        """Execute a tool.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool execution results
        """
        if name == "list_cached_transcripts":
            return await self._list_cached_transcripts(arguments)
        elif name == "list_all_transcripts":
            return await self._list_all_transcripts(arguments)
        elif name == "list_zoom_recordings":
            return await self._list_zoom_recordings(arguments)
        elif name == "fetch_zoom_transcript":
            return await self._fetch_zoom_transcript(arguments)
        elif name == "generate_snapshot_from_zoom":
            return await self._generate_snapshot_from_zoom(arguments)
        elif name == "generate_customer_snapshot":
            return await self._generate_snapshot(arguments)
        elif name == "read_transcript_content":
            return await self._read_transcript_content(arguments)
        else:
            raise MCPServerError(
                error_code=ErrorCode.INVALID_INPUT,
                message=f"Unknown tool: {name}",
                details={"tool_name": name},
            )

    def _generate_transcript_id(self, vtt_content: str) -> str:
        """Generate a unique ID for transcript content.

        Args:
            vtt_content: VTT content string

        Returns:
            Short hash-based ID
        """
        content_hash = hashlib.sha256(vtt_content.encode()).hexdigest()
        return content_hash[:12]  # Use first 12 chars for readability

    async def _list_cached_transcripts(
        self, arguments: dict[str, Any]
    ) -> list[TextContent]:
        """List all transcripts currently cached in server memory.

        Args:
            arguments: Tool arguments (none required)

        Returns:
            List of cached transcripts with metadata
        """
        self.logger.info(
            "Listing cached transcripts",
            extra={"count": len(self.transcripts)},
        )

        if not self.transcripts:
            return [
                TextContent(
                    type="text",
                    text="No transcripts currently cached in memory.\n\n"
                    + "You can:\n"
                    + "- Use list_zoom_recordings to find available Zoom meetings\n"
                    + "- Use fetch_zoom_transcript to cache a transcript from Zoom\n"
                    + "- Enable DEMO_MODE to preload the demo transcript",
                )
            ]

        # Build list of cached transcripts
        transcripts_list = []
        for transcript_id, transcript_data in self.transcripts.items():
            transcript_info = {
                "transcript_id": transcript_id,
                "uri": transcript_data["uri"],
                "filename": transcript_data["filename"],
                "source": transcript_data.get("source", "unknown"),
            }

            # Add source-specific metadata
            if (
                transcript_data.get("source") == "zoom"
                and "zoom_metadata" in transcript_data
            ):
                zoom_meta = transcript_data["zoom_metadata"]
                transcript_info["metadata"] = {
                    "meeting_id": zoom_meta.get("meeting_id"),
                    "topic": zoom_meta.get("topic"),
                    "start_time": zoom_meta.get("start_time"),
                    "duration": zoom_meta.get("duration"),
                }
            elif (
                transcript_data.get("source") == "demo"
                and "demo_metadata" in transcript_data
            ):
                demo_meta = transcript_data["demo_metadata"]
                transcript_info["metadata"] = {
                    "topic": demo_meta.get("topic"),
                    "start_time": demo_meta.get("start_time"),
                    "duration": demo_meta.get("duration"),
                    "description": demo_meta.get("description"),
                }

            # Add speaker information
            parsed_data = transcript_data.get("parsed_data")
            if parsed_data is not None:
                transcript_info["speakers"] = parsed_data.speakers
                transcript_info["speaker_turns"] = len(parsed_data.speaker_turns)
            else:
                transcript_info["speakers"] = []
                transcript_info["speaker_turns"] = 0

            transcripts_list.append(transcript_info)

        response_data = {
            "cached_transcripts": transcripts_list,
            "total_count": len(transcripts_list),
        }

        self.logger.info(
            f"Found {len(transcripts_list)} cached transcript(s)",
            extra={"count": len(transcripts_list)},
        )

        return [
            TextContent(
                type="text",
                text=f"Found {len(transcripts_list)} cached transcript(s) in memory\n\n"
                + json.dumps(response_data, indent=2)
                + "\n\nYou can use any transcript URI with the generate_customer_snapshot tool.",
            )
        ]

    async def _list_all_transcripts(
        self, arguments: dict[str, Any]
    ) -> list[TextContent]:
        """List all available transcripts from cached memory and Zoom cloud.

        Aggregates results from both sources, handling missing Zoom credentials gracefully.

        Args:
            arguments: Tool arguments including optional date range and search query for Zoom

        Returns:
            Combined list of transcripts from all sources
        """
        self.logger.info(
            "Listing all transcripts",
            extra={
                "from_date": arguments.get("from_date"),
                "to_date": arguments.get("to_date"),
                "search_query": arguments.get("search_query"),
            },
        )

        # Initialize response components
        cached_transcripts: list[dict[str, Any]] = []
        zoom_recordings: list[dict[str, Any]] = []
        zoom_note: str | None = None
        zoom_error: str | None = None
        zoom_metadata: dict[str, Any] | None = None

        # 1. Get cached transcripts (always available)
        for transcript_id, transcript_data in self.transcripts.items():
            transcript_info: dict[str, Any] = {
                "transcript_id": transcript_id,
                "uri": transcript_data["uri"],
                "filename": transcript_data["filename"],
                "source": transcript_data.get("source", "unknown"),
                "location": "cached",
            }

            # Add source-specific metadata
            if (
                transcript_data.get("source") == "zoom"
                and "zoom_metadata" in transcript_data
            ):
                zoom_meta = transcript_data["zoom_metadata"]
                transcript_info["metadata"] = {
                    "meeting_id": zoom_meta.get("meeting_id"),
                    "topic": zoom_meta.get("topic"),
                    "start_time": zoom_meta.get("start_time"),
                    "duration": zoom_meta.get("duration"),
                }
            elif (
                transcript_data.get("source") == "demo"
                and "demo_metadata" in transcript_data
            ):
                demo_meta = transcript_data["demo_metadata"]
                transcript_info["metadata"] = {
                    "topic": demo_meta.get("topic"),
                    "start_time": demo_meta.get("start_time"),
                    "duration": demo_meta.get("duration"),
                    "description": demo_meta.get("description"),
                }

            # Add speaker information
            parsed_data = transcript_data.get("parsed_data")
            if parsed_data is not None:
                transcript_info["speakers"] = parsed_data.speakers
                transcript_info["speaker_turns"] = len(parsed_data.speaker_turns)
            else:
                transcript_info["speakers"] = []
                transcript_info["speaker_turns"] = 0

            cached_transcripts.append(transcript_info)

        # Build set of cached meeting IDs for duplicate detection
        cached_meeting_ids: set[str] = set()
        for t in cached_transcripts:
            meeting_id = t.get("metadata", {}).get("meeting_id")
            if meeting_id:
                cached_meeting_ids.add(str(meeting_id))

        # 2. Get Zoom cloud recordings (if configured)
        if self.settings.is_zoom_configured:
            try:
                from mcp_snapshot_server.tools.zoom_api import (
                    ZoomAPIManager,
                    list_user_recordings,
                    search_recordings_by_topic,
                )

                from_date = arguments.get("from_date")
                to_date = arguments.get("to_date")
                search_query = arguments.get("search_query")

                manager = ZoomAPIManager()
                result = await list_user_recordings(
                    manager=manager,
                    from_date=from_date,
                    to_date=to_date,
                    page_size=30,
                    has_transcript=True,
                )

                meetings = result["meetings"]

                # Apply search filter if provided
                if search_query:
                    meetings = search_recordings_by_topic(meetings, search_query)

                # Format Zoom recordings
                for meeting in meetings:
                    meeting_id = str(meeting.get("id"))
                    zoom_recordings.append(
                        {
                            "meeting_id": meeting_id,
                            "uuid": meeting.get("uuid"),
                            "topic": meeting.get("topic"),
                            "start_time": meeting.get("start_time"),
                            "duration": meeting.get("duration"),
                            "recording_count": meeting.get("recording_count"),
                            "location": "zoom_cloud",
                            "already_cached": meeting_id in cached_meeting_ids,
                        }
                    )

                zoom_metadata = {
                    "from_date": result["from_date"],
                    "to_date": result["to_date"],
                    "search_query": search_query,
                }

            except Exception as e:
                self.logger.warning(
                    f"Failed to fetch Zoom recordings: {e}",
                    extra={"error_type": type(e).__name__},
                )
                zoom_error = str(e)
        else:
            zoom_note = (
                "Zoom credentials not configured. "
                "Set ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, and ZOOM_CLIENT_SECRET "
                "to see Zoom cloud recordings."
            )

        # 3. Build combined response
        response_data: dict[str, Any] = {
            "cached_transcripts": cached_transcripts,
            "zoom_recordings": zoom_recordings,
            "summary": {
                "cached_count": len(cached_transcripts),
                "zoom_cloud_count": len(zoom_recordings),
                "total_available": len(cached_transcripts) + len(zoom_recordings),
            },
        }

        # Add Zoom metadata if available
        if zoom_metadata:
            response_data["zoom_search_params"] = zoom_metadata

        # Add notes/errors if present
        if zoom_note:
            response_data["note"] = zoom_note
        if zoom_error:
            response_data["zoom_error"] = zoom_error

        # Build human-readable summary
        summary_parts = [f"{len(cached_transcripts)} cached"]
        if self.settings.is_zoom_configured and zoom_error is None:
            summary_parts.append(f"{len(zoom_recordings)} in Zoom cloud")
        elif zoom_note:
            summary_parts.append("Zoom not configured")
        elif zoom_error:
            summary_parts.append("Zoom query failed")

        summary_text = ", ".join(summary_parts)

        self.logger.info(
            f"Listed all transcripts: {summary_text}",
            extra={
                "cached_count": len(cached_transcripts),
                "zoom_count": len(zoom_recordings),
            },
        )

        # Build output text
        output_lines = [
            f"Found transcripts: {summary_text}",
            "",
            json.dumps(response_data, indent=2),
            "",
            "Usage:",
            "- Cached transcripts: Use the 'uri' directly with generate_customer_snapshot or read_transcript_content",
            "- Zoom cloud recordings: Use fetch_zoom_transcript with the 'meeting_id' to cache them first",
        ]

        return [
            TextContent(
                type="text",
                text="\n".join(output_lines),
            )
        ]

    async def _generate_snapshot(self, arguments: dict[str, Any]) -> list[TextContent]:
        """Generate customer success snapshot from cached transcript URI.

        Args:
            arguments: Tool arguments including transcript_uri (required) and output_format

        Returns:
            Generated snapshot as TextContent
        """
        transcript_uri = arguments.get("transcript_uri")
        output_format = arguments.get("output_format", "json")

        # Validate transcript_uri is provided
        if not transcript_uri:
            raise MCPServerError(
                error_code=ErrorCode.INVALID_INPUT,
                message="transcript_uri is required",
                details={"provided_args": list(arguments.keys())},
            )

        # Parse URI (format: transcript://abc123)
        if not transcript_uri.startswith("transcript://"):
            raise MCPServerError(
                error_code=ErrorCode.INVALID_INPUT,
                message=f"Invalid transcript URI format: {transcript_uri}",
                details={"uri": transcript_uri, "expected_format": "transcript://<id>"},
            )

        transcript_id = transcript_uri.replace("transcript://", "")

        # Retrieve from cache
        if transcript_id not in self.transcripts:
            raise MCPServerError(
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Transcript not found: {transcript_uri}. Use fetch_zoom_transcript first.",
                details={"uri": transcript_uri, "transcript_id": transcript_id},
            )

        # Retrieve cached transcript
        cached = self.transcripts[transcript_id]
        vtt_content = cached["content"]
        filename = cached["filename"]

        self.logger.info(
            "Using cached transcript for snapshot generation",
            extra={
                "transcript_id": transcript_id,
                "uri": transcript_uri,
                "filename": filename,
            },
        )

        self.logger.info(
            "Generating snapshot",
            extra={
                "filename": filename,
                "format": output_format,
                "content_length": len(vtt_content) if vtt_content else 0,
            },
        )

        try:
            # Generate snapshot using orchestrator with typed input
            orchestration_input = OrchestrationInput(
                vtt_content=vtt_content,
                filename=filename,
            )
            result = await self.orchestrator.process(orchestration_input)

            # Handle both SnapshotOutput model and dict returns (for test compatibility)
            if isinstance(result, SnapshotOutput):
                result_dict = result.model_dump()
                sections_count = len(result.sections)
                avg_confidence = result.metadata.avg_confidence
            else:
                # Legacy dict format (from tests or older code)
                result_dict = result
                sections_count = len(result.get("sections", {}))
                avg_confidence = result.get("metadata", {}).get("avg_confidence", 0)

            # Store snapshot for later access via Resources
            snapshot_id = Path(filename).stem
            self.snapshots[snapshot_id] = result_dict

            # Format output
            if output_format == "markdown":
                content = self._format_as_markdown(result_dict)
            else:
                content = json.dumps(result_dict, indent=2)

            self.logger.info(
                "Snapshot generated successfully",
                extra={
                    "snapshot_id": snapshot_id,
                    "sections": sections_count,
                    "avg_confidence": avg_confidence,
                },
            )

            return [
                TextContent(
                    type="text",
                    text=content,
                )
            ]

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

    async def _list_zoom_recordings(
        self, arguments: dict[str, Any]
    ) -> list[TextContent]:
        """List Zoom cloud recordings with transcripts.

        Args:
            arguments: Tool arguments including date range and search query

        Returns:
            List of recordings with metadata
        """
        from mcp_snapshot_server.tools.zoom_api import (
            ZoomAPIManager,
            list_user_recordings,
            search_recordings_by_topic,
        )

        from_date = arguments.get("from_date")
        to_date = arguments.get("to_date")
        search_query = arguments.get("search_query")
        page_size = arguments.get("page_size", 30)

        self.logger.info(
            "Listing Zoom recordings",
            extra={
                "from_date": from_date,
                "to_date": to_date,
                "search_query": search_query,
                "page_size": page_size,
            },
        )

        try:
            # Initialize Zoom manager
            manager = ZoomAPIManager()

            # List recordings
            result = await list_user_recordings(
                manager=manager,
                from_date=from_date,
                to_date=to_date,
                page_size=page_size,
                has_transcript=True,
            )

            meetings = result["meetings"]

            # Apply search filter if provided
            if search_query:
                meetings = search_recordings_by_topic(meetings, search_query)

            # Format response
            recordings_list = []
            for meeting in meetings:
                recordings_list.append(
                    {
                        "meeting_id": str(meeting.get("id")),
                        "uuid": meeting.get("uuid"),
                        "topic": meeting.get("topic"),
                        "start_time": meeting.get("start_time"),
                        "duration": meeting.get("duration"),
                        "recording_count": meeting.get("recording_count"),
                    }
                )

            response_data = {
                "recordings": recordings_list,
                "total_count": len(recordings_list),
                "from_date": result["from_date"],
                "to_date": result["to_date"],
                "search_query": search_query,
            }

            self.logger.info(
                f"Found {len(recordings_list)} recordings with transcripts",
                extra={"count": len(recordings_list)},
            )

            return [
                TextContent(
                    type="text",
                    text=f"Found {len(recordings_list)} Zoom recordings with transcripts\n\n"
                    + json.dumps(response_data, indent=2),
                )
            ]

        except MCPServerError:
            raise
        except Exception as e:
            self.logger.error(
                f"Failed to list Zoom recordings: {e}",
                extra={"error_type": type(e).__name__},
            )
            raise MCPServerError(
                error_code=ErrorCode.ZOOM_API_ERROR,
                message=f"Failed to list Zoom recordings: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__},
            ) from e

    async def _fetch_zoom_transcript(
        self, arguments: dict[str, Any]
    ) -> list[TextContent]:
        """Fetch a Zoom transcript and cache it in server memory.

        Args:
            arguments: Tool arguments including meeting_id

        Returns:
            Transcript URI and metadata that can be used for querying or snapshot generation
        """
        from mcp_snapshot_server.tools.transcript_utils import parse_vtt_content
        from mcp_snapshot_server.tools.zoom_api import (
            ZoomAPIManager,
            download_transcript_content,
            find_transcript_file,
            get_meeting_recordings,
        )

        meeting_id = arguments.get("meeting_id")

        if not meeting_id:
            raise MCPServerError(
                error_code=ErrorCode.INVALID_INPUT,
                message="meeting_id is required",
                details={"provided_args": list(arguments.keys())},
            )

        self.logger.info(
            "Fetching Zoom transcript",
            extra={"meeting_id": meeting_id},
        )

        try:
            # Initialize Zoom manager
            manager = ZoomAPIManager()

            # Get meeting recordings
            meeting_data = await get_meeting_recordings(manager, meeting_id)

            # Find transcript file
            recording_files = meeting_data.get("recording_files", [])
            transcript_file = find_transcript_file(recording_files)

            if not transcript_file:
                raise MCPServerError(
                    error_code=ErrorCode.TRANSCRIPT_NOT_AVAILABLE,
                    message=f"No VTT transcript found for meeting {meeting_id}. The meeting may not have a transcript, or it may still be processing.",
                    details={
                        "meeting_id": meeting_id,
                        "recording_files_count": len(recording_files),
                    },
                )

            # Check if transcript is still processing
            if transcript_file.get("status") != "completed":
                raise MCPServerError(
                    error_code=ErrorCode.TRANSCRIPT_PROCESSING,
                    message=f"Transcript is still processing for meeting {meeting_id}. Status: {transcript_file.get('status')}",
                    details={
                        "meeting_id": meeting_id,
                        "status": transcript_file.get("status"),
                    },
                )

            # Download transcript content
            download_url = transcript_file.get("download_url")

            # Get fresh access token
            access_token = await manager._get_access_token()

            vtt_content = await download_transcript_content(
                download_url=download_url,
                access_token=access_token,
                timeout=manager.settings.zoom.api_timeout,
            )

            # Parse and validate transcript
            filename = f"zoom_{meeting_id}.vtt"
            parsed_data = parse_vtt_content(vtt_content, filename)

            # Generate unique ID and cache
            transcript_id = self._generate_transcript_id(vtt_content)
            transcript_uri = f"transcript://{transcript_id}"

            # Store with Zoom metadata
            self.transcripts[transcript_id] = {
                "content": vtt_content,
                "filename": filename,
                "parsed_data": parsed_data,
                "uri": transcript_uri,
                "source": "zoom",
                "zoom_metadata": {
                    "meeting_id": meeting_id,
                    "topic": meeting_data.get("topic"),
                    "start_time": meeting_data.get("start_time"),
                    "duration": meeting_data.get("duration"),
                },
            }

            self.logger.info(
                "Zoom transcript fetched and cached",
                extra={
                    "meeting_id": meeting_id,
                    "transcript_id": transcript_id,
                    "uri": transcript_uri,
                    "speakers": len(parsed_data.speakers),
                },
            )

            # Extract transcript text for immediate use
            transcript_text = parsed_data.text

            # Build response with metadata
            response = {
                "uri": transcript_uri,
                "transcript_id": transcript_id,
                "meeting_id": meeting_id,
                "topic": meeting_data.get("topic"),
                "filename": filename,
                "speakers": parsed_data.speakers,
                "duration": parsed_data.duration,
                "speaker_turns": len(parsed_data.speaker_turns),
            }

            # Return response with transcript text included
            return [
                TextContent(
                    type="text",
                    text="Zoom transcript fetched and cached successfully!\n\n"
                    + f"URI: {transcript_uri}\n\n"
                    + "Metadata:\n"
                    + json.dumps(response, indent=2)
                    + "\n\n"
                    + "--- Transcript Content ---\n"
                    + transcript_text,
                )
            ]

        except MCPServerError:
            raise
        except Exception as e:
            self.logger.error(
                f"Failed to download Zoom transcript: {e}",
                extra={"meeting_id": meeting_id, "error_type": type(e).__name__},
            )
            raise MCPServerError(
                error_code=ErrorCode.ZOOM_API_ERROR,
                message=f"Failed to download Zoom transcript: {str(e)}",
                details={
                    "meeting_id": meeting_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            ) from e

    async def _read_transcript_content(
        self, arguments: dict[str, Any]
    ) -> list[TextContent]:
        """Read raw transcript content from a cached transcript.

        Args:
            arguments: Tool arguments including transcript_uri, include_timestamps, max_turns

        Returns:
            Transcript content with metadata and speaker dialogue
        """
        transcript_uri = arguments.get("transcript_uri")
        include_timestamps = arguments.get("include_timestamps", False)
        max_turns = arguments.get("max_turns")

        # Validate transcript_uri is provided
        if not transcript_uri:
            raise MCPServerError(
                error_code=ErrorCode.INVALID_INPUT,
                message="transcript_uri is required",
                details={"provided_args": list(arguments.keys())},
            )

        # Parse URI (format: transcript://abc123)
        if not transcript_uri.startswith("transcript://"):
            raise MCPServerError(
                error_code=ErrorCode.INVALID_INPUT,
                message=f"Invalid transcript URI format: {transcript_uri}",
                details={"uri": transcript_uri, "expected_format": "transcript://<id>"},
            )

        transcript_id = transcript_uri.replace("transcript://", "")

        # Retrieve from cache
        if transcript_id not in self.transcripts:
            available_uris = [t["uri"] for t in self.transcripts.values()]
            raise MCPServerError(
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Transcript not found: {transcript_uri}",
                details={
                    "uri": transcript_uri,
                    "transcript_id": transcript_id,
                    "available_uris": available_uris,
                    "hint": "Use list_cached_transcripts to see available transcripts",
                },
            )

        self.logger.info(
            "Reading transcript content",
            extra={
                "transcript_id": transcript_id,
                "include_timestamps": include_timestamps,
                "max_turns": max_turns,
            },
        )

        cached = self.transcripts[transcript_id]
        parsed_data = cached.get("parsed_data")

        if parsed_data is None:
            raise MCPServerError(
                error_code=ErrorCode.INTERNAL_ERROR,
                message=f"Transcript data not available for: {transcript_uri}",
                details={"uri": transcript_uri},
            )

        # Build metadata response
        source = cached.get("source", "unknown")
        source_metadata = cached.get(f"{source}_metadata", {})

        metadata = {
            "uri": transcript_uri,
            "transcript_id": transcript_id,
            "topic": source_metadata.get("topic", "Unknown"),
            "filename": cached.get("filename", "Unknown"),
            "speakers": parsed_data.speakers,
            "duration": parsed_data.duration,
            "speaker_turns": len(parsed_data.speaker_turns),
            "source": source,
        }

        # Format transcript content
        speaker_turns = parsed_data.speaker_turns
        total_turns = len(speaker_turns)

        if max_turns is not None and max_turns > 0:
            speaker_turns = speaker_turns[:max_turns]

        content_lines = []
        for turn in speaker_turns:
            if include_timestamps:
                content_lines.append(
                    f"[{turn.start} --> {turn.end}] {turn.speaker}: {turn.text}"
                )
            else:
                content_lines.append(f"{turn.speaker}: {turn.text}")

        transcript_content = "\n".join(content_lines)

        # Build response (matching fetch_zoom_transcript format)
        response_parts = [
            "Cached transcript retrieved successfully!",
            "",
            f"URI: {transcript_uri}",
            "",
            "Metadata:",
            json.dumps(metadata, indent=2),
            "",
            "--- Transcript Content ---",
            transcript_content,
        ]

        if max_turns is not None and total_turns > max_turns:
            response_parts.append(
                f"\n... (truncated, showing {max_turns} of {total_turns} turns)"
            )

        self.logger.info(
            "Transcript content retrieved",
            extra={
                "transcript_id": transcript_id,
                "turns_returned": len(speaker_turns),
                "total_turns": total_turns,
            },
        )

        return [TextContent(type="text", text="\n".join(response_parts))]

    async def _generate_snapshot_from_zoom(
        self, arguments: dict[str, Any]
    ) -> list[TextContent]:
        """Download Zoom transcript and generate snapshot in one step.

        Args:
            arguments: Tool arguments including meeting_id and output_format

        Returns:
            Generated snapshot as TextContent
        """
        meeting_id = arguments.get("meeting_id")
        output_format = arguments.get("output_format", "json")

        if not meeting_id:
            raise MCPServerError(
                error_code=ErrorCode.INVALID_INPUT,
                message="meeting_id is required",
                details={"provided_args": list(arguments.keys())},
            )

        self.logger.info(
            "Generating snapshot from Zoom meeting",
            extra={"meeting_id": meeting_id, "output_format": output_format},
        )

        try:
            # Step 1: Fetch transcript
            download_result = await self._fetch_zoom_transcript(
                {"meeting_id": meeting_id}
            )

            # Extract transcript_uri from the download result
            # The result text contains JSON with the URI
            result_text = download_result[0].text
            # Parse the JSON part (after the success message)
            json_start = result_text.find("{")
            if json_start == -1:
                raise ValueError("Could not parse download result")

            download_data = json.loads(result_text[json_start:])
            transcript_uri = download_data["uri"]

            # Step 2: Generate snapshot
            snapshot_result = await self._generate_snapshot(
                {
                    "transcript_uri": transcript_uri,
                    "output_format": output_format,
                }
            )

            self.logger.info(
                "Snapshot generated from Zoom meeting successfully",
                extra={"meeting_id": meeting_id, "transcript_uri": transcript_uri},
            )

            return snapshot_result

        except MCPServerError:
            raise
        except Exception as e:
            self.logger.error(
                f"Failed to generate snapshot from Zoom: {e}",
                extra={"meeting_id": meeting_id, "error_type": type(e).__name__},
            )
            raise MCPServerError(
                error_code=ErrorCode.INTERNAL_ERROR,
                message=f"Failed to generate snapshot from Zoom: {str(e)}",
                details={
                    "meeting_id": meeting_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            ) from e

    def _format_as_markdown(self, snapshot: dict[str, Any]) -> str:
        """Format snapshot as Markdown.

        Args:
            snapshot: Snapshot data

        Returns:
            Markdown-formatted string
        """
        lines = ["# Customer Success Snapshot\n"]

        # Add metadata
        metadata = snapshot.get("metadata", {})
        lines.append("## Metadata\n")
        lines.append(
            f"- **Average Confidence**: {metadata.get('avg_confidence', 0):.2f}"
        )
        lines.append(f"- **Total Sections**: {metadata.get('total_sections', 0)}")
        lines.append("")

        # Add sections
        sections = snapshot.get("sections", {})
        for section_name, section_data in sections.items():
            lines.append(f"## {section_name}\n")
            lines.append(section_data.get("content", ""))
            lines.append("")
            lines.append(f"*Confidence: {section_data.get('confidence', 0):.2f}*")
            lines.append("")

        # Add validation results
        validation = snapshot.get("validation", {})
        if not validation.get("requires_improvements", False):
            lines.append("## Validation\n")
            lines.append("✅ All quality checks passed")
        else:
            lines.append("## Validation Issues\n")
            for issue in validation.get("issues", []):
                lines.append(f"- {issue}")

        return "\n".join(lines)

    # ==================== Resources Primitive ====================

    async def _list_resources(self) -> list[Resource]:
        """List available resources.

        Returns:
            List of available resources
        """
        resources = []

        # Add transcript resources
        for transcript_id, transcript_data in self.transcripts.items():
            # Build description based on source
            if (
                transcript_data.get("source") == "zoom"
                and "zoom_metadata" in transcript_data
            ):
                zoom_meta = transcript_data["zoom_metadata"]
                topic = zoom_meta.get("topic", "Unknown Meeting")
                start_time = zoom_meta.get("start_time", "")
                # Format start_time for display (e.g., "2024-11-23T10:30:00Z" -> "2024-11-23")
                date_str = start_time.split("T")[0] if start_time else "Unknown date"
                description = f"Zoom meeting: {topic} ({date_str})"
                name = f"Zoom: {topic}"
            elif (
                transcript_data.get("source") == "demo"
                and "demo_metadata" in transcript_data
            ):
                demo_meta = transcript_data["demo_metadata"]
                topic = demo_meta.get("topic", "Demo Transcript")
                start_time = demo_meta.get("start_time", "")
                date_str = start_time.split("T")[0] if start_time else ""
                description = f"Demo transcript: {topic}" + (
                    f" ({date_str})" if date_str else ""
                )
                name = f"Demo: {topic}"
            else:
                description = f"VTT transcript: {transcript_data['filename']}"
                name = f"Transcript: {transcript_data['filename']}"

            resources.append(
                Resource(
                    uri=f"transcript://{transcript_id}",  # type: ignore[arg-type]
                    name=name,
                    description=description,
                    mimeType="text/vtt",
                )
            )

        # Add snapshot resources
        for snapshot_id in self.snapshots:
            resources.append(
                Resource(
                    uri=f"snapshot://{snapshot_id}",  # type: ignore[arg-type]
                    name=f"Snapshot: {snapshot_id}",
                    description=f"Complete customer success snapshot for {snapshot_id}",
                    mimeType="application/json",
                )
            )

        # Add section resources for each snapshot
        for snapshot_id, snapshot in self.snapshots.items():
            for section_name in snapshot.get("sections", {}):
                section_slug = section_name.lower().replace(" ", "_")
                resources.append(
                    Resource(
                        uri=f"snapshot://{snapshot_id}/section/{section_slug}",  # type: ignore[arg-type]
                        name=f"{snapshot_id} - {section_name}",
                        description=f"{section_name} section from snapshot {snapshot_id}",
                        mimeType="text/plain",
                    )
                )

        # Add field definition resources
        for field_name in FIELD_DEFINITIONS:
            resources.append(
                Resource(
                    uri=f"field://{field_name}",  # type: ignore[arg-type]
                    name=f"Field: {field_name}",
                    description=f"Definition for {field_name} field",
                    mimeType="application/json",
                )
            )

        return resources

    async def _read_resource(self, uri: str) -> str:
        """Read a resource by URI.

        Args:
            uri: Resource URI

        Returns:
            Resource content

        Raises:
            MCPServerError: If resource not found
        """
        self.logger.info("Reading resource", extra={"uri": uri})

        # Parse URI
        if uri.startswith("transcript://"):
            return await self._read_transcript_resource(uri)
        elif uri.startswith("snapshot://"):
            return await self._read_snapshot_resource(uri)
        elif uri.startswith("field://"):
            return await self._read_field_resource(uri)
        else:
            raise MCPServerError(
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Unknown resource URI scheme: {uri}",
                details={"uri": uri},
            )

    async def _read_transcript_resource(self, uri: str) -> str:
        """Read transcript resource.

        Args:
            uri: Transcript URI (transcript://<id>)

        Returns:
            Resource content as JSON string with text, metadata, and structure
        """
        transcript_id = uri.replace("transcript://", "")

        if transcript_id not in self.transcripts:
            raise MCPServerError(
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Transcript not found: {transcript_id}",
                details={"transcript_id": transcript_id},
            )

        transcript_data = self.transcripts[transcript_id]
        parsed_data = transcript_data["parsed_data"]

        # Build response with full text prominent for LLM consumption
        response = {
            "uri": uri,
            "transcript_id": transcript_id,
            "filename": transcript_data["filename"],
            # Full text is the primary content for LLM queries
            "text": parsed_data.text,
            # Include speakers for context
            "speakers": parsed_data.speakers,
            # Add Zoom metadata if available
            "source": transcript_data.get("source"),
        }

        # Include Zoom-specific metadata if this is from Zoom
        if (
            transcript_data.get("source") == "zoom"
            and "zoom_metadata" in transcript_data
        ):
            response["zoom_metadata"] = transcript_data["zoom_metadata"]

        # Include full parsed data for detailed analysis if needed
        response["parsed_data"] = {
            "speaker_turns": [turn.model_dump() for turn in parsed_data.speaker_turns],
            "duration": parsed_data.duration,
            "metadata": parsed_data.metadata.model_dump(),
        }

        return json.dumps(response, indent=2)

    async def _read_snapshot_resource(self, uri: str) -> str:
        """Read snapshot resource.

        Args:
            uri: Snapshot URI (snapshot://<id> or snapshot://<id>/section/<section>)

        Returns:
            Resource content as JSON string
        """
        parts = uri.replace("snapshot://", "").split("/")
        snapshot_id = parts[0]

        if snapshot_id not in self.snapshots:
            raise MCPServerError(
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Snapshot not found: {snapshot_id}",
                details={"snapshot_id": snapshot_id},
            )

        snapshot = self.snapshots[snapshot_id]

        # Check if requesting specific section
        if len(parts) >= 3 and parts[1] == "section":
            section_slug = parts[2]
            # Find section by slug
            for section_name, section_data in snapshot["sections"].items():
                if section_name.lower().replace(" ", "_") == section_slug:
                    return json.dumps(section_data, indent=2)

            raise MCPServerError(
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Section not found: {section_slug}",
                details={"snapshot_id": snapshot_id, "section_slug": section_slug},
            )

        # Return full snapshot
        return json.dumps(snapshot, indent=2)

    async def _read_field_resource(self, uri: str) -> str:
        """Read field definition resource.

        Args:
            uri: Field URI (field://<field_name>)

        Returns:
            Field definition as JSON string
        """
        field_name = uri.replace("field://", "")
        field_info = get_field_info(field_name)

        if not field_info:
            raise MCPServerError(
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Field not found: {field_name}",
                details={"field_name": field_name},
            )

        return json.dumps(field_info, indent=2)

    # ==================== Prompts Primitive ====================

    async def _list_prompts(self) -> list[Prompt]:
        """List available prompts.

        Returns:
            List of available prompts
        """
        prompts = []

        # Add section generation prompts
        for _section_key, section_data in SECTION_PROMPTS.items():
            prompts.append(
                Prompt(
                    name=section_data["name"],
                    description=section_data["description"],
                    arguments=[
                        PromptArgument(
                            name=arg,
                            description=f"{arg} for section generation",
                            required=True,
                        )
                        for arg in section_data.get("arguments", [])
                    ],
                )
            )

        # Add field elicitation prompt
        prompts.append(
            Prompt(
                name="elicit_missing_field",
                description="Generate a prompt to elicit missing field information from the user",
                arguments=[
                    PromptArgument(
                        name="field_name",
                        description="Name of the missing field",
                        required=True,
                    ),
                    PromptArgument(
                        name="section_name",
                        description="Section that needs this field",
                        required=True,
                    ),
                ],
            )
        )

        return prompts

    async def _get_prompt(
        self, name: str, arguments: dict[str, str]
    ) -> GetPromptResult:
        """Get a specific prompt.

        Args:
            name: Prompt name
            arguments: Prompt arguments

        Returns:
            Prompt result with messages
        """
        self.logger.info("Getting prompt", extra={"name": name, "arguments": arguments})

        # Check if it's an elicitation prompt
        if name == "elicit_missing_field":
            return await self._get_elicitation_prompt(arguments)

        # Check section prompts
        for _section_key, section_data in SECTION_PROMPTS.items():
            if section_data["name"] == name:
                # Format template with arguments
                template = section_data["template"]
                try:
                    prompt_text = template.format(**arguments)
                except KeyError as e:
                    raise MCPServerError(
                        error_code=ErrorCode.INVALID_INPUT,
                        message=f"Missing required argument: {e}",
                        details={"prompt": name, "arguments": arguments},
                    ) from e

                return GetPromptResult(
                    description=section_data["description"],
                    messages=[
                        PromptMessage(
                            role="user",
                            content=TextContent(type="text", text=prompt_text),
                        )
                    ],
                )

        raise MCPServerError(
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            message=f"Prompt not found: {name}",
            details={"prompt_name": name},
        )

    async def _get_elicitation_prompt(
        self, arguments: dict[str, str]
    ) -> GetPromptResult:
        """Generate field elicitation prompt.

        Args:
            arguments: Must contain field_name and section_name

        Returns:
            Prompt result for field elicitation
        """
        field_name = arguments.get("field_name")
        section_name = arguments.get("section_name")

        if not field_name or not section_name:
            raise MCPServerError(
                error_code=ErrorCode.INVALID_INPUT,
                message="field_name and section_name are required",
                details={"arguments": arguments},
            )

        field_info = get_field_info(field_name)
        if not field_info:
            raise MCPServerError(
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Field not found: {field_name}",
                details={"field_name": field_name},
            )

        # Build elicitation prompt
        prompt_text = f"""The {section_name} section is missing the following information:

**{field_name.replace("_", " ").title()}**
{field_info["description"]}

Example: {field_info["example"]}

Could you please provide this information?"""

        return GetPromptResult(
            description=f"Elicit {field_name} for {section_name}",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt_text),
                )
            ],
        )

    # ==================== Server Lifecycle ====================

    async def run(self) -> None:
        """Run the MCP server using stdio transport."""
        self.logger.info("Starting MCP Snapshot Server")

        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


async def async_main() -> None:
    """Async main function for the MCP server."""
    server = SnapshotMCPServer()
    await server.run()


def main() -> None:
    """Synchronous entry point for the MCP server (called by script entry point)."""
    import asyncio

    from mcp_snapshot_server.utils.logging_config import setup_logging

    # Initialize logging
    setup_logging(level="INFO", structured=True)

    asyncio.run(async_main())


if __name__ == "__main__":
    main()
