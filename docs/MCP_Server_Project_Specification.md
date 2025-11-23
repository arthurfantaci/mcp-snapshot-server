# Python MCP Server with Customer Success Snapshot Generator
## Comprehensive Project Specification for Claude Code

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Development Environment & Tooling](#development-environment--tooling)
3. [Project Structure](#project-structure)
4. [MCP Primitives Implementation](#mcp-primitives-implementation)
5. [Customer Success Snapshot Generator Tool](#customer-success-snapshot-generator-tool)
6. [Multi-Agent Architecture](#multi-agent-architecture)
7. [Configuration Management](#configuration-management)
8. [Code Quality Standards](#code-quality-standards)
9. [Error Handling & Logging](#error-handling--logging)
10. [Testing Strategy](#testing-strategy)
11. [Documentation Requirements](#documentation-requirements)
12. [Security Best Practices](#security-best-practices)
13. [Success Criteria](#success-criteria)
14. [Implementation Phases](#implementation-phases)

---

## Project Overview

### Objectives
Build a production-grade Model Context Protocol (MCP) server in Python that:
- Implements all 6 MCP primitives (Tools, Resources, Prompts, Sampling, Elicitation, Logging)
- Uses modern Python development tooling (uv, ruff)
- Includes a sophisticated Customer Success Snapshot Generator as the flagship tool
- Demonstrates multi-agent orchestration using MCP Sampling
- Follows data engineering best practices for big data and Databricks platforms

### Target Use Case
The primary tool processes VTT (WebVTT) transcript files from customer meetings and generates comprehensive 11-section Customer Success Snapshot documents using a multi-agent workflow with specialized sub-agents for each section.

### Reference Architecture
- **Zoom Transcripts MCP Server** (TypeScript) - MCP patterns and tool structure
- **Customer Solution Snapshot Generator** (Python) - Modern Python tooling with uv/ruff
- **Official MCP Documentation** - https://modelcontextprotocol.io/docs

---

## Development Environment & Tooling

### Core Requirements
- **Python Version**: 3.10+ (3.11 or 3.12 recommended)
- **Package Manager**: `uv` (Rust-based, 10-100x faster than pip)
- **Linter/Formatter**: `ruff` (Rust-based, replaces black, isort, flake8)
- **Configuration**: Single `pyproject.toml` file for all project configuration
- **Type Checking**: `mypy` for static type analysis
- **Testing**: `pytest` with fixtures and mocks

### Why These Tools?

**uv Benefits:**
- 10-100x faster dependency resolution than pip
- Automatic virtual environment management
- Reproducible builds with `uv.lock`
- Better dependency conflict resolution
- Compatible with existing pip workflows

**ruff Benefits:**
- Single tool replacing multiple linters (black, isort, flake8, etc.)
- 10-100x faster than alternatives
- Auto-fix capabilities
- Built-in import sorting
- Comprehensive rule sets

### Installation & Setup
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Initialize project
uv init mcp-snapshot-server
cd mcp-snapshot-server

# Install core dependencies
uv add mcp pydantic python-dotenv anthropic webvtt-py pycaption nltk spacy

# Install dev dependencies
uv add --dev ruff mypy pytest pytest-asyncio pytest-mock

# Download NLP models
uv run python -m spacy download en_core_web_sm
```

---

## Project Structure

```
mcp-snapshot-server/
├── src/
│   └── mcp_snapshot_server/
│       ├── __init__.py
│       ├── server.py                    # Main MCP server class
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── snapshot_generator.py    # Main snapshot generation tool
│       │   └── transcript_utils.py      # VTT parsing utilities
│       ├── resources/
│       │   ├── __init__.py
│       │   ├── transcript_resource.py   # Transcript access
│       │   └── analysis_resource.py     # Analysis results access
│       ├── prompts/
│       │   ├── __init__.py
│       │   ├── section_prompts.py       # 11 section prompt templates
│       │   └── workflow_prompts.py      # Orchestration prompts
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── orchestrator.py          # Main orchestration agent
│       │   ├── analyzer.py              # Transcript analysis agent
│       │   ├── section_generator.py     # Section generation agents
│       │   └── validator.py             # Validation agent
│       └── utils/
│           ├── __init__.py
│           ├── config.py                # Configuration management
│           ├── logging_config.py        # Structured logging
│           ├── validators.py            # Input validation
│           └── formatters.py            # Output formatting
├── tests/
│   ├── __init__.py
│   ├── conftest.py                      # Pytest fixtures
│   ├── test_tools/
│   ├── test_resources/
│   ├── test_prompts/
│   ├── test_agents/
│   └── fixtures/
│       ├── sample_input.vtt
│       ├── test_jama.vtt
│       └── expected_outputs/
├── pyproject.toml                       # Project configuration
├── uv.lock                              # Dependency lock file
├── .env.example                         # Environment template
├── .gitignore
├── README.md
├── SETUP.md                             # Development setup guide
└── LICENSE
```

---

## MCP Primitives Implementation

### 1. Tools (Required)

**Definition**: Callable functions that the LLM can invoke to perform actions.

**Implementation Requirements:**
- Each tool must have a JSON Schema for input validation
- Clear, detailed descriptions for LLM understanding
- Best practices hints for optimal usage
- Comprehensive error handling with informative messages
- Return structured results with metadata

**Primary Tool - `generate_customer_snapshot`:**
```python
{
    "name": "generate_customer_snapshot",
    "description": """Process VTT transcript and generate comprehensive Customer Success 
    Snapshot document using multi-agent workflow. This tool orchestrates 11 specialized 
    sub-agents to create a professional customer success story document.""",
    "bestPractices": """
    - Ensure VTT file is valid and contains speaker labels
    - Provide additional context if available (industry, company size)
    - Choose output format based on intended use (Markdown for editing, HTML for presentation)
    - Review confidence scores for each section
    - Use elicitation to fill in missing critical information
    """,
    "inputSchema": {
        "type": "object",
        "properties": {
            "vtt_file_path": {
                "type": "string",
                "description": "Path to VTT transcript file"
            },
            "output_format": {
                "type": "string",
                "enum": ["markdown", "html"],
                "default": "markdown",
                "description": "Output format for the snapshot document"
            },
            "include_sections": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
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
                        "Executive Summary"
                    ]
                },
                "description": "Optional: Specific sections to generate (defaults to all 11)"
            },
            "additional_context": {
                "type": "string",
                "description": "Optional: Additional context about the customer or project"
            },
            "enable_elicitation": {
                "type": "boolean",
                "default": true,
                "description": "Whether to request user input for missing information"
            }
        },
        "required": ["vtt_file_path"]
    }
}
```

**Additional Supporting Tools:**
- `parse_vtt_transcript` - Parse and clean VTT files
- `analyze_transcript` - Extract entities, topics, and structure
- `validate_section` - Validate individual section content
- `format_document` - Convert to Markdown or HTML

### 2. Resources (Required)

**Definition**: Data and content that the LLM can read via URI patterns.

**Implementation Requirements:**
- Use URI pattern: `resource://server-name/type/id`
- Support resource listing (discover available resources)
- Include metadata with each resource (name, mimeType, description)
- Implement efficient resource fetching

**Resource URIs:**
```
resource://snapshot-server/transcript/{transcript_id}
resource://snapshot-server/analysis/{transcript_id}
resource://snapshot-server/section/{transcript_id}/{section_name}
resource://snapshot-server/snapshot/{transcript_id}
```

**Resource Types:**

1. **Transcript Resource**
   - URI: `resource://snapshot-server/transcript/{id}`
   - MIME Type: `text/plain`
   - Content: Parsed and cleaned transcript text
   - Metadata: Speaker count, duration, word count

2. **Analysis Resource**
   - URI: `resource://snapshot-server/analysis/{id}`
   - MIME Type: `application/json`
   - Content: Extracted entities, topics, key phrases
   - Metadata: Confidence scores, extraction timestamp

3. **Section Resource**
   - URI: `resource://snapshot-server/section/{id}/{section_name}`
   - MIME Type: `text/markdown` or `text/html`
   - Content: Individual section content
   - Metadata: Confidence score, missing fields, word count

4. **Snapshot Resource**
   - URI: `resource://snapshot-server/snapshot/{id}`
   - MIME Type: `text/markdown` or `text/html`
   - Content: Complete assembled document
   - Metadata: Total sections, generation timestamp, validation status

### 3. Prompts (Required)

**Definition**: Pre-defined prompt templates for common workflows.

**Implementation Requirements:**
- Create reusable prompt templates with arguments
- Include clear descriptions of when to use each prompt
- Support prompt composition and chaining
- Provide examples for each prompt

**Prompt Categories:**

**A. Section Generation Prompts (11 templates)**

Each section has a dedicated prompt template:

```python
SECTION_PROMPTS = {
    "customer_information": {
        "name": "customer_information_section",
        "description": "Extract customer information from transcript",
        "arguments": [
            {
                "name": "transcript",
                "description": "Full transcript text",
                "required": True
            },
            {
                "name": "entities",
                "description": "Pre-extracted named entities",
                "required": False
            }
        ],
        "template": """
Based on the following meeting transcript, extract detailed customer information:

TRANSCRIPT:
{transcript}

IDENTIFIED ENTITIES: {entities}

Extract and structure the following information:
• Company Name:
• Industry:
• Location:
• Primary Contact:
• Position:
• Contact Information:

INSTRUCTIONS:
- Be precise and factual
- If information is not explicitly stated, indicate "Not mentioned in transcript"
- You may make reasonable inferences if clearly labeled as [INFERRED]
- Provide complete contact details if available
- Note any ambiguities or uncertainties

OUTPUT FORMAT: Structured bullet points as shown above
"""
    },
    
    "background": {
        "name": "background_section",
        "description": "Identify customer's initial problems and challenges",
        "arguments": [
            {
                "name": "transcript",
                "description": "Full transcript text",
                "required": True
            }
        ],
        "template": """
From this meeting transcript, identify and describe the customer's initial problems or challenges 
that led them to seek a solution:

TRANSCRIPT:
{transcript}

Extract and structure the following:

• Problem / Challenge Information:
  [Describe the specific problem/challenge the customer faced]
  
• Business Context:
  [When did this problem begin? What triggered the need for a solution?]
  
• Impact on Business:
  [How was this problem affecting operations, revenue, efficiency, or other metrics?]
  
• Urgency/Priority:
  [How critical was solving this problem?]

INSTRUCTIONS:
- Focus on pain points explicitly mentioned
- Distinguish between stated problems and implied challenges
- Include quotes when they effectively illustrate the problem
- Note if multiple problems or a complex challenge is described

OUTPUT FORMAT: Structured narrative with bullet points
"""
    },
    
    "solution": {
        "name": "solution_section",
        "description": "Detail the solution that was implemented",
        "template": """
Based on this transcript, describe the solution that was implemented or proposed:

TRANSCRIPT:
{transcript}

Extract and structure:

• Product/Service Used:
  [Mention the specific product/service]
  
• Implementation Process:
  [Describe how the solution was implemented or planned to be implemented]
  
• Technical Details:
  [Any technical specifications, integrations, or configurations mentioned]
  
• Key Features Utilized:
  [Which features or capabilities were most relevant]

INSTRUCTIONS:
- Be specific about products, versions, or service tiers mentioned
- Describe the implementation approach and methodology
- Note any customizations or special configurations
- Include technical details that demonstrate sophistication

OUTPUT FORMAT: Structured narrative with technical detail
"""
    },
    
    "engagement_details": {
        "name": "engagement_details_section",
        "description": "Outline engagement timeline and milestones",
        "template": """
Extract engagement and implementation details with timeline:

TRANSCRIPT:
{transcript}

Structure the following:

• Start Date: [Project start date]
• Key Milestones: [List important milestones with dates if available]
• Completion Date: [Completion date or expected completion]
• Post-Implementation Review: [Any reviews or assessments mentioned]
• Engagement Team: [Groups involved - CSM/CSE/Pre-Sales/R&D/Partners]
• Engagement Overview: [Describe team involvement beyond PS consultants]

INSTRUCTIONS:
- Extract all date references and timeline markers
- List milestones in chronological order
- Identify all team members and their roles
- Note phase-based approaches or iterative development

OUTPUT FORMAT: Timeline with structured sections
"""
    },
    
    "results_achievements": {
        "name": "results_achievements_section",
        "description": "Extract quantifiable results and achievements",
        "template": """
Identify key achievements and quantifiable improvements:

TRANSCRIPT:
{transcript}

Extract:

• Key Achievements:
  [List main benefits/results achieved with metrics if available]
  
• Quantifiable Improvements:
  [List measurable improvements - percentages, time savings, cost reductions]
  
• Testimonial/Quote:
  [Include direct quotes that highlight positive experience]
  
• Success Metrics:
  [KPIs or metrics used to measure success]

INSTRUCTIONS:
- Prioritize hard numbers and quantifiable metrics
- Look for before/after comparisons
- Extract meaningful customer quotes
- Note both immediate and downstream benefits

OUTPUT FORMAT: Metrics-focused with supporting narrative
"""
    },
    
    "adoption_usage": {
        "name": "adoption_usage_section",
        "description": "Detail solution adoption and usage patterns",
        "template": """
Extract adoption and usage information:

TRANSCRIPT:
{transcript}

Structure:

• User Adoption Rate:
  [Detail the rate of adoption among customer's staff]
  
• Usage Metrics:
  [Specific usage statistics post-implementation]
  
• User Feedback:
  [How users responded to the solution]
  
• Training & Onboarding:
  [Any training programs or onboarding processes mentioned]

INSTRUCTIONS:
- Look for user counts, frequency of use, engagement metrics
- Note adoption timeline (immediate vs. gradual)
- Include user satisfaction indicators
- Describe rollout approach

OUTPUT FORMAT: Usage-focused with adoption trajectory
"""
    },
    
    "financial_impact": {
        "name": "financial_impact_section",
        "description": "Extract financial benefits and ROI",
        "template": """
Identify financial benefits and business value:

TRANSCRIPT:
{transcript}

Extract:

• Cost Savings:
  [Detail any cost savings achieved with amounts if available]
  
• Revenue Increase:
  [Any revenue increases attributed to the solution]
  
• ROI:
  [Return on investment calculations or estimates]
  
• Efficiency Gains:
  [Cost avoidance or efficiency improvements with financial impact]

INSTRUCTIONS:
- Prioritize concrete financial figures
- Look for cost-benefit analyses
- Note both direct and indirect financial impacts
- Include payback period if mentioned

OUTPUT FORMAT: Financial metrics with business context
"""
    },
    
    "long_term_impact": {
        "name": "long_term_impact_section",
        "description": "Describe strategic benefits and future plans",
        "template": """
Extract long-term strategic impact:

TRANSCRIPT:
{transcript}

Structure:

• Strategic Benefits:
  [Long-term benefits beyond immediate ROI]
  
• Future Plans:
  [Future projects or expansions discussed]
  
• Competitive Advantage:
  [How solution improves competitive position]
  
• Organizational Change:
  [Cultural or operational transformations enabled]

INSTRUCTIONS:
- Focus on strategic, not just tactical benefits
- Look for planned expansions or future phases
- Note capability building and organizational learning
- Identify transformational outcomes

OUTPUT FORMAT: Strategic narrative with forward-looking view
"""
    },
    
    "visuals": {
        "name": "visuals_section",
        "description": "Identify opportunities for visual elements",
        "template": """
Identify data and information suitable for visual representation:

TRANSCRIPT:
{transcript}

Suggest visual elements:

• Implementation Timeline Graphic:
  [Describe timeline that could be visualized]
  
• Before and After Comparisons:
  [Data suitable for comparison charts]
  
• Metrics Dashboard:
  [Key metrics that could be visualized]
  
• Process Diagrams:
  [Workflows or architectures to diagram]
  
• Customer Logo Placement:
  [Note if company name/logo should be featured]

INSTRUCTIONS:
- Identify quantitative data suitable for charts/graphs
- Suggest timeline visualizations if dates are available
- Note opportunities for process flow diagrams
- Recommend infographic elements

OUTPUT FORMAT: Descriptions of visual elements to create
"""
    },
    
    "additional_commentary": {
        "name": "additional_commentary_section",
        "description": "Extract relevant details not fitting other sections",
        "template": """
Identify important details not covered in standard sections:

TRANSCRIPT:
{transcript}

Extract:

• Unique Circumstances:
  [Special conditions or unique aspects of engagement]
  
• Lessons Learned:
  [Key insights or takeaways from the project]
  
• Partnership Dynamics:
  [Collaborative aspects worth highlighting]
  
• Industry Context:
  [Relevant industry trends or challenges]
  
• Innovation/Differentiation:
  [Innovative approaches or unique implementations]

INSTRUCTIONS:
- Include context that enriches the overall story
- Note creative problem-solving or innovative approaches
- Highlight partnership quality and collaboration
- Add industry-specific insights

OUTPUT FORMAT: Narrative commentary with supporting details
"""
    },
    
    "executive_summary": {
        "name": "executive_summary_section",
        "description": "Create high-level overview synthesizing all sections",
        "arguments": [
            {
                "name": "all_sections",
                "description": "Content from all previous sections",
                "required": True
            }
        ],
        "template": """
Create a compelling executive summary based on all completed sections:

SECTION CONTENT:
{all_sections}

Synthesize into executive summary with:

• Opening Statement:
  [Compelling one-sentence overview]
  
• Customer & Challenge:
  [Who the customer is and what problem they faced]
  
• Solution Deployed:
  [What was implemented]
  
• Key Results:
  [3-5 most impressive outcomes with metrics]
  
• Strategic Value:
  [Long-term business impact]
  
• Conclusion:
  [Forward-looking statement]

INSTRUCTIONS:
- Keep concise (300-400 words maximum)
- Lead with most impressive results
- Make it scannable with clear structure
- Focus on business value, not technical details
- Write for C-level audience

OUTPUT FORMAT: Polished executive summary
"""
    }
}
```

**B. Workflow Orchestration Prompts**

```python
WORKFLOW_PROMPTS = {
    "analyze_transcript": {
        "name": "analyze_transcript",
        "description": "Initial transcript analysis to extract structure and entities",
        "template": """
Analyze this meeting transcript and extract structured information:

TRANSCRIPT:
{transcript}

Extract:

1. NAMED ENTITIES:
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
   - Meeting type (kickoff, review, planning, etc.)
   - Number of speakers
   - Discussion flow and phases

4. DATA AVAILABILITY:
   - Which sections will have strong supporting data
   - Which sections may lack information
   - Confidence assessment for each section

OUTPUT: Structured JSON with extracted information
"""
    },
    
    "validate_consistency": {
        "name": "validate_consistency",
        "description": "Validate consistency across generated sections",
        "template": """
Review generated sections for consistency and quality:

SECTIONS:
{sections}

Check for:

1. FACTUAL CONSISTENCY:
   - Are facts consistent across sections?
   - Are there contradictions?
   - Are dates and numbers consistent?

2. COMPLETENESS:
   - Are all required fields present?
   - Are there gaps in the narrative?
   - Is context sufficient?

3. QUALITY:
   - Professional tone throughout?
   - Clear and compelling narrative?
   - Appropriate level of detail?

4. IMPROVEMENTS:
   - Suggest specific enhancements
   - Flag sections needing revision

OUTPUT: Validation report with improvement suggestions
"""
    }
}
```

### 4. Sampling (Required)

**Definition**: Server requests LLM completions for dynamic content generation.

**Implementation Requirements:**
- Use MCP's sampling capability to request completions
- Implement multiple sampling strategies (temperature, max_tokens)
- Handle streaming responses where appropriate
- Cache and reuse results when possible

**Sampling Use Cases in This Project:**

1. **Section Generation** - Each of 11 sections uses sampling with specialized system prompts
2. **Analysis** - Initial transcript analysis uses sampling for entity extraction
3. **Validation** - Cross-section validation uses sampling for consistency checking
4. **Executive Summary** - Final synthesis uses sampling with context from all sections
5. **Improvements** - Iterative improvement uses sampling to enhance low-confidence sections

**Implementation Pattern:**
```python
async def sample_llm(
    prompt: str,
    system_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 1500,
    model: str = "claude-sonnet-4-20250514"
) -> dict:
    """
    Request LLM completion via MCP sampling.
    
    Args:
        prompt: User prompt/template filled with data
        system_prompt: System instructions for the agent role
        temperature: Sampling temperature (0.0-1.0)
        max_tokens: Maximum tokens in response
        model: Model identifier
        
    Returns:
        dict with 'content' and 'metadata'
    """
    
    logger.debug("Requesting LLM sampling", extra={
        "prompt_length": len(prompt),
        "system_prompt_length": len(system_prompt),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "model": model
    })
    
    try:
        # Use MCP sampling request
        response = await mcp_server.sample(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            model=model
        )
        
        logger.info("LLM sampling completed", extra={
            "response_length": len(response.get("content", "")),
            "model": model
        })
        
        return {
            "content": response.get("content", ""),
            "metadata": {
                "model": model,
                "tokens_used": response.get("usage", {}),
                "finish_reason": response.get("finish_reason")
            }
        }
        
    except Exception as e:
        logger.error(f"LLM sampling failed: {str(e)}")
        raise
```

**System Prompts for Specialized Agents:**
```python
SYSTEM_PROMPTS = {
    "analyzer": """
You are an expert transcript analyst specializing in extracting structured information 
from business meeting transcripts. You excel at identifying entities (people, companies, 
products), key topics, and conversation structure. Be precise, thorough, and output 
structured data in JSON format.
""",
    
    "customer_information_agent": """
You are a data extraction specialist focused on customer information. Extract and structure 
company details, contacts, and organizational information from transcripts. Be precise 
with facts, clearly mark inferences, and maintain professional formatting.
""",
    
    "background_agent": """
You are a business analyst expert at identifying core business challenges and problems. 
Focus on understanding the 'why' behind customer needs. Extract pain points, business 
impact, and triggering events. Provide context and depth.
""",
    
    "solution_agent": """
You are a solutions architect documenting technical implementations. Focus on specific 
products/services used, implementation processes, and technical details. Be concrete, 
specific, and technically accurate.
""",
    
    "engagement_agent": """
You are a project manager documenting engagement timelines and team dynamics. Extract 
dates, milestones, team members, and project phases. Organize information chronologically 
and highlight collaboration.
""",
    
    "results_agent": """
You are a metrics and outcomes specialist. Extract quantifiable results, KPIs, improvements, 
and customer testimonials. Prioritize hard numbers, measurable impact, and concrete evidence 
of success.
""",
    
    "adoption_agent": """
You are a change management specialist analyzing solution adoption. Focus on user engagement, 
adoption rates, training programs, and usage patterns. Provide insights into how well the 
solution was embraced.
""",
    
    "financial_agent": """
You are a financial analyst extracting business value and ROI. Focus on cost savings, 
revenue impact, efficiency gains, and return on investment. Provide clear financial metrics 
and business justification.
""",
    
    "strategic_agent": """
You are a strategy consultant analyzing long-term impact. Focus on strategic benefits, 
competitive advantages, organizational transformation, and future opportunities. Think 
beyond immediate ROI to lasting value.
""",
    
    "visuals_agent": """
You are a data visualization specialist. Identify quantitative data, timelines, processes, 
and comparisons that would benefit from visual representation. Suggest specific chart types 
and visualization approaches.
""",
    
    "commentary_agent": """
You are a business storyteller capturing unique aspects and insights. Look for innovative 
approaches, lessons learned, partnership dynamics, and contextual details that enrich the 
overall narrative.
""",
    
    "executive_summary_agent": """
You are a senior executive communications expert. Synthesize complex information into 
compelling, concise overviews highlighting strategic value. Write for C-level audiences 
with focus on business outcomes and ROI. Be persuasive and results-oriented.
""",
    
    "validator": """
You are a quality assurance specialist reviewing technical documentation. Check for 
factual consistency, completeness, professional tone, and narrative flow. Identify 
contradictions, gaps, and opportunities for improvement. Be thorough and constructive.
""",
    
    "orchestrator": """
You are a senior technical writer orchestrating document assembly. Ensure consistency 
across sections, maintain professional quality, and create cohesive narratives. Make 
strategic decisions about content organization and emphasis.
"""
}
```

### 5. Elicitation (Required)

**Definition**: Interactive data gathering from users through structured prompts.

**Implementation Requirements:**
- Request user input when critical information is missing
- Support multi-step workflows requiring user decisions
- Provide clear context for why input is needed
- Track elicitation state and progress

**Elicitation Use Cases:**

1. **Missing Customer Information** - Request company details not in transcript
2. **Missing Metrics** - Request specific performance metrics for results section
3. **Date Clarification** - Request exact dates when only approximate timeframes mentioned
4. **Ambiguity Resolution** - Request clarification when transcript is unclear
5. **Additional Context** - Request industry context or background not in transcript

**Implementation Pattern:**
```python
async def elicit_missing_information(
    section_name: str,
    missing_fields: list,
    context: dict
) -> dict:
    """
    Use MCP Elicitation to request user input for missing information.
    
    Args:
        section_name: Name of section needing information
        missing_fields: List of missing field identifiers
        context: Additional context to help user understand request
        
    Returns:
        dict: User-provided information
    """
    
    logger.info(f"Eliciting information for {section_name}", extra={
        "missing_fields": missing_fields,
        "context": context
    })
    
    # Build field descriptions
    field_prompts = []
    for field in missing_fields:
        field_info = FIELD_DEFINITIONS.get(field, {})
        field_prompts.append({
            "name": field,
            "description": field_info.get("description", ""),
            "type": field_info.get("type", "string"),
            "required": field in REQUIRED_FIELDS.get(section_name, []),
            "example": field_info.get("example", ""),
            "default": ""
        })
    
    # Create elicitation request
    elicitation_request = {
        "type": "input_required",
        "section": section_name,
        "message": f"""
The {section_name} section is missing some important information that will improve 
the quality and completeness of the Customer Success Snapshot.

Context: {context.get('message', 'Additional information needed')}

Please provide the following information:
""",
        "fields": field_prompts,
        "allow_skip": not any(
            field in REQUIRED_FIELDS.get(section_name, []) 
            for field in missing_fields
        )
    }
    
    # Request user input through MCP elicitation
    try:
        user_input = await mcp_server.elicit_input(elicitation_request)
        
        logger.info(f"Elicitation completed for {section_name}", extra={
            "fields_provided": len(user_input),
            "skipped": user_input.get("_skipped", False)
        })
        
        return user_input
        
    except Exception as e:
        logger.warning(f"Elicitation failed for {section_name}: {str(e)}")
        return {}
```

**Field Definitions for Elicitation:**
```python
FIELD_DEFINITIONS = {
    "company_name": {
        "description": "Full legal name of the customer company",
        "type": "string",
        "example": "Acme Corporation",
        "validation": r"^[A-Za-z0-9\s\.,&'-]{2,100}$"
    },
    "industry": {
        "description": "Primary industry or sector",
        "type": "string",
        "example": "Financial Services, Healthcare, Manufacturing",
        "validation": r"^[A-Za-z\s,]{2,50}$"
    },
    "location": {
        "description": "Primary location (City, State/Province, Country)",
        "type": "string",
        "example": "San Francisco, California, USA",
        "validation": None
    },
    "start_date": {
        "description": "Project start date",
        "type": "date",
        "example": "2024-07-14",
        "validation": r"^\d{4}-\d{2}-\d{2}$"
    },
    "cost_savings": {
        "description": "Cost savings amount with currency",
        "type": "string",
        "example": "$250,000 annually",
        "validation": None
    },
    "roi_percentage": {
        "description": "Return on investment percentage",
        "type": "number",
        "example": "150% over 18 months",
        "validation": None
    }
    # Add more field definitions as needed
}

REQUIRED_FIELDS = {
    "Customer Information": ["company_name", "industry"],
    "Engagement Details": ["start_date"],
    "Results and Achievements": [],  # No absolutely required fields
    "Financial Impact": [],  # Optional but valuable
    # ... define for all sections
}
```

### 6. Logging (Required)

**Definition**: Structured logging of all operations for debugging and monitoring.

**Implementation Requirements:**
- Log to stderr for MCP compatibility
- Use structured logging with JSON format option
- Include appropriate log levels (DEBUG, INFO, WARNING, ERROR)
- Add context with extra fields
- Log all tool invocations, resource access, and sampling requests

**Logging Configuration:**
```python
# src/mcp_snapshot_server/utils/logging_config.py

import logging
import sys
import json
from datetime import datetime
from typing import Any

class StructuredFormatter(logging.Formatter):
    """
    Custom formatter for structured logging output.
    Outputs JSON for easy parsing by log aggregation systems.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)

def setup_logging(
    level: str = "INFO",
    structured: bool = True
) -> None:
    """
    Configure logging for MCP server.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        structured: Whether to use structured JSON logging
    """
    
    # Create logger
    logger = logging.getLogger("mcp_snapshot_server")
    logger.setLevel(getattr(logging, level.upper()))
    
    # Create stderr handler (MCP requirement)
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(getattr(logging, level.upper()))
    
    # Set formatter
    if structured:
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Prevent propagation to root logger
    logger.propagate = False

class ContextLogger:
    """
    Logger wrapper that adds contextual information to all log messages.
    """
    
    def __init__(self, name: str, context: dict = None):
        self.logger = logging.getLogger(name)
        self.context = context or {}
    
    def _add_context(self, extra: dict) -> dict:
        """Merge context with extra fields."""
        merged = self.context.copy()
        merged.update(extra or {})
        return merged
    
    def debug(self, msg: str, extra: dict = None):
        extra_fields = self._add_context(extra)
        self.logger.debug(msg, extra={"extra_fields": extra_fields})
    
    def info(self, msg: str, extra: dict = None):
        extra_fields = self._add_context(extra)
        self.logger.info(msg, extra={"extra_fields": extra_fields})
    
    def warning(self, msg: str, extra: dict = None):
        extra_fields = self._add_context(extra)
        self.logger.warning(msg, extra={"extra_fields": extra_fields})
    
    def error(self, msg: str, extra: dict = None):
        extra_fields = self._add_context(extra)
        self.logger.error(msg, extra={"extra_fields": extra_fields})
```

**Logging Points in Workflow:**
```python
# Server startup
logger.info("MCP Snapshot Server starting", extra={
    "version": __version__,
    "python_version": sys.version
})

# Tool invocation
logger.info("Tool invoked", extra={
    "tool": "generate_customer_snapshot",
    "args": {"vtt_file_path": vtt_file_path, "output_format": output_format},
    "workflow_id": workflow_id
})

# Workflow stages
logger.info("Starting workflow stage", extra={
    "stage": "transcript_parsing",
    "workflow_id": workflow_id
})

# Section generation
logger.info("Generating section", extra={
    "section": section_name,
    "workflow_id": workflow_id,
    "agent": "section_generator"
})

# Sampling requests
logger.debug("Requesting LLM sampling", extra={
    "prompt_length": len(prompt),
    "system_prompt_length": len(system_prompt),
    "temperature": temperature,
    "max_tokens": max_tokens,
    "model": model
})

# Sampling completion
logger.info("LLM sampling completed", extra={
    "response_length": len(response),
    "tokens_used": response.get("usage", {})
})

# Validation warnings
logger.warning("Section validation issues", extra={
    "section": section_name,
    "confidence": confidence_score,
    "missing_fields": missing_fields,
    "issues": validation_issues
})

# Elicitation
logger.info("Requesting user input", extra={
    "section": section_name,
    "missing_fields": missing_fields,
    "required": required_fields
})

# Errors
logger.error("Section generation failed", extra={
    "section": section_name,
    "error": str(e),
    "attempt": retry_attempt
})

# Final assembly
logger.info("Document assembly complete", extra={
    "total_sections": len(sections),
    "output_format": output_format,
    "document_length": len(final_doc),
    "workflow_id": workflow_id
})
```

---

## Customer Success Snapshot Generator Tool

### Document Structure

The Customer Success Snapshot consists of **11 sections**:

1. **Customer Information** - Company details, industry, location, primary contact
2. **Background** - Initial problems/challenges before solution
3. **Solution** - Products/services implemented and how
4. **Engagement / Implementation Details and Timeline** - Project timeline, milestones, team
5. **Results and Achievements** - Quantifiable improvements, testimonials, metrics
6. **Adoption and Usage** - User adoption rates, usage statistics
7. **Financial Impact** - Cost savings, revenue increases, ROI
8. **Long-Term Impact** - Strategic benefits, future plans
9. **Visuals** - Descriptions/placeholders for charts, graphs, timelines
10. **Additional Commentary** - Relevant details not fitting other sections
11. **Executive Summary** - High-level overview synthesizing all sections

### Input Format

**VTT (WebVTT) Transcript Format:**
```vtt
WEBVTT

00:00:00.000 --> 00:00:05.000
<v John Smith>Hi everyone, thanks for taking the time to meet with us today.

00:00:05.000 --> 00:00:10.000
<v John Smith>I'm John Smith, CTO at Acme Corporation.

00:00:10.000 --> 00:00:15.000
<v Sarah Jameson>Thanks for having us, John. I'm Sarah Jameson, Solutions Architect.
```

**Key VTT Requirements:**
- Valid WebVTT format with timestamps
- Speaker labels using `<v Speaker Name>` tags
- UTF-8 encoding
- Proper cue timing and formatting

### Tool Workflow

**High-Level Flow:**
```
VTT File Input
    ↓
1. Parse & Clean Transcript
    ↓
2. Analyze with Analysis Agent
    ↓
3. Generate 11 Sections in Parallel/Sequential
    ↓
4. Validate Consistency
    ↓
5. Elicit Missing Info (if needed)
    ↓
6. Assemble Final Document
    ↓
7. Format Output (Markdown/HTML)
    ↓
Customer Success Snapshot Document
```

**Detailed Implementation:**
```python
async def generate_customer_snapshot(
    vtt_file_path: str,
    output_format: str = "markdown",
    include_sections: list = None,
    additional_context: str = "",
    enable_elicitation: bool = True
) -> dict:
    """
    Generate Customer Success Snapshot from VTT transcript.
    
    Multi-stage workflow with specialized agents for each section.
    
    Args:
        vtt_file_path: Path to VTT transcript file
        output_format: "markdown" or "html"
        include_sections: Optional list of specific sections to generate
        additional_context: Additional context about customer/project
        enable_elicitation: Whether to request user input for missing info
        
    Returns:
        dict: {
            "document": str,  # Final formatted document
            "metadata": dict,  # Generation metadata
            "sections": dict,  # Individual section results
            "validation": dict  # Validation results
        }
    """
    
    workflow_id = str(uuid.uuid4())
    
    logger.info("Starting Customer Snapshot generation", extra={
        "vtt_file": vtt_file_path,
        "output_format": output_format,
        "workflow_id": workflow_id
    })
    
    try:
        # Phase 1: Parse VTT Transcript
        logger.info("Phase 1: Parsing transcript", extra={"workflow_id": workflow_id})
        transcript_data = await parse_vtt_transcript(vtt_file_path)
        
        # Phase 2: Analyze Transcript
        logger.info("Phase 2: Analyzing transcript", extra={"workflow_id": workflow_id})
        analysis = await analyze_transcript(
            transcript_text=transcript_data["text"],
            additional_context=additional_context
        )
        
        # Phase 3: Generate Sections
        logger.info("Phase 3: Generating sections", extra={"workflow_id": workflow_id})
        sections = await generate_all_sections(
            transcript_text=transcript_data["text"],
            analysis=analysis,
            include_sections=include_sections,
            workflow_id=workflow_id
        )
        
        # Phase 4: Validate Consistency
        logger.info("Phase 4: Validating consistency", extra={"workflow_id": workflow_id})
        validation = await validate_sections(sections)
        
        # Phase 5: Elicit Missing Information
        if enable_elicitation and validation.get("missing_critical_info"):
            logger.info("Phase 5: Eliciting missing information", extra={
                "workflow_id": workflow_id
            })
            elicited_data = await elicit_missing_data(sections, validation)
            
            # Regenerate sections with elicited data
            sections = await update_sections_with_elicited_data(
                sections, elicited_data
            )
        
        # Phase 6: Generate Executive Summary
        logger.info("Phase 6: Generating executive summary", extra={
            "workflow_id": workflow_id
        })
        sections["Executive Summary"] = await generate_executive_summary(
            all_sections=sections
        )
        
        # Phase 7: Assemble and Format Document
        logger.info("Phase 7: Assembling final document", extra={
            "workflow_id": workflow_id
        })
        final_document = await assemble_and_format(
            sections=sections,
            output_format=output_format,
            metadata={
                "workflow_id": workflow_id,
                "generation_timestamp": datetime.utcnow().isoformat(),
                "source_file": vtt_file_path
            }
        )
        
        logger.info("Customer Snapshot generation complete", extra={
            "workflow_id": workflow_id,
            "document_length": len(final_document),
            "sections_generated": len(sections)
        })
        
        return {
            "document": final_document,
            "metadata": {
                "workflow_id": workflow_id,
                "timestamp": datetime.utcnow().isoformat(),
                "source_file": vtt_file_path,
                "output_format": output_format,
                "sections_count": len(sections)
            },
            "sections": sections,
            "validation": validation
        }
        
    except Exception as e:
        logger.error(f"Snapshot generation failed: {str(e)}", extra={
            "workflow_id": workflow_id,
            "error_type": type(e).__name__
        })
        raise
```

---

## Multi-Agent Architecture

### Agent Hierarchy

```
┌─────────────────────────────────────┐
│   Orchestration Agent (Main)       │
│   Coordinates entire workflow       │
└─────────────────┬───────────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
┌───────▼──────┐   ┌───────▼──────────┐
│  Analysis    │   │  Section Gen     │
│  Agent       │   │  Coordinator     │
└──────────────┘   └───────┬──────────┘
                           │
                ┌──────────┴──────────┐
                │                     │
        ┌───────▼──────┐      ┌──────▼────────┐
        │  Individual  │      │  Validation   │
        │  Section     │      │  Agent        │
        │  Agents (11) │      └───────────────┘
        └──────────────┘
```

### Agent Responsibilities

**1. Orchestration Agent**
- Coordinates the entire workflow
- Manages phase transitions
- Makes strategic decisions about section generation order
- Handles error recovery
- Ensures document quality and consistency

**2. Analysis Agent**
- Parses and analyzes transcript
- Extracts named entities (people, companies, products, locations)
- Identifies key topics and themes
- Structures conversation flow
- Assesses data availability for each section

**3. Section Generator Agents (11 specialized)**
- Each has deep expertise in one section type
- Uses section-specific prompts and system instructions
- Generates content based on transcript and analysis
- Provides confidence scores
- Identifies missing information

**4. Validation Agent**
- Cross-checks facts across sections
- Ensures consistency (dates, names, metrics)
- Validates completeness
- Checks professional tone and quality
- Suggests improvements

**5. Assembly Agent**
- Combines sections into cohesive document
- Applies formatting (Markdown/HTML)
- Adds metadata and structure
- Ensures proper section ordering
- Creates table of contents

### Agent Implementation Patterns

**Base Agent Class:**
```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.
    """
    
    def __init__(self, name: str, system_prompt: str, logger: ContextLogger):
        self.name = name
        self.system_prompt = system_prompt
        self.logger = logger
    
    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input and return results.
        
        Args:
            input_data: Input data for processing
            
        Returns:
            Processing results with metadata
        """
        pass
    
    async def sample_llm(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 1500
    ) -> Dict[str, Any]:
        """
        Request LLM sampling with agent's system prompt.
        """
        return await sample_llm(
            prompt=prompt,
            system_prompt=self.system_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )
```

**Analysis Agent:**
```python
class AnalysisAgent(BaseAgent):
    """
    Agent responsible for initial transcript analysis.
    """
    
    def __init__(self, logger: ContextLogger):
        super().__init__(
            name="AnalysisAgent",
            system_prompt=SYSTEM_PROMPTS["analyzer"],
            logger=logger
        )
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze transcript and extract structured information.
        """
        transcript = input_data["transcript"]
        additional_context = input_data.get("additional_context", "")
        
        self.logger.info("Starting transcript analysis", extra={
            "transcript_length": len(transcript)
        })
        
        # Build analysis prompt
        prompt = WORKFLOW_PROMPTS["analyze_transcript"]["template"].format(
            transcript=transcript
        )
        
        if additional_context:
            prompt += f"\n\nADDITIONAL CONTEXT:\n{additional_context}"
        
        # Sample LLM
        response = await self.sample_llm(
            prompt=prompt,
            temperature=0.2,  # Lower for factual extraction
            max_tokens=2000
        )
        
        # Parse response
        try:
            analysis_data = json.loads(response["content"])
        except json.JSONDecodeError:
            # Fallback to structured parsing
            analysis_data = self._parse_analysis_text(response["content"])
        
        self.logger.info("Transcript analysis complete", extra={
            "entities_found": len(analysis_data.get("entities", [])),
            "topics_found": len(analysis_data.get("topics", []))
        })
        
        return {
            "entities": analysis_data.get("entities", []),
            "topics": analysis_data.get("topics", []),
            "structure": analysis_data.get("structure", {}),
            "data_availability": analysis_data.get("data_availability", {}),
            "metadata": response.get("metadata", {})
        }
    
    def _parse_analysis_text(self, text: str) -> Dict[str, Any]:
        """
        Fallback parser for non-JSON analysis responses.
        """
        # Implementation of text parsing logic
        pass
```

**Section Generator Agent:**
```python
class SectionGeneratorAgent(BaseAgent):
    """
    Agent responsible for generating individual sections.
    """
    
    def __init__(
        self,
        section_name: str,
        system_prompt: str,
        prompt_template: str,
        logger: ContextLogger
    ):
        super().__init__(
            name=f"SectionGenerator_{section_name}",
            system_prompt=system_prompt,
            logger=logger
        )
        self.section_name = section_name
        self.prompt_template = prompt_template
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate section content.
        """
        transcript = input_data["transcript"]
        analysis = input_data.get("analysis", {})
        context = input_data.get("context", {})
        
        self.logger.info(f"Generating section: {self.section_name}", extra={
            "entities_available": len(analysis.get("entities", [])),
            "topics_available": len(analysis.get("topics", []))
        })
        
        # Build section prompt
        prompt = self.prompt_template.format(
            transcript=transcript,
            entities=self._format_entities(analysis.get("entities", [])),
            topics=self._format_topics(analysis.get("topics", [])),
            **context
        )
        
        # Sample LLM
        response = await self.sample_llm(
            prompt=prompt,
            temperature=0.3,
            max_tokens=1500
        )
        
        content = response["content"]
        
        # Calculate confidence
        confidence = self._calculate_confidence(content, analysis)
        
        # Identify missing fields
        missing_fields = self._identify_missing_fields(content)
        
        self.logger.info(f"Section generated: {self.section_name}", extra={
            "confidence": confidence,
            "missing_fields": missing_fields,
            "content_length": len(content)
        })
        
        return {
            "section_name": self.section_name,
            "content": content,
            "confidence": confidence,
            "missing_fields": missing_fields,
            "metadata": response.get("metadata", {})
        }
    
    def _calculate_confidence(
        self,
        content: str,
        analysis: Dict[str, Any]
    ) -> float:
        """
        Calculate confidence score for generated section.
        """
        score = 1.0
        
        # Reduce score for common placeholder phrases
        placeholders = [
            "not mentioned",
            "not specified",
            "not available",
            "[inferred]",
            "unclear from transcript"
        ]
        for placeholder in placeholders:
            if placeholder.lower() in content.lower():
                score -= 0.1
        
        # Check for expected content patterns
        if self.section_name == "Customer Information":
            if "company name:" not in content.lower():
                score -= 0.2
            if "industry:" not in content.lower():
                score -= 0.1
        
        # Minimum score
        return max(0.0, score)
    
    def _identify_missing_fields(self, content: str) -> list:
        """
        Identify fields that are missing or incomplete.
        """
        missing = []
        
        # Section-specific field checks
        if self.section_name == "Customer Information":
            if "company name: not mentioned" in content.lower():
                missing.append("company_name")
            if "industry: not mentioned" in content.lower():
                missing.append("industry")
            if "location: not mentioned" in content.lower():
                missing.append("location")
        
        # Add more field checks per section
        
        return missing
    
    def _format_entities(self, entities: list) -> str:
        """Format entities for prompt."""
        if not entities:
            return "No entities extracted"
        return ", ".join(entities)
    
    def _format_topics(self, topics: list) -> str:
        """Format topics for prompt."""
        if not topics:
            return "No specific topics identified"
        return ", ".join(topics)
```

**Validation Agent:**
```python
class ValidationAgent(BaseAgent):
    """
    Agent responsible for validating section consistency and quality.
    """
    
    def __init__(self, logger: ContextLogger):
        super().__init__(
            name="ValidationAgent",
            system_prompt=SYSTEM_PROMPTS["validator"],
            logger=logger
        )
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate sections for consistency and quality.
        """
        sections = input_data["sections"]
        
        self.logger.info("Starting section validation", extra={
            "sections_count": len(sections)
        })
        
        # Build validation prompt
        sections_text = "\n\n".join([
            f"## {name}\n{section['content']}"
            for name, section in sections.items()
        ])
        
        prompt = WORKFLOW_PROMPTS["validate_consistency"]["template"].format(
            sections=sections_text
        )
        
        # Sample LLM
        response = await self.sample_llm(
            prompt=prompt,
            temperature=0.2,
            max_tokens=2000
        )
        
        # Parse validation results
        validation_results = self._parse_validation_response(response["content"])
        
        self.logger.info("Validation complete", extra={
            "issues_found": len(validation_results.get("issues", [])),
            "requires_improvements": validation_results.get("requires_improvements", False)
        })
        
        return validation_results
    
    def _parse_validation_response(self, response: str) -> Dict[str, Any]:
        """
        Parse validation response into structured results.
        """
        # Implementation of parsing logic
        return {
            "factual_consistency": True,
            "completeness": True,
            "quality": True,
            "issues": [],
            "improvements": [],
            "requires_improvements": False,
            "missing_critical_info": []
        }
```

**Orchestration Agent:**
```python
class OrchestrationAgent(BaseAgent):
    """
    Main orchestration agent coordinating the entire workflow.
    """
    
    def __init__(self, logger: ContextLogger):
        super().__init__(
            name="OrchestrationAgent",
            system_prompt=SYSTEM_PROMPTS["orchestrator"],
            logger=logger
        )
        
        # Initialize sub-agents
        self.analysis_agent = AnalysisAgent(logger)
        self.validation_agent = ValidationAgent(logger)
        
        # Initialize section generators
        self.section_agents = {}
        for section_name, prompt_config in SECTION_PROMPTS.items():
            self.section_agents[section_name] = SectionGeneratorAgent(
                section_name=section_name,
                system_prompt=SYSTEM_PROMPTS.get(
                    f"{section_name}_agent",
                    SYSTEM_PROMPTS["section_generator"]
                ),
                prompt_template=prompt_config["template"],
                logger=logger
            )
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orchestrate the complete snapshot generation workflow.
        """
        workflow_id = input_data.get("workflow_id", str(uuid.uuid4()))
        
        self.logger.info("Orchestration starting", extra={
            "workflow_id": workflow_id
        })
        
        # Phase 1: Analysis
        analysis = await self.analysis_agent.process({
            "transcript": input_data["transcript"],
            "additional_context": input_data.get("additional_context", "")
        })
        
        # Phase 2: Section Generation
        sections = {}
        include_sections = input_data.get("include_sections")
        
        for section_name, agent in self.section_agents.items():
            if include_sections and section_name not in include_sections:
                continue
            
            section_result = await agent.process({
                "transcript": input_data["transcript"],
                "analysis": analysis,
                "context": {}
            })
            
            sections[section_name] = section_result
        
        # Phase 3: Validation
        validation = await self.validation_agent.process({
            "sections": sections
        })
        
        # Phase 4: Handle improvements if needed
        if validation.get("requires_improvements"):
            sections = await self._apply_improvements(sections, validation)
        
        # Phase 5: Generate Executive Summary
        if "Executive Summary" not in sections or sections["Executive Summary"]["confidence"] < 0.7:
            exec_summary = await self._generate_executive_summary(sections)
            sections["Executive Summary"] = exec_summary
        
        self.logger.info("Orchestration complete", extra={
            "workflow_id": workflow_id,
            "sections_generated": len(sections)
        })
        
        return {
            "sections": sections,
            "analysis": analysis,
            "validation": validation,
            "workflow_id": workflow_id
        }
    
    async def _apply_improvements(
        self,
        sections: Dict[str, Any],
        validation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply improvements based on validation feedback.
        """
        # Implementation of improvement logic
        return sections
    
    async def _generate_executive_summary(
        self,
        sections: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate executive summary from all sections.
        """
        # Concatenate all section content
        all_sections_text = "\n\n".join([
            f"## {name}\n{section['content']}"
            for name, section in sections.items()
            if name != "Executive Summary"
        ])
        
        prompt = SECTION_PROMPTS["executive_summary"]["template"].format(
            all_sections=all_sections_text
        )
        
        response = await self.sample_llm(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPTS["executive_summary_agent"],
            temperature=0.3,
            max_tokens=1000
        )
        
        return {
            "section_name": "Executive Summary",
            "content": response["content"],
            "confidence": 0.9,
            "missing_fields": [],
            "metadata": response.get("metadata", {})
        }
```

---

## Configuration Management

### Configuration Structure

```python
# src/mcp_snapshot_server/utils/config.py

from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional
import os

class MCPServerSettings(BaseSettings):
    """
    Main MCP Server configuration.
    """
    
    # Server settings
    server_name: str = Field(
        default="snapshot-server",
        description="MCP server name"
    )
    
    version: str = Field(
        default="0.1.0",
        description="Server version"
    )
    
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    
    structured_logging: bool = Field(
        default=True,
        description="Enable structured JSON logging"
    )
    
    class Config:
        env_prefix = "MCP_"
        env_file = ".env"


class LLMSettings(BaseSettings):
    """
    LLM/Claude configuration.
    """
    
    # API settings
    anthropic_api_key: str = Field(
        ...,  # Required
        description="Anthropic API key"
    )
    
    model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Claude model to use"
    )
    
    temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Sampling temperature"
    )
    
    max_tokens_per_section: int = Field(
        default=1500,
        ge=100,
        le=4000,
        description="Maximum tokens per section"
    )
    
    max_tokens_analysis: int = Field(
        default=2000,
        ge=500,
        le=4000,
        description="Maximum tokens for analysis"
    )
    
    timeout: int = Field(
        default=60,
        ge=10,
        le=300,
        description="API timeout in seconds"
    )
    
    max_retries: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum retry attempts"
    )
    
    class Config:
        env_prefix = "LLM_"
        env_file = ".env"


class WorkflowSettings(BaseSettings):
    """
    Snapshot generation workflow configuration.
    """
    
    # Generation settings
    parallel_section_generation: bool = Field(
        default=False,
        description="Generate sections in parallel"
    )
    
    min_confidence_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum acceptable confidence score"
    )
    
    enable_elicitation: bool = Field(
        default=True,
        description="Enable user input elicitation for missing info"
    )
    
    enable_validation: bool = Field(
        default=True,
        description="Enable cross-section validation"
    )
    
    enable_improvements: bool = Field(
        default=True,
        description="Enable automatic improvements for low-confidence sections"
    )
    
    max_improvement_iterations: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Maximum iterations for section improvements"
    )
    
    # Output settings
    default_output_format: str = Field(
        default="markdown",
        description="Default output format"
    )
    
    include_metadata: bool = Field(
        default=True,
        description="Include generation metadata in output"
    )
    
    include_confidence_scores: bool = Field(
        default=False,
        description="Include confidence scores in output"
    )
    
    class Config:
        env_prefix = "WORKFLOW_"
        env_file = ".env"


class NLPSettings(BaseSettings):
    """
    NLP processing configuration.
    """
    
    spacy_model: str = Field(
        default="en_core_web_sm",
        description="spaCy model for entity extraction"
    )
    
    extract_entities: bool = Field(
        default=True,
        description="Extract named entities from transcript"
    )
    
    extract_topics: bool = Field(
        default=True,
        description="Extract key topics from transcript"
    )
    
    min_entity_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for entity extraction"
    )
    
    class Config:
        env_prefix = "NLP_"
        env_file = ".env"


class Settings:
    """
    Aggregated settings for the entire application.
    """
    
    def __init__(self):
        self.server = MCPServerSettings()
        self.llm = LLMSettings()
        self.workflow = WorkflowSettings()
        self.nlp = NLPSettings()
    
    def validate(self) -> bool:
        """
        Validate all settings.
        """
        # Check required API keys
        if not self.llm.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required")
        
        # Validate model name
        valid_models = [
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514",
            "claude-3-5-sonnet-20241022"
        ]
        if self.llm.model not in valid_models:
            raise ValueError(f"Invalid model. Must be one of: {valid_models}")
        
        return True


# Global settings instance
settings = Settings()
```

### Environment Variables (.env.example)

```bash
# MCP Server Configuration
MCP_SERVER_NAME=snapshot-server
MCP_VERSION=0.1.0
MCP_LOG_LEVEL=INFO
MCP_STRUCTURED_LOGGING=true

# LLM Configuration (Required)
LLM_ANTHROPIC_API_KEY=your_anthropic_api_key_here
LLM_MODEL=claude-sonnet-4-20250514
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS_PER_SECTION=1500
LLM_MAX_TOKENS_ANALYSIS=2000
LLM_TIMEOUT=60
LLM_MAX_RETRIES=3

# Workflow Configuration
WORKFLOW_PARALLEL_SECTION_GENERATION=false
WORKFLOW_MIN_CONFIDENCE_THRESHOLD=0.5
WORKFLOW_ENABLE_ELICITATION=true
WORKFLOW_ENABLE_VALIDATION=true
WORKFLOW_ENABLE_IMPROVEMENTS=true
WORKFLOW_MAX_IMPROVEMENT_ITERATIONS=2
WORKFLOW_DEFAULT_OUTPUT_FORMAT=markdown
WORKFLOW_INCLUDE_METADATA=true
WORKFLOW_INCLUDE_CONFIDENCE_SCORES=false

# NLP Configuration
NLP_SPACY_MODEL=en_core_web_sm
NLP_EXTRACT_ENTITIES=true
NLP_EXTRACT_TOPICS=true
NLP_MIN_ENTITY_CONFIDENCE=0.5

# Optional: Databricks Configuration (for future expansion)
# DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
# DATABRICKS_TOKEN=your_databricks_token
```

---

## Code Quality Standards

### pyproject.toml Configuration

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "mcp-snapshot-server"
version = "0.1.0"
description = "Python MCP Server with Customer Success Snapshot Generator"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "your.email@example.com"},
]
keywords = ["mcp", "model-context-protocol", "ai", "nlp", "customer-success"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

dependencies = [
    "mcp>=0.9.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "python-dotenv>=1.0.0",
    "anthropic>=0.34.0",
    "webvtt-py>=0.4.6",
    "pycaption>=2.2.1",
    "spacy>=3.7.2",
    "nltk>=3.8.1",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.13.0",
    "mypy>=1.10.0",
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-mock>=3.11.0",
]

[project.urls]
Homepage = "https://github.com/yourusername/mcp-snapshot-server"
Repository = "https://github.com/yourusername/mcp-snapshot-server"
Issues = "https://github.com/yourusername/mcp-snapshot-server/issues"

[project.scripts]
mcp-snapshot-server = "mcp_snapshot_server.server:main"

[tool.setuptools.packages.find]
where = ["src"]

# Ruff Configuration
[tool.ruff]
line-length = 88
target-version = "py310"
exclude = [
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "dist",
]

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # Pyflakes
    "I",      # isort
    "N",      # pep8-naming
    "UP",     # pyupgrade
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "SIM",    # flake8-simplify
    "TCH",    # flake8-type-checking
]

ignore = [
    "E501",   # line too long (handled by formatter)
    "B008",   # do not perform function calls in argument defaults
]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]  # unused imports
"tests/*" = ["S101"]      # use of assert

[tool.ruff.lint.isort]
known-first-party = ["mcp_snapshot_server"]

# MyPy Configuration
[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_any_generics = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
strict_optional = true

[[tool.mypy.overrides]]
module = "webvtt.*"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "pycaption.*"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "nltk.*"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "spacy.*"
ignore_missing_imports = true

# Pytest Configuration
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--verbose",
    "--strict-markers",
    "-ra",
]
asyncio_mode = "auto"
markers = [
    "slow: marks tests as slow",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
]
```

### Development Commands

```bash
# Format code (run before every commit)
uv run ruff format .

# Check for linting issues
uv run ruff check .

# Auto-fix linting issues
uv run ruff check --fix .

# Type checking
uv run mypy src/mcp_snapshot_server/

# Run tests
uv run pytest

# Run specific test types
uv run pytest -m unit
uv run pytest -m integration

# Run with coverage
uv run pytest --cov=mcp_snapshot_server --cov-report=html
```

---

## Error Handling & Logging

### Error Handling Strategy

**Error Categories:**

1. **Input Validation Errors** - Invalid VTT format, missing files
2. **API Errors** - Anthropic API failures, rate limits
3. **Processing Errors** - Parsing failures, unexpected formats
4. **Resource Errors** - File system access, resource not found
5. **Configuration Errors** - Missing API keys, invalid settings

**Error Handling Pattern:**
```python
from enum import Enum
from typing import Optional

class ErrorCode(Enum):
    """Standard error codes for MCP server."""
    
    INVALID_INPUT = "INVALID_INPUT"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    PARSE_ERROR = "PARSE_ERROR"
    API_ERROR = "API_ERROR"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"

class MCPServerError(Exception):
    """Base exception for MCP server errors."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        details: Optional[dict] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> dict:
        """Convert error to dictionary for JSON serialization."""
        return {
            "error": self.error_code.value,
            "message": self.message,
            "details": self.details
        }

# Usage examples
def parse_vtt_file(file_path: str) -> dict:
    """Parse VTT file with comprehensive error handling."""
    
    if not os.path.exists(file_path):
        raise MCPServerError(
            message=f"VTT file not found: {file_path}",
            error_code=ErrorCode.FILE_NOT_FOUND,
            details={"file_path": file_path}
        )
    
    try:
        # Parse VTT
        vtt_data = webvtt.read(file_path)
        return {"success": True, "data": vtt_data}
        
    except webvtt.errors.MalformedFileError as e:
        raise MCPServerError(
            message=f"Invalid VTT format: {str(e)}",
            error_code=ErrorCode.PARSE_ERROR,
            details={
                "file_path": file_path,
                "parse_error": str(e)
            }
        )
    
    except Exception as e:
        raise MCPServerError(
            message=f"Failed to parse VTT file: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
            details={
                "file_path": file_path,
                "error_type": type(e).__name__
            }
        )

# Retry decorator for transient errors
from functools import wraps
import asyncio

def retry_on_error(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0
):
    """Decorator for retrying on transient errors."""
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                
                except (MCPServerError, Exception) as e:
                    last_exception = e
                    
                    if attempt < max_retries - 1:
                        wait_time = delay * (backoff ** attempt)
                        logger.warning(
                            f"Attempt {attempt + 1} failed, retrying in {wait_time}s",
                            extra={
                                "function": func.__name__,
                                "error": str(e),
                                "attempt": attempt + 1
                            }
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(
                            f"All {max_retries} attempts failed",
                            extra={
                                "function": func.__name__,
                                "error": str(e)
                            }
                        )
            
            raise last_exception
        
        return wrapper
    return decorator
```

---

## Testing Strategy

### Test Structure

```
tests/
├── __init__.py
├── conftest.py                 # Pytest fixtures
├── test_tools/
│   ├── test_snapshot_generator.py
│   └── test_transcript_utils.py
├── test_resources/
│   ├── test_transcript_resource.py
│   └── test_analysis_resource.py
├── test_prompts/
│   └── test_section_prompts.py
├── test_agents/
│   ├── test_analysis_agent.py
│   ├── test_section_generator.py
│   ├── test_validation_agent.py
│   └── test_orchestrator.py
├── test_utils/
│   ├── test_config.py
│   └── test_validators.py
└── fixtures/
    ├── sample_input.vtt
    ├── test_jama.vtt
    └── expected_outputs/
        ├── customer_information.md
        ├── background.md
        └── complete_snapshot.md
```

### Pytest Fixtures (conftest.py)

```python
# tests/conftest.py

import pytest
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock

@pytest.fixture
def fixtures_dir():
    """Path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"

@pytest.fixture
def sample_vtt_path(fixtures_dir):
    """Path to sample VTT file."""
    return fixtures_dir / "sample_input.vtt"

@pytest.fixture
def sample_transcript_text():
    """Sample transcript text for testing."""
    return """
    John Smith: Hi everyone, thanks for taking the time to meet with us today.
    I'm John Smith, CTO at Acme Corporation.
    Sarah Jameson: Thanks for having us, John. I'm Sarah Jameson, Solutions Architect.
    We're excited to learn more about your infrastructure challenges.
    """

@pytest.fixture
def sample_analysis():
    """Sample analysis results."""
    return {
        "entities": [
            "John Smith",
            "Sarah Jameson",
            "Acme Corporation"
        ],
        "topics": [
            "infrastructure challenges",
            "cloud migration",
            "cost optimization"
        ],
        "structure": {
            "meeting_type": "initial_consultation",
            "speaker_count": 2
        },
        "data_availability": {
            "Customer Information": 0.9,
            "Background": 0.7,
            "Solution": 0.5
        }
    }

@pytest.fixture
def mock_llm_response():
    """Mock LLM sampling response."""
    return {
        "content": "Generated content from LLM",
        "metadata": {
            "model": "claude-sonnet-4-20250514",
            "tokens_used": {"input": 500, "output": 200},
            "finish_reason": "stop"
        }
    }

@pytest.fixture
def mock_mcp_server():
    """Mock MCP server for testing."""
    server = Mock()
    server.sample = AsyncMock()
    server.list_resources = AsyncMock()
    server.read_resource = AsyncMock()
    server.elicit_input = AsyncMock()
    return server
```

### Unit Test Examples

```python
# tests/test_agents/test_analysis_agent.py

import pytest
from mcp_snapshot_server.agents.analyzer import AnalysisAgent
from mcp_snapshot_server.utils.logging_config import ContextLogger

@pytest.mark.asyncio
async def test_analysis_agent_extracts_entities(
    sample_transcript_text,
    mock_llm_response,
    mocker
):
    """Test that analysis agent extracts entities correctly."""
    
    # Mock LLM sampling
    mock_llm_response["content"] = """
    {
        "entities": ["John Smith", "Acme Corporation"],
        "topics": ["infrastructure", "cloud migration"],
        "structure": {"meeting_type": "consultation"}
    }
    """
    mocker.patch(
        "mcp_snapshot_server.agents.analyzer.sample_llm",
        return_value=mock_llm_response
    )
    
    # Create agent
    logger = ContextLogger("test")
    agent = AnalysisAgent(logger)
    
    # Process
    result = await agent.process({
        "transcript": sample_transcript_text,
        "additional_context": ""
    })
    
    # Assert
    assert "entities" in result
    assert "John Smith" in result["entities"]
    assert "Acme Corporation" in result["entities"]
    assert "topics" in result
    assert len(result["topics"]) > 0


@pytest.mark.asyncio
async def test_analysis_agent_handles_malformed_response(
    sample_transcript_text,
    mock_llm_response,
    mocker
):
    """Test that analysis agent handles non-JSON responses gracefully."""
    
    # Mock LLM with non-JSON response
    mock_llm_response["content"] = "This is not JSON"
    mocker.patch(
        "mcp_snapshot_server.agents.analyzer.sample_llm",
        return_value=mock_llm_response
    )
    
    # Create agent
    logger = ContextLogger("test")
    agent = AnalysisAgent(logger)
    
    # Process (should not raise)
    result = await agent.process({
        "transcript": sample_transcript_text,
        "additional_context": ""
    })
    
    # Assert fallback parsing worked
    assert "entities" in result
    assert isinstance(result["entities"], list)


# tests/test_agents/test_section_generator.py

import pytest
from mcp_snapshot_server.agents.section_generator import SectionGeneratorAgent
from mcp_snapshot_server.prompts.section_prompts import SECTION_PROMPTS
from mcp_snapshot_server.utils.logging_config import ContextLogger

@pytest.mark.asyncio
async def test_section_generator_creates_content(
    sample_transcript_text,
    sample_analysis,
    mock_llm_response,
    mocker
):
    """Test section generator creates valid content."""
    
    # Mock LLM sampling
    mock_llm_response["content"] = """
    • Company Name: Acme Corporation
    • Industry: Technology
    • Location: San Francisco, CA
    • Primary Contact: John Smith
    • Position: CTO
    """
    mocker.patch(
        "mcp_snapshot_server.agents.section_generator.sample_llm",
        return_value=mock_llm_response
    )
    
    # Create agent
    logger = ContextLogger("test")
    agent = SectionGeneratorAgent(
        section_name="Customer Information",
        system_prompt="Test system prompt",
        prompt_template=SECTION_PROMPTS["customer_information"]["template"],
        logger=logger
    )
    
    # Process
    result = await agent.process({
        "transcript": sample_transcript_text,
        "analysis": sample_analysis,
        "context": {}
    })
    
    # Assert
    assert result["section_name"] == "Customer Information"
    assert len(result["content"]) > 0
    assert result["confidence"] > 0
    assert "Acme Corporation" in result["content"]


@pytest.mark.asyncio
async def test_section_generator_calculates_confidence(
    sample_transcript_text,
    sample_analysis,
    mock_llm_response,
    mocker
):
    """Test confidence score calculation."""
    
    # Mock LLM with low-quality response
    mock_llm_response["content"] = """
    • Company Name: Not mentioned
    • Industry: Not mentioned
    • Location: Not specified
    """
    mocker.patch(
        "mcp_snapshot_server.agents.section_generator.sample_llm",
        return_value=mock_llm_response
    )
    
    # Create agent
    logger = ContextLogger("test")
    agent = SectionGeneratorAgent(
        section_name="Customer Information",
        system_prompt="Test system prompt",
        prompt_template=SECTION_PROMPTS["customer_information"]["template"],
        logger=logger
    )
    
    # Process
    result = await agent.process({
        "transcript": sample_transcript_text,
        "analysis": sample_analysis,
        "context": {}
    })
    
    # Assert low confidence due to placeholders
    assert result["confidence"] < 0.7
    assert len(result["missing_fields"]) > 0


# tests/test_tools/test_snapshot_generator.py

import pytest
from mcp_snapshot_server.tools.snapshot_generator import generate_customer_snapshot

@pytest.mark.asyncio
async def test_generate_snapshot_complete_workflow(
    sample_vtt_path,
    mocker
):
    """Test complete snapshot generation workflow."""
    
    # Mock all LLM calls
    mock_responses = {
        "analysis": {"entities": [], "topics": []},
        "sections": {"content": "Test content", "confidence": 0.8}
    }
    
    mocker.patch(
        "mcp_snapshot_server.agents.analyzer.sample_llm",
        return_value={"content": '{"entities": [], "topics": []}'}
    )
    mocker.patch(
        "mcp_snapshot_server.agents.section_generator.sample_llm",
        return_value={"content": "Test section content"}
    )
    
    # Generate snapshot
    result = await generate_customer_snapshot(
        vtt_file_path=str(sample_vtt_path),
        output_format="markdown"
    )
    
    # Assert
    assert "document" in result
    assert "metadata" in result
    assert "sections" in result
    assert len(result["document"]) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_snapshot_with_real_api(sample_vtt_path):
    """Integration test with real Anthropic API (requires API key)."""
    
    # Skip if no API key
    if not os.getenv("LLM_ANTHROPIC_API_KEY"):
        pytest.skip("API key not available")
    
    # Generate snapshot
    result = await generate_customer_snapshot(
        vtt_file_path=str(sample_vtt_path),
        output_format="markdown"
    )
    
    # Assert
    assert len(result["sections"]) >= 10
    assert "Executive Summary" in result["sections"]
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run only unit tests
uv run pytest -m unit

# Run only integration tests (requires API key)
uv run pytest -m integration

# Run with coverage
uv run pytest --cov=mcp_snapshot_server --cov-report=html

# Run specific test file
uv run pytest tests/test_agents/test_analysis_agent.py

# Run with verbose output
uv run pytest -v

# Run and show print statements
uv run pytest -s
```

---

## Documentation Requirements

### README.md Structure

```markdown
# MCP Snapshot Server

Python MCP Server with Customer Success Snapshot Generator using modern Python tooling.

## Overview

This MCP server implements all 6 Model Context Protocol primitives:
- ✅ **Tools** - Customer Success Snapshot Generator and supporting tools
- ✅ **Resources** - Access to transcripts, analyses, and generated sections
- ✅ **Prompts** - 11 section-specific prompt templates + workflow prompts
- ✅ **Sampling** - Multi-agent orchestration using LLM sampling
- ✅ **Elicitation** - Interactive data gathering for missing information
- ✅ **Logging** - Comprehensive structured logging

## Features

- **Customer Success Snapshot Generator**: Process VTT transcripts into professional 11-section customer success documents
- **Multi-Agent Architecture**: Specialized agents for analysis, section generation, validation, and orchestration
- **Modern Python Tooling**: Built with uv (fast package manager) and ruff (fast linter/formatter)
- **Production-Ready**: Comprehensive error handling, logging, and testing

## Quick Start

### Prerequisites
- Python 3.10+ (3.11 or 3.12 recommended)
- [uv](https://docs.astral.sh/uv/) package manager
- Anthropic API key

### Installation

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone https://github.com/yourusername/mcp-snapshot-server.git
cd mcp-snapshot-server

# Install dependencies
uv sync

# Download NLP models
uv run python -m spacy download en_core_web_sm

# Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Usage

#### Running the MCP Server

```bash
uv run mcp-snapshot-server
```

#### Using with Claude Desktop

Add to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "snapshot-server": {
      "command": "uv",
      "args": [
        "run",
        "mcp-snapshot-server"
      ],
      "cwd": "/path/to/mcp-snapshot-server",
      "env": {
        "LLM_ANTHROPIC_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

## Tools

### `generate_customer_snapshot`

Generate comprehensive Customer Success Snapshot from VTT transcript.

**Input:**
```json
{
  "vtt_file_path": "/path/to/transcript.vtt",
  "output_format": "markdown",
  "enable_elicitation": true
}
```

**Output:** 11-section customer success document

**Workflow:**
1. Parse VTT transcript
2. Analyze with Analysis Agent (extract entities, topics)
3. Generate 11 sections using specialized agents
4. Validate cross-section consistency
5. Elicit missing critical information
6. Assemble and format final document

## Resources

Access intermediate and final results:

- `resource://snapshot-server/transcript/{id}` - Parsed transcript
- `resource://snapshot-server/analysis/{id}` - Analysis results
- `resource://snapshot-server/section/{id}/{section}` - Individual section
- `resource://snapshot-server/snapshot/{id}` - Complete snapshot

## Prompts

11 section-specific prompts + 2 workflow prompts:
- Customer Information
- Background
- Solution
- Engagement Details
- Results and Achievements
- Adoption and Usage
- Financial Impact
- Long-Term Impact
- Visuals
- Additional Commentary
- Executive Summary

Plus: `analyze_transcript`, `validate_consistency`

## Development

### Code Quality

```bash
# Format code
uv run ruff format .

# Lint
uv run ruff check --fix .

# Type check
uv run mypy src/mcp_snapshot_server/

# Run tests
uv run pytest
```

### Project Structure

```
mcp-snapshot-server/
├── src/mcp_snapshot_server/
│   ├── server.py           # Main MCP server
│   ├── tools/              # Tools implementation
│   ├── resources/          # Resources implementation
│   ├── prompts/            # Prompt templates
│   ├── agents/             # Multi-agent system
│   └── utils/              # Configuration, logging, etc.
├── tests/                  # Test suite
├── pyproject.toml          # Project configuration
└── README.md
```

## Configuration

See `.env.example` for all configuration options.

Key settings:
- `LLM_ANTHROPIC_API_KEY` - Required
- `LLM_MODEL` - Claude model (default: claude-sonnet-4-20250514)
- `LLM_TEMPERATURE` - Sampling temperature (default: 0.3)
- `WORKFLOW_ENABLE_ELICITATION` - Interactive data gathering (default: true)

## License

MIT License

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Run `uv run ruff format . && uv run ruff check --fix .`
4. Submit a pull request
```

### SETUP.md

Create a detailed setup guide covering:
- Prerequisites and installation
- Environment configuration
- Development workflow
- Common issues and troubleshooting
- IDE setup (VS Code configuration)

### API Documentation

Document all public APIs:
- Tool schemas
- Resource URIs
- Prompt templates
- Agent interfaces
- Configuration options

---

## Security Best Practices

### API Key Management

```python
# ❌ NEVER do this
api_key = "sk-ant-1234567890"

# ✅ Always use environment variables
import os
api_key = os.getenv("ANTHROPIC_API_KEY")

# ✅ Or use pydantic-settings
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str
    
    class Config:
        env_file = ".env"
```

### Input Validation

```python
from pathlib import Path
import os

def validate_vtt_file_path(file_path: str) -> Path:
    """
    Validate VTT file path to prevent security issues.
    """
    # Convert to Path object
    path = Path(file_path).resolve()
    
    # Check if file exists
    if not path.exists():
        raise ValueError(f"File does not exist: {file_path}")
    
    # Check if it's a file (not directory)
    if not path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")
    
    # Check file extension
    if path.suffix.lower() != ".vtt":
        raise ValueError(f"File must have .vtt extension: {file_path}")
    
    # Prevent directory traversal
    allowed_dirs = [Path("/path/to/data"), Path.cwd()]
    if not any(path.is_relative_to(allowed_dir) for allowed_dir in allowed_dirs):
        raise ValueError(f"File path not in allowed directories: {file_path}")
    
    return path
```

### .gitignore

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
dist/
*.egg-info/
.venv/
venv/
env/

# Environment
.env
.env.local
*.key
secrets/

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# MyPy
.mypy_cache/

# Ruff
.ruff_cache/

# uv
uv.lock

# Data
*.vtt
*.transcript
transcripts/
snapshots/
```

---

## Success Criteria

Your MCP server implementation is complete when:

### Core Functionality
- ✅ MCP server starts without errors
- ✅ All 6 MCP primitives are implemented:
  - Tools (snapshot generator + utilities)
  - Resources (transcripts, analyses, sections)
  - Prompts (11 section templates + workflow prompts)
  - Sampling (multi-agent LLM requests)
  - Elicitation (interactive data gathering)
  - Logging (structured, comprehensive)

### Customer Success Snapshot Generator
- ✅ Parses VTT files correctly
- ✅ Extracts entities and topics
- ✅ Generates all 11 sections
- ✅ Validates cross-section consistency
- ✅ Elicits missing information when needed
- ✅ Outputs properly formatted Markdown/HTML

### Code Quality
- ✅ All code passes `ruff format --check`
- ✅ All code passes `ruff check`
- ✅ Type hints on all functions
- ✅ Google-style docstrings throughout
- ✅ Comprehensive error handling

### Testing
- ✅ Unit tests for all agents
- ✅ Integration tests for tools
- ✅ Test coverage > 80%
- ✅ All tests passing

### Documentation
- ✅ Complete README.md with examples
- ✅ Detailed SETUP.md
- ✅ .env.example with all variables
- ✅ Inline code documentation
- ✅ API reference for public interfaces

### Configuration
- ✅ pyproject.toml properly configured
- ✅ All dependencies in pyproject.toml
- ✅ Environment variables documented
- ✅ Settings validation working

---

## Implementation Phases

### Phase 1: Foundation (Week 1)
**Goal:** Set up project structure and core infrastructure

**Tasks:**
1. Initialize project with uv
2. Set up pyproject.toml with dependencies
3. Create project structure (src/, tests/, etc.)
4. Configure ruff and mypy
5. Set up logging infrastructure
6. Create configuration management (Settings classes)
7. Write .env.example
8. Create basic README.md and SETUP.md

**Deliverables:**
- Project scaffolding complete
- Configuration system working
- Logging infrastructure operational
- Documentation started

### Phase 2: VTT Processing & Analysis (Week 2)
**Goal:** Implement transcript parsing and analysis

**Tasks:**
1. Implement VTT parser with error handling
2. Create transcript cleaning utilities
3. Implement Analysis Agent
4. Add entity extraction (spaCy)
5. Add topic extraction (NLTK)
6. Write unit tests for parsing and analysis
7. Create test fixtures (sample VTT files)

**Deliverables:**
- VTT files successfully parsed
- Entities and topics extracted
- Analysis Agent operational
- Tests passing

### Phase 3: Section Generation (Week 3)
**Goal:** Implement section generation system

**Tasks:**
1. Define all 11 section prompts
2. Create Section Generator Agent base class
3. Implement specialized system prompts
4. Add confidence scoring
5. Implement missing field detection
6. Create section generation tests
7. Test with sample transcripts

**Deliverables:**
- All 11 sections generating content
- Confidence scoring working
- Missing field detection operational
- Tests passing

### Phase 4: Multi-Agent Orchestration (Week 4)
**Goal:** Implement complete workflow orchestration

**Tasks:**
1. Create Orchestration Agent
2. Implement workflow phases
3. Add Validation Agent
4. Implement cross-section validation
5. Add improvement iteration logic
6. Create Executive Summary generation
7. Write integration tests

**Deliverables:**
- Complete workflow operational
- Validation working
- Executive summaries generated
- Integration tests passing

### Phase 5: MCP Integration (Week 5)
**Goal:** Integrate all components into MCP server

**Tasks:**
1. Implement MCP Tools (generate_customer_snapshot)
2. Implement MCP Resources (URIs for all artifacts)
3. Register MCP Prompts
4. Implement Sampling calls
5. Implement Elicitation system
6. Wire up logging throughout
7. Test with Claude Desktop

**Deliverables:**
- MCP server operational
- All primitives implemented
- Works with Claude Desktop
- End-to-end testing complete

### Phase 6: Polish & Documentation (Week 6)
**Goal:** Production readiness

**Tasks:**
1. Complete README.md
2. Complete SETUP.md
3. Add inline documentation
4. Improve error messages
5. Add usage examples
6. Create contribution guidelines
7. Final code quality pass
8. Performance optimization

**Deliverables:**
- Complete documentation
- Production-ready code
- Performance optimized
- Ready for deployment

---

## Additional Notes

### Databricks Integration (Future Enhancement)

When extending this for Databricks:

**Additional Tools:**
- `run_spark_query` - Execute Spark SQL queries
- `submit_databricks_job` - Submit and monitor jobs
- `access_delta_table` - Read from Delta tables
- `create_notebook` - Generate Databricks notebooks

**Additional Resources:**
- `resource://snapshot-server/databricks/table/{catalog}/{schema}/{table}`
- `resource://snapshot-server/databricks/job/{job_id}`
- `resource://snapshot-server/databricks/notebook/{path}`

**Additional Prompts:**
- PySpark code generation prompts
- Data pipeline design prompts
- ETL workflow prompts

### Performance Optimization

**Parallel Section Generation:**
```python
import asyncio

async def generate_all_sections_parallel(transcript, analysis):
    """Generate sections in parallel for speed."""
    
    tasks = [
        generate_section(name, transcript, analysis)
        for name in SECTION_NAMES
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle any errors
    sections = {}
    for name, result in zip(SECTION_NAMES, results):
        if isinstance(result, Exception):
            logger.error(f"Section {name} failed: {str(result)}")
            sections[name] = create_placeholder_section(name)
        else:
            sections[name] = result
    
    return sections
```

**Caching:**
```python
from functools import lru_cache
import hashlib

@lru_cache(maxsize=100)
def get_cached_analysis(transcript_hash: str):
    """Cache analysis results."""
    pass

def hash_transcript(transcript: str) -> str:
    """Generate hash for caching."""
    return hashlib.sha256(transcript.encode()).hexdigest()
```

---

## Quick Reference

### Essential Commands
```bash
# Setup
uv init mcp-snapshot-server
uv sync
uv run python -m spacy download en_core_web_sm

# Development
uv run ruff format .
uv run ruff check --fix .
uv run mypy src/
uv run pytest

# Run server
uv run mcp-snapshot-server
```

### Key Files
- `pyproject.toml` - All project configuration
- `.env` - Environment variables (never commit)
- `src/mcp_snapshot_server/server.py` - Main entry point
- `src/mcp_snapshot_server/agents/orchestrator.py` - Workflow orchestration
- `src/mcp_snapshot_server/prompts/section_prompts.py` - Section templates

### Important URLs
- MCP Documentation: https://modelcontextprotocol.io/docs
- uv Documentation: https://docs.astral.sh/uv/
- ruff Documentation: https://docs.astral.sh/ruff/
- Anthropic API: https://docs.anthropic.com/

---

## Conclusion

This specification provides everything needed to build a production-grade Python MCP Server with a sophisticated Customer Success Snapshot Generator. The project demonstrates:

- All 6 MCP primitives working together
- Modern Python development practices
- Multi-agent orchestration
- Production-ready code quality
- Comprehensive testing and documentation

Use Claude Code in Planning Mode with this specification to create a detailed project plan and begin implementation.

**Next Steps:**
1. Review this specification thoroughly
2. Ask clarifying questions if needed
3. Use Claude Code Planning Mode to create implementation plan
4. Begin Phase 1: Foundation

Good luck with your implementation! 🚀
