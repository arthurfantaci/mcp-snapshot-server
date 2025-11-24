"""VTT transcript parsing and processing utilities.

This module provides functions for parsing WebVTT transcript content,
cleaning and normalizing transcript text, and extracting speaker information.
"""

import io
import logging
import re
from pathlib import Path
from typing import Any

import webvtt

from mcp_snapshot_server.utils.errors import ErrorCode, MCPServerError

logger = logging.getLogger(__name__)


def validate_vtt_file(file_path: str) -> Path:
    """Validate VTT file path and existence.

    Args:
        file_path: Path to VTT file

    Returns:
        Validated Path object

    Raises:
        MCPServerError: If file doesn't exist, is not a file, or wrong extension
    """
    try:
        path = Path(file_path).resolve()
    except Exception as e:
        raise MCPServerError(
            message=f"Invalid file path: {file_path}",
            error_code=ErrorCode.INVALID_INPUT,
            details={"file_path": file_path, "error": str(e)},
        )

    # Check if file exists
    if not path.exists():
        raise MCPServerError(
            message=f"VTT file not found: {file_path}",
            error_code=ErrorCode.FILE_NOT_FOUND,
            details={"file_path": file_path},
        )

    # Check if it's a file (not directory)
    if not path.is_file():
        raise MCPServerError(
            message=f"Path is not a file: {file_path}",
            error_code=ErrorCode.INVALID_INPUT,
            details={"file_path": file_path},
        )

    # Check file extension
    if path.suffix.lower() != ".vtt":
        raise MCPServerError(
            message=f"File must have .vtt extension: {file_path}",
            error_code=ErrorCode.INVALID_INPUT,
            details={"file_path": file_path, "extension": path.suffix},
        )

    return path


def extract_speaker_info(text: str) -> tuple[str, str]:
    """Extract speaker name and role from text line.

    Args:
        text: Text line potentially containing speaker info

    Returns:
        Tuple of (speaker_name, clean_text)
    """
    # Pattern: "Name (Role): text" or "Name: text"
    pattern = r"^([^:(]+?)(?:\s*\([^)]+\))?\s*:\s*(.*)$"
    match = re.match(pattern, text.strip())

    if match:
        speaker = match.group(1).strip()
        clean_text = match.group(2).strip()
        return speaker, clean_text

    return "", text.strip()


def clean_transcript_text(text: str) -> str:
    """Clean and normalize transcript text.

    Args:
        text: Raw transcript text

    Returns:
        Cleaned text
    """
    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text)

    # Remove common VTT artifacts
    text = re.sub(r"<[^>]+>", "", text)  # Remove HTML tags

    # Normalize quotes
    text = text.replace(""", '"').replace(""", '"')
    text = text.replace("'", "'").replace("'", "'")

    return text.strip()


def parse_vtt_content(vtt_content: str, filename: str = "transcript.vtt") -> dict[str, Any]:
    """Parse VTT transcript content string directly.

    Args:
        vtt_content: VTT transcript content as a string
        filename: Optional filename for context in error messages and metadata

    Returns:
        Dictionary containing:
            - text: Full transcript text with speaker labels
            - speakers: List of unique speakers
            - speaker_turns: List of individual speaking turns
            - duration: Duration in seconds
            - metadata: Additional metadata

    Raises:
        MCPServerError: If content cannot be parsed
    """
    logger.info(f"Parsing VTT content from {filename}")

    # Validate that content is not empty
    if not vtt_content or not vtt_content.strip():
        raise MCPServerError(
            message="VTT content is empty",
            error_code=ErrorCode.INVALID_INPUT,
            details={"vtt_filename": filename},
        )

    # Validate that content starts with WEBVTT header
    if not vtt_content.strip().startswith("WEBVTT"):
        raise MCPServerError(
            message="Invalid VTT format: content must start with 'WEBVTT'",
            error_code=ErrorCode.INVALID_INPUT,
            details={"vtt_filename": filename, "first_line": vtt_content.split("\n")[0]},
        )

    try:
        # Parse VTT content directly using StringIO buffer
        # This avoids temporary file creation for better performance
        buffer = io.StringIO(vtt_content)
        vtt_data = webvtt.WebVTT.from_buffer(buffer)

        speakers = set()
        speaker_turns = []
        full_text_parts = []

        for caption in vtt_data:
            # Get raw text
            raw_text = caption.text

            # Clean text
            clean_text = clean_transcript_text(raw_text)

            # Extract speaker
            speaker, content = extract_speaker_info(clean_text)

            if speaker:
                speakers.add(speaker)
                speaker_turns.append(
                    {
                        "speaker": speaker,
                        "text": content,
                        "start": caption.start,
                        "end": caption.end,
                    }
                )
                full_text_parts.append(f"{speaker}: {content}")
            else:
                # No speaker identified, just add content
                if content:
                    speaker_turns.append(
                        {
                            "speaker": "Unknown",
                            "text": content,
                            "start": caption.start,
                            "end": caption.end,
                        }
                    )
                    full_text_parts.append(content)

        # Calculate duration (last caption end time)
        duration = 0.0
        if vtt_data.captions:
            last_caption = vtt_data.captions[-1]
            # Parse end time (format: HH:MM:SS.mmm)
            time_parts = last_caption.end.split(":")
            hours = float(time_parts[0])
            minutes = float(time_parts[1])
            seconds = float(time_parts[2])
            duration = hours * 3600 + minutes * 60 + seconds

        # Combine full text
        full_text = "\n".join(full_text_parts)

        logger.info(
            "Successfully parsed VTT content",
            extra={
                "vtt_filename": filename,
                "speakers_count": len(speakers),
                "turns_count": len(speaker_turns),
                "duration_seconds": duration,
                "text_length": len(full_text),
            },
        )

        return {
            "text": full_text,
            "speakers": sorted(speakers),
            "speaker_turns": speaker_turns,
            "duration": duration,
            "metadata": {
                "vtt_filename": filename,
                "caption_count": len(vtt_data.captions),
                "speaker_count": len(speakers),
            },
        }

    except webvtt.errors.MalformedFileError as e:
        raise MCPServerError(
            message=f"Invalid VTT format: {str(e)}",
            error_code=ErrorCode.PARSE_ERROR,
            details={"vtt_filename": filename, "parse_error": str(e)},
        ) from e

    except MCPServerError:
        # Re-raise our own errors
        raise

    except Exception as e:
        raise MCPServerError(
            message=f"Failed to parse VTT content: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
            details={"vtt_filename": filename, "error_type": type(e).__name__},
        ) from e


