# MCP Server File Access Issue - Bug Report & Fix Request

## Executive Summary

The `mcp-snapshot-server` MCP Server is unable to access VTT transcript files from the file system, regardless of the path provided. This prevents the `generate_customer_snapshot` tool from functioning correctly. The issue appears to be related to file system isolation between the MCP server's execution context and the Claude.ai environment's file system.

---

## Environment Details

### MCP Server Information
- **Server Name**: mcp-snapshot-server
- **Tool Name**: `generate_customer_snapshot`
- **Expected Functionality**: Parse VTT transcript files and generate Customer Success Snapshot documents

### Execution Environment
- **Platform**: Claude.ai with MCP server integration
- **File System Context**: Files accessible to Claude via computer use tools at various paths
- **Test File**: `sample_transcript.vtt` (8.5KB VTT format transcript)

---

## Issue Description

### Symptom
The `generate_customer_snapshot` tool consistently returns a file not found error, regardless of the path provided:

```
Failed to generate snapshot: Failed to parse VTT file: VTT file not found: <path>
```

### Attempted File Paths (All Failed)

1. **Original upload location**:
   ```
   /mnt/user-data/uploads/sample_transcript.vtt
   ```
   Error: `VTT file not found: /mnt/user-data/uploads/sample_transcript.vtt`

2. **Copied to home directory**:
   ```
   /home/claude/sample_transcript.vtt
   ```
   Error: `VTT file not found: /home/claude/sample_transcript.vtt`
   Note: File verified to exist via `ls -lh` command

3. **Relative path**:
   ```
   sample_transcript.vtt
   ```
   Error: `VTT file not found: sample_transcript.vtt`

4. **Temp directory**:
   ```
   /tmp/sample_transcript.vtt
   ```
   Error: `VTT file not found: /tmp/sample_transcript.vtt`
   Note: File verified to exist via `ls -lh` command

### File Verification

The file definitely exists and is readable:
```bash
$ ls -lh /tmp/sample_transcript.vtt
-r--r--r-- 1 root root 8.5K Nov 23 19:58 /tmp/sample_transcript.vtt

$ ls -lh /home/claude/sample_transcript.vtt
-r--r--r-- 1 root root 8.5K Nov 23 19:57 /home/claude/sample_transcript.vtt
```

---

## Root Cause Analysis

### Hypothesis 1: File System Isolation ⭐ (Most Likely)
The MCP server is likely running in a separate container, process, or sandbox with its own file system namespace that is isolated from the Claude.ai computer use environment's file system.

**Evidence**:
- All file paths fail, even `/tmp` which is typically shared
- Files verified to exist in Claude's context but invisible to MCP server
- Error message suggests file system access, not permission issues

### Hypothesis 2: Working Directory Mismatch
The MCP server may have a different working directory than expected, and relative paths are not resolving correctly.

**Evidence**:
- Relative path `sample_transcript.vtt` fails
- No indication of what the server's actual working directory is

### Hypothesis 3: Permission Issues
The MCP server process may lack read permissions for the file paths attempted.

**Evidence** (Against this hypothesis):
- Files have `r--r--r--` permissions (world-readable)
- Error is "file not found" not "permission denied"

---

## Technical Context

### Expected Tool Signature
```python
generate_customer_snapshot(
    vtt_file_path: str,
    output_format: str = "json" | "markdown"
) -> SnapshotDocument
```

### Current Implementation Issues
The tool's file access mechanism is unable to:
1. Access files in the standard Claude.ai file system paths
2. Resolve relative paths to files in any accessible location
3. Access shared temporary directories like `/tmp`

---

## Recommended Fixes

### Priority 1: File Content Passing (Recommended Approach)
**Problem**: MCP server cannot access the file system directly.
**Solution**: Modify the tool to accept file content directly instead of a file path.

#### Proposed New Signature:
```python
generate_customer_snapshot(
    vtt_content: str,           # VTT file content as string
    output_format: str = "json" | "markdown",
    filename: str = None        # Optional filename for context
) -> SnapshotDocument
```

#### Benefits:
- Eliminates file system access issues entirely
- More flexible - works with any file source (API, database, memory, etc.)
- Follows better MCP design patterns for cross-context tools
- No dependency on specific file system paths or mount points

#### Implementation Steps:
1. Update tool schema to accept `vtt_content` parameter instead of `vtt_file_path`
2. Remove file reading logic from the tool
3. Pass VTT content directly to the parser
4. Update tool documentation and examples

---

