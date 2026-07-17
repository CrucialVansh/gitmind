"""
SQLite database layer for GitMind.

Handles schema creation, migrations, and CRUD operations for:
  - commits
  - sessions
  - session_chunks
  - commit_session_pairs

Uses aiosqlite for async I/O so the CLI stays responsive during indexing.

Week 1 task: implement create_tables() and the insert/query methods below.
"""

import json
import sqlite3
from pathlib import Path

from gitmind.config import settings
from gitmind.models import Commit, CommitSessionPair, Session, SessionChunk


# ── Schema ─────────────────────────────────────────────────────────────────────

# All CREATE TABLE statements in one place.
# Run via: db.create_tables()
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS commits (
    hash                TEXT PRIMARY KEY,
    short_hash          TEXT NOT NULL,
    message             TEXT NOT NULL,
    author              TEXT NOT NULL,
    timestamp           INTEGER NOT NULL,   -- unix epoch
    diff                TEXT NOT NULL,
    files_changed       TEXT NOT NULL,      -- JSON array
    functions_touched   TEXT NOT NULL       -- JSON array, populated in Week 2
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id      TEXT PRIMARY KEY,
    source          TEXT NOT NULL,          -- SessionSource enum value
    start_time      INTEGER NOT NULL,       -- unix epoch
    end_time        INTEGER NOT NULL,       -- unix epoch
    raw_transcript  TEXT NOT NULL,
    files_mentioned TEXT NOT NULL           -- JSON array
);

CREATE TABLE IF NOT EXISTS session_chunks (
    chunk_id        TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(session_id),
    text            TEXT NOT NULL,
    turn_index      INTEGER NOT NULL,
    files_mentioned TEXT NOT NULL,          -- JSON array
    embedding       BLOB                    -- stored as raw bytes, populated in Week 2
);

CREATE TABLE IF NOT EXISTS commit_session_pairs (
    pair_id             TEXT PRIMARY KEY,
    commit_hash         TEXT NOT NULL REFERENCES commits(hash),
    session_id          TEXT NOT NULL REFERENCES sessions(session_id),
    relevance_score     REAL NOT NULL,
    chunk_ids           TEXT NOT NULL       -- JSON array of session_chunk IDs
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_commits_timestamp
    ON commits(timestamp);

CREATE INDEX IF NOT EXISTS idx_sessions_start
    ON sessions(start_time);

CREATE INDEX IF NOT EXISTS idx_chunks_session
    ON session_chunks(session_id);

CREATE INDEX IF NOT EXISTS idx_pairs_commit
    ON commit_session_pairs(commit_hash);
"""


# ── Database Class ─────────────────────────────────────────────────────────────

class GitMindDB:
    """
    Thin wrapper around SQLite.

    Usage:
        db = GitMindDB()
        db.create_tables()
        db.insert_commit(commit)
    """

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or settings.db_path

    def _connect(self) -> sqlite3.Connection:
        """Open a connection with foreign key enforcement on."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    def create_tables(self) -> None:
        """
        Create all tables and indexes.
        Safe to call multiple times (uses CREATE IF NOT EXISTS).

        TODO (Week 1): call this from `gitmind index` before inserting data.
        """
        settings.ensure_data_dir()
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    # ── Commits ────────────────────────────────────────────────────────────────

    def insert_commit(self, commit: Commit) -> None:
        """
        Insert a single commit. Ignores duplicates (IGNORE conflict).

        TODO (Week 1): implement this.
        """
        raise NotImplementedError

    def get_commit(self, hash: str) -> Commit | None:
        """
        Fetch a commit by its full hash.

        TODO (Week 1): implement this.
        """
        raise NotImplementedError

    def get_commits_by_file(self, filepath: str) -> list[Commit]:
        """
        Return all commits that touched a given filepath.
        Used by the Decision Synthesizer to build the timeline.

        TODO (Week 1): implement this.
        """
        raise NotImplementedError

    # ── Sessions ───────────────────────────────────────────────────────────────

    def insert_session(self, session: Session) -> None:
        """
        Insert a session and all its chunks.

        TODO (Week 1): implement this.
        """
        raise NotImplementedError

    def get_session(self, session_id: str) -> Session | None:
        """
        TODO (Week 1): implement this.
        """
        raise NotImplementedError

    def get_sessions_in_window(
        self,
        center_timestamp: float,
        window_seconds: int,
    ) -> list[Session]:
        """
        Return all sessions whose time range overlaps with
        [center_timestamp - window, center_timestamp + window].

        Used by the linker to find sessions near a commit.

        TODO (Week 1): implement this.
        """
        raise NotImplementedError

    # ── Commit-Session Pairs ────────────────────────────────────────────────────

    def insert_pair(self, pair: CommitSessionPair) -> None:
        """
        TODO (Week 1): implement this.
        """
        raise NotImplementedError

    def get_pairs_for_function(self, function_name: str) -> list[CommitSessionPair]:
        """
        Return all (commit, session) pairs where the commit touched
        the given function. Used by the Decision Synthesizer.

        Requires that commits.functions_touched is populated (Week 2).

        TODO (Week 2): implement this (depends on tree-sitter).
        """
        raise NotImplementedError

    # ── Stats ──────────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, int]:
        """
        Return row counts for all tables.
        Used by `gitmind status` to show index health.

        TODO (Week 1): implement this.
        """
        raise NotImplementedError
