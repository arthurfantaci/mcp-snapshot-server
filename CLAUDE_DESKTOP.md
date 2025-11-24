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

### 2. Find Your uv Installation Path

Claude Desktop doesn't inherit your terminal's PATH, so you need to use the **full path** to `uv`.

**Find your uv path:**
```bash
which uv
```

Common locations:
- macOS/Linux: `/Users/yourname/.local/bin/uv` or `/home/yourname/.local/bin/uv`
- Homebrew: `/opt/homebrew/bin/uv` or `/usr/local/bin/uv`

### 3. Add MCP Server Configuration

Open the configuration file and add the MCP Snapshot Server:

```json
{
  "mcpServers": {
    "mcp-snapshot-server": {
      "command": "/Users/yourname/.local/bin/uv",
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

**Important:**
- Replace `/Users/yourname/.local/bin/uv` with your actual uv path from step 2
- Replace `/absolute/path/to/mcp-snapshot-server` with the actual absolute path to this project directory

### 4. Set Environment Variables

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

### 5. Restart Claude Desktop

After updating the configuration:
1. Quit Claude Desktop completely
2. Relaunch Claude Desktop
3. The MCP server should automatically connect

### 6. Verify Integration

In Claude Desktop, you should see:
- **4 Tools available:** `list_zoom_recordings`, `fetch_zoom_transcript`, `generate_customer_snapshot`, `generate_snapshot_from_zoom`
- **Resources:** Transcripts, snapshots, sections, and field definitions
- **Prompts:** 11 section-specific prompts + field elicitation prompts

## Usage in Claude Desktop

### Two Modes of Operation

**Mode 1: Ad-Hoc Transcript Queries (Fast)**

```
# List recent meetings
List my Zoom recordings from the past week

# Fetch a specific transcript
Fetch transcript for meeting ID 123456789

# Ask questions immediately
What pain points were discussed in this meeting?
Who were the key stakeholders?
What were the main action items?
```

**Mode 2: Generate Full Snapshot (Comprehensive)**

```
# One-step: fetch and generate
Generate a customer success snapshot from Zoom meeting 123456789

# Two-step: fetch first, then generate
1. Fetch transcript for meeting 123456789
2. Generate a snapshot from transcript://abc123
```

### Common Examples

**List and search Zoom recordings:**
```
List my Zoom recordings with transcripts
Search Zoom recordings containing "customer feedback"
Show recordings from November 2024
```

**Query transcripts directly:**
```
Fetch transcript from meeting 123456789
What technical requirements were mentioned?
Summarize the customer's main concerns
Who was the decision maker in this conversation?
```

**Generate documentation:**
```
Generate a customer success snapshot from meeting 123456789
Create a markdown snapshot from transcript://abc123
```

**Access specific sections:**
```
Show me the executive summary from the snapshot
What's in the financial impact section?
```

## Available Primitives

### 1. Tools (4 Total)
- **list_zoom_recordings**: List and search Zoom cloud recordings
  - Input: `from_date`, `to_date`, `search_query`, `page_size`
  - Output: List of recordings with metadata

- **fetch_zoom_transcript**: Fetch and cache Zoom transcript
  - Input: `meeting_id`
  - Output: Full transcript text + URI for reference

- **generate_customer_snapshot**: Generate from cached transcript
  - Input: `transcript_uri`, `output_format`
  - Output: Complete 11-section snapshot

- **generate_snapshot_from_zoom**: One-step fetch and generate
  - Input: `meeting_id`, `output_format`
  - Output: Complete 11-section snapshot

### 2. Resources
- **transcript://<id>**: Cached Zoom transcript with full text and metadata
- **snapshot://<id>**: Full snapshot data
- **snapshot://<id>/section/<section>**: Individual section
- **field://<field_name>**: Field definition and examples

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

### Error: "spawn uv ENOENT" or Server Not Connecting

This is the most common error and occurs when Claude Desktop cannot find the `uv` command.

**Problem:** GUI applications like Claude Desktop don't inherit your terminal's PATH environment variable.

**Solution:** Use the full path to `uv` in your config:

1. **Find your uv path:**
   ```bash
   which uv
   ```
   Example output: `/Users/yourname/.local/bin/uv`

2. **Update your config with the full path:**
   ```json
   {
     "mcpServers": {
       "mcp-snapshot-server": {
         "command": "/Users/yourname/.local/bin/uv",  ← Use full path here
         "args": ["--directory", "/path/to/project", "run", "mcp-snapshot-server"]
       }
     }
   }
   ```

3. **Restart Claude Desktop** (Quit completely with Cmd+Q, then reopen)

**Common uv locations:**
- `~/.local/bin/uv` (standard installation)
- `/opt/homebrew/bin/uv` (Homebrew on Apple Silicon)
- `/usr/local/bin/uv` (Homebrew on Intel Mac)

### Config Syntax Errors

1. Check the config file syntax (must be valid JSON)
2. Verify all paths use forward slashes, even on Windows
3. Ensure no trailing commas in JSON
4. Use a JSON validator if unsure

### API Key Issues

1. Verify API key is valid
2. Check environment variable is set correctly
3. Ensure no extra whitespace in config

### Permission Errors

1. Ensure the project directory is readable
2. Check file permissions on VTT files
3. Verify uv has execute permissions:
   ```bash
   ls -l $(which uv)
   # Should show: -rwxr-xr-x (executable)
   ```

### Viewing Claude Desktop Logs

To see detailed error messages:

**macOS:**
```bash
# View logs in real-time
tail -f ~/Library/Logs/Claude/mcp*.log

# Or check Console.app
# Open Console.app → Search for "Claude" or "MCP"
```

**Windows:**
```powershell
# Check logs in:
%APPDATA%\Claude\logs\
```

**Linux:**
```bash
# Check logs in:
~/.config/Claude/logs/
```

Look for error messages containing "ENOENT", "spawn", or "mcp-snapshot-server".

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
      "command": "/Users/you/.local/bin/uv",
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