def parse_vtt_transcript(file_path: str) -> dict[str, Any]:
    """Parse VTT transcript file and extract structured data.

    Args:
        file_path: Path to VTT transcript file

    Returns:
        Dictionary containing:
            - text: Full transcript text with speaker labels
            - speakers: List of unique speakers
            - speaker_turns: List of individual speaking turns
            - duration: Duration in seconds
            - metadata: Additional metadata

    Raises:
        MCPServerError: If file cannot be parsed
    """
    logger.info(f"Parsing VTT transcript: {file_path}")

    # Validate file
    path = validate_vtt_file(file_path)

    try:
        # Parse VTT file
        vtt_data = webvtt.read(str(path))

        speakers = set()
        speaker_turns = []
        full_text_parts = []

        for caption in vtt_data:
            # Get raw text
            raw_text = caption.text

            # Clean text
            clean_text = clean_transcript_text(raw_text)

            # Extract speaker
            speaker, content = extract_speaker_info(clean_text)

            if speaker:
                speakers.add(speaker)
                speaker_turns.append(
                    {
                        "speaker": speaker,
                        "text": content,
                        "start": caption.start,
                        "end": caption.end,
                    }
                )
                full_text_parts.append(f"{speaker}: {content}")
            else:
                # No speaker identified, just add content
                if content:
                    speaker_turns.append(
                        {
                            "speaker": "Unknown",
                            "text": content,
                            "start": caption.start,
                            "end": caption.end,
                        }
                    )
                    full_text_parts.append(content)

        # Calculate duration (last caption end time)
        duration = 0.0
        if vtt_data.captions:
            last_caption = vtt_data.captions[-1]
            # Parse end time (format: HH:MM:SS.mmm)
            time_parts = last_caption.end.split(":")
            hours = float(time_parts[0])
            minutes = float(time_parts[1])
            seconds = float(time_parts[2])
            duration = hours * 3600 + minutes * 60 + seconds

        # Combine full text
        full_text = "\n".join(full_text_parts)

        logger.info(
            "Successfully parsed VTT file",
            extra={
                "speakers_count": len(speakers),
                "turns_count": len(speaker_turns),
                "duration_seconds": duration,
                "text_length": len(full_text),
            },
        )

        return {
            "text": full_text,
            "speakers": sorted(speakers),
            "speaker_turns": speaker_turns,
            "duration": duration,
            "metadata": {
                "file_path": str(path),
                "caption_count": len(vtt_data.captions),
                "speaker_count": len(speakers),
            },
        }

    except webvtt.errors.MalformedFileError as e:
        raise MCPServerError(
            message=f"Invalid VTT format: {str(e)}",
            error_code=ErrorCode.PARSE_ERROR,
            details={"file_path": str(path), "parse_error": str(e)},
        )

    except Exception as e:
        raise MCPServerError(
            message=f"Failed to parse VTT file: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
            details={"file_path": str(path), "error_type": type(e).__name__},
        )


def get_transcript_summary(transcript_data: dict[str, Any]) -> str:
    """Generate a brief summary of transcript data.

    Args:
        transcript_data: Parsed transcript data

    Returns:
        Human-readable summary string
    """
    speakers = transcript_data.get("speakers", [])
    duration = transcript_data.get("duration", 0)
    turns = transcript_data.get("speaker_turns", [])
    text_length = len(transcript_data.get("text", ""))

    minutes = int(duration // 60)
    seconds = int(duration % 60)

    return f"""Transcript Summary:
- Speakers: {len(speakers)} ({", ".join(speakers[:3])}{"..." if len(speakers) > 3 else ""})
- Duration: {minutes}m {seconds}s
- Speaking turns: {len(turns)}
- Total text length: {text_length:,} characters
"""
