# API Reference

Complete API reference for the MCP Snapshot Server.

## Table of Contents
- [MCP Primitives](#mcp-primitives)
- [Tools](#tools)
- [Resources](#resources)
- [Prompts](#prompts)
- [Configuration](#configuration)
- [Error Codes](#error-codes)

## MCP Primitives

The server implements all 6 Model Context Protocol primitives:

1. **Tools** - 7 tools for transcript management, Zoom integration, and snapshot generation
2. **Resources** - Transcripts, snapshots, sections, and field definitions
3. **Prompts** - 11 section prompts + field elicitation prompts
4. **Sampling** - Claude AI integration with retry logic and confidence scoring
5. **Elicitation** - Interactive collection of missing field information
6. **Logging** - Structured JSON logging with full traceability

## Tools

### list_cached_transcripts

List all transcripts currently cached in server memory. This includes demo transcripts (when DEMO_MODE is enabled) and any transcripts previously fetched from Zoom.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {}
}
```

**Output:**
Returns list of cached transcripts with metadata:
- `transcript_id`: Unique identifier
- `uri`: transcript://[id] for use with generate_customer_snapshot
- `filename`: Original file name
- `source`: "demo", "zoom", or other source
- `metadata`: Source-specific metadata (topic, speakers, duration, etc.)
- `speakers`: List of speaker names
- `speaker_turns`: Number of speaking turns

**Example:**
```json
{
  "cached_transcripts": [
    {
      "transcript_id": "quest-enterprises-demo",
      "uri": "transcript://quest-enterprises-demo",
      "filename": "quest_enterprises_project_kickoff_transcript.vtt",
      "source": "demo",
      "metadata": {
        "topic": "Quest Enterprises - Quiznos Analytics Professional Services Engagement Kickoff",
        "start_time": "2024-07-14T09:00:00Z",
        "duration": 4113,
        "description": "Demo transcript for testing and demonstrations"
      },
      "speakers": ["Bob Jones", "Franklin Dorsey"],
      "speaker_turns": 133
    }
  ],
  "total_count": 1
}
```

---

### list_all_transcripts

List all available transcripts from both cached memory and Zoom cloud storage. Provides a unified view for discovering transcripts without making separate calls. Shows which Zoom recordings are already cached.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "from_date": {
      "type": "string",
      "description": "Start date for Zoom recordings (YYYY-MM-DD). Defaults to 30 days ago."
    },
    "to_date": {
      "type": "string",
      "description": "End date for Zoom recordings (YYYY-MM-DD). Defaults to today."
    },
    "search_query": {
      "type": "string",
      "description": "Search query to filter Zoom recordings by topic (case-insensitive)."
    }
  }
}
```

**Output:**
Returns combined response with:
- `cached_transcripts`: Transcripts in server memory (ready to use)
- `zoom_recordings`: Recordings in Zoom cloud (need fetch_zoom_transcript first)
- `summary`: Counts for each source and total
- `note`: (Optional) Message if Zoom not configured
- `zoom_error`: (Optional) Error message if Zoom API fails
- `zoom_search_params`: (Optional) Date range and search params used

**Example:**
```json
{
  "cached_transcripts": [
    {
      "transcript_id": "quest-enterprises-demo",
      "uri": "transcript://quest-enterprises-demo",
      "filename": "quest_enterprises_project_kickoff_transcript.vtt",
      "source": "demo",
      "location": "cached",
      "metadata": {
        "topic": "Quest Enterprises - Quiznos Analytics...",
        "duration": 4113
      },
      "speakers": ["Bob Jones", "Franklin Dorsey"],
      "speaker_turns": 133
    }
  ],
  "zoom_recordings": [
    {
      "meeting_id": "123456789",
      "topic": "Customer Meeting",
      "start_time": "2024-11-23T10:30:00Z",
      "duration": 3600,
      "location": "zoom_cloud",
      "already_cached": false
    }
  ],
  "summary": {
    "cached_count": 1,
    "zoom_cloud_count": 1,
    "total_available": 2
  }
}
```

**Graceful Degradation:**
- If Zoom credentials not configured: Returns cached transcripts with informative `note` field
- If Zoom API fails: Returns cached transcripts with `zoom_error` field

---

### list_zoom_recordings

List Zoom cloud recordings with available transcripts.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "from_date": {
      "type": "string",
      "description": "Start date (YYYY-MM-DD). Defaults to 30 days ago."
    },
    "to_date": {
      "type": "string",
      "description": "End date (YYYY-MM-DD). Defaults to today."
    },
    "search_query": {
      "type": "string",
      "description": "Search query to filter by topic/title (case-insensitive)."
    },
    "page_size": {
      "type": "integer",
      "description": "Number of recordings per page (max 300). Default: 30.",
      "default": 30
    }
  }
}
```

**Output:**
Returns list of recordings with metadata (meeting ID, topic, date, duration, transcript availability).

---

### fetch_zoom_transcript

Fetch and cache a VTT transcript from a Zoom meeting. Returns the transcript URI and full content immediately for analysis.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "meeting_id": {
      "type": "string",
      "description": "Zoom meeting ID (obtain from list_zoom_recordings)."
    }
  },
  "required": ["meeting_id"]
}
```

**Output:**
Returns:
- `uri`: transcript://abc123 (for future reference)
- `metadata`: Meeting topic, speakers, duration, etc.
- `transcript content`: Full text for immediate analysis

The transcript is cached and exposed as an MCP Resource for querying.

---

### read_transcript_content

Read raw transcript content from a cached transcript without generating a snapshot. Useful for ad-hoc queries, summarization, or inspecting transcript dialogue.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "transcript_uri": {
      "type": "string",
      "description": "URI of a cached transcript (e.g., 'transcript://quest-enterprises-demo'). Obtain from list_cached_transcripts."
    },
    "include_timestamps": {
      "type": "boolean",
      "description": "Include VTT timestamps in output. Default: false.",
      "default": false
    },
    "max_turns": {
      "type": "integer",
      "description": "Limit number of speaker turns returned. Useful for previewing long transcripts. Returns all if not specified."
    }
  },
  "required": ["transcript_uri"]
}
```

**Output:**
Returns transcript content with metadata:
- Success message
- URI reference
- Metadata JSON (topic, speakers, duration, turn count)
- Full transcript dialogue (with optional timestamps)
- Truncation notice if max_turns applied

**Example Response:**
```
Cached transcript retrieved successfully!

URI: transcript://quest-enterprises-demo

Metadata:
{
  "uri": "transcript://quest-enterprises-demo",
  "transcript_id": "quest-enterprises-demo",
  "topic": "Quest Enterprises - Quiznos Analytics Professional Services Engagement Kickoff",
  "filename": "quest_enterprises_project_kickoff_transcript.vtt",
  "speakers": ["Bob Jones", "Franklin Dorsey"],
  "duration": 4113,
  "speaker_turns": 133,
  "source": "demo"
}

--- Transcript Content ---
Bob Jones: Hi everyone, thanks for joining today...
Franklin Dorsey: Thanks Bob, excited to get started...
...
```

**With Timestamps (`include_timestamps: true`):**
```
--- Transcript Content ---
[00:00:10.190 --> 00:00:13.230] Franklin Dorsey: And it's recording alright perfect.
[00:00:13.290 --> 00:00:20.840] Bob Jones: Yeah. So we'll take this transcript...
```

**Error Codes:**
- `INVALID_INPUT`: Missing transcript_uri or invalid URI format
- `RESOURCE_NOT_FOUND`: Transcript not in cache

---

### generate_customer_snapshot

Generate a complete Customer Success Snapshot from a cached transcript URI.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "transcript_uri": {
      "type": "string",
      "description": "URI of cached transcript (e.g., 'transcript://abc123'). Obtain from fetch_zoom_transcript."
    },
    "output_format": {
      "type": "string",
      "enum": ["json", "markdown"],
      "description": "Output format for the snapshot",
      "default": "json"
    }
  },
  "required": ["transcript_uri"]
}
```

**Output:**
Returns complete 11-section snapshot with metadata, validation results, and confidence scores.

---

### generate_snapshot_from_zoom

Convenience tool that fetches a Zoom transcript and generates a snapshot in one step.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "meeting_id": {
      "type": "string",
      "description": "Zoom meeting ID (obtain from list_zoom_recordings)."
    },
    "output_format": {
      "type": "string",
      "enum": ["json", "markdown"],
      "description": "Output format for the snapshot",
      "default": "json"
    }
  },
  "required": ["meeting_id"]
}
```

**Output:**
```json
{
  "sections": {
    "Customer Information": {
      "content": "Company Name: Acme Corp...",
      "confidence": 0.9,
      "missing_fields": []
    },
    "Background": { ... },
    ...
  },
  "metadata": {
    "avg_confidence": 0.85,
    "total_sections": 11,
    "entities_extracted": { ... },
    "topics_identified": [ ... ]
  },
  "validation": {
    "factual_consistency": true,
    "completeness": true,
    "quality": true,
    "issues": [],
    "improvements": [],
    "requires_improvements": false
  },
  "missing_fields": ["location", "roi_percentage"]
}
```

## Resources

Resources provide access to transcripts, generated snapshots, sections, and field definitions.

### Resource URIs

#### 1. Transcript Resource

**URI:** `transcript://<transcript_id>`