### Priority 2: Shared Volume Mount (Alternative Approach)
**Problem**: MCP server and Claude environment have isolated file systems.
**Solution**: Configure a shared volume that both contexts can access.

#### Implementation Steps:
1. Create a shared mount point (e.g., `/mnt/shared` or `/mcp-data`)
2. Configure MCP server to have read access to this mount point
3. Update documentation to specify files must be placed in this shared location
4. Add environment variable to configure the shared path

#### Example Configuration:
```yaml
# MCP Server Config
volumes:
  - /mcp-data:/mcp-data:ro  # Read-only access to shared data directory
environment:
  MCP_DATA_DIR: /mcp-data
```

#### Benefits:
- Maintains file-based interface
- Allows batch processing of multiple files
- Can handle large files more efficiently

#### Drawbacks:
- Requires infrastructure changes
- Less portable across different deployment environments
- Adds complexity to setup and configuration

---

### Priority 3: File Content Retrieval Service (Hybrid Approach)
**Problem**: Need to access files from Claude's context.
**Solution**: Implement a file content retrieval mechanism within the MCP server.

#### Implementation Approach:
```python
# MCP Server would call back to Claude to retrieve file content
generate_customer_snapshot(
    file_reference: str,        # URI or reference to file
    output_format: str = "json" | "markdown"
) -> SnapshotDocument
```

#### Process Flow:
1. Claude provides a file reference (URI, handle, or resource ID)
2. MCP server requests file content from Claude via callback
3. Claude reads file and returns content
4. MCP server processes content

#### Benefits:
- Works with Claude's existing file access permissions
- No need for shared file systems
- Maintains security boundaries

#### Drawbacks:
- More complex to implement
- Requires bidirectional communication
- May have performance implications

---

## Testing Recommendations

### Test Case 1: Basic VTT Parsing
```python
# Test with minimal valid VTT content
vtt_content = """WEBVTT

00:00:00.000 --> 00:00:05.000
Speaker 1: Test content
"""

result = generate_customer_snapshot(
    vtt_content=vtt_content,
    output_format="json"
)

assert result["participants"] is not None
```

### Test Case 2: Complex Transcript
```python
# Test with multi-speaker, multi-topic conversation
# Use the sample_transcript.vtt content provided below
```

### Test Case 3: Error Handling
```python
# Test with invalid VTT format
invalid_vtt = "This is not a valid VTT file"

try:
    result = generate_customer_snapshot(vtt_content=invalid_vtt)
    assert False, "Should have raised validation error"
except ValueError as e:
    assert "Invalid VTT format" in str(e)
```

---

## Sample VTT Content for Testing

The following is a complete, valid VTT transcript that can be used for testing the fixed implementation:

