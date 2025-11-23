"""Tests for VTT transcript processing utilities."""

from pathlib import Path

import pytest

from mcp_snapshot_server.tools.transcript_utils import (
    clean_transcript_text,
    extract_speaker_info,
    get_transcript_summary,
    parse_vtt_transcript,
    validate_vtt_file,
)
from mcp_snapshot_server.utils.errors import ErrorCode, MCPServerError


@pytest.mark.unit
class TestValidateVTTFile:
    """Tests for VTT file validation."""

    def test_validate_existing_vtt_file(self, sample_vtt_path: Path) -> None:
        """Test validation of existing VTT file."""
        result = validate_vtt_file(str(sample_vtt_path))
        assert isinstance(result, Path)
        assert result.suffix == ".vtt"
        assert result.exists()

    def test_validate_nonexistent_file(self) -> None:
        """Test validation fails for nonexistent file."""
        with pytest.raises(MCPServerError) as exc_info:
            validate_vtt_file("/path/to/nonexistent.vtt")

        assert exc_info.value.error_code == ErrorCode.FILE_NOT_FOUND

    def test_validate_wrong_extension(self, tmp_path: Path) -> None:
        """Test validation fails for wrong file extension."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("test content")

        with pytest.raises(MCPServerError) as exc_info:
            validate_vtt_file(str(txt_file))

        assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
        assert "extension" in str(exc_info.value.message).lower()

    def test_validate_directory_path(self, tmp_path: Path) -> None:
        """Test validation fails for directory path."""
        with pytest.raises(MCPServerError) as exc_info:
            validate_vtt_file(str(tmp_path))

        assert exc_info.value.error_code == ErrorCode.INVALID_INPUT


@pytest.mark.unit
class TestExtractSpeakerInfo:
    """Tests for speaker information extraction."""

    def test_extract_with_role(self) -> None:
        """Test extracting speaker with role in parentheses."""
        text = "John Smith (Customer): This is the message"
        speaker, content = extract_speaker_info(text)

        assert speaker == "John Smith"
        assert content == "This is the message"

    def test_extract_without_role(self) -> None:
        """Test extracting speaker without role."""
        text = "Sarah Jameson: Here is some content"
        speaker, content = extract_speaker_info(text)

        assert speaker == "Sarah Jameson"
        assert content == "Here is some content"

    def test_no_speaker_label(self) -> None:
        """Test text without speaker label."""
        text = "Just some regular text without a speaker"
        speaker, content = extract_speaker_info(text)

        assert speaker == ""
        assert content == text.strip()

    def test_complex_speaker_name(self) -> None:
        """Test complex speaker names."""
        text = "Dr. Maria Rodriguez-Smith (Chief Architect): The solution"
        speaker, content = extract_speaker_info(text)

        assert speaker == "Dr. Maria Rodriguez-Smith"
        assert content == "The solution"


@pytest.mark.unit
class TestCleanTranscriptText:
    """Tests for transcript text cleaning."""

    def test_remove_extra_whitespace(self) -> None:
        """Test removing extra whitespace."""
        text = "This  has   extra    spaces"
        result = clean_transcript_text(text)

        assert result == "This has extra spaces"

    def test_remove_html_tags(self) -> None:
        """Test removing HTML tags."""
        text = "Text with <b>bold</b> and <i>italic</i> tags"
        result = clean_transcript_text(text)

        assert "<b>" not in result
        assert "<i>" not in result
        assert "bold" in result
        assert "italic" in result

    def test_strip_whitespace(self) -> None:
        """Test stripping leading and trailing whitespace."""
        text = "   Text with spaces   "
        result = clean_transcript_text(text)

        assert result == "Text with spaces"
        assert not result.startswith(" ")
        assert not result.endswith(" ")


@pytest.mark.unit
class TestParseVTTTranscript:
    """Tests for VTT transcript parsing."""

    def test_parse_sample_vtt(self, sample_vtt_path: Path) -> None:
        """Test parsing sample VTT file."""
        result = parse_vtt_transcript(str(sample_vtt_path))

        assert "text" in result
        assert "speakers" in result
        assert "speaker_turns" in result
        assert "duration" in result
        assert "metadata" in result

        # Check that we extracted speakers
        assert len(result["speakers"]) > 0
        assert "John Smith" in result["speakers"]

        # Check that we have speaking turns
        assert len(result["speaker_turns"]) > 0

        # Check text is not empty
        assert len(result["text"]) > 0

    def test_parse_includes_metadata(self, sample_vtt_path: Path) -> None:
        """Test that parsing includes metadata."""
        result = parse_vtt_transcript(str(sample_vtt_path))

        metadata = result["metadata"]
        assert "file_path" in metadata
        assert "caption_count" in metadata
        assert "speaker_count" in metadata

    def test_parse_calculates_duration(self, sample_vtt_path: Path) -> None:
        """Test that duration is calculated."""
        result = parse_vtt_transcript(str(sample_vtt_path))

        assert result["duration"] > 0

    def test_parse_nonexistent_file(self) -> None:
        """Test parsing nonexistent file raises error."""
        with pytest.raises(MCPServerError):
            parse_vtt_transcript("/path/to/nonexistent.vtt")


@pytest.mark.unit
class TestGetTranscriptSummary:
    """Tests for transcript summary generation."""

    def test_generate_summary(self) -> None:
        """Test generating transcript summary."""
        transcript_data = {
            "text": "Sample transcript text",
            "speakers": ["Alice", "Bob", "Charlie"],
            "speaker_turns": [{"speaker": "Alice", "text": "Hello"}] * 10,
            "duration": 185.5,  # 3m 5.5s
        }

        summary = get_transcript_summary(transcript_data)

        assert "3m 5s" in summary
        assert "3" in summary  # speaker count
        assert "10" in summary  # turns
        assert "Alice" in summary

    def test_summary_truncates_speakers(self) -> None:
        """Test that summary truncates long speaker lists."""
        transcript_data = {
            "text": "text",
            "speakers": ["Person1", "Person2", "Person3", "Person4", "Person5"],
            "speaker_turns": [],
            "duration": 100,
        }

        summary = get_transcript_summary(transcript_data)

        # Should show first 3 and indicate more
        assert "Person1" in summary
        assert "Person2" in summary
        assert "Person3" in summary
        assert "..." in summary
