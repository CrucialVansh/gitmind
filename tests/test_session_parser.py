"""
Tests for gitmind/parsers/session_parser.py

Week 1: write these tests alongside your implementation.

Run with:  pytest tests/test_session_parser.py -v
"""

import pytest
from pathlib import Path

from gitmind.parsers.session_parser import (
    extract_files_mentioned,
    chunk_session,
)
from gitmind.models import Session, SessionSource
from datetime import datetime, timezone


# ── Fixtures ───────────────────────────────────────────────────────────────────

SAMPLE_TRANSCRIPT = (
    "Human: I'm looking at the retry logic in src/api.py. "
    "The function fetchUserWithRetry is retrying on 503 but not 429. Is that intentional?\n\n"
    "Assistant: Yes, that's intentional. The vendor API will ban clients that auto-retry "
    "on 429s. We only retry on 503 because those are transient server errors.\n\n"
    "Human: Makes sense. Should we add a comment to src/api.py to explain this?\n\n"
    "Assistant: Absolutely. Add a docstring to fetchUserWithRetry explaining the 503-only policy."
)


@pytest.fixture
def sample_session() -> Session:
    return Session(
        session_id="test-session-001",
        source=SessionSource.MANUAL,
        start_time=datetime(2025, 11, 14, 10, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2025, 11, 14, 10, 30, 0, tzinfo=timezone.utc),
        raw_transcript=SAMPLE_TRANSCRIPT,
        files_mentioned=["src/api.py"],
    )


# ── Tests for extract_files_mentioned ─────────────────────────────────────────


# @pytest.mark.skip(reason="TODO Week 1: implement extract_files_mentioned first")
def test_extract_files_mentioned_basic():
    text = "I edited src/api.py and tests/test_api.py today."
    result = extract_files_mentioned(text)
    assert "src/api.py" in result
    assert "tests/test_api.py" in result


# @pytest.mark.skip(reason="TODO Week 1: implement extract_files_mentioned first")
def test_extract_files_mentioned_deduplicates():
    text = "src/api.py was mentioned and src/api.py again."
    result = extract_files_mentioned(text)
    assert result.count("src/api.py") == 1


# @pytest.mark.skip(reason="TODO Week 1: implement extract_files_mentioned first")
def test_extract_files_mentioned_ignores_non_paths():
    text = "The quick brown fox jumps over the lazy dog."
    result = extract_files_mentioned(text)
    assert result == []


# @pytest.mark.skip(reason="TODO Week 1: implement extract_files_mentioned first")
def test_extract_files_mentioned_multiple_extensions():
    text = "Modified main.go, styles.css, and components/Button.tsx"
    result = extract_files_mentioned(text)
    assert len(result) == 3


# ── Tests for chunk_session ───────────────────────────────────────────────────


# @pytest.mark.skip(reason="TODO Week 1: implement chunk_session first")
def test_chunk_session_produces_chunks(sample_session):
    chunks = chunk_session(sample_session)
    assert len(chunks) > 0


# @pytest.mark.skip(reason="TODO Week 1: implement chunk_session first")
def test_chunk_has_unique_ids(sample_session):
    chunks = chunk_session(sample_session)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)), "Chunk IDs must be unique"


##@pytest.mark.skip(reason="TODO Week 1: implement chunk_session first")
def test_chunk_ids_reference_session(sample_session):
    chunks = chunk_session(sample_session)
    for chunk in chunks:
        assert chunk.session_id == sample_session.session_id
        assert sample_session.session_id in chunk.chunk_id


# @pytest.mark.skip(reason="TODO Week 1: implement chunk_session first")
def test_chunks_mention_files(sample_session):
    chunks = chunk_session(sample_session)
    # At least one chunk should mention src/api.py
    mentioned = [f for c in chunks for f in c.files_mentioned]
    assert "src/api.py" in mentioned


# @pytest.mark.skip(reason="TODO Week 1: implement chunk_session first")
def test_chunk_embedding_is_none_before_week2(sample_session):
    chunks = chunk_session(sample_session)
    for chunk in chunks:
        assert chunk.embedding is None, "Embeddings are set in Week 2, not Week 1"