```vtt
WEBVTT

00:00:00.000 --> 00:00:10.000
John Smith (Customer): Hi everyone, thanks for taking the time to meet with us today. I'm John Smith, CTO at Acme Corporation.

00:00:10.000 --> 00:00:25.000
Sarah Jameson (Sales Engineer): Thanks for having us, John. I'm Sarah Jameson, and this is Charles Michaels, our Solutions Architect. We're excited to learn more about your infrastructure challenges.

00:00:25.000 --> 00:00:45.000
John Smith (Customer): Great. So we're currently running about 200 servers on-premise, mix of Windows and Linux environments. We're looking at cloud migration options primarily for cost optimization and disaster recovery.

00:00:45.000 --> 00:01:05.000
Charles Michaels (Solutions Architect): That's a substantial infrastructure. What's driving the urgency for migration? Are you experiencing specific pain points with your current setup?

00:01:05.000 --> 00:01:25.000
John Smith (Customer): We've had some downtime issues lately. Last month we had a 6-hour outage that cost us significantly. Our disaster recovery is basically non-existent right now, and we're projecting 50% growth next year.

00:01:25.000 --> 00:01:40.000
Sarah Jameson (Sales Engineer): I can definitely understand the concern. Six hours of downtime is substantial. What's your current RTO and RPO requirements, and how much are you looking to improve those?

00:01:40.000 --> 00:01:55.000
John Smith (Customer): Ideally, we'd like to get to 4-hour RTO and 1-hour RPO. Right now we're probably looking at 24+ hours to fully recover from a major incident.

00:01:55.000 --> 00:02:15.000
Charles Michaels (Solutions Architect): Those are very reasonable targets. In terms of your applications, are these primarily legacy applications, or do you have any cloud-native applications already?

00:02:15.000 --> 00:02:35.000
John Smith (Customer): It's mostly legacy stuff. We have some .NET applications that are probably 8-10 years old, and several Java applications. We do have one newer microservices application that we built last year.

00:02:35.000 --> 00:02:50.000
Sarah Jameson (Sales Engineer): Perfect. That gives us a good mix to work with. What's your timeline looking like for this migration? Is this something you want to complete this year?

00:02:50.000 --> 00:03:10.000
John Smith (Customer): We're hoping to have a decision by end of Q2, and ideally start the migration in Q3. The board is pushing for this after the outage, so we have executive support, which is good.

00:03:10.000 --> 00:03:25.000
Mary Davis (Finance): I'm Mary Davis, CFO. From a budget perspective, we're looking at this as a 3-year investment. What kind of cost savings should we expect compared to our current datacenter costs?

00:03:25.000 --> 00:03:45.000
Sarah Jameson (Sales Engineer): That's a great question, Mary. Typically we see 20-30% cost reduction in the first year, and even more as you optimize. But a lot depends on your current utilization and how we architect the cloud solution.

00:03:45.000 --> 00:04:05.000
Mary Davis (Finance): Our current datacenter costs are running about $2.8 million annually, including staffing. If we could save even 25%, that's significant money we could reinvest in other initiatives.

00:04:05.000 --> 00:04:20.000
Charles Michaels (Solutions Architect): Absolutely. And beyond cost savings, you'll gain agility. The ability to spin up new environments for development and testing becomes much easier and faster.

00:04:20.000 --> 00:04:35.000
John Smith (Customer): That's actually a big pain point for us right now. Our developers are constantly waiting for infrastructure. Sometimes it takes weeks to get a new dev environment provisioned.

00:04:35.000 --> 00:04:50.000
Sarah Jameson (Sales Engineer): With Infrastructure as Code, that becomes a matter of minutes instead of weeks. What are you currently using for monitoring and management of your infrastructure?

00:04:50.000 --> 00:05:05.000
John Smith (Customer): We're using SCOM for Windows monitoring and Nagios for Linux. It's... functional, but we don't have great visibility into application performance.

00:05:05.000 --> 00:05:25.000
Charles Michaels (Solutions Architect): That's very common. Cloud-native monitoring solutions give you much better application insights, with machine learning-based anomaly detection and predictive analytics.

00:05:25.000 --> 00:05:40.000
John Smith (Customer): That sounds interesting. One concern I have is vendor lock-in. We've heard horror stories about companies getting locked into one cloud provider and then facing huge costs to migrate later.

00:05:40.000 --> 00:05:55.000
Sarah Jameson (Sales Engineer): That's a very valid concern. We always recommend a multi-cloud strategy when possible, using containerization and cloud-agnostic services where it makes sense.

00:05:55.000 --> 00:06:10.000
John Smith (Customer): Speaking of containers, we've been looking at Kubernetes. Is that something you'd recommend for our legacy applications, or should we focus on lift-and-shift first?

00:06:10.000 --> 00:06:30.000
Charles Michaels (Solutions Architect): Great question. I'd recommend a phased approach. Start with lift-and-shift for the legacy apps to get immediate benefits, then modernize to containers over time. That microservices app you mentioned would be perfect for Kubernetes.

00:06:30.000 --> 00:06:45.000
John Smith (Customer): That makes sense. What about security? That's obviously a big concern for our board. How do we ensure we're not increasing our security risk by moving to the cloud?

00:06:45.000 --> 00:07:05.000
Sarah Jameson (Sales Engineer): Security is actually often improved in the cloud. You get access to enterprise-grade security tools that would be expensive to implement on-premise. Plus, the cloud providers have dedicated security teams that are much larger than most internal teams.

00:07:05.000 --> 00:07:20.000
Mary Davis (Finance): What about compliance? We're in the financial services sector, so we have pretty strict regulatory requirements.

00:07:20.000 --> 00:07:35.000
Charles Michaels (Solutions Architect): The major cloud providers all have extensive compliance certifications including SOC 2, PCI DSS, and others specific to financial services. We can help you design a compliant architecture from day one.

00:07:35.000 --> 00:07:50.000
John Smith (Customer): Excellent. So what would be the next steps if we wanted to move forward? We'd probably need some kind of assessment of our current environment.

00:07:50.000 --> 00:08:10.000
Sarah Jameson (Sales Engineer): Absolutely. We'd start with a comprehensive discovery and assessment. This typically takes 2-3 weeks and gives us a detailed migration plan with timelines, costs, and risk assessments.

00:08:10.000 --> 00:08:25.000
Mary Davis (Finance): What's the cost for that assessment? And would that cost be credited toward the implementation if we move forward?

00:08:25.000 --> 00:08:40.000
Sarah Jameson (Sales Engineer): The assessment is typically $25,000, but yes, we do credit that full amount toward the implementation project if you decide to proceed with us.

00:08:40.000 --> 00:08:55.000
John Smith (Customer): That seems reasonable. Mary, can we budget for that assessment in Q1?

00:08:55.000 --> 00:09:05.000
Mary Davis (Finance): Yes, I think we can make that work. I'd like to see a formal proposal though.

00:09:05.000 --> 00:09:20.000
Sarah Jameson (Sales Engineer): Of course. I'll get you a detailed proposal by Friday. Mike, can you include some architecture diagrams showing the before and after state?

00:09:20.000 --> 00:09:30.000
Charles Michaels (Solutions Architect): Absolutely. I'll include a high-level migration roadmap as well, showing the phased approach we discussed.

00:09:30.000 --> 00:09:45.000
John Smith (Customer): Perfect. One last question - can you connect us with a reference customer? Ideally someone in financial services who's done a similar migration?

00:09:45.000 --> 00:10:00.000
Sarah Jameson (Sales Engineer): Definitely. I have a great contact at First National Bank who completed a very similar migration last year. I'll reach out to them and set up a reference call.

00:10:00.000 --> 00:10:15.000
John Smith (Customer): Excellent. I think we have everything we need to move forward. Thanks everyone for your time today.

00:10:15.000 --> 00:10:25.000
Sarah Jameson (Sales Engineer): Thank you, John and Mary. I'll follow up with the proposal and reference call details by end of week.

00:10:25.000 --> 00:10:30.000
Charles Michaels (Solutions Architect): Looking forward to working with you both on this project.
```