**Description:** Access cached Zoom meeting transcript with full text and metadata

**Example:**
```python
content = await mcp_server._read_resource("transcript://abc123")
```

**Returns:** JSON string with:
```json
{
  "uri": "transcript://abc123",
  "transcript_id": "abc123",
  "filename": "zoom_123456789.vtt",
  "text": "Full transcript text with speaker labels...",
  "speakers": ["John Smith", "Sarah Johnson"],
  "source": "zoom",
  "zoom_metadata": {
    "meeting_id": "123456789",
    "topic": "Customer Success Review",
    "start_time": "2024-11-23T10:30:00Z",
    "duration": 3600
  },
  "parsed_data": {
    "speaker_turns": [...],
    "duration": 3600,
    "metadata": {...}
  }
}
```

**Usage:**
Transcripts are automatically exposed as resources when fetched via `fetch_zoom_transcript`. Reference them directly in conversations for ad-hoc queries.

---

#### 2. Snapshot Resource

**URI:** `snapshot://<snapshot_id>`

**Description:** Access complete generated snapshot

**Example:**
```python
content = await mcp_server._read_resource("snapshot://acme-meeting")
```

**Returns:** JSON string with complete snapshot data

#### 2. Section Resource

**URI:** `snapshot://<snapshot_id>/section/<section_slug>`

