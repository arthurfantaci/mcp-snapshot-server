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

    def __init__(self):
        """Initialize the MCP server."""
        self.server = Server("mcp-snapshot-server")
        self.settings = get_settings()
        self.logger = ContextLogger("mcp_server")

        # Initialize orchestrator
        self.orchestrator = OrchestrationAgent(logger=self.logger)

        # Storage for generated snapshots (in-memory for now)
        self.snapshots: dict[str, dict[str, Any]] = {}

        # Storage for uploaded transcripts (in-memory cache)
        # Key: transcript_id (hash of content), Value: {content, filename, parsed_data}
        self.transcripts: dict[str, dict[str, Any]] = {}

        # Register handlers
        self._register_handlers()

        self.logger.info("MCP Snapshot Server initialized")

    def _register_handlers(self):
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

    # ==================== Tools Primitive ====================

    async def _list_tools(self) -> list[Tool]:
        """List available tools.

        Returns:
            List of available tools
        """
        return [
            Tool(
                name="list_zoom_recordings",
                description="List Zoom cloud recordings with available transcripts. Requires Zoom API credentials to be configured (ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET).",
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
                description="Generate a comprehensive Customer Success Snapshot from a cached transcript URI. The transcript must first be fetched from Zoom using fetch_zoom_transcript.",
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
        if name == "list_zoom_recordings":
            return await self._list_zoom_recordings(arguments)
        elif name == "fetch_zoom_transcript":
            return await self._fetch_zoom_transcript(arguments)
        elif name == "generate_snapshot_from_zoom":
            return await self._generate_snapshot_from_zoom(arguments)
        elif name == "generate_customer_snapshot":
            return await self._generate_snapshot(arguments)
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
            extra={"filename": filename, "format": output_format, "content_length": len(vtt_content) if vtt_content else 0},
        )

        try:
            # Generate snapshot using orchestrator
            result = await self.orchestrator.process({
                "vtt_content": vtt_content,
                "filename": filename
            })

            # Store snapshot for later access via Resources
            snapshot_id = Path(filename).stem
            self.snapshots[snapshot_id] = result

            # Format output
            if output_format == "markdown":
                content = self._format_as_markdown(result)
            else:
                content = json.dumps(result, indent=2)

            self.logger.info(
                "Snapshot generated successfully",
                extra={
                    "snapshot_id": snapshot_id,
                    "sections": len(result["sections"]),
                    "avg_confidence": result["metadata"]["avg_confidence"],
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

    async def _list_zoom_recordings(self, arguments: dict[str, Any]) -> list[TextContent]:
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
                recordings_list.append({
                    "meeting_id": str(meeting.get("id")),
                    "uuid": meeting.get("uuid"),
                    "topic": meeting.get("topic"),
                    "start_time": meeting.get("start_time"),
                    "duration": meeting.get("duration"),
                    "recording_count": meeting.get("recording_count"),
                })

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
            self.logger.error(f"Failed to list Zoom recordings: {e}", extra={"error_type": type(e).__name__})
            raise MCPServerError(
                error_code=ErrorCode.ZOOM_API_ERROR,
                message=f"Failed to list Zoom recordings: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__},
            ) from e

    async def _fetch_zoom_transcript(self, arguments: dict[str, Any]) -> list[TextContent]:
        """Fetch a Zoom transcript and cache it in server memory.

        Args:
            arguments: Tool arguments including meeting_id

        Returns:
            Transcript URI and metadata that can be used for querying or snapshot generation
        """
        from mcp_snapshot_server.tools.zoom_api import (
            ZoomAPIManager,
            download_transcript_content,
            find_transcript_file,
            get_meeting_recordings,
        )
        from mcp_snapshot_server.tools.transcript_utils import parse_vtt_content

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
                    details={"meeting_id": meeting_id, "recording_files_count": len(recording_files)},
                )

            # Check if transcript is still processing
            if transcript_file.get("status") != "completed":
                raise MCPServerError(
                    error_code=ErrorCode.TRANSCRIPT_PROCESSING,
                    message=f"Transcript is still processing for meeting {meeting_id}. Status: {transcript_file.get('status')}",
                    details={"meeting_id": meeting_id, "status": transcript_file.get("status")},
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
                    "speakers": len(parsed_data.get("speakers", [])),
                },
            )

            # Return response
            response = {
                "uri": transcript_uri,
                "transcript_id": transcript_id,
                "meeting_id": meeting_id,
                "topic": meeting_data.get("topic"),
                "filename": filename,
                "speakers": parsed_data.get("speakers", []),
                "duration": parsed_data.get("duration", 0),
                "speaker_turns": len(parsed_data.get("speaker_turns", [])),
            }

            return [
                TextContent(
                    type="text",
                    text=f"Zoom transcript fetched and cached successfully!\n\nURI: {transcript_uri}\n\n"
                    + json.dumps(response, indent=2),
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
                details={"meeting_id": meeting_id, "error": str(e), "error_type": type(e).__name__},
            ) from e

    async def _generate_snapshot_from_zoom(self, arguments: dict[str, Any]) -> list[TextContent]:
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
            download_result = await self._fetch_zoom_transcript({"meeting_id": meeting_id})

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
            snapshot_result = await self._generate_snapshot({
                "transcript_uri": transcript_uri,
                "output_format": output_format,
            })

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
                details={"meeting_id": meeting_id, "error": str(e), "error_type": type(e).__name__},
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
            if transcript_data.get("source") == "zoom" and "zoom_metadata" in transcript_data:
                zoom_meta = transcript_data["zoom_metadata"]
                topic = zoom_meta.get("topic", "Unknown Meeting")
                start_time = zoom_meta.get("start_time", "")
                # Format start_time for display (e.g., "2024-11-23T10:30:00Z" -> "2024-11-23")
                date_str = start_time.split("T")[0] if start_time else "Unknown date"
                description = f"Zoom meeting: {topic} ({date_str})"
                name = f"Zoom: {topic}"
            else:
                description = f"VTT transcript: {transcript_data['filename']}"
                name = f"Transcript: {transcript_data['filename']}"

            resources.append(
                Resource(
                    uri=f"transcript://{transcript_id}",
                    name=name,
                    description=description,
                    mimeType="text/vtt",
                )
            )

        # Add snapshot resources
        for snapshot_id in self.snapshots:
            resources.append(
                Resource(
                    uri=f"snapshot://{snapshot_id}",
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
                        uri=f"snapshot://{snapshot_id}/section/{section_slug}",
                        name=f"{snapshot_id} - {section_name}",
                        description=f"{section_name} section from snapshot {snapshot_id}",
                        mimeType="text/plain",
                    )
                )

        # Add field definition resources
        for field_name in FIELD_DEFINITIONS:
            resources.append(
                Resource(
                    uri=f"field://{field_name}",
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
            "text": parsed_data.get("text", ""),
            # Include speakers for context
            "speakers": parsed_data.get("speakers", []),
            # Add Zoom metadata if available
            "source": transcript_data.get("source"),
        }

        # Include Zoom-specific metadata if this is from Zoom
        if transcript_data.get("source") == "zoom" and "zoom_metadata" in transcript_data:
            response["zoom_metadata"] = transcript_data["zoom_metadata"]

        # Include full parsed data for detailed analysis if needed
        response["parsed_data"] = {
            "speaker_turns": parsed_data.get("speaker_turns", []),
            "duration": parsed_data.get("duration", 0),
            "metadata": parsed_data.get("metadata", {}),
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

    async def run(self):
        """Run the MCP server using stdio transport."""
        self.logger.info("Starting MCP Snapshot Server")

        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


async def async_main():
    """Async main function for the MCP server."""
    server = SnapshotMCPServer()
    await server.run()


def main():
    """Synchronous entry point for the MCP server (called by script entry point)."""
    import asyncio

    asyncio.run(async_main())


if __name__ == "__main__":
    main()
