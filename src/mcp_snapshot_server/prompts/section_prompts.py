"""Section prompt templates for Customer Success Snapshot generation.

This module contains detailed prompt templates for generating each of the 11
sections of a Customer Success Snapshot document.
"""

from typing import Any

# Define all 11 section prompts with detailed templates
SECTION_PROMPTS: dict[str, dict[str, Any]] = {
    "customer_information": {
        "name": "customer_information_section",
        "description": "Extract customer information from transcript",
        "arguments": ["transcript", "entities"],
        "template": """Based on the following meeting transcript, extract detailed customer information:

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
""",
    },
    "background": {
        "name": "background_section",
        "description": "Identify customer's initial problems and challenges",
        "arguments": ["transcript"],
        "template": """From this meeting transcript, identify and describe the customer's initial problems or challenges that led them to seek a solution:

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
""",
    },
    "solution": {
        "name": "solution_section",
        "description": "Detail the solution that was implemented",
        "arguments": ["transcript"],
        "template": """Based on this transcript, describe the solution that was implemented or proposed:

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
""",
    },
    "engagement_details": {
        "name": "engagement_details_section",
        "description": "Outline engagement timeline and milestones",
        "arguments": ["transcript"],
        "template": """Extract engagement and implementation details with timeline:

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
""",
    },
    "results_achievements": {
        "name": "results_achievements_section",
        "description": "Extract quantifiable results and achievements",
        "arguments": ["transcript"],
        "template": """Identify key achievements and quantifiable improvements:

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
""",
    },
    "adoption_usage": {
        "name": "adoption_usage_section",
        "description": "Detail solution adoption and usage patterns",
        "arguments": ["transcript"],
        "template": """Extract adoption and usage information:

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
""",
    },
    "financial_impact": {
        "name": "financial_impact_section",
        "description": "Extract financial benefits and ROI",
        "arguments": ["transcript"],
        "template": """Identify financial benefits and business value:

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
""",
    },
    "long_term_impact": {
        "name": "long_term_impact_section",
        "description": "Describe strategic benefits and future plans",
        "arguments": ["transcript"],
        "template": """Extract long-term strategic impact:

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
""",
    },
    "visuals": {
        "name": "visuals_section",
        "description": "Identify opportunities for visual elements",
        "arguments": ["transcript"],
        "template": """Identify data and information suitable for visual representation:

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
""",
    },
    "additional_commentary": {
        "name": "additional_commentary_section",
        "description": "Extract relevant details not fitting other sections",
        "arguments": ["transcript"],
        "template": """Identify important details not covered in standard sections:

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
""",
    },
    "executive_summary": {
        "name": "executive_summary_section",
        "description": "Create high-level overview synthesizing all sections",
        "arguments": ["all_sections"],
        "template": """Create a compelling executive summary based on all completed sections:

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
""",
    },
}

# Workflow prompts for analysis and validation
WORKFLOW_PROMPTS = {
    "analyze_transcript": {
        "name": "analyze_transcript",
        "description": "Initial transcript analysis to extract structure and entities",
        "template": """Analyze this meeting transcript and extract structured information:

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
""",
    },
    "validate_consistency": {
        "name": "validate_consistency",
        "description": "Validate consistency across generated sections",
        "template": """Review generated sections for consistency and quality:

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
""",
    },
}