**Description:** Access individual section from a snapshot

**Section Slugs:**
- `customer_information`
- `background`
- `solution`
- `engagement_details`
- `results_and_achievements`
- `adoption_and_usage`
- `financial_impact`
- `long_term_impact`
- `visuals`
- `additional_commentary`
- `executive_summary`

**Example:**
```python
content = await mcp_server._read_resource(
    "snapshot://acme-meeting/section/customer_information"
)
```

**Returns:** JSON string with section data:
```json
{
  "content": "Company Name: Acme Corp\nIndustry: Technology",
  "confidence": 0.9,
  "missing_fields": [],
  "metadata": {}
}
```

#### 3. Field Definition Resource

**URI:** `field://<field_name>`

**Description:** Access field definition with validation rules

**Available Fields:**
- `company_name`
- `industry`
- `location`
- `primary_contact`
- `contact_position`
- `contact_email`
- `start_date`
- `completion_date`
- `product_name`
- `cost_savings`
- `revenue_increase`
- `roi_percentage`
- `user_count`
- `adoption_rate`
- `efficiency_improvement`

**Example:**
```python
content = await mcp_server._read_resource("field://company_name")
```

**Returns:**
```json
{
  "description": "Full legal name of the customer company",
  "type": "string",
  "example": "Acme Corporation",
  "validation": "^[A-Za-z0-9\\s\\.,&'-]{2,100}$"
}
```

### Listing Resources

```python
resources = await mcp_server._list_resources()
```

**Returns:** List of available resources with:
- `uri` - Resource URI
- `name` - Human-readable name
- `description` - Resource description
- `mimeType` - Content type

## Prompts

Prompts provide templates for section generation and field elicitation.

### Section Prompts

#### customer_information_section

Extract customer information from transcript.

**Arguments:**
- `transcript` (required) - Transcript text
- `entities` (required) - Extracted entities

**Example:**
```python
result = await mcp_server._get_prompt(
    "customer_information_section",
    {
        "transcript": "Discussion about Acme Corp...",
        "entities": "ORG: Acme Corp; PERSON: John Smith"
    }
)
```

#### background_section

Identify customer's initial problems and challenges.

**Arguments:**
- `transcript` (required) - Transcript text

#### solution_section

Detail the solution that was implemented.

**Arguments:**
- `transcript` (required) - Transcript text

#### engagement_details_section

Outline engagement timeline and milestones.

**Arguments:**
- `transcript` (required) - Transcript text

#### results_achievements_section

Extract quantifiable results and achievements.

**Arguments:**
- `transcript` (required) - Transcript text

#### adoption_usage_section

Detail solution adoption and usage patterns.

**Arguments:**
- `transcript` (required) - Transcript text

