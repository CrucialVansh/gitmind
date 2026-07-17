"""
Commit-Session Linker — Week 1 core task.

This is the heart of GitMind's zero-label-cost approach.

The key insight from the paper:
    A commit and a session are "linked" if:
      1. The session ended within ±TIME_WINDOW of the commit timestamp
      2. The session mentions at least one of the files the commit changed

    This heuristic requires zero human annotation.
    The commit IS the label — it tells us what changed.
    The session IS the rationale — it tells us why.

Public API:
    link_all(commits, sessions)  →  list[CommitSessionPair]
    link_commit(commit, sessions)  →  list[CommitSessionPair]

Scoring:
    relevance_score = overlap score between 0.0 and 1.0, computed as:
        - Base: 0.5 if any file overlaps
        - Bonus: +0.1 per additional overlapping file (capped at 0.4)
        - Time penalty: -0.1 if session ended >1h before/after commit
        - Result is clamped to [0.0, 1.0]

    Only pairs with relevance_score >= MIN_PAIR_SCORE are kept.

Week 1 TODO list (in order):
  [ ] Implement link_commit() with the timestamp + filepath overlap logic
  [ ] Implement _compute_relevance_score() using the scoring formula above
  [ ] Implement _extract_relevant_chunks() to filter chunks by file mention
  [ ] Implement link_all() as a loop over link_commit()
  [ ] Add deduplication: skip pairs already in the DB
  [ ] Write tests in tests/test_linker.py
"""

from __future__ import annotations

from gitmind.models import Commit, CommitSessionPair, Session, SessionChunk
from gitmind.config import settings

# Pairs below this score are discarded (too noisy)
MIN_PAIR_SCORE = 0.5


def link_all(
    commits: list[Commit],
    sessions: list[Session],
) -> list[CommitSessionPair]:
    """
    Link every commit to any sessions that likely contain its rationale.

    Args:
        commits:  All commits from git_parser.
        sessions: All sessions from session_parser.

    Returns:
        List of CommitSessionPair objects, sorted by commit timestamp desc.

    TODO (Week 1): implement this (thin wrapper over link_commit).
    """
    raise NotImplementedError


def link_commit(
    commit: Commit,
    sessions: list[Session],
) -> list[CommitSessionPair]:
    """
    Find all sessions likely to contain the rationale for a single commit.

    Algorithm:
        1. Narrow sessions to those within the time window of the commit.
        2. Among those, find sessions that mention >= 1 of the commit's files.
        3. Score each match with _compute_relevance_score().
        4. Filter out pairs below MIN_PAIR_SCORE.
        5. For each passing session, extract only the relevant chunks.

    Args:
        commit:   The commit to find rationale for.
        sessions: All available sessions to search through.

    Returns:
        List of CommitSessionPair objects (may be empty if no match found).

    TODO (Week 1): implement this.
    """
    raise NotImplementedError


def _is_in_time_window(commit: Commit, session: Session) -> bool:
    """
    Return True if the session's end time is within
    settings.link_time_window_seconds of the commit timestamp.

    TODO (Week 1): implement this.
    """
    raise NotImplementedError


def _compute_relevance_score(
    commit: Commit,
    session: Session,
) -> float:
    """
    Score how confident we are that this session contains the rationale
    for this commit. Higher = more confident.

    Scoring formula:
        base      = 0.5  (any file overlap at all)
        file_bonus = min(0.4, 0.1 * len(overlapping_files))
        time_delta = abs(commit.timestamp - session.end_time).total_seconds()
        time_penalty = 0.1 if time_delta > 3600 else 0.0
        score = clamp(base + file_bonus - time_penalty, 0.0, 1.0)

    TODO (Week 1): implement this.
    """
    raise NotImplementedError


def _extract_relevant_chunks(
    session: Session,
    commit: Commit,
) -> list[SessionChunk]:
    """
    From a session, return only the chunks that mention at least one
    of the files changed in the commit.

    We don't want to store the entire session — just the parts that
    are directly relevant to this commit's changes.

    TODO (Week 1): implement this.
    """
    raise NotImplementedError
