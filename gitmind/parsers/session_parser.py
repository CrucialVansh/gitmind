"""
Session Parser — Week 1 core task.

Reads AI session transcripts from multiple sources and produces
a stream of Session objects with chunked content.

Supported sources (add more in future):
  - Cursor  : reads local SQLite workspace history
  - Claude  : reads exported JSON from Claude Projects
  - Manual  : reads a plain-text or markdown transcript file

Public API:
    parse_cursor_sessions(workspace_path)  →  Iterator[Session]
    parse_claude_export(json_path)         →  Iterator[Session]
    parse_manual_transcript(file_path)     →  Session
    chunk_session(session)                 →  list[SessionChunk]

Key design decision — CHUNKING STRATEGY:
  Don't store entire sessions as one blob.
  Split into chunks at natural boundaries (turn boundaries)
  so the retrieval system can surface the specific part of a session
  that's relevant, not the whole 10,000-token conversation.

  A "chunk" = one full user+assistant exchange (a turn pair).
  If a turn pair is >1000 tokens, split it further at sentence boundaries.

Week 1 TODO list (in order):
  [ ] Implement parse_cursor_sessions() — read ~/.cursor/User/workspaceStorage/
  [ ] Implement _find_cursor_db_files() to glob for history.db files
  [ ] Implement _parse_cursor_row() to parse one row from Cursor's SQLite
  [ ] Implement parse_claude_export() for Claude's JSON export format
  [ ] Implement parse_manual_transcript() for plain .md files
  [ ] Implement chunk_session() to split sessions into SessionChunk objects
  [ ] Implement _extract_files_mentioned() using filepath regex patterns
  [ ] Write tests in tests/test_session_parser.py
"""

import re
from pathlib import Path
from typing import Iterator

from gitmind.models import Session, SessionChunk, SessionSource


# ── Filepath detection regex ───────────────────────────────────────────────────
# Matches patterns like: src/api.py, ./utils/helpers.ts, /home/user/project/main.go
_FILEPATH_PATTERN = re.compile(
    r"""
    (?:^|[\s'"`(])          # preceded by whitespace or quote
    (
        (?:\.{0,2}/)?       # optional relative prefix (./ or ../)
        [\w\-/]+            # directory path components
        \.                  # must have an extension
        (?:py|ts|js|go|rs|java|cpp|c|rb|swift|kt|md|yaml|yml|json|toml|css|tsx|html|pyi|sh|cfg)
    )
    (?:$|[\s'"`):,])        # followed by whitespace or punctuation
    """,
    re.VERBOSE | re.MULTILINE,
)

MAX_CHUNK_TOKENS = 1000

# ── Cursor ─────────────────────────────────────────────────────────────────────


def parse_cursor_sessions(
    workspace_path: Path | None = None,
) -> Iterator[Session]:
    """
    Read Cursor's local session history from its SQLite workspace databases.

    Cursor stores conversation history in:
        ~/.cursor/User/workspaceStorage/<hash>/history.db

    Each database contains a `conversations` table with columns:
        id, timestamp, messages (JSON blob)

    Args:
        workspace_path: Override the default Cursor storage path.
                        Defaults to ~/.cursor/User/workspaceStorage/

    Yields:
        Session objects, newest first.

    TODO (Week 1): implement this.
    """
    raise NotImplementedError


def _find_cursor_db_files(storage_root: Path) -> list[Path]:
    """
    Glob for all history.db files under the Cursor workspaceStorage directory.

    TODO (Week 1): implement this.
    """
    raise NotImplementedError


def _parse_cursor_row(row: dict) -> Session | None:
    """
    Convert one row from Cursor's conversations table into a Session.

    The messages column is a JSON array of {role, content} objects.
    Parse it into a raw_transcript string and extract files_mentioned.

    Returns None if the row doesn't contain useful content.

    TODO (Week 1): implement this.
    """
    raise NotImplementedError


# ── Claude ─────────────────────────────────────────────────────────────────────


def parse_claude_export(json_path: Path) -> Iterator[Session]:
    """
    Parse a Claude Projects conversation export (JSON format).

    To export from Claude:
        Claude.ai → Project → ··· → Export conversations → JSON

    The export format is a list of conversation objects:
        [{ "id": "...", "created_at": "...", "messages": [...] }]

    TODO (Week 1): implement this.
    """
    raise NotImplementedError


# ── Manual / Markdown ──────────────────────────────────────────────────────────


def parse_manual_transcript(file_path: Path) -> Session:
    """
    Parse a manually exported transcript (plain text or markdown).

    Expected format (flexible — try to handle common paste formats):
        Human: <message>
        Assistant: <message>
        ...

    or:
        You: <message>
        Claude/ChatGPT/Cursor: <message>
        ...

    TODO (Week 1): implement this.
    """
    raise NotImplementedError


# ── Chunking ───────────────────────────────────────────────────────────────────


def chunk_session(session: Session) -> list[SessionChunk]:
    """
    Split a session into retrievable chunks at turn boundaries.

    Strategy:
        - One chunk = one user turn + its assistant response
        - If a chunk exceeds MAX_CHUNK_TOKENS, split at sentence boundaries
        - Assign each chunk a unique ID: "{session_id}::chunk_{n}"
        - Extract files_mentioned for each chunk independently

    Args:
        session: A fully populated Session object.

    Returns:
        List of SessionChunk objects (embeddings left as None — set in Week 2).

    TODO (Week 1): implement this.
    """
    chunk = session.raw_transcript.split("Human:")
    chunks = []
    n = 0
    count = 1
    for c in chunk:
        if not c.strip():
            continue
        if len(c.split()) > MAX_CHUNK_TOKENS:
            while len(c.split()) - n > MAX_CHUNK_TOKENS:
                chunks.append(
                    SessionChunk(
                        chunk_id=session.session_id + "::chunk_" + str(count),
                        session_id=session.session_id,
                        text=" ".join(c.split()[n : n + MAX_CHUNK_TOKENS]),
                        turn_index=len(chunks),
                        files_mentioned=extract_files_mentioned(c),
                    )
                )
                n += MAX_CHUNK_TOKENS
                count += 1
            chunks.append(
                SessionChunk(
                    chunk_id=session.session_id + "::chunk_" + str(count),
                    session_id=session.session_id,
                    text=" ".join(c.split()[n:]),
                    turn_index=len(chunks),
                    files_mentioned=extract_files_mentioned(c),
                )
            )
            n = 0
            count += 1
        else:
            chunks.append(
                SessionChunk(
                    chunk_id=session.session_id + "::chunk_" + str(count),
                    session_id=session.session_id,
                    text=c,
                    turn_index=len(chunks),
                    files_mentioned=extract_files_mentioned(c),
                )
            )
            count += 1

    return chunks


# ── Helpers ────────────────────────────────────────────────────────────────────


def extract_files_mentioned(text: str) -> list[str]:
    """
    Scan a block of text for filepath-like patterns and return unique matches.

    Uses _FILEPATH_PATTERN regex. Deduplicates and sorts results.

    Args:
        text: Any string (session transcript, commit message, etc.)

    Returns:
        Sorted list of unique filepath strings found in the text.

    Example:
        >>> extract_files_mentioned("I edited src/api.py and tests/test_api.py")
        ['src/api.py', 'tests/test_api.py']

    TODO (Week 1): implement this — it's used by both parsers and the linker.
    """
    return list(dict.fromkeys(re.findall(_FILEPATH_PATTERN, text)))
