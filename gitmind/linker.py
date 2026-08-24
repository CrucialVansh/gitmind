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
"""

from __future__ import annotations

import logging
from os.path import basename

from gitmind.models import Commit, CommitSessionPair, Session, SessionChunk
from gitmind.config import settings
from gitmind.parsers.session_parser import chunk_session

logger = logging.getLogger(__name__)

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
    """
    pairs: list[CommitSessionPair] = []

    for commit in commits:
        commit_pairs = link_commit(commit, sessions)
        pairs.extend(commit_pairs)

    # Sort by commit timestamp, newest first
    pairs.sort(key=lambda p: p.commit.timestamp, reverse=True)

    logger.info(
        "Linked %d commit-session pairs from %d commits and %d sessions",
        len(pairs),
        len(commits),
        len(sessions),
    )

    return pairs


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
    """
    pairs: list[CommitSessionPair] = []

    for session in sessions:
        # Step 1: check time window
        if not _is_in_time_window(commit, session):
            continue

        # Step 2 + 3: compute relevance (returns 0 if no file overlap)
        score = _compute_relevance_score(commit, session)

        # Step 4: filter by minimum score
        if score < MIN_PAIR_SCORE:
            continue

        # Step 5: extract relevant chunks
        # Ensure the session has chunks — generate them if needed
        if not session.chunks:
            session.chunks = chunk_session(session)

        relevant_chunks = _extract_relevant_chunks(session, commit)

        # If no specific chunks match files, include all chunks
        # (the session itself was linked by time + file overlap at session level)
        if not relevant_chunks and session.chunks:
            relevant_chunks = session.chunks

        pair = CommitSessionPair(
            pair_id=f"{commit.hash}::{session.session_id}",
            commit=commit,
            session_id=session.session_id,
            relevance_score=score,
            session_chunks=relevant_chunks,
        )
        pairs.append(pair)

        logger.debug(
            "Linked commit %s to session %s (score=%.2f, %d chunks)",
            commit.short_hash,
            session.session_id,
            score,
            len(relevant_chunks),
        )

    return pairs


def _is_in_time_window(commit: Commit, session: Session) -> bool:
    """
    Return True if the session's end time is within
    settings.link_time_window_seconds of the commit timestamp.
    """
    time_delta = abs(
        (commit.timestamp - session.end_time).total_seconds()
    )
    return time_delta <= settings.link_time_window_seconds


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

    Returns 0.0 if there is no file overlap at all.
    """
    # Compute file overlap — normalize paths for comparison
    commit_files = set(_normalize_path(f) for f in commit.files_changed)
    session_files = set(_normalize_path(f) for f in session.files_mentioned)

    overlapping = commit_files & session_files
    if not overlapping:
        return 0.0

    # Base score for any overlap
    base = 0.5

    # Bonus for additional overlapping files
    file_bonus = min(0.4, 0.1 * len(overlapping))

    # Time penalty
    time_delta = abs((commit.timestamp - session.end_time).total_seconds())
    time_penalty = 0.1 if time_delta > 3600 else 0.0

    # Clamp to [0.0, 1.0]
    score = max(0.0, min(1.0, base + file_bonus - time_penalty))
    return score


def _normalize_path(path: str) -> str:
    """Normalize a file path for comparison (strip ./ prefix, etc.)."""
    path = path.strip()
    if path.startswith("./"):
        path = path[2:]
    if path.startswith("/"):
        # Use just the relative portion — take basename as fallback
        parts = path.split("/")
        # Try to find a reasonable relative path
        for i, part in enumerate(parts):
            if part in ("src", "lib", "app", "tests", "test", "pkg", "internal"):
                return "/".join(parts[i:])
        return basename(path)
    return path


def _extract_relevant_chunks(
    session: Session,
    commit: Commit,
) -> list[SessionChunk]:
    """
    From a session, return only the chunks that mention at least one
    of the files changed in the commit.

    We don't want to store the entire session — just the parts that
    are directly relevant to this commit's changes.
    """
    commit_files = set(_normalize_path(f) for f in commit.files_changed)

    relevant: list[SessionChunk] = []
    for chunk in session.chunks:
        chunk_files = set(_normalize_path(f) for f in chunk.files_mentioned)
        if chunk_files & commit_files:
            relevant.append(chunk)

    return relevant