#### financial_impact_section

Extract financial benefits and ROI.

**Arguments:**
- `transcript` (required) - Transcript text

#### long_term_impact_section

Describe strategic benefits and future plans.

**Arguments:**
- `transcript` (required) - Transcript text

#### visuals_section

Identify opportunities for visual elements.

**Arguments:**
- `transcript` (required) - Transcript text

#### additional_commentary_section

Extract relevant details not fitting other sections.

**Arguments:**
- `transcript` (required) - Transcript text

#### executive_summary_section

Create high-level overview synthesizing all sections.

**Arguments:**
- `all_sections` (required) - Combined content of all sections

### Elicitation Prompt

#### elicit_missing_field

Generate prompt to collect missing field information.

**Arguments:**
- `field_name` (required) - Name of missing field
- `section_name` (required) - Section needing the field

**Example:**
```python
result = await mcp_server._get_prompt(
    "elicit_missing_field",
    {
        "field_name": "company_name",
        "section_name": "Customer Information"
    }
)
```

**Returns:**
```json
{
  "description": "Elicit company_name for Customer Information",
  "messages": [
    {
      "role": "user",
      "content": {
        "type": "text",
        "text": "The Customer Information section is missing...\nCould you please provide this information?"
      }
    }
  ]
}
```

### Listing Prompts

```python
prompts = await mcp_server._list_prompts()
```

**Returns:** List of available prompts with:
- `name` - Prompt identifier
- `description` - Prompt purpose
- `arguments` - Required arguments

## Configuration

### Environment Variables

#### LLM Settings

```bash
# Required
LLM_ANTHROPIC_API_KEY=sk-ant-your-key

# Optional
LLM_MODEL=claude-3-5-sonnet-20241022
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS=4000
LLM_MAX_TOKENS_PER_SECTION=2000
```

**Models:**
- `claude-3-5-sonnet-20241022` (recommended)
- `claude-3-opus-20240229` (most capable)
- `claude-3-haiku-20240307` (fastest)

**Temperature:** 0.0-1.0 (lower = more conservative)

#### Workflow Settings

```bash
WORKFLOW_PARALLEL_SECTION_GENERATION=false
WORKFLOW_MIN_CONFIDENCE_THRESHOLD=0.5
WORKFLOW_MAX_IMPROVEMENT_ITERATIONS=2
```

#### NLP Settings

```bash
NLP_SPACY_MODEL=en_core_web_sm
NLP_MAX_ENTITIES_PER_TYPE=10
NLP_MAX_TOPICS=15
```

#### MCP Settings

```bash
MCP_SERVER_NAME=mcp-snapshot-server
MCP_SERVER_VERSION=1.0.0
```

### Configuration via Code

```python
from mcp_snapshot_server.utils.config import Settings

# Custom configuration
settings = Settings(
    llm=LLMSettings(
        anthropic_api_key="your-key",
        model="claude-3-5-sonnet-20241022",
        temperature=0.3
    ),
    workflow=WorkflowSettings(
        parallel_section_generation=True,
        min_confidence_threshold=0.6
    )
)
```

## Error Codes

### Standard Error Codes

```python
class ErrorCode(Enum):
    INVALID_INPUT = "INVALID_INPUT"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    PARSE_ERROR = "PARSE_ERROR"
    API_ERROR = "API_ERROR"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"
```

### Error Response Format

```json
{
  "error_code": "PARSE_ERROR",
  "message": "Failed to parse VTT file: Invalid format",
  "details": {
    "file_path": "/path/to/file.vtt",
    "parse_error": "Missing WEBVTT header"
  }
}
```

### Common Errors

#### INVALID_INPUT
**Cause:** Invalid input parameters
**Example:** Missing required field, invalid file path
**Solution:** Validate input before calling

#### FILE_NOT_FOUND
**Cause:** VTT file doesn't exist
**Solution:** Check file path is correct

#### PARSE_ERROR
**Cause:** Invalid VTT format
**Solution:** Validate VTT file format

#### API_ERROR
**Cause:** Anthropic API call failed
**Solution:** Check API key, network connection, rate limits

#### RATE_LIMIT
**Cause:** API rate limit exceeded
**Solution:** Wait and retry, implement backoff

#### RESOURCE_NOT_FOUND
**Cause:** Requested resource doesn't exist
**Solution:** Check resource URI, ensure snapshot was generated

## Data Structures

### Section Data

