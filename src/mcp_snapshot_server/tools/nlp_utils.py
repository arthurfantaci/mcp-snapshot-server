"""NLP utilities for entity and topic extraction from transcripts.

This module provides functions for extracting named entities using spaCy
and identifying key topics using NLTK from meeting transcripts.
"""

import logging
from collections import Counter

from mcp_snapshot_server.models.analysis import TranscriptStructure
from mcp_snapshot_server.models.transcript import TranscriptData
from mcp_snapshot_server.utils.config import get_settings
from mcp_snapshot_server.utils.errors import ErrorCode, MCPServerError

logger = logging.getLogger(__name__)


def extract_entities(text: str) -> dict[str, list[str]]:
    """Extract named entities from text using spaCy.

    Args:
        text: Text to extract entities from

    Returns:
        Dictionary with entity types as keys and lists of entities as values
    """
    try:
        import spacy

        settings = get_settings()
        model_name = settings.nlp.spacy_model

        logger.debug(f"Loading spaCy model: {model_name}")

        try:
            nlp = spacy.load(model_name)
        except OSError as err:
            # Model not found, try to provide helpful error
            raise MCPServerError(
                message=f"spaCy model '{model_name}' not found. "
                f"Please install it: python -m spacy download {model_name}",
                error_code=ErrorCode.INTERNAL_ERROR,
                details={"model": model_name},
            ) from err

        # Process text
        doc = nlp(text)

        # Extract entities by type
        entities_by_type: dict[str, list[str]] = {
            "PERSON": [],
            "ORG": [],
            "PRODUCT": [],
            "GPE": [],  # Geo-political entities (locations)
            "DATE": [],
            "MONEY": [],
            "PERCENT": [],
        }

        for ent in doc.ents:
            # Simple deduplication
            if (
                ent.label_ in entities_by_type
                and ent.text not in entities_by_type[ent.label_]
            ):
                entities_by_type[ent.label_].append(ent.text)

        # Clean up empty categories
        entities_by_type = {k: v for k, v in entities_by_type.items() if v}

        logger.info(
            "Extracted entities",
            extra={
                "total_entities": sum(len(v) for v in entities_by_type.values()),
                "entity_types": list(entities_by_type.keys()),
            },
        )

        return entities_by_type

    except ImportError as err:
        raise MCPServerError(
            message="spaCy not installed. Install with: pip install spacy",
            error_code=ErrorCode.INTERNAL_ERROR,
            details={"missing_package": "spacy"},
        ) from err
    except Exception as e:
        raise MCPServerError(
            message=f"Entity extraction failed: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
            details={"error_type": type(e).__name__},
        ) from e


def extract_topics(text: str, top_n: int = 10) -> list[str]:
    """Extract key topics from text using NLTK.

    Args:
        text: Text to extract topics from
        top_n: Number of top topics to return

    Returns:
        List of key topics/phrases
    """
    try:
        import nltk
        from nltk import word_tokenize
        from nltk.corpus import stopwords
        from nltk.probability import FreqDist

        # Try to use punkt tokenizer, download if needed
        try:
            nltk.data.find("tokenizers/punkt")
        except LookupError:
            logger.warning("Downloading NLTK punkt tokenizer")
            nltk.download("punkt", quiet=True)

        # Try to use stopwords, download if needed
        try:
            nltk.data.find("corpora/stopwords")
        except LookupError:
            logger.warning("Downloading NLTK stopwords")
            nltk.download("stopwords", quiet=True)

        # Tokenize text
        tokens = word_tokenize(text.lower())

        # Remove stopwords and non-alphabetic tokens
        stop_words = set(stopwords.words("english"))
        filtered_tokens = [
            token
            for token in tokens
            if token.isalpha() and token not in stop_words and len(token) > 3
        ]

        # Get frequency distribution
        freq_dist = FreqDist(filtered_tokens)

        # Get top N most common words as topics
        topics = [word for word, freq in freq_dist.most_common(top_n)]

        logger.info(
            "Extracted topics",
            extra={"topics_count": len(topics), "total_tokens": len(tokens)},
        )

        return topics

    except ImportError as err:
        raise MCPServerError(
            message="NLTK not installed. Install with: pip install nltk",
            error_code=ErrorCode.INTERNAL_ERROR,
            details={"missing_package": "nltk"},
        ) from err
    except Exception as e:
        raise MCPServerError(
            message=f"Topic extraction failed: {str(e)}",
            error_code=ErrorCode.INTERNAL_ERROR,
            details={"error_type": type(e).__name__},
        ) from e


