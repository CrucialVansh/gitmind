"""
SQLite database layer for GitMind.

Handles schema creation, migrations, and CRUD operations for:
  - commits
  - sessions
  - session_chunks
  - commit_session_pairs

Uses synchronous sqlite3 for the CLI.
"""

from datetime import datetime, timezone
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
        """
        settings.ensure_data_dir()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    # ── Commits ────────────────────────────────────────────────────────────────

    def insert_commit(self, commit: Commit) -> None:
        """Insert a single commit. Ignores duplicates (IGNORE conflict)."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT OR IGNORE INTO commits "
                "(hash, short_hash, message, author, timestamp, diff, files_changed, functions_touched) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    commit.hash,
                    commit.short_hash,
                    commit.message,
                    commit.author,
                    int(commit.timestamp.timestamp()),
                    commit.diff,
                    json.dumps(commit.files_changed),
                    json.dumps(commit.functions_touched),
                ),
            )
            conn.commit()

    def get_commit(self, hash: str) -> Commit | None:
        """Fetch a commit by its full hash."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM commits WHERE hash = ?", (hash,))
            row = cur.fetchone()
            if row is None:
                return None
            return _row_to_commit(row)

    def get_all_commits(self) -> list[Commit]:
        """Return all indexed commits, newest first."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM commits ORDER BY timestamp DESC")
            return [_row_to_commit(row) for row in cur.fetchall()]

    def get_commits_by_file(self, filepath: str) -> list[Commit]:
        """
        Return all commits that touched a given filepath.
        Used by the Decision Synthesizer to build the timeline.
        """
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM commits WHERE files_changed LIKE ? ORDER BY timestamp DESC",
                (f"%{filepath}%",),
            )
            return [_row_to_commit(row) for row in cur.fetchall()]

    # ── Sessions ───────────────────────────────────────────────────────────────

    def insert_session(self, session: Session) -> None:
        """Insert a session and all its chunks."""
        with self._connect() as conn:
            cur = conn.cursor()

            # Insert the session itself
            cur.execute(
                "INSERT OR IGNORE INTO sessions "
                "(session_id, source, start_time, end_time, raw_transcript, files_mentioned) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    session.session_id,
                    session.source.value if hasattr(session.source, 'value') else str(session.source),
                    int(session.start_time.timestamp()),
                    int(session.end_time.timestamp()),
                    session.raw_transcript,
                    json.dumps(session.files_mentioned),
                ),
            )

            # Insert all chunks
            for chunk in session.chunks:
                cur.execute(
                    "INSERT OR IGNORE INTO session_chunks "
                    "(chunk_id, session_id, text, turn_index, files_mentioned, embedding) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        chunk.chunk_id,
                        chunk.session_id,
                        chunk.text,
                        chunk.turn_index,
                        json.dumps(chunk.files_mentioned),
                        None,  # embedding set in Week 2
                    ),
                )

            conn.commit()

    def get_session(self, session_id: str) -> Session | None:
        """Fetch a session by its ID, including its chunks."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = cur.fetchone()
            if row is None:
                return None

            session = _row_to_session(row)

            # Load chunks
            cur.execute(
                "SELECT * FROM session_chunks WHERE session_id = ? ORDER BY turn_index",
                (session_id,),
            )
            session.chunks = [_row_to_chunk(r) for r in cur.fetchall()]

            return session

    def get_all_sessions(self) -> list[Session]:
        """Return all indexed sessions, newest first."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM sessions ORDER BY start_time DESC")
            return [_row_to_session(row) for row in cur.fetchall()]

    def get_sessions_in_window(
        self,
        center_timestamp: float,
        window_seconds: int,
    ) -> list[Session]:
        """
        Return all sessions whose time range overlaps with
        [center_timestamp - window, center_timestamp + window].

        Used by the linker to find sessions near a commit.
        """
        lo = center_timestamp - window_seconds
        hi = center_timestamp + window_seconds
        with self._connect() as conn:
            cur = conn.cursor()
            # A session overlaps the window if it starts before the window ends
            # AND ends after the window starts
            cur.execute(
                "SELECT * FROM sessions WHERE start_time <= ? AND end_time >= ?",
                (hi, lo),
            )
            return [_row_to_session(row) for row in cur.fetchall()]

    # ── Session Chunks ──────────────────────────────────────────────────────────

    def get_all_chunks(self) -> list[SessionChunk]:
        """Return all session chunks."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM session_chunks ORDER BY session_id, turn_index")
            return [_row_to_chunk(row) for row in cur.fetchall()]

    # ── Commit-Session Pairs ────────────────────────────────────────────────────

    def insert_pair(self, pair: CommitSessionPair) -> None:
        """Insert a commit-session pair with its chunk IDs."""
        with self._connect() as conn:
            cur = conn.cursor()
            chunk_ids = [c.chunk_id for c in pair.session_chunks]
            cur.execute(
                "INSERT OR IGNORE INTO commit_session_pairs "
                "(pair_id, commit_hash, session_id, relevance_score, chunk_ids) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    pair.pair_id,
                    pair.commit.hash,
                    pair.session_id,
                    pair.relevance_score,
                    json.dumps(chunk_ids),
                ),
            )
            conn.commit()

    def get_pairs_for_commit(self, commit_hash: str) -> list[dict]:
        """Return all pairs for a given commit hash."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM commit_session_pairs WHERE commit_hash = ?",
                (commit_hash,),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_pairs_for_function(self, function_name: str) -> list[dict]:
        """
        Return all (commit, session) pair records where the commit touched
        the given function. Used by the Decision Synthesizer.

        Returns lightweight dicts rather than full CommitSessionPair objects
        to avoid the circular loading problem.
        """
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT csp.*, c.timestamp as commit_timestamp, c.message as commit_message
                   FROM commit_session_pairs csp
                   JOIN commits c ON csp.commit_hash = c.hash
                   WHERE c.functions_touched LIKE ?
                   ORDER BY c.timestamp DESC""",
                (f"%{function_name}%",),
            )
            return [dict(row) for row in cur.fetchall()]

    # ── Stats ──────────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, int]:
        """
        Return row counts for all tables.
        Used by `gitmind status` to show index health.
        """
        with self._connect() as conn:
            cur = conn.cursor()

            cur.execute("SELECT COUNT(*) FROM commits")
            commits = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM sessions")
            sessions = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM session_chunks")
            chunks = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM commit_session_pairs")
            pairs = cur.fetchone()[0]

            return {
                "commits": commits,
                "sessions": sessions,
                "chunks": chunks,
                "pairs": pairs,
            }


# ── Helper functions ──────────────────────────────────────────────────────────


def _row_to_commit(row: sqlite3.Row) -> Commit:
    """Convert a database row to a Commit model."""
    return Commit(
        hash=row["hash"],
        short_hash=row["short_hash"],
        message=row["message"],
        author=row["author"],
        timestamp=datetime.fromtimestamp(row["timestamp"], tz=timezone.utc),
        diff=row["diff"],
        files_changed=json.loads(row["files_changed"]),
        functions_touched=json.loads(row["functions_touched"]),
    )


def _row_to_session(row: sqlite3.Row) -> Session:
    """Convert a database row to a Session model."""
    return Session(
        session_id=row["session_id"],
        source=row["source"],
        start_time=datetime.fromtimestamp(row["start_time"], tz=timezone.utc),
        end_time=datetime.fromtimestamp(row["end_time"], tz=timezone.utc),
        raw_transcript=row["raw_transcript"],
        files_mentioned=json.loads(row["files_mentioned"]),
    )


def _row_to_chunk(row: sqlite3.Row) -> SessionChunk:
    """Convert a database row to a SessionChunk model."""
    return SessionChunk(
        chunk_id=row["chunk_id"],
        session_id=row["session_id"],
        text=row["text"],
        turn_index=row["turn_index"],
        files_mentioned=json.loads(row["files_mentioned"]),
        embedding=None,  # loaded separately when needed
    )