```typescript
interface Section {
  section_name: string;
  content: string;
  confidence: number;  // 0.0-1.0
  missing_fields: string[];
  metadata: {
    [key: string]: any;
  };
}
```

### Snapshot Output

```typescript
interface SnapshotOutput {
  sections: {
    [sectionName: string]: {
      content: string;
      confidence: number;
      missing_fields: string[];
    };
  };
  metadata: {
    avg_confidence: number;
    total_sections: number;
    entities_extracted: {
      [entityType: string]: string[];
    };
    topics_identified: string[];
  };
  validation: {
    factual_consistency: boolean;
    completeness: boolean;
    quality: boolean;
    issues: string[];
    improvements: string[];
    requires_improvements: boolean;
    missing_critical_info: string[];
  };
  missing_fields: string[];
}
```

### Validation Results

```typescript
interface ValidationResults {
  factual_consistency: boolean;
  completeness: boolean;
  quality: boolean;
  issues: string[];
  improvements: string[];
  requires_improvements: boolean;
  missing_critical_info: string[];
}
```

## Usage Examples

### Complete Workflow

```python
from mcp_snapshot_server.server import SnapshotMCPServer

# 1. Initialize server
server = SnapshotMCPServer()

# 2. Generate snapshot
result = await server._call_tool(
    "generate_customer_snapshot",
    {
        "vtt_file_path": "/path/to/meeting.vtt",
        "output_format": "json"
    }
)

# 3. Access snapshot via resource
snapshot_content = await server._read_resource("snapshot://meeting")

# 4. Access specific section
section_content = await server._read_resource(
    "snapshot://meeting/section/executive_summary"
)

# 5. Get elicitation prompt for missing field
prompt = await server._get_prompt(
    "elicit_missing_field",
    {
        "field_name": "roi_percentage",
        "section_name": "Financial Impact"
    }
)
```

### Error Handling

```python
from mcp_snapshot_server.utils.errors import MCPServerError, ErrorCode

try:
    result = await server._call_tool(
        "generate_customer_snapshot",
        {"vtt_file_path": "meeting.vtt"}
    )
except MCPServerError as e:
    if e.error_code == ErrorCode.FILE_NOT_FOUND:
        print("File not found")
    elif e.error_code == ErrorCode.PARSE_ERROR:
        print("Invalid VTT format")
    elif e.error_code == ErrorCode.API_ERROR:
        print("API call failed")
    else:
        print(f"Error: {e.message}")
```

### Custom Prompts

```python
# Get section generation prompt
result = await server._get_prompt(
    "background_section",
    {"transcript": "Customer had manual processes..."}
)

# Use the prompt
prompt_text = result.messages[0].content.text
# Send to LLM or use in custom workflow
```

## Performance Considerations

### Parallel Processing

```python
# Enable parallel section generation for speed
settings.workflow.parallel_section_generation = True

# Trade-off: More API calls, faster generation
```

### Token Usage

```python
# Reduce tokens to save costs
settings.llm.max_tokens_per_section = 1500  # Default: 2000

# Use smaller model for analysis
settings.llm.model = "claude-3-haiku-20240307"
```

### Caching

```python
# Cache transcript analysis
analysis_cache = {}

def get_cached_analysis(transcript):
    key = hash(transcript)
    if key not in analysis_cache:
        analysis_cache[key] = analyze(transcript)
    return analysis_cache[key]
```

## Extending the Server

### Custom Section

```python
# Add custom section prompt
SECTION_PROMPTS["custom_section"] = {
    "name": "custom_section",
    "description": "Custom section generation",
    "arguments": ["transcript"],
    "template": "Extract custom information: {transcript}"
}

# Register section generator
orchestrator.section_generators["Custom Section"] = SectionGeneratorAgent(
    section_name="Custom Section",
    system_prompt="Custom instructions",
    prompt_template=SECTION_PROMPTS["custom_section"]["template"],
    logger=logger
)
```

### Custom Field

```python
# Add custom field definition
FIELD_DEFINITIONS["custom_field"] = {
    "description": "Custom field description",
    "type": "string",
    "example": "Example value",
    "validation": r"^[A-Z]{2,10}$"
}
```

## Support

For API questions or issues:
- Check this reference first
- Review [README.md](README.md) for examples
- Check [TROUBLESHOOTING](#) section
- Open GitHub issue with minimal reproduction

## Changelog

### v1.0.0 (Current)
- All 6 MCP primitives implemented
- 11 snapshot sections
- 15 elicitable fields
- Comprehensive validation
- Claude Desktop integration