def extract_key_phrases(text: str, top_n: int = 15) -> list[str]:
    """Extract key phrases (bigrams and trigrams) from text.

    Args:
        text: Text to extract phrases from
        top_n: Number of top phrases to return

    Returns:
        List of key phrases
    """
    try:
        from nltk import word_tokenize
        from nltk.corpus import stopwords
        from nltk.util import ngrams

        # Tokenize
        tokens = word_tokenize(text.lower())

        # Remove stopwords
        stop_words = set(stopwords.words("english"))
        filtered_tokens = [
            token
            for token in tokens
            if token.isalpha() and token not in stop_words and len(token) > 3
        ]

        # Generate bigrams and trigrams
        bigrams = list(ngrams(filtered_tokens, 2))
        trigrams = list(ngrams(filtered_tokens, 3))

        # Count frequencies
        bigram_freq = Counter(bigrams)
        trigram_freq = Counter(trigrams)

        # Get top phrases
        top_bigrams = [
            " ".join(gram) for gram, freq in bigram_freq.most_common(top_n // 2)
        ]
        top_trigrams = [
            " ".join(gram)
            for gram, freq in trigram_freq.most_common(top_n - len(top_bigrams))
        ]

        phrases = top_trigrams + top_bigrams

        logger.info(
            "Extracted key phrases",
            extra={"phrases_count": len(phrases)},
        )

        return phrases[:top_n]

    except Exception as e:
        logger.warning(f"Key phrase extraction failed: {str(e)}")
        return []


def analyze_transcript_structure(
    transcript_data: TranscriptData,
) -> TranscriptStructure:
    """Analyze the structure of a transcript.

    Args:
        transcript_data: Parsed TranscriptData model

    Returns:
        TranscriptStructure model with structural analysis
    """
    speakers = transcript_data.speakers
    turns = transcript_data.speaker_turns
    duration = transcript_data.duration

    # Count turns per speaker
    speaker_turns_count: dict[str, int] = {}
    speaker_word_count: dict[str, int] = {}

    for turn in turns:
        speaker = turn.speaker
        text = turn.text

        speaker_turns_count[speaker] = speaker_turns_count.get(speaker, 0) + 1
        word_count = len(text.split())
        speaker_word_count[speaker] = speaker_word_count.get(speaker, 0) + word_count

    # Determine meeting type heuristically
    meeting_type = "discussion"
    if len(speakers) == 2:
        meeting_type = "one_on_one"
    elif len(speakers) <= 4:
        meeting_type = "small_group"
    elif len(speakers) > 4:
        meeting_type = "large_group"

    # Check for specific patterns
    text_lower = transcript_data.text.lower()
    if "kickoff" in text_lower or "introduction" in text_lower:
        meeting_type = "kickoff"
    elif "review" in text_lower or "retrospective" in text_lower:
        meeting_type = "review"

    # Calculate average turn length
    avg_turn_length = (
        sum(len(t.text.split()) for t in turns) / len(turns) if turns else 0.0
    )

    return TranscriptStructure(
        meeting_type=meeting_type,
        speaker_count=len(speakers),
        total_turns=len(turns),
        duration_seconds=duration,
        speaker_turns_count=speaker_turns_count,
        speaker_word_count=speaker_word_count,
        avg_turn_length=avg_turn_length,
    )
