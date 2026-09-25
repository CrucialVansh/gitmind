"""
Tests for gitmind/linker.py

Run with:  pytest tests/test_linker.py -v
"""

from datetime import datetime, timezone, timedelta

import pytest

from gitmind.linker import (
    link_commit,
    link_all,
    _is_in_time_window,
    _compute_relevance_score,
    MIN_PAIR_SCORE,
)
from gitmind.models import Commit, Session, SessionSource


# ── Fixtures ───────────────────────────────────────────────────────────────────

BASE_TIME = datetime(2025, 11, 14, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_commit() -> Commit:
    return Commit(
        hash="a" * 40,
        short_hash="aaaaaaa",
        message="fix retry logic to only retry on 503",
        author="dev@example.com",
        timestamp=BASE_TIME,
        diff="--- a/src/api.py\n+++ b/src/api.py\n@@ ... @@",
        files_changed=["src/api.py", "tests/test_api.py"],
        functions_touched=[],
    )


@pytest.fixture
def matching_session() -> Session:
    """A session that temporally and file-wise overlaps with the commit."""
    transcript = (
        "Human: We discussed src/api.py retry logic. The vendor said...\n\n"
        "Assistant: Yes, we should only retry on 503."
    )
    return Session(
        session_id="session-match",
        source=SessionSource.CURSOR,
        start_time=BASE_TIME - timedelta(hours=1),
        end_time=BASE_TIME - timedelta(minutes=10),  # ended 10min before commit
        raw_transcript=transcript,
        files_mentioned=["src/api.py"],
    )


@pytest.fixture
def non_overlapping_session() -> Session:
    """A session that has no file overlap with the commit."""
    transcript = (
        "Human: Worked on styles.css and index.html today.\n\n"
        "Assistant: Great, the CSS looks good."
    )
    return Session(
        session_id="session-no-match",
        source=SessionSource.CURSOR,
        start_time=BASE_TIME - timedelta(hours=1),
        end_time=BASE_TIME - timedelta(minutes=10),
        raw_transcript=transcript,
        files_mentioned=["styles.css", "index.html"],
    )


@pytest.fixture
def out_of_window_session() -> Session:
    """A session that overlaps on files but is outside the time window."""
    return Session(
        session_id="session-old",
        source=SessionSource.CURSOR,
        start_time=BASE_TIME - timedelta(days=7),
        end_time=BASE_TIME - timedelta(days=6),  # a week before the commit
        raw_transcript="Human: Edited src/api.py for a different reason.\n\nAssistant: OK.",
        files_mentioned=["src/api.py"],
    )


# ── Tests for _is_in_time_window ──────────────────────────────────────────────

def test_session_in_window(sample_commit, matching_session):
    assert _is_in_time_window(sample_commit, matching_session) is True


def test_session_out_of_window(sample_commit, out_of_window_session):
    assert _is_in_time_window(sample_commit, out_of_window_session) is False


def test_session_at_boundary(sample_commit):
    """Session ending exactly at the window boundary should be included."""
    from gitmind.config import settings
    boundary_session = Session(
        session_id="session-boundary",
        source=SessionSource.CURSOR,
        start_time=BASE_TIME - timedelta(hours=3),
        end_time=BASE_TIME - timedelta(seconds=settings.link_time_window_seconds),
        raw_transcript="Human: test",
        files_mentioned=["src/api.py"],
    )
    assert _is_in_time_window(sample_commit, boundary_session) is True


# ── Tests for _compute_relevance_score ────────────────────────────────────────

def test_score_above_minimum_for_match(sample_commit, matching_session):
    score = _compute_relevance_score(sample_commit, matching_session)
    assert score >= MIN_PAIR_SCORE


def test_score_is_zero_for_no_file_overlap(sample_commit, non_overlapping_session):
    score = _compute_relevance_score(sample_commit, non_overlapping_session)
    assert score == 0.0


def test_score_in_valid_range(sample_commit, matching_session):
    score = _compute_relevance_score(sample_commit, matching_session)
    assert 0.0 <= score <= 1.0


def test_score_increases_with_more_files(sample_commit):
    """More file overlaps should increase the score."""
    single_file_session = Session(
        session_id="s1",
        source=SessionSource.CURSOR,
        start_time=BASE_TIME - timedelta(hours=1),
        end_time=BASE_TIME - timedelta(minutes=10),
        raw_transcript="test",
        files_mentioned=["src/api.py"],
    )
    multi_file_session = Session(
        session_id="s2",
        source=SessionSource.CURSOR,
        start_time=BASE_TIME - timedelta(hours=1),
        end_time=BASE_TIME - timedelta(minutes=10),
        raw_transcript="test",
        files_mentioned=["src/api.py", "tests/test_api.py"],
    )
    score1 = _compute_relevance_score(sample_commit, single_file_session)
    score2 = _compute_relevance_score(sample_commit, multi_file_session)
    assert score2 > score1


# ── Tests for link_commit ─────────────────────────────────────────────────────

def test_link_commit_finds_matching_session(
    sample_commit, matching_session, non_overlapping_session
):
    pairs = link_commit(sample_commit, [matching_session, non_overlapping_session])
    assert len(pairs) == 1
    assert pairs[0].session_id == matching_session.session_id


def test_link_commit_returns_empty_for_no_match(sample_commit, non_overlapping_session):
    pairs = link_commit(sample_commit, [non_overlapping_session])
    assert not pairs


def test_link_commit_excludes_out_of_window(sample_commit, out_of_window_session):
    pairs = link_commit(sample_commit, [out_of_window_session])
    assert not pairs


def test_pair_id_format(sample_commit, matching_session):
    pairs = link_commit(sample_commit, [matching_session])
    assert pairs[0].pair_id == f"{sample_commit.hash}::{matching_session.session_id}"


def test_pair_has_chunks(sample_commit, matching_session):
    pairs = link_commit(sample_commit, [matching_session])
    assert len(pairs) == 1
    assert len(pairs[0].session_chunks) > 0


# ── Tests for link_all ────────────────────────────────────────────────────────

def test_link_all_basic(sample_commit, matching_session, non_overlapping_session):
    pairs = link_all([sample_commit], [matching_session, non_overlapping_session])
    assert len(pairs) == 1


def test_link_all_returns_empty_when_no_sessions(sample_commit):
    pairs = link_all([sample_commit], [])
    assert not pairs
