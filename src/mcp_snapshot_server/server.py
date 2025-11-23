"""MCP Server for Customer Success Snapshot Generation.

This module implements the Model Context Protocol (MCP) server with all 6 primitives:
- Tools: generate_customer_snapshot
- Resources: transcript, snapshot, section, field URIs
- Prompts: section generation prompts
- Sampling: LLM integration for content generation
- Elicitation: Missing field collection from users
- Logging: Structured logging throughout
"""

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
                name="generate_customer_snapshot",
                description="Generate a comprehensive Customer Success Snapshot from VTT transcript content. Pass the VTT file content as a string.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "vtt_content": {
                            "type": "string",
                            "description": "VTT transcript content as a string (must start with 'WEBVTT')",
                        },
                        "filename": {
                            "type": "string",
                            "description": "Optional filename for context (default: 'transcript.vtt')",
                            "default": "transcript.vtt",
                        },
                        "output_format": {
                            "type": "string",
                            "enum": ["json", "markdown"],
                            "description": "Output format for the snapshot",
                            "default": "json",
                        },
                    },
                    "required": ["vtt_content"],
                },
            )
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
        if name == "generate_customer_snapshot":
            return await self._generate_snapshot(arguments)
        else:
            raise MCPServerError(
                error_code=ErrorCode.INVALID_INPUT,
                message=f"Unknown tool: {name}",
                details={"tool_name": name},
            )

    async def _generate_snapshot(self, arguments: dict[str, Any]) -> list[TextContent]:
        """Generate customer success snapshot.

        Args:
            arguments: Tool arguments including vtt_content, filename (optional), and output_format

        Returns:
            Generated snapshot as TextContent
        """
        vtt_content = arguments.get("vtt_content")
        filename = arguments.get("filename", "transcript.vtt")
        output_format = arguments.get("output_format", "json")

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
        if uri.startswith("snapshot://"):
            return await self._read_snapshot_resource(uri)
        elif uri.startswith("field://"):
            return await self._read_field_resource(uri)
        else:
            raise MCPServerError(
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Unknown resource URI scheme: {uri}",
                details={"uri": uri},
            )

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