---

## Expected Output Structure

After implementing the fix, the tool should generate a structured snapshot with sections including:

### Required Sections:
1. **Meeting Overview** - Date, duration, participants
2. **Company Profile** - Industry, size, current state
3. **Business Drivers** - Pain points, objectives, goals
4. **Technical Requirements** - Infrastructure, applications, integrations
5. **Decision Criteria** - Budget, timeline, success metrics
6. **Key Concerns** - Risks, objections, blockers
7. **Next Steps** - Action items, follow-ups, timeline
8. **Opportunity Assessment** - Deal size, probability, strategic value

### Output Format Options:
- **JSON**: Structured data for programmatic processing
- **Markdown**: Human-readable document for sharing

---

## Implementation Priority

**URGENT**: This is blocking the core functionality of the MCP server. Recommend implementing Priority 1 fix (File Content Passing) as it:
- Solves the immediate problem
- Requires minimal changes
- Improves the tool's overall design
- Eliminates an entire class of file system issues

---

## Additional Notes

### MCP Best Practices
According to MCP design patterns, tools that process file content should preferably accept content directly rather than file paths, as this:
- Improves portability across different execution contexts
- Simplifies security model (no file system access needed)
- Makes testing easier
- Reduces dependencies on infrastructure configuration

### Backward Compatibility
If maintaining backward compatibility with existing integrations is important, consider:
1. Accepting both `vtt_file_path` and `vtt_content` parameters
2. Deprecating `vtt_file_path` with a warning
3. Eventually removing file path support in a future major version

---

## Contact & Follow-up

Once the fix is implemented, please test with the provided sample VTT content and verify:
1. Content parsing works correctly
2. All expected sections are generated
3. Both JSON and Markdown output formats work
4. Error handling is appropriate for invalid VTT content

---

## Appendix: Error Trace

```
Call 1: vtt_file_path="/mnt/user-data/uploads/sample_transcript.vtt"
Result: Failed to generate snapshot: Failed to parse VTT file: VTT file not found: /mnt/user-data/uploads/sample_transcript.vtt

Call 2: vtt_file_path="/home/claude/sample_transcript.vtt"  
Result: Failed to generate snapshot: Failed to parse VTT file: VTT file not found: /home/claude/sample_transcript.vtt

Call 3: vtt_file_path="sample_transcript.vtt"
Result: Failed to generate snapshot: Failed to parse VTT file: VTT file not found: sample_transcript.vtt

Call 4: vtt_file_path="/tmp/sample_transcript.vtt"
Result: Failed to generate snapshot: Failed to parse VTT file: VTT file not found: /tmp/sample_transcript.vtt
```

All calls resulted in the same error pattern, confirming file system isolation as the root cause.
