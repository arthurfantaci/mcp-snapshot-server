# Claude Desktop Integration

This guide explains how to integrate the MCP Snapshot Server with Claude Desktop.

## Prerequisites

- Claude Desktop app installed
- Anthropic API key
- uv package manager installed
- This project set up and tested

## Configuration Steps

### 1. Locate Claude Desktop Config

The Claude Desktop configuration file is located at:

**macOS:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**Linux:**
```
~/.config/Claude/claude_desktop_config.json
```

### 2. Add MCP Server Configuration

Open the configuration file and add the MCP Snapshot Server:

```json
{
  "mcpServers": {
    "mcp-snapshot-server": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/mcp-snapshot-server",
        "run",
        "mcp-snapshot-server"
      ],
      "env": {
        "LLM_ANTHROPIC_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

**Important:** Replace `/absolute/path/to/mcp-snapshot-server` with the actual absolute path to this project directory.

### 3. Set Environment Variables

You can either:

**Option A:** Use the config file (shown above)
```json
"env": {
  "LLM_ANTHROPIC_API_KEY": "sk-ant-..."
}
```

**Option B:** Reference system environment variable
```json
"env": {
  "LLM_ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}"
}
```

### 4. Restart Claude Desktop

After updating the configuration:
1. Quit Claude Desktop completely
2. Relaunch Claude Desktop
3. The MCP server should automatically connect

### 5. Verify Integration

In Claude Desktop, you should see:
- **Tool available:** `generate_customer_snapshot`
- **Resources:** Field definitions and generated snapshots
- **Prompts:** Section generation and elicitation prompts

## Usage in Claude Desktop

### Generating a Snapshot

```
Can you generate a customer success snapshot from this VTT file:
/path/to/transcript.vtt
```

Claude will use the `generate_customer_snapshot` tool to process the transcript.

### Accessing Resources

```
Show me the customer_information section from the snapshot
```

Claude can access sections via the Resources primitive.

### Using Prompts

```
Help me collect the missing company_name field
```

Claude can use the elicitation prompts to gather missing information.

## Available Primitives

### 1. Tools
- **generate_customer_snapshot**: Generate complete snapshot from VTT file
  - Input: `vtt_file_path`, `output_format` (json|markdown)
  - Output: Complete 11-section snapshot

### 2. Resources
- **snapshot://<id>**: Full snapshot data
- **snapshot://<id>/section/<section>**: Individual section
- **field://<field_name>**: Field definition

### 3. Prompts
- **Section prompts**: customer_information_section, background_section, etc.
- **Elicitation prompt**: elicit_missing_field

### 4. Sampling
- Integrated with Anthropic API for LLM calls
- Automatic retry with exponential backoff
- Confidence scoring for generated content

### 5. Elicitation
- Interactive field collection when information is missing
- Field-specific prompts with examples
- Validation patterns for input

### 6. Logging
- Structured JSON logging to stderr
- Full workflow traceability
- Error tracking with context

## Troubleshooting

### Server Not Connecting

1. Check the config file syntax (must be valid JSON)
2. Verify the absolute path is correct
3. Ensure uv is in your PATH
4. Check Claude Desktop logs

### API Key Issues

1. Verify API key is valid
2. Check environment variable is set correctly
3. Ensure no extra whitespace in config

### Permission Errors

1. Ensure the project directory is readable
2. Check file permissions on VTT files
3. Verify uv has execute permissions

### Debug Mode

Enable detailed logging by setting environment variable:
```json
"env": {
  "LLM_ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}",
  "LOG_LEVEL": "DEBUG"
}
```

## Example Session

```
User: Generate a customer success snapshot from meeting.vtt

Claude: I'll use the generate_customer_snapshot tool to process that transcript.
[Calls tool with vtt_file_path="meeting.vtt"]

Result: Generated 11 sections with average confidence 0.85
- Customer Information: Acme Corporation, Technology sector
- Background: Manual process automation challenges
- Solution: Enterprise Cloud Platform implementation
[... 8 more sections ...]
- Executive Summary: Comprehensive transformation...

User: What's the confidence for the Financial Impact section?

Claude: [Accesses resource snapshot://meeting/section/financial_impact]
The Financial Impact section has a confidence score of 0.72 and shows:
- Cost savings: $250,000 annually
- ROI: 150% over 18 months
[... additional details ...]
```

## Configuration Reference

Full example with all options:

```json
{
  "mcpServers": {
    "mcp-snapshot-server": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/you/projects/mcp-snapshot-server",
        "run",
        "mcp-snapshot-server"
      ],
      "env": {
        "LLM_ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}",
        "LLM_MODEL": "claude-3-5-sonnet-20241022",
        "LLM_TEMPERATURE": "0.3",
        "LLM_MAX_TOKENS": "4000",
        "WORKFLOW_PARALLEL_SECTION_GENERATION": "false",
        "WORKFLOW_MIN_CONFIDENCE_THRESHOLD": "0.5",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

## Support

For issues or questions:
1. Check this documentation
2. Review server logs in Claude Desktop
3. Verify all tests pass: `uv run pytest tests/ -v`
4. Check the project README.md for additional setup information
