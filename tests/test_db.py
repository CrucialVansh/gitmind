"""
Tests for gitmind/db.py

Integration tests using a temporary database.

Run with:  pytest tests/test_db.py -v
"""

from datetime import datetime, timezone, timedelta

import pytest

from gitmind.db import GitMindDB
from gitmind.models import (
    Commit,
    CommitSessionPair,
    Session,
    SessionChunk,
    SessionSource,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def db(tmp_path):
    """Create a fresh database for each test."""
    db_path = tmp_path / "test_gitmind.db"
    db = GitMindDB(db_path=db_path)
    db.create_tables()
    return db


@pytest.fixture
def sample_commit() -> Commit:
    return Commit(
        hash="a" * 40,
        short_hash="aaaaaaa",
        message="fix retry logic",
        author="dev@example.com",
        timestamp=datetime(2025, 11, 14, 12, 0, 0, tzinfo=timezone.utc),
        diff="--- a/src/api.py\n+++ b/src/api.py",
        files_changed=["src/api.py", "tests/test_api.py"],
        functions_touched=["fetchUserWithRetry"],
    )


@pytest.fixture
def sample_session() -> Session:
    return Session(
        session_id="test-session-001",
        source=SessionSource.CURSOR,
        start_time=datetime(2025, 11, 14, 10, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2025, 11, 14, 11, 0, 0, tzinfo=timezone.utc),
        raw_transcript="Human: Discussed retry logic\n\nAssistant: Only retry on 503",
        files_mentioned=["src/api.py"],
        chunks=[
            SessionChunk(
                chunk_id="test-session-001::chunk_1",
                session_id="test-session-001",
                text="Discussed retry logic for src/api.py",
                turn_index=0,
                files_mentioned=["src/api.py"],
            ),
        ],
    )


# ── Commit CRUD ───────────────────────────────────────────────────────────────

def test_insert_and_get_commit(db, sample_commit):
    db.insert_commit(sample_commit)
    result = db.get_commit(sample_commit.hash)

    assert result is not None
    assert result.hash == sample_commit.hash
    assert result.message == sample_commit.message
    assert result.files_changed == sample_commit.files_changed
    assert result.functions_touched == sample_commit.functions_touched


def test_get_nonexistent_commit(db):
    result = db.get_commit("b" * 40)
    assert result is None


def test_insert_duplicate_commit_is_ignored(db, sample_commit):
    db.insert_commit(sample_commit)
    db.insert_commit(sample_commit)  # should not raise
    stats = db.stats()
    assert stats["commits"] == 1


def test_get_commits_by_file(db, sample_commit):
    db.insert_commit(sample_commit)
    results = db.get_commits_by_file("src/api.py")
    assert len(results) == 1
    assert results[0].hash == sample_commit.hash


def test_get_commits_by_file_no_match(db, sample_commit):
    db.insert_commit(sample_commit)
    results = db.get_commits_by_file("nonexistent.py")
    assert results == []


def test_get_all_commits(db, sample_commit):
    db.insert_commit(sample_commit)
    results = db.get_all_commits()
    assert len(results) == 1


# ── Session CRUD ──────────────────────────────────────────────────────────────

def test_insert_and_get_session(db, sample_session):
    db.insert_session(sample_session)
    result = db.get_session(sample_session.session_id)

    assert result is not None
    assert result.session_id == sample_session.session_id
    assert result.files_mentioned == sample_session.files_mentioned
    assert len(result.chunks) == 1


def test_get_nonexistent_session(db):
    result = db.get_session("nonexistent")
    assert result is None


def test_get_sessions_in_window(db, sample_session):
    db.insert_session(sample_session)

    # Center of the window is within the session's time range
    center = sample_session.start_time.timestamp() + 1800  # 30 min after start
    results = db.get_sessions_in_window(center, 7200)

    assert len(results) == 1


def test_get_sessions_in_window_no_match(db, sample_session):
    db.insert_session(sample_session)

    # Window far from the session
    center = (sample_session.start_time - timedelta(days=30)).timestamp()
    results = db.get_sessions_in_window(center, 7200)

    assert results == []


# ── Pairs ─────────────────────────────────────────────────────────────────────

def test_insert_pair(db, sample_commit, sample_session):
    db.insert_commit(sample_commit)
    db.insert_session(sample_session)

    pair = CommitSessionPair(
        pair_id=f"{sample_commit.hash}::{sample_session.session_id}",
        commit=sample_commit,
        session_id=sample_session.session_id,
        relevance_score=0.8,
        session_chunks=sample_session.chunks,
    )
    db.insert_pair(pair)

    stats = db.stats()
    assert stats["pairs"] == 1


def test_get_pairs_for_commit(db, sample_commit, sample_session):
    db.insert_commit(sample_commit)
    db.insert_session(sample_session)

    pair = CommitSessionPair(
        pair_id=f"{sample_commit.hash}::{sample_session.session_id}",
        commit=sample_commit,
        session_id=sample_session.session_id,
        relevance_score=0.8,
        session_chunks=sample_session.chunks,
    )
    db.insert_pair(pair)

    results = db.get_pairs_for_commit(sample_commit.hash)
    assert len(results) == 1
    assert results[0]["commit_hash"] == sample_commit.hash


# ── Stats ─────────────────────────────────────────────────────────────────────

def test_stats_empty(db):
    stats = db.stats()
    assert stats == {"commits": 0, "sessions": 0, "chunks": 0, "pairs": 0}


def test_stats_populated(db, sample_commit, sample_session):
    db.insert_commit(sample_commit)
    db.insert_session(sample_session)

    stats = db.stats()
    assert stats["commits"] == 1
    assert stats["sessions"] == 1
    assert stats["chunks"] == 1
