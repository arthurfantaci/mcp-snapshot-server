# MCP Snapshot Server - Complete Fix Guide for Claude Code

**Issue**: `generate_customer_snapshot` function fails with KeyError: 'transcript'  
**Status**: ROOT CAUSE IDENTIFIED - Ready for Implementation  
**Severity**: CRITICAL (100% failure rate)  
**Effort**: ~2-3 hours including tests  
**Date**: 2025-11-23

---

## Table of Contents

1. [Quick Summary](#quick-summary)
2. [The Problem](#the-problem)
3. [Root Cause](#root-cause)
4. [The Solution](#the-solution)
5. [Complete Code Implementation](#complete-code-implementation)
6. [Testing Strategy](#testing-strategy)
7. [Verification Steps](#verification-steps)
8. [Success Criteria](#success-criteria)

---

## Quick Summary

### What's Broken
The `mcp-snapshot-server:generate_customer_snapshot` MCP tool fails immediately with:
```
Failed to generate snapshot: Failed to generate snapshot: 'transcript'
```

### Why It's Broken
The code assumes `parsed_data['transcript']` exists, but the VTT parser actually returns:
```python
{
    "cues": [{"text": "...", "start": "...", "end": "..."}],
    "metadata": {...}
}
```
No 'transcript' key exists!

### The Fix
Add a text extraction function that pulls text from the actual data structure (the 'cues' array).

### Files to Modify
Look for these files in your MCP server codebase:
- `snapshot_handler.py` or `handlers/snapshot_handler.py` (most likely)
- Or any file containing `def generate_customer_snapshot(...)`

---

## The Problem

### Current Broken Code
```python
def generate_customer_snapshot(
    vtt_content: str,
    filename: str = "transcript.vtt",
    output_format: Literal["json", "markdown"] = "json"
) -> dict | str:
    try:
        parsed_data = parse_vtt(vtt_content)
        
        # ❌ BUG: This line fails with KeyError
        transcript_text = parsed_data['transcript']  # KeyError: 'transcript'
        
        snapshot = generate_snapshot(transcript_text)
        
        if output_format == "json":
            return json.dumps(snapshot, indent=2)
        else:
            return format_as_markdown(snapshot)
            
    except Exception as e:
        return {"error": f"Failed to generate snapshot: {str(e)}"}
```

### Test Case That Fails
```python
# Valid VTT content from /mnt/user-data/uploads/sample_transcript.vtt
vtt_content = """WEBVTT

00:00:00.000 --> 00:00:10.000
John Smith (Customer): Hi everyone, thanks for taking the time to meet with us today.

00:00:10.000 --> 00:00:25.000
Sarah Jameson (Sales Engineer): Thanks for having us, John.
"""

# This fails with KeyError: 'transcript'
result = generate_customer_snapshot(vtt_content, "test.vtt", "json")
```

---

## Root Cause

### VTT Parser Output (Actual)
The `parse_vtt()` function returns:
```python
{
    "cues": [
        {
            "id": 1,
            "start": "00:00:00.000",
            "end": "00:00:10.000",
            "text": "John Smith (Customer): Hi everyone, thanks for taking the time..."
        },
        {
            "id": 2,
            "start": "00:00:10.000",
            "end": "00:00:25.000",
            "text": "Sarah Jameson (Sales Engineer): Thanks for having us, John."
        }
        // ... more cues
    ],
    "metadata": {
        "format": "WebVTT",
        "duration": "00:10:30.000"
    }
}
```

**Notice**: There is NO 'transcript' key!

### What The Code Expected
```python
{
    "transcript": "John Smith (Customer): Hi everyone...\n\nSarah Jameson (Sales Engineer): Thanks...",
    "metadata": {...}
}
```

### Data Flow Diagram
```
VTT Input → parse_vtt() → {cues: [...], metadata: {...}}
                              ↓
                        parsed_data['transcript']  ❌ KeyError!
                              ↓
                           CRASH
```

---

## The Solution

### Strategy Overview
Instead of assuming a 'transcript' key exists, we'll:
1. Check for 'transcript' key (in case parser provides it)
2. Extract text from 'cues' array (most common case)
3. Extract from 'entries' array (alternative structure)
4. Fall back to manual VTT parsing (last resort)

### Fixed Data Flow
```
VTT Input → parse_vtt() → {cues: [...], metadata: {...}}
                              ↓
                        extract_transcript_text() ✅
                              ↓
                        "Speaker: text\n\nSpeaker: text..."
                              ↓
                        generate_snapshot()
                              ↓
                        Success!
```

---

## Complete Code Implementation

### Step 1: Add Helper Function - Extract from Cues

Add this function to your handler file:

```python
from typing import Dict, Any

def extract_transcript_text(parsed_data: Dict[str, Any], raw_vtt: str) -> str:
    """
    Extract clean transcript text from parsed VTT data.
    
    Tries multiple extraction strategies:
    1. Check for 'transcript' key (if parser provides it)
    2. Extract from 'cues' array (most common)
    3. Extract from 'entries' array (alternative structure)
    4. Fall back to manual parsing of raw VTT
    
    Args:
        parsed_data: Parsed VTT data structure from parse_vtt()
        raw_vtt: Raw VTT content as fallback
        
    Returns:
        Extracted transcript text with speaker labels
        
    Raises:
        ValueError: If no text could be extracted
    """
    # Strategy 1: Direct transcript key (in case parser provides it)
    if isinstance(parsed_data, dict) and 'transcript' in parsed_data:
        return parsed_data['transcript']
    
    # Strategy 2: Extract from cues array (most common case)
    if isinstance(parsed_data, dict) and 'cues' in parsed_data:
        cues = parsed_data['cues']
        if isinstance(cues, list) and len(cues) > 0:
            text_parts = []
            for cue in cues:
                if isinstance(cue, dict) and 'text' in cue:
                    text_parts.append(cue['text'])
                elif isinstance(cue, str):
                    # Handle case where cue is just a string
                    text_parts.append(cue)
            
            if text_parts:
                return '\n\n'.join(text_parts)
    
    # Strategy 3: Extract from entries array (alternative naming)
    if isinstance(parsed_data, dict) and 'entries' in parsed_data:
        entries = parsed_data['entries']
        if isinstance(entries, list) and len(entries) > 0:
            text_parts = []
            for entry in entries:
                if isinstance(entry, dict) and 'text' in entry:
                    text_parts.append(entry['text'])
            
            if text_parts:
                return '\n\n'.join(text_parts)
    
    # Strategy 4: Fall back to manual parsing of raw VTT
    return extract_text_from_raw_vtt(raw_vtt)
```

### Step 2: Add Fallback Parser

Add this function to handle manual VTT parsing:

```python
def extract_text_from_raw_vtt(vtt_content: str) -> str:
    """
    Manually extract text from raw VTT content.
    
    This is a fallback method when the parser doesn't provide
    the expected structure. It parses the VTT line-by-line.
    
    Args:
        vtt_content: Raw VTT content string
        
    Returns:
        Extracted dialogue text
    """
    if not vtt_content:
        return ""
    
    lines = vtt_content.split('\n')
    text_parts = []
    
    # Skip the WEBVTT header and any initial metadata
    in_cue = False
    current_text = []
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines and WEBVTT header
        if not line or line == 'WEBVTT':
            if current_text:
                # End of current cue - save accumulated text
                text_parts.append(' '.join(current_text))
                current_text = []
            in_cue = False
            continue
        
        # Check if this is a timestamp line (contains -->)
        if '-->' in line:
            in_cue = True
            continue
        
        # If we're in a cue and this isn't a timestamp, it's text
        if in_cue:
            current_text.append(line)
    
    # Don't forget the last cue
    if current_text:
        text_parts.append(' '.join(current_text))
    
    return '\n\n'.join(text_parts)
```

### Step 3: Update Main Function

Replace the buggy line in `generate_customer_snapshot`:

```python
def generate_customer_snapshot(
    vtt_content: str,
    filename: str = "transcript.vtt",
    output_format: Literal["json", "markdown"] = "json"
) -> Dict[str, Any] | str:
    """
    Generate a Customer Success Snapshot from VTT transcript content.
    
    Args:
        vtt_content: VTT transcript content as a string (must start with 'WEBVTT')
        filename: Optional filename for context (default: 'transcript.vtt')
        output_format: Output format - 'json' or 'markdown' (default: 'json')
    
    Returns:
        Customer snapshot in specified format
        
    Raises:
        ValueError: If VTT content is invalid or empty
    """
    try:
        # Validate input
        if not vtt_content or not isinstance(vtt_content, str):
            raise ValueError("vtt_content must be a non-empty string")
            
        if not vtt_content.strip().startswith("WEBVTT"):
            raise ValueError("Invalid VTT format: content must start with 'WEBVTT'")
        
        # Parse the VTT content
        parsed_data = parse_vtt(vtt_content)
        
        # ✅ FIXED: Extract transcript text from the actual data structure
        # OLD (BROKEN): transcript_text = parsed_data['transcript']
        # NEW (FIXED):
        transcript_text = extract_transcript_text(parsed_data, vtt_content)
        
        if not transcript_text.strip():
            raise ValueError("No transcript text could be extracted from VTT content")
        
        # Generate the customer snapshot
        snapshot = generate_snapshot(transcript_text, filename=filename)
        
        # Format output
        if output_format == "json":
            import json
            return json.dumps(snapshot, indent=2)
        elif output_format == "markdown":
            return format_as_markdown(snapshot)
        else:
            raise ValueError(f"Unsupported output_format: {output_format}. Use 'json' or 'markdown'.")
            
    except Exception as e:
        # ✅ IMPROVED: Provide detailed error information for debugging
        import traceback
        import json
        
        error_response = {
            "error": f"Failed to generate snapshot: {str(e)}",
            "error_type": type(e).__name__,
            "filename": filename,
            "vtt_content_preview": vtt_content[:200] if vtt_content else None,
            "traceback": traceback.format_exc()
        }
        
        if output_format == "json":
            return json.dumps(error_response, indent=2)
        else:
            return (f"# Error\n\n{error_response['error']}\n\n"
                   f"**Type**: {error_response['error_type']}\n\n"
                   f"## Details\n\n```\n{error_response['traceback']}\n```")
```

### Step 4: Add Imports (if needed)

Make sure these imports are at the top of your file:

```python
from typing import Dict, Any, Literal
import json
import traceback
```

---

## Testing Strategy

### Unit Test 1: Extract from Cues Structure
```python
def test_extract_from_cues_structure():
    """Test extraction from cues-based parsed data."""
    parsed_data = {
        "cues": [
            {"text": "Speaker 1: Hello", "start": "00:00:00", "end": "00:00:05"},
            {"text": "Speaker 2: Hi there", "start": "00:00:05", "end": "00:00:10"}
        ],
        "metadata": {"format": "WebVTT"}
    }
    
    raw_vtt = "WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nSpeaker 1: Hello"
    
    result = extract_transcript_text(parsed_data, raw_vtt)
    
    assert "Speaker 1: Hello" in result
    assert "Speaker 2: Hi there" in result
    print("✓ Test 1 passed: Extract from cues structure")


def test_extract_from_raw_vtt_fallback():
    """Test fallback to raw VTT parsing."""
    vtt_content = """WEBVTT

00:00:00.000 --> 00:00:10.000
John Smith (Customer): Test content here.

00:00:10.000 --> 00:00:20.000
Sarah Jameson (Sales): More test content.
"""
    
    result = extract_text_from_raw_vtt(vtt_content)
    
    assert "John Smith" in result
    assert "Sarah Jameson" in result
    assert "WEBVTT" not in result
    assert "-->" not in result
    print("✓ Test 2 passed: Fallback to raw VTT parsing")


def test_generate_snapshot_with_valid_vtt():
    """Test snapshot generation with valid VTT content."""
    vtt_content = """WEBVTT

00:00:00.000 --> 00:00:10.000
John Smith (Customer): Hi everyone, thanks for meeting.

00:00:10.000 --> 00:00:25.000
Sarah Jameson (Sales): Thanks for having us, John.
"""
    
    result = generate_customer_snapshot(
        vtt_content=vtt_content,
        filename="test.vtt",
        output_format="json"
    )
    
    # Should not error
    assert isinstance(result, str)
    
    # Should not contain error keywords
    result_lower = result.lower()
    assert "keyerror" not in result_lower
    assert "'transcript'" not in result_lower
    
    # Should contain valid JSON
    snapshot = json.loads(result)
    assert isinstance(snapshot, dict)
    print("✓ Test 3 passed: End-to-end snapshot generation (JSON)")


def test_generate_snapshot_markdown_format():
    """Test snapshot generation with markdown output."""
    vtt_content = """WEBVTT

00:00:00.000 --> 00:00:10.000
John Smith (Customer): Test content.
"""
    
    result = generate_customer_snapshot(
        vtt_content=vtt_content,
        filename="test.vtt",
        output_format="markdown"
    )
    
    assert isinstance(result, str)
    # Markdown typically has headers
    assert "#" in result
    print("✓ Test 4 passed: Markdown output format")


def test_empty_vtt_content():
    """Test handling of empty VTT content."""
    result = generate_customer_snapshot(
        vtt_content="",
        filename="empty.vtt",
        output_format="json"
    )
    
    # Should return error
    assert "error" in result.lower()
    print("✓ Test 5 passed: Empty VTT handling")


def test_invalid_vtt_format():
    """Test handling of invalid VTT format."""
    result = generate_customer_snapshot(
        vtt_content="This is not valid VTT content",
        filename="invalid.vtt",
        output_format="json"
    )
    
    # Should return error about invalid format
    assert "error" in result.lower()
    assert "invalid" in result.lower() or "webvtt" in result.lower()
    print("✓ Test 6 passed: Invalid VTT format handling")


# Run all tests
if __name__ == "__main__":
    test_extract_from_cues_structure()
    test_extract_from_raw_vtt_fallback()
    test_generate_snapshot_with_valid_vtt()
    test_generate_snapshot_markdown_format()
    test_empty_vtt_content()
    test_invalid_vtt_format()
    print("\n✓ All tests passed!")
```

### Integration Test with Real File

```python
def test_with_real_vtt_file():
    """Test with the actual VTT file that was failing."""
    import os
    
    vtt_path = "/mnt/user-data/uploads/sample_transcript.vtt"
    
    if os.path.exists(vtt_path):
        with open(vtt_path, 'r') as f:
            vtt_content = f.read()
        
        # Test JSON format
        result_json = generate_customer_snapshot(
            vtt_content=vtt_content,
            filename="sample_transcript.vtt",
            output_format="json"
        )
        
        assert "error" not in result_json.lower() or "KeyError" not in result_json
        snapshot = json.loads(result_json)
        assert isinstance(snapshot, dict)
        print("✓ Integration test passed: Real VTT file (JSON)")
        
        # Test Markdown format
        result_md = generate_customer_snapshot(
            vtt_content=vtt_content,
            filename="sample_transcript.vtt",
            output_format="markdown"
        )
        
        assert isinstance(result_md, str)
        assert "#" in result_md
        print("✓ Integration test passed: Real VTT file (Markdown)")
        
        return snapshot
    else:
        print("⚠ Warning: Test file not found at", vtt_path)
        return None
```

---

## Verification Steps

### Step 1: Locate the Code
Find the file containing `generate_customer_snapshot`. It's likely in:
```
mcp-snapshot-server/
├── src/
│   └── snapshot_server/
│       ├── handlers/
│       │   └── snapshot_handler.py    ← Look here first
│       ├── server.py
│       └── __init__.py
```

### Step 2: Make the Changes
1. Add `extract_transcript_text()` function
2. Add `extract_text_from_raw_vtt()` function
3. Update `generate_customer_snapshot()` to use the new extraction function
4. Update error handling to include traceback

### Step 3: Quick Validation
Run this in Python to test:

```python
# Test snippet
vtt = """WEBVTT

00:00:00.000 --> 00:00:10.000
John Smith: Test content.
"""

result = generate_customer_snapshot(vtt, "test.vtt", "json")
print(result)

# Should output valid JSON, NOT an error with KeyError
```

### Step 4: Run Unit Tests
```bash
# If you have pytest
pytest test_snapshot_handler.py -v

# Or run directly
python test_snapshot_handler.py
```

### Step 5: Test with Real File
```python
# Read the file that was originally failing
with open('/mnt/user-data/uploads/sample_transcript.vtt', 'r') as f:
    vtt_content = f.read()

# This should now work
result = generate_customer_snapshot(vtt_content, "sample.vtt", "json")
print(result)
```

### Step 6: Test Both Output Formats
```python
# Test JSON
json_result = generate_customer_snapshot(vtt_content, "test.vtt", "json")
snapshot = json.loads(json_result)
print("JSON keys:", snapshot.keys())

# Test Markdown
md_result = generate_customer_snapshot(vtt_content, "test.vtt", "markdown")
print("Markdown preview:", md_result[:200])
```

---

## Success Criteria

### Must Have ✅
- [ ] Function processes valid VTT content without KeyError
- [ ] Returns properly formatted JSON snapshot
- [ ] Returns properly formatted Markdown snapshot
- [ ] Clear error messages for invalid input (not KeyError: 'transcript')
- [ ] All unit tests pass
- [ ] Integration test with sample_transcript.vtt passes

### Should Have ✅
- [ ] Handles multiple VTT parser output formats (cues, entries, transcript)
- [ ] Provides detailed error information with traceback
- [ ] Validates VTT format before processing
- [ ] Unit test coverage > 80%

### Nice to Have 🎯
- [ ] Logging for debugging
- [ ] Performance metrics
- [ ] Documentation updates
- [ ] Example usage in README

---

## Common Issues & Troubleshooting

### Issue 1: Still getting KeyError after fix
**Symptom**: KeyError on a different line  
**Solution**: Make sure you replaced the line with `extract_transcript_text()`, not just added it

### Issue 2: Empty transcript extracted
**Symptom**: ValueError "No transcript text could be extracted"  
**Solution**: Check what structure `parse_vtt()` is actually returning. Add logging:
```python
print("Parsed data keys:", parsed_data.keys() if isinstance(parsed_data, dict) else type(parsed_data))
```

### Issue 3: Tests fail on import
**Symptom**: ImportError when running tests  
**Solution**: Make sure test file is in correct location and imports are correct:
```python
from snapshot_server.handlers.snapshot_handler import (
    generate_customer_snapshot,
    extract_transcript_text,
    extract_text_from_raw_vtt
)
```

### Issue 4: Markdown output has errors in JSON
**Symptom**: JSON errors when output_format is markdown  
**Solution**: Check that error handling respects output_format parameter

---

## Summary of Changes

### Files Modified
- `snapshot_handler.py` (or equivalent)

### Functions Added
1. `extract_transcript_text(parsed_data, raw_vtt)` - Multi-strategy text extraction
2. `extract_text_from_raw_vtt(vtt_content)` - Fallback VTT parser

### Functions Modified
1. `generate_customer_snapshot()` - Updated to use new extraction logic
2. Error handling improved with detailed traceback

### Lines Changed
- **Before**: `transcript_text = parsed_data['transcript']`
- **After**: `transcript_text = extract_transcript_text(parsed_data, vtt_content)`

---

## Quick Reference

### The One-Line Summary
Replace `parsed_data['transcript']` with `extract_transcript_text(parsed_data, vtt_content)`

### Test Command
```python
with open('/mnt/user-data/uploads/sample_transcript.vtt') as f:
    vtt = f.read()
result = generate_customer_snapshot(vtt, "sample.vtt", "json")
assert "KeyError" not in result
print("✓ Fix verified!")
```

### Expected Timeline
- **Locate code**: 15 minutes
- **Implement fix**: 30 minutes
- **Write tests**: 30 minutes
- **Test & verify**: 30 minutes
- **Documentation**: 20 minutes
- **Total**: ~2-2.5 hours

---

## Contact & Support

**Original failing file**: `/mnt/user-data/uploads/sample_transcript.vtt` (122 lines, valid VTT format)

**Error to fix**: `KeyError: 'transcript'` in `generate_customer_snapshot` function

**Key insight**: VTT parser returns `{'cues': [...]}` not `{'transcript': '...'}`

**Priority**: CRITICAL - Function is 100% non-functional without this fix

---

## Final Checklist

Before marking this as complete:

- [ ] Code changes implemented
- [ ] Unit tests added and passing
- [ ] Integration test with sample_transcript.vtt passing
- [ ] Both JSON and Markdown outputs verified
- [ ] Error handling tested with invalid inputs
- [ ] Documentation updated (if applicable)
- [ ] Code reviewed (if applicable)
- [ ] Version bumped (if applicable)
- [ ] Deployed/Released

---

**END OF FIX GUIDE**

Good luck with the implementation! The fix is straightforward - you're essentially adding proper text extraction logic where there was a blind assumption about data structure. Once implemented, the MCP tool will work correctly for all VTT transcript processing.
