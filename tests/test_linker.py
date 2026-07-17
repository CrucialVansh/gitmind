"""
Tests for gitmind/linker.py

Week 1: write these tests alongside your implementation.

Run with:  pytest tests/test_linker.py -v
"""

import pytest
from datetime import datetime, timezone, timedelta

from gitmind.linker import (
    link_commit,
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
    return Session(
        session_id="session-match",
        source=SessionSource.CURSOR,
        start_time=BASE_TIME - timedelta(hours=1),
        end_time=BASE_TIME - timedelta(minutes=10),  # ended 10min before commit
        raw_transcript="We discussed src/api.py retry logic. The vendor said...",
        files_mentioned=["src/api.py"],
    )


@pytest.fixture
def non_overlapping_session() -> Session:
    """A session that has no file overlap with the commit."""
    return Session(
        session_id="session-no-match",
        source=SessionSource.CURSOR,
        start_time=BASE_TIME - timedelta(hours=1),
        end_time=BASE_TIME - timedelta(minutes=10),
        raw_transcript="Worked on styles.css and index.html today.",
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
        raw_transcript="Edited src/api.py for a different reason.",
        files_mentioned=["src/api.py"],
    )


# ── Tests for _is_in_time_window ──────────────────────────────────────────────

@pytest.mark.skip(reason="TODO Week 1: implement _is_in_time_window first")
def test_session_in_window(sample_commit, matching_session):
    assert _is_in_time_window(sample_commit, matching_session) is True


@pytest.mark.skip(reason="TODO Week 1: implement _is_in_time_window first")
def test_session_out_of_window(sample_commit, out_of_window_session):
    assert _is_in_time_window(sample_commit, out_of_window_session) is False


# ── Tests for _compute_relevance_score ────────────────────────────────────────

@pytest.mark.skip(reason="TODO Week 1: implement _compute_relevance_score first")
def test_score_above_minimum_for_match(sample_commit, matching_session):
    score = _compute_relevance_score(sample_commit, matching_session)
    assert score >= MIN_PAIR_SCORE


@pytest.mark.skip(reason="TODO Week 1: implement _compute_relevance_score first")
def test_score_is_zero_for_no_file_overlap(sample_commit, non_overlapping_session):
    score = _compute_relevance_score(sample_commit, non_overlapping_session)
    assert score < MIN_PAIR_SCORE


@pytest.mark.skip(reason="TODO Week 1: implement _compute_relevance_score first")
def test_score_in_valid_range(sample_commit, matching_session):
    score = _compute_relevance_score(sample_commit, matching_session)
    assert 0.0 <= score <= 1.0


# ── Tests for link_commit ─────────────────────────────────────────────────────

@pytest.mark.skip(reason="TODO Week 1: implement link_commit first")
def test_link_commit_finds_matching_session(
    sample_commit, matching_session, non_overlapping_session
):
    pairs = link_commit(sample_commit, [matching_session, non_overlapping_session])
    assert len(pairs) == 1
    assert pairs[0].session_id == matching_session.session_id


@pytest.mark.skip(reason="TODO Week 1: implement link_commit first")
def test_link_commit_returns_empty_for_no_match(sample_commit, non_overlapping_session):
    pairs = link_commit(sample_commit, [non_overlapping_session])
    assert pairs == []


@pytest.mark.skip(reason="TODO Week 1: implement link_commit first")
def test_link_commit_excludes_out_of_window(sample_commit, out_of_window_session):
    pairs = link_commit(sample_commit, [out_of_window_session])
    assert pairs == []


@pytest.mark.skip(reason="TODO Week 1: implement link_commit first")
def test_pair_id_format(sample_commit, matching_session):
    pairs = link_commit(sample_commit, [matching_session])
    assert pairs[0].pair_id == f"{sample_commit.hash}::{matching_session.session_id}"
