"""Tests for MCP Server."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_snapshot_server.server import SnapshotMCPServer
from mcp_snapshot_server.utils.errors import ErrorCode, MCPServerError


@pytest.fixture
def mcp_server():
    """Create an MCP server instance."""
    return SnapshotMCPServer()


@pytest.fixture
def mock_snapshot_result():
    """Mock snapshot generation result."""
    return {
        "sections": {
            "Customer Information": {
                "content": "Company: Acme Corp\nIndustry: Technology",
                "confidence": 0.9,
                "missing_fields": [],
            },
            "Background": {
                "content": "Faced automation challenges",
                "confidence": 0.8,
                "missing_fields": [],
            },
            "Executive Summary": {
                "content": "Comprehensive overview",
                "confidence": 0.85,
                "missing_fields": [],
            },
        },
        "metadata": {
            "avg_confidence": 0.85,
            "total_sections": 3,
            "entities_extracted": {"ORG": ["Acme Corp"]},
            "topics_identified": ["automation"],
        },
        "validation": {
            "factual_consistency": True,
            "completeness": True,
            "quality": True,
            "issues": [],
            "improvements": [],
            "requires_improvements": False,
        },
        "missing_fields": [],
    }


class TestMCPServerInitialization:
    """Test MCP server initialization."""

    def test_server_creation(self, mcp_server):
        """Test server is created with correct components."""
        assert mcp_server.server is not None
        assert mcp_server.settings is not None
        assert mcp_server.logger is not None
        assert mcp_server.orchestrator is not None
        assert isinstance(mcp_server.snapshots, dict)

    def test_handlers_registered(self, mcp_server):
        """Test that all handlers are registered."""
        # Handlers should be registered (we verify this by checking methods exist)
        # The MCP Server class doesn't expose internal handler state
        # Instead, verify the handler methods are callable
        assert callable(mcp_server._list_tools)
        assert callable(mcp_server._call_tool)
        assert callable(mcp_server._list_resources)
        assert callable(mcp_server._read_resource)
        assert callable(mcp_server._list_prompts)
        assert callable(mcp_server._get_prompt)


class TestToolsPrimitive:
    """Test Tools primitive implementation."""

    @pytest.mark.asyncio
    async def test_list_tools(self, mcp_server):
        """Test listing available tools."""
        tools = await mcp_server._list_tools()

        assert len(tools) == 1
        assert tools[0].name == "generate_customer_snapshot"
        assert "VTT transcript" in tools[0].description
        assert "vtt_file_path" in tools[0].inputSchema["properties"]

    @pytest.mark.asyncio
    async def test_call_unknown_tool(self, mcp_server):
        """Test calling unknown tool raises error."""
        with pytest.raises(MCPServerError) as exc_info:
            await mcp_server._call_tool("unknown_tool", {})

        assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
        assert "Unknown tool" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_generate_snapshot_json(
        self, mcp_server, mock_snapshot_result, test_env_vars
    ):
        """Test snapshot generation with JSON output."""
        # Mock orchestrator
        mcp_server.orchestrator.process = AsyncMock(return_value=mock_snapshot_result)

        result = await mcp_server._generate_snapshot(
            {"vtt_file_path": "test.vtt", "output_format": "json"}
        )

        assert len(result) == 1
        assert result[0].type == "text"
        assert "Customer Information" in result[0].text
        assert "Acme Corp" in result[0].text

        # Check snapshot was stored
        assert "test" in mcp_server.snapshots

    @pytest.mark.asyncio
    async def test_generate_snapshot_markdown(
        self, mcp_server, mock_snapshot_result, test_env_vars
    ):
        """Test snapshot generation with Markdown output."""
        mcp_server.orchestrator.process = AsyncMock(return_value=mock_snapshot_result)

        result = await mcp_server._generate_snapshot(
            {"vtt_file_path": "test.vtt", "output_format": "markdown"}
        )

        assert len(result) == 1
        assert result[0].type == "text"
        # Check markdown formatting
        assert "# Customer Success Snapshot" in result[0].text
        assert "## Customer Information" in result[0].text
        assert "## Metadata" in result[0].text
        assert "Average Confidence" in result[0].text

    @pytest.mark.asyncio
    async def test_generate_snapshot_error_handling(self, mcp_server):
        """Test snapshot generation error handling."""
        mcp_server.orchestrator.process = AsyncMock(
            side_effect=Exception("Test error")
        )

        with pytest.raises(MCPServerError) as exc_info:
            await mcp_server._generate_snapshot({"vtt_file_path": "test.vtt"})

        assert exc_info.value.error_code == ErrorCode.INTERNAL_ERROR
        assert "Failed to generate snapshot" in str(exc_info.value.message)

    def test_format_as_markdown(self, mcp_server, mock_snapshot_result):
        """Test markdown formatting."""
        markdown = mcp_server._format_as_markdown(mock_snapshot_result)

        assert "# Customer Success Snapshot" in markdown
        assert "## Customer Information" in markdown
        assert "Acme Corp" in markdown
        assert "Confidence:" in markdown
        assert "✅ All quality checks passed" in markdown

    def test_format_as_markdown_with_issues(self, mcp_server, mock_snapshot_result):
        """Test markdown formatting with validation issues."""
        mock_snapshot_result["validation"]["requires_improvements"] = True
        mock_snapshot_result["validation"]["issues"] = ["Missing date", "Short section"]

        markdown = mcp_server._format_as_markdown(mock_snapshot_result)

        assert "## Validation Issues" in markdown
        assert "Missing date" in markdown
        assert "Short section" in markdown


class TestResourcesPrimitive:
    """Test Resources primitive implementation."""

    @pytest.mark.asyncio
    async def test_list_resources_empty(self, mcp_server):
        """Test listing resources when no snapshots exist."""
        resources = await mcp_server._list_resources()

        # Should only have field definitions
        field_resources = [r for r in resources if str(r.uri).startswith("field://")]
        assert len(field_resources) > 0

    @pytest.mark.asyncio
    async def test_list_resources_with_snapshots(
        self, mcp_server, mock_snapshot_result
    ):
        """Test listing resources with snapshots."""
        mcp_server.snapshots["test_snapshot"] = mock_snapshot_result

        resources = await mcp_server._list_resources()

        # Check snapshot resource
        snapshot_resources = [r for r in resources if str(r.uri).startswith("snapshot://")]
        assert len(snapshot_resources) > 0

        # Check for main snapshot
        main_snapshot = next(
            (r for r in snapshot_resources if str(r.uri) == "snapshot://test_snapshot"), None
        )
        assert main_snapshot is not None
        assert main_snapshot.mimeType == "application/json"

        # Check for section resources
        section_resources = [
            r
            for r in snapshot_resources
            if "/section/" in str(r.uri) and "test_snapshot" in str(r.uri)
        ]
        assert len(section_resources) == 3  # Customer Info, Background, Exec Summary

    @pytest.mark.asyncio
    async def test_read_full_snapshot(self, mcp_server, mock_snapshot_result):
        """Test reading full snapshot resource."""
        mcp_server.snapshots["test"] = mock_snapshot_result

        content = await mcp_server._read_resource("snapshot://test")

        assert "Customer Information" in content
        assert "Acme Corp" in content
        # Should be JSON
        import json

        parsed = json.loads(content)
        assert parsed["metadata"]["avg_confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_read_section_resource(self, mcp_server, mock_snapshot_result):
        """Test reading specific section resource."""
        mcp_server.snapshots["test"] = mock_snapshot_result

        content = await mcp_server._read_resource(
            "snapshot://test/section/customer_information"
        )

        assert "Acme Corp" in content
        assert "confidence" in content.lower()

    @pytest.mark.asyncio
    async def test_read_nonexistent_snapshot(self, mcp_server):
        """Test reading nonexistent snapshot raises error."""
        with pytest.raises(MCPServerError) as exc_info:
            await mcp_server._read_resource("snapshot://nonexistent")

        assert exc_info.value.error_code == ErrorCode.RESOURCE_NOT_FOUND

    @pytest.mark.asyncio
    async def test_read_nonexistent_section(self, mcp_server, mock_snapshot_result):
        """Test reading nonexistent section raises error."""
        mcp_server.snapshots["test"] = mock_snapshot_result

        with pytest.raises(MCPServerError) as exc_info:
            await mcp_server._read_resource("snapshot://test/section/nonexistent")

        assert exc_info.value.error_code == ErrorCode.RESOURCE_NOT_FOUND

    @pytest.mark.asyncio
    async def test_read_field_resource(self, mcp_server):
        """Test reading field definition resource."""
        content = await mcp_server._read_resource("field://company_name")

        assert "description" in content
        assert "Acme Corporation" in content  # Example
        import json

        parsed = json.loads(content)
        assert parsed["type"] == "string"

    @pytest.mark.asyncio
    async def test_read_nonexistent_field(self, mcp_server):
        """Test reading nonexistent field raises error."""
        with pytest.raises(MCPServerError) as exc_info:
            await mcp_server._read_resource("field://nonexistent_field")

        assert exc_info.value.error_code == ErrorCode.RESOURCE_NOT_FOUND

    @pytest.mark.asyncio
    async def test_read_unknown_uri_scheme(self, mcp_server):
        """Test reading unknown URI scheme raises error."""
        with pytest.raises(MCPServerError) as exc_info:
            await mcp_server._read_resource("unknown://something")

        assert exc_info.value.error_code == ErrorCode.RESOURCE_NOT_FOUND
        assert "Unknown resource URI scheme" in str(exc_info.value.message)


class TestPromptsPrimitive:
    """Test Prompts primitive implementation."""

    @pytest.mark.asyncio
    async def test_list_prompts(self, mcp_server):
        """Test listing available prompts."""
        prompts = await mcp_server._list_prompts()

        assert len(prompts) > 0

        # Check for section prompts
        section_prompt_names = [p.name for p in prompts]
        assert "customer_information_section" in section_prompt_names
        assert "background_section" in section_prompt_names

        # Check for elicitation prompt
        assert "elicit_missing_field" in section_prompt_names

    @pytest.mark.asyncio
    async def test_get_section_prompt(self, mcp_server):
        """Test getting a section generation prompt."""
        result = await mcp_server._get_prompt(
            "customer_information_section",
            {
                "transcript": "Sample transcript",
                "entities": "PERSON: Alice; ORG: Acme",
            },
        )

        assert result.description is not None
        assert len(result.messages) == 1
        assert result.messages[0].role == "user"
        assert "Sample transcript" in result.messages[0].content.text
        assert "Acme" in result.messages[0].content.text

    @pytest.mark.asyncio
    async def test_get_elicitation_prompt(self, mcp_server):
        """Test getting field elicitation prompt."""
        result = await mcp_server._get_prompt(
            "elicit_missing_field",
            {"field_name": "company_name", "section_name": "Customer Information"},
        )

        assert "Customer Information" in result.description
        assert len(result.messages) == 1
        message_text = result.messages[0].content.text
        assert "company name" in message_text.lower()
        assert "Acme Corporation" in message_text  # Example

    @pytest.mark.asyncio
    async def test_get_elicitation_prompt_missing_args(self, mcp_server):
        """Test elicitation prompt with missing arguments."""
        with pytest.raises(MCPServerError) as exc_info:
            await mcp_server._get_prompt("elicit_missing_field", {})

        assert exc_info.value.error_code == ErrorCode.INVALID_INPUT

    @pytest.mark.asyncio
    async def test_get_elicitation_prompt_invalid_field(self, mcp_server):
        """Test elicitation prompt with invalid field."""
        with pytest.raises(MCPServerError) as exc_info:
            await mcp_server._get_prompt(
                "elicit_missing_field",
                {
                    "field_name": "nonexistent_field",
                    "section_name": "Customer Information",
                },
            )

        assert exc_info.value.error_code == ErrorCode.RESOURCE_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_nonexistent_prompt(self, mcp_server):
        """Test getting nonexistent prompt raises error."""
        with pytest.raises(MCPServerError) as exc_info:
            await mcp_server._get_prompt("nonexistent_prompt", {})

        assert exc_info.value.error_code == ErrorCode.RESOURCE_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_prompt_missing_arguments(self, mcp_server):
        """Test getting prompt with missing required arguments."""
        with pytest.raises(MCPServerError) as exc_info:
            await mcp_server._get_prompt("customer_information_section", {})

        assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
        assert "Missing required argument" in str(exc_info.value.message)


class TestIntegration:
    """Integration tests for MCP server."""

    @pytest.mark.asyncio
    async def test_full_workflow(self, mcp_server, mock_snapshot_result, test_env_vars):
        """Test complete workflow from tool call to resource access."""
        # Mock orchestrator
        mcp_server.orchestrator.process = AsyncMock(return_value=mock_snapshot_result)

        # 1. Generate snapshot using tool
        result = await mcp_server._call_tool(
            "generate_customer_snapshot",
            {"vtt_file_path": "integration_test.vtt", "output_format": "json"},
        )

        assert len(result) == 1
        assert "Customer Information" in result[0].text

        # 2. List resources - should include the snapshot
        resources = await mcp_server._list_resources()
        snapshot_uris = [str(r.uri) for r in resources if "integration_test" in str(r.uri)]
        assert len(snapshot_uris) > 0

        # 3. Read the snapshot resource
        content = await mcp_server._read_resource("snapshot://integration_test")
        assert "Acme Corp" in content

        # 4. Read a specific section
        section_content = await mcp_server._read_resource(
            "snapshot://integration_test/section/customer_information"
        )
        assert "Acme Corp" in section_content

    @pytest.mark.asyncio
    async def test_elicitation_workflow(self, mcp_server):
        """Test elicitation prompt generation workflow."""
        # 1. List prompts
        prompts = await mcp_server._list_prompts()
        elicit_prompt = next(p for p in prompts if p.name == "elicit_missing_field")
        assert elicit_prompt is not None

        # 2. Get elicitation prompt for specific field
        result = await mcp_server._get_prompt(
            "elicit_missing_field",
            {"field_name": "industry", "section_name": "Customer Information"},
        )

        message_text = result.messages[0].content.text
        assert "industry" in message_text.lower()
        assert "Customer Information" in message_text

        # 3. Read field definition
        field_def = await mcp_server._read_resource("field://industry")
        assert "Financial Services" in field_def  # Example from definition
