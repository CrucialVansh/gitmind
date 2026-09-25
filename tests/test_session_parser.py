"""
Tests for gitmind/parsers/session_parser.py

Run with:  pytest tests/test_session_parser.py -v
"""

from datetime import datetime, timezone
import json

import pytest

from gitmind.models import Session, SessionSource
from gitmind.parsers.session_parser import (
    chunk_session,
    extract_files_mentioned,
    parse_claude_export,
    parse_manual_transcript,
)


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


def test_extract_files_mentioned_basic():
    text = "I edited src/api.py and tests/test_api.py today."
    result = extract_files_mentioned(text)
    assert "src/api.py" in result
    assert "tests/test_api.py" in result


def test_extract_files_mentioned_deduplicates():
    text = "src/api.py was mentioned and src/api.py again."
    result = extract_files_mentioned(text)
    assert result.count("src/api.py") == 1


def test_extract_files_mentioned_ignores_non_paths():
    text = "The quick brown fox jumps over the lazy dog."
    result = extract_files_mentioned(text)
    assert result == []


def test_extract_files_mentioned_multiple_extensions():
    text = "Modified main.go, styles.css, and components/Button.tsx"
    result = extract_files_mentioned(text)
    assert len(result) == 3


def test_extract_files_mentioned_sorted():
    text = "Check out utils/helpers.py and api/routes.py and auth/login.py"
    result = extract_files_mentioned(text)
    assert result == sorted(result)


# ── Tests for chunk_session ───────────────────────────────────────────────────


def test_chunk_session_produces_chunks(sample_session):
    chunks = chunk_session(sample_session)
    assert len(chunks) > 0


def test_chunk_has_unique_ids(sample_session):
    chunks = chunk_session(sample_session)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)), "Chunk IDs must be unique"


def test_chunk_ids_reference_session(sample_session):
    chunks = chunk_session(sample_session)
    for chunk in chunks:
        assert chunk.session_id == sample_session.session_id
        assert sample_session.session_id in chunk.chunk_id


def test_chunks_mention_files(sample_session):
    chunks = chunk_session(sample_session)
    # At least one chunk should mention src/api.py
    mentioned = [f for c in chunks for f in c.files_mentioned]
    assert "src/api.py" in mentioned


def test_chunk_embedding_is_none_before_week2(sample_session):
    chunks = chunk_session(sample_session)
    for chunk in chunks:
        assert chunk.embedding is None, "Embeddings are set in Week 2, not Week 1"


def test_chunk_text_is_not_empty(sample_session):
    chunks = chunk_session(sample_session)
    for chunk in chunks:
        assert chunk.text.strip(), "Chunk text should not be empty"


# ── Tests for parse_manual_transcript ─────────────────────────────────────────


def test_parse_manual_transcript(tmp_path):
    """Should parse a manual transcript file into a Session."""
    transcript = (
        "Human: How should we handle authentication?\n\n"
        "Assistant: We should use JWT tokens with refresh tokens.\n\n"
        "Human: What about the token expiry?\n\n"
        "Assistant: Set access tokens to 15 minutes, refresh tokens to 7 days."
    )
    file_path = tmp_path / "session.md"
    file_path.write_text(transcript)

    session = parse_manual_transcript(file_path)

    assert session.session_id.startswith("manual-")
    assert session.source == SessionSource.MANUAL
    assert "authentication" in session.raw_transcript.lower()


# ── Tests for parse_claude_export ─────────────────────────────────────────────


def test_parse_claude_export_basic(tmp_path):
    """Should parse a Claude export JSON file."""
    export_data = [
        {
            "uuid": "conv-123",
            "name": "API Design Discussion",
            "created_at": "2025-11-14T10:00:00Z",
            "updated_at": "2025-11-14T11:00:00Z",
            "chat_messages": [
                {"sender": "human", "text": "Let's discuss the API for src/routes.py"},
                {"sender": "assistant", "text": "Sure, we should use RESTful patterns."},
            ],
        }
    ]
    json_path = tmp_path / "conversations.json"
    json_path.write_text(json.dumps(export_data))

    sessions = list(parse_claude_export(json_path))

    assert len(sessions) == 1
    assert sessions[0].source == SessionSource.CLAUDE
    assert "src/routes.py" in sessions[0].files_mentioned
