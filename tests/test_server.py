"""Tests for MCP Server."""

from unittest.mock import AsyncMock

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

        assert len(tools) == 7

        # Check list_cached_transcripts tool
        cached_tool = next(t for t in tools if t.name == "list_cached_transcripts")
        assert "cached" in cached_tool.description.lower()
        assert "transcript" in cached_tool.description.lower()

        # Check list_zoom_recordings tool
        list_tool = next(t for t in tools if t.name == "list_zoom_recordings")
        assert "zoom" in list_tool.description.lower()
        assert "from_date" in list_tool.inputSchema["properties"]
        assert "to_date" in list_tool.inputSchema["properties"]

        # Check fetch_zoom_transcript tool
        fetch_tool = next(t for t in tools if t.name == "fetch_zoom_transcript")
        assert "fetch" in fetch_tool.description.lower()
        assert "meeting_id" in fetch_tool.inputSchema["properties"]
        assert "meeting_id" in fetch_tool.inputSchema["required"]

        # Check generate_snapshot_from_zoom tool
        zoom_snapshot_tool = next(t for t in tools if t.name == "generate_snapshot_from_zoom")
        assert "zoom" in zoom_snapshot_tool.description.lower()
        assert "meeting_id" in zoom_snapshot_tool.inputSchema["properties"]
        assert "output_format" in zoom_snapshot_tool.inputSchema["properties"]

        # Check generate_customer_snapshot tool
        snapshot_tool = next(t for t in tools if t.name == "generate_customer_snapshot")
        assert "transcript_uri" in snapshot_tool.inputSchema["properties"]
        assert "transcript_uri" in snapshot_tool.inputSchema["required"]
        assert "output_format" in snapshot_tool.inputSchema["properties"]

    @pytest.mark.asyncio
    async def test_call_unknown_tool(self, mcp_server):
        """Test calling unknown tool raises error."""
        with pytest.raises(MCPServerError) as exc_info:
            await mcp_server._call_tool("unknown_tool", {})

        assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
        assert "Unknown tool" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_generate_snapshot_json(
        self, mcp_server, mock_snapshot_result, sample_vtt_content, test_env_vars
    ):
        """Test snapshot generation with JSON output using transcript URI."""
        # Mock orchestrator
        mcp_server.orchestrator.process = AsyncMock(return_value=mock_snapshot_result)

        # Manually cache a transcript first (simulating fetch_zoom_transcript)
        from mcp_snapshot_server.tools.transcript_utils import parse_vtt_content

        parsed_data = parse_vtt_content(sample_vtt_content, "test.vtt")
        transcript_id = mcp_server._generate_transcript_id(sample_vtt_content)
        transcript_uri = f"transcript://{transcript_id}"

        mcp_server.transcripts[transcript_id] = {
            "content": sample_vtt_content,
            "filename": "test.vtt",
            "parsed_data": parsed_data,
            "uri": transcript_uri,
            "source": "zoom",
        }

        # Generate snapshot using cached transcript
        result = await mcp_server._generate_snapshot(
            {"transcript_uri": transcript_uri, "output_format": "json"}
        )

        assert len(result) == 1
        assert result[0].type == "text"
        assert "Customer Information" in result[0].text
        assert "Acme Corp" in result[0].text

        # Check snapshot was stored
        assert "test" in mcp_server.snapshots

    @pytest.mark.asyncio
    async def test_generate_snapshot_markdown(
        self, mcp_server, mock_snapshot_result, sample_vtt_content, test_env_vars
    ):
        """Test snapshot generation with Markdown output using transcript URI."""
        mcp_server.orchestrator.process = AsyncMock(return_value=mock_snapshot_result)

        # Manually cache a transcript first
        from mcp_snapshot_server.tools.transcript_utils import parse_vtt_content

        parsed_data = parse_vtt_content(sample_vtt_content, "test.vtt")
        transcript_id = mcp_server._generate_transcript_id(sample_vtt_content)
        transcript_uri = f"transcript://{transcript_id}"

        mcp_server.transcripts[transcript_id] = {
            "content": sample_vtt_content,
            "filename": "test.vtt",
            "parsed_data": parsed_data,
            "uri": transcript_uri,
            "source": "zoom",
        }

        result = await mcp_server._generate_snapshot(
            {"transcript_uri": transcript_uri, "output_format": "markdown"}
        )

        assert len(result) == 1
        assert result[0].type == "text"
        # Check markdown formatting
        assert "# Customer Success Snapshot" in result[0].text
        assert "## Customer Information" in result[0].text
        assert "## Metadata" in result[0].text
        assert "Average Confidence" in result[0].text

    @pytest.mark.asyncio
    async def test_generate_snapshot_error_handling(self, mcp_server, sample_vtt_content):
        """Test snapshot generation error handling with cached transcript."""
        mcp_server.orchestrator.process = AsyncMock(side_effect=Exception("Test error"))

        # Manually cache a transcript first
        from mcp_snapshot_server.tools.transcript_utils import parse_vtt_content

        parsed_data = parse_vtt_content(sample_vtt_content, "test.vtt")
        transcript_id = mcp_server._generate_transcript_id(sample_vtt_content)
        transcript_uri = f"transcript://{transcript_id}"

        mcp_server.transcripts[transcript_id] = {
            "content": sample_vtt_content,
            "filename": "test.vtt",
            "parsed_data": parsed_data,
            "uri": transcript_uri,
            "source": "zoom",
        }

        with pytest.raises(MCPServerError) as exc_info:
            await mcp_server._generate_snapshot({"transcript_uri": transcript_uri})

        assert exc_info.value.error_code == ErrorCode.INTERNAL_ERROR
        assert "Failed to generate snapshot" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_generate_snapshot_with_uri(
        self, mcp_server, mock_snapshot_result, sample_vtt_content, test_env_vars
    ):
        """Test generating snapshot using transcript URI (Zoom workflow)."""
        # Manually cache a transcript (simulating fetch_zoom_transcript)
        from mcp_snapshot_server.tools.transcript_utils import parse_vtt_content

        parsed_data = parse_vtt_content(sample_vtt_content, "meeting.vtt")
        transcript_id = mcp_server._generate_transcript_id(sample_vtt_content)
        transcript_uri = f"transcript://{transcript_id}"

        mcp_server.transcripts[transcript_id] = {
            "content": sample_vtt_content,
            "filename": "meeting.vtt",
            "parsed_data": parsed_data,
            "uri": transcript_uri,
            "source": "zoom",
        }

        # Mock orchestrator
        mcp_server.orchestrator.process = AsyncMock(return_value=mock_snapshot_result)

        # Generate snapshot using URI
        result = await mcp_server._generate_snapshot({
            "transcript_uri": transcript_uri,
            "output_format": "json"
        })

        assert len(result) == 1
        assert "Customer Information" in result[0].text

        # Verify orchestrator was called with content from cache
        mcp_server.orchestrator.process.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_snapshot_no_transcript_uri_error(self, mcp_server):
        """Test error when transcript_uri is not provided."""
        with pytest.raises(MCPServerError) as exc_info:
            await mcp_server._generate_snapshot({})

        assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
        assert "transcript_uri is required" in str(exc_info.value.message).lower()

    @pytest.mark.asyncio
    async def test_generate_snapshot_invalid_uri(self, mcp_server):
        """Test error with invalid transcript URI."""
        with pytest.raises(MCPServerError) as exc_info:
            await mcp_server._generate_snapshot({
                "transcript_uri": "invalid://abc123"
            })

        assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
        assert "Invalid transcript URI format" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_generate_snapshot_nonexistent_uri(self, mcp_server):
        """Test error with nonexistent transcript URI."""
        with pytest.raises(MCPServerError) as exc_info:
            await mcp_server._generate_snapshot({
                "transcript_uri": "transcript://nonexistent"
            })

        assert exc_info.value.error_code == ErrorCode.RESOURCE_NOT_FOUND
        assert "Transcript not found" in str(exc_info.value.message)

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
        snapshot_resources = [
            r for r in resources if str(r.uri).startswith("snapshot://")
        ]
        assert len(snapshot_resources) > 0

        # Check for main snapshot
        main_snapshot = next(
            (r for r in snapshot_resources if str(r.uri) == "snapshot://test_snapshot"),
            None,
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

    @pytest.mark.asyncio
    async def test_list_resources_with_zoom_transcript(
        self, mcp_server, sample_vtt_content
    ):
        """Test that Zoom transcripts appear in resources with proper metadata."""
        from mcp_snapshot_server.tools.transcript_utils import parse_vtt_content

        # Clear any demo transcripts that may have been loaded (e.g., when DEMO_MODE=true)
        demo_keys = [k for k in mcp_server.transcripts if "demo" in k]
        for key in demo_keys:
            del mcp_server.transcripts[key]

        # Cache a Zoom transcript
        parsed_data = parse_vtt_content(sample_vtt_content, "zoom_123.vtt")
        transcript_id = mcp_server._generate_transcript_id(sample_vtt_content)

        mcp_server.transcripts[transcript_id] = {
            "content": sample_vtt_content,
            "filename": "zoom_123.vtt",
            "parsed_data": parsed_data,
            "uri": f"transcript://{transcript_id}",
            "source": "zoom",
            "zoom_metadata": {
                "meeting_id": "123456789",
                "topic": "Customer Success Review",
                "start_time": "2024-11-23T10:30:00Z",
                "duration": 3600,
            },
        }

        resources = await mcp_server._list_resources()

        # Find transcript resources
        transcript_resources = [
            r for r in resources if str(r.uri).startswith("transcript://")
        ]
        assert len(transcript_resources) == 1

        # Check Zoom transcript has proper name and description
        zoom_transcript = transcript_resources[0]
        assert "Customer Success Review" in zoom_transcript.name
        assert "2024-11-23" in zoom_transcript.description
        assert zoom_transcript.mimeType == "text/vtt"

    @pytest.mark.asyncio
    async def test_read_transcript_resource(self, mcp_server, sample_vtt_content):
        """Test reading a transcript resource returns text and metadata."""
        from mcp_snapshot_server.tools.transcript_utils import parse_vtt_content
        import json

        # Cache a transcript
        parsed_data = parse_vtt_content(sample_vtt_content, "test.vtt")
        transcript_id = mcp_server._generate_transcript_id(sample_vtt_content)

        mcp_server.transcripts[transcript_id] = {
            "content": sample_vtt_content,
            "filename": "test.vtt",
            "parsed_data": parsed_data,
            "uri": f"transcript://{transcript_id}",
            "source": "upload",
        }

        # Read the resource
        content = await mcp_server._read_resource(f"transcript://{transcript_id}")

        # Parse response
        response = json.loads(content)

        # Check that text field is present and contains transcript content
        assert "text" in response
        assert len(response["text"]) > 0
        assert "speakers" in response
        assert response["filename"] == "test.vtt"
        assert response["source"] == "upload"

    @pytest.mark.asyncio
    async def test_read_zoom_transcript_resource(
        self, mcp_server, sample_vtt_content
    ):
        """Test that Zoom transcript resources include zoom_metadata."""
        from mcp_snapshot_server.tools.transcript_utils import parse_vtt_content
        import json

        # Cache a Zoom transcript
        parsed_data = parse_vtt_content(sample_vtt_content, "zoom_123.vtt")
        transcript_id = mcp_server._generate_transcript_id(sample_vtt_content)

        mcp_server.transcripts[transcript_id] = {
            "content": sample_vtt_content,
            "filename": "zoom_123.vtt",
            "parsed_data": parsed_data,
            "uri": f"transcript://{transcript_id}",
            "source": "zoom",
            "zoom_metadata": {
                "meeting_id": "123456789",
                "topic": "Customer Success Review",
                "start_time": "2024-11-23T10:30:00Z",
                "duration": 3600,
            },
        }

        # Read the resource
        content = await mcp_server._read_resource(f"transcript://{transcript_id}")

        # Parse response
        response = json.loads(content)

        # Check that zoom_metadata is included
        assert "zoom_metadata" in response
        assert response["zoom_metadata"]["meeting_id"] == "123456789"
        assert response["zoom_metadata"]["topic"] == "Customer Success Review"
        assert response["source"] == "zoom"

        # Check that text is prominent for LLM consumption
        assert "text" in response
        assert len(response["text"]) > 0

    @pytest.mark.asyncio
    async def test_read_nonexistent_transcript(self, mcp_server):
        """Test reading nonexistent transcript raises error."""
        with pytest.raises(MCPServerError) as exc_info:
            await mcp_server._read_resource("transcript://nonexistent")

        assert exc_info.value.error_code == ErrorCode.RESOURCE_NOT_FOUND
        assert "Transcript not found" in str(exc_info.value.message)


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
    async def test_full_workflow(self, mcp_server, mock_snapshot_result, sample_vtt_content, test_env_vars):
        """Test complete workflow from caching transcript to resource access."""
        # Mock orchestrator
        mcp_server.orchestrator.process = AsyncMock(return_value=mock_snapshot_result)

        # 1. Manually cache a transcript (simulating download_zoom_transcript)
        from mcp_snapshot_server.tools.transcript_utils import parse_vtt_content

        parsed_data = parse_vtt_content(sample_vtt_content, "integration_test.vtt")
        transcript_id = mcp_server._generate_transcript_id(sample_vtt_content)
        transcript_uri = f"transcript://{transcript_id}"

        mcp_server.transcripts[transcript_id] = {
            "content": sample_vtt_content,
            "filename": "integration_test.vtt",
            "parsed_data": parsed_data,
            "uri": transcript_uri,
            "source": "zoom",
        }

        # 2. Generate snapshot using cached transcript URI
        result = await mcp_server._call_tool(
            "generate_customer_snapshot",
            {"transcript_uri": transcript_uri, "output_format": "json"},
        )

        assert len(result) == 1
        assert "Customer Information" in result[0].text

        # 3. List resources - should include the snapshot
        resources = await mcp_server._list_resources()
        snapshot_uris = [
            str(r.uri) for r in resources if "integration_test" in str(r.uri)
        ]
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


class TestReadTranscriptContent:
    """Tests for read_transcript_content tool."""

    @pytest.mark.asyncio
    async def test_read_transcript_content_basic(
        self, mcp_server, sample_vtt_content, test_env_vars
    ):
        """Test reading cached transcript content."""
        from mcp_snapshot_server.tools.transcript_utils import parse_vtt_content

        # Setup: Cache a transcript
        parsed_data = parse_vtt_content(sample_vtt_content, "test.vtt")
        transcript_id = mcp_server._generate_transcript_id(sample_vtt_content)
        transcript_uri = f"transcript://{transcript_id}"

        mcp_server.transcripts[transcript_id] = {
            "content": sample_vtt_content,
            "filename": "test.vtt",
            "parsed_data": parsed_data,
            "uri": transcript_uri,
            "source": "zoom",
            "zoom_metadata": {"topic": "Test Meeting", "duration": 3600},
        }

        # Test
        result = await mcp_server._call_tool(
            "read_transcript_content", {"transcript_uri": transcript_uri}
        )

        assert len(result) == 1
        text = result[0].text
        assert "Cached transcript retrieved successfully!" in text
        assert transcript_uri in text
        assert "--- Transcript Content ---" in text
        assert "Metadata:" in text

    @pytest.mark.asyncio
    async def test_read_transcript_content_with_timestamps(
        self, mcp_server, sample_vtt_content, test_env_vars
    ):
        """Test reading transcript with timestamps included."""
        from mcp_snapshot_server.tools.transcript_utils import parse_vtt_content

        parsed_data = parse_vtt_content(sample_vtt_content, "test.vtt")
        transcript_id = mcp_server._generate_transcript_id(sample_vtt_content)
        transcript_uri = f"transcript://{transcript_id}"

        mcp_server.transcripts[transcript_id] = {
            "content": sample_vtt_content,
            "filename": "test.vtt",
            "parsed_data": parsed_data,
            "uri": transcript_uri,
            "source": "zoom",
            "zoom_metadata": {"topic": "Test Meeting"},
        }

        result = await mcp_server._call_tool(
            "read_transcript_content",
            {"transcript_uri": transcript_uri, "include_timestamps": True},
        )

        text = result[0].text
        # Should contain timestamp format [HH:MM:SS.mmm --> HH:MM:SS.mmm]
        assert "-->" in text

    @pytest.mark.asyncio
    async def test_read_transcript_content_max_turns(
        self, mcp_server, sample_vtt_content, test_env_vars
    ):
        """Test truncation with max_turns parameter."""
        from mcp_snapshot_server.tools.transcript_utils import parse_vtt_content

        parsed_data = parse_vtt_content(sample_vtt_content, "test.vtt")
        transcript_id = mcp_server._generate_transcript_id(sample_vtt_content)
        transcript_uri = f"transcript://{transcript_id}"

        mcp_server.transcripts[transcript_id] = {
            "content": sample_vtt_content,
            "filename": "test.vtt",
            "parsed_data": parsed_data,
            "uri": transcript_uri,
            "source": "zoom",
            "zoom_metadata": {"topic": "Test Meeting"},
        }

        result = await mcp_server._call_tool(
            "read_transcript_content",
            {"transcript_uri": transcript_uri, "max_turns": 3},
        )

        text = result[0].text
        assert "truncated" in text.lower()
        assert "3 of" in text

    @pytest.mark.asyncio
    async def test_read_transcript_content_not_found(self, mcp_server, test_env_vars):
        """Test error when transcript not found."""
        with pytest.raises(MCPServerError) as exc_info:
            await mcp_server._call_tool(
                "read_transcript_content",
                {"transcript_uri": "transcript://nonexistent"},
            )

        assert exc_info.value.error_code == ErrorCode.RESOURCE_NOT_FOUND
        assert "not found" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_read_transcript_content_invalid_uri(self, mcp_server, test_env_vars):
        """Test error for invalid URI format."""
        with pytest.raises(MCPServerError) as exc_info:
            await mcp_server._call_tool(
                "read_transcript_content",
                {"transcript_uri": "invalid-uri-format"},
            )

        assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
        assert "Invalid transcript URI format" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_read_transcript_content_missing_uri(self, mcp_server, test_env_vars):
        """Test error when transcript_uri not provided."""
        with pytest.raises(MCPServerError) as exc_info:
            await mcp_server._call_tool("read_transcript_content", {})

        assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
        assert "transcript_uri is required" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_read_demo_transcript(self, test_env_vars, monkeypatch):
        """Test reading the demo transcript when DEMO_MODE enabled."""
        monkeypatch.setenv("DEMO_MODE", "true")

        from mcp_snapshot_server.server import SnapshotMCPServer

        mcp_server = SnapshotMCPServer()

        # Demo transcript should be loaded
        assert "quest-enterprises-demo" in mcp_server.transcripts

        result = await mcp_server._call_tool(
            "read_transcript_content",
            {"transcript_uri": "transcript://quest-enterprises-demo"},
        )

        text = result[0].text
        assert "Cached transcript retrieved successfully!" in text
        assert "quest-enterprises-demo" in text
        # Check for at least one of the demo speakers
        assert "Bob Jones" in text or "Franklin Dorsey" in text

    @pytest.mark.asyncio
    async def test_list_tools_includes_read_transcript(self, mcp_server):
        """Test that read_transcript_content appears in tool list."""
        tools = await mcp_server._list_tools()
        tool_names = [t.name for t in tools]

        assert "read_transcript_content" in tool_names

        read_tool = next(t for t in tools if t.name == "read_transcript_content")
        assert "transcript_uri" in read_tool.inputSchema["properties"]
        assert "include_timestamps" in read_tool.inputSchema["properties"]
        assert "max_turns" in read_tool.inputSchema["properties"]
        assert "transcript_uri" in read_tool.inputSchema["required"]


class TestListAllTranscripts:
    """Tests for list_all_transcripts tool."""

    @pytest.mark.asyncio
    async def test_list_all_transcripts_empty_no_zoom(self, test_env_vars, monkeypatch):
        """Test empty cache with Zoom not configured."""
        # Ensure Zoom is not configured - must set before settings are loaded
        monkeypatch.setenv("ZOOM_ACCOUNT_ID", "")
        monkeypatch.setenv("ZOOM_CLIENT_ID", "")
        monkeypatch.setenv("ZOOM_CLIENT_SECRET", "")
        monkeypatch.setenv("DEMO_MODE", "false")

        # Clear cached settings to force reload with new env vars
        import mcp_snapshot_server.utils.config as config_module
        if "_settings" in dir(config_module):
            delattr(config_module, "_settings")

        from mcp_snapshot_server.server import SnapshotMCPServer

        server = SnapshotMCPServer()
        server.transcripts.clear()

        result = await server._call_tool("list_all_transcripts", {})

        assert len(result) == 1
        text = result[0].text
        assert "0 cached" in text
        assert "Zoom not configured" in text
        assert "note" in text

    @pytest.mark.asyncio
    async def test_list_all_transcripts_with_cached(
        self, mcp_server, sample_vtt_content, test_env_vars
    ):
        """Test listing includes manually cached transcripts."""
        from mcp_snapshot_server.tools.transcript_utils import parse_vtt_content

        parsed_data = parse_vtt_content(sample_vtt_content, "test.vtt")
        transcript_id = mcp_server._generate_transcript_id(sample_vtt_content)

        mcp_server.transcripts[transcript_id] = {
            "content": sample_vtt_content,
            "filename": "test.vtt",
            "parsed_data": parsed_data,
            "uri": f"transcript://{transcript_id}",
            "source": "zoom",
            "zoom_metadata": {"topic": "Test Meeting", "meeting_id": "123"},
        }

        result = await mcp_server._call_tool("list_all_transcripts", {})

        text = result[0].text
        assert transcript_id in text
        assert "cached_transcripts" in text
        assert '"location": "cached"' in text

    @pytest.mark.asyncio
    async def test_list_all_transcripts_demo_mode(self, test_env_vars, monkeypatch):
        """Test demo transcript appears when DEMO_MODE enabled."""
        monkeypatch.setenv("DEMO_MODE", "true")
        monkeypatch.setenv("ZOOM_ACCOUNT_ID", "")
        monkeypatch.setenv("ZOOM_CLIENT_ID", "")
        monkeypatch.setenv("ZOOM_CLIENT_SECRET", "")

        # Clear cached settings to force reload with new env vars
        import mcp_snapshot_server.utils.config as config_module
        if "_settings" in dir(config_module):
            delattr(config_module, "_settings")

        from mcp_snapshot_server.server import SnapshotMCPServer

        server = SnapshotMCPServer()

        result = await server._call_tool("list_all_transcripts", {})

        text = result[0].text
        assert "quest-enterprises-demo" in text
        assert '"source": "demo"' in text
        assert "1 cached" in text

    @pytest.mark.asyncio
    async def test_list_all_transcripts_summary_counts(self, test_env_vars, monkeypatch):
        """Test summary counts are accurate."""
        # Ensure Zoom is not configured for predictable test
        monkeypatch.setenv("ZOOM_ACCOUNT_ID", "")
        monkeypatch.setenv("ZOOM_CLIENT_ID", "")
        monkeypatch.setenv("ZOOM_CLIENT_SECRET", "")
        monkeypatch.setenv("DEMO_MODE", "false")

        # Clear cached settings to force reload with new env vars
        import mcp_snapshot_server.utils.config as config_module
        if "_settings" in dir(config_module):
            delattr(config_module, "_settings")

        from mcp_snapshot_server.server import SnapshotMCPServer

        server = SnapshotMCPServer()
        server.transcripts.clear()

        # Add exactly 2 cached transcripts
        server.transcripts["test1"] = {
            "uri": "transcript://test1",
            "filename": "test1.vtt",
            "source": "demo",
            "parsed_data": None,
            "demo_metadata": {"topic": "Test 1"},
        }
        server.transcripts["test2"] = {
            "uri": "transcript://test2",
            "filename": "test2.vtt",
            "source": "zoom",
            "parsed_data": None,
            "zoom_metadata": {"topic": "Test 2", "meeting_id": "456"},
        }

        result = await server._call_tool("list_all_transcripts", {})
        text = result[0].text

        assert '"cached_count": 2' in text
        assert '"zoom_cloud_count": 0' in text
        assert '"total_available": 2' in text

    @pytest.mark.asyncio
    async def test_list_all_transcripts_includes_usage_hints(
        self, mcp_server, test_env_vars
    ):
        """Test response includes usage hints."""
        result = await mcp_server._call_tool("list_all_transcripts", {})
        text = result[0].text

        assert "Usage:" in text
        assert "generate_customer_snapshot" in text
        assert "fetch_zoom_transcript" in text

    @pytest.mark.asyncio
    async def test_list_tools_includes_list_all_transcripts(self, mcp_server):
        """Test that list_all_transcripts appears in tool list."""
        tools = await mcp_server._list_tools()
        tool_names = [t.name for t in tools]

        assert "list_all_transcripts" in tool_names

        all_tool = next(t for t in tools if t.name == "list_all_transcripts")
        assert "from_date" in all_tool.inputSchema["properties"]
        assert "to_date" in all_tool.inputSchema["properties"]
        assert "search_query" in all_tool.inputSchema["properties"]

    @pytest.mark.asyncio
    async def test_list_all_transcripts_cached_has_location_field(
        self, mcp_server, sample_vtt_content, test_env_vars
    ):
        """Test cached transcripts have location: cached field."""
        from mcp_snapshot_server.tools.transcript_utils import parse_vtt_content

        parsed_data = parse_vtt_content(sample_vtt_content, "test.vtt")
        transcript_id = mcp_server._generate_transcript_id(sample_vtt_content)

        mcp_server.transcripts[transcript_id] = {
            "content": sample_vtt_content,
            "filename": "test.vtt",
            "parsed_data": parsed_data,
            "uri": f"transcript://{transcript_id}",
            "source": "zoom",
            "zoom_metadata": {"topic": "Test Meeting", "meeting_id": "789"},
        }

        result = await mcp_server._call_tool("list_all_transcripts", {})
        text = result[0].text

        # Verify the location field is present
        assert '"location": "cached"' in text
