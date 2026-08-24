"""
Session Parser — Week 1 core task.

Reads AI session transcripts from multiple sources and produces
a stream of Session objects with chunked content.

Supported sources (add more in future):
  - Cursor  : reads local SQLite workspace history (state.vscdb / cursorDiskKV)
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
"""

import hashlib
import json
import logging
import platform
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from gitmind.models import Session, SessionChunk, SessionSource

logger = logging.getLogger(__name__)

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

# Turn-boundary pattern: matches Human:, You:, User:, Assistant:, Claude:, etc.
_TURN_PATTERN = re.compile(
    r"^(Human|You|User|Assistant|Claude|ChatGPT|Cursor|AI|System)\s*:",
    re.MULTILINE | re.IGNORECASE,
)

MAX_CHUNK_TOKENS = 1000


# ── Cursor ─────────────────────────────────────────────────────────────────────


def _get_cursor_storage_root() -> Path:
    """Get the platform-specific Cursor workspace storage root."""
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Cursor" / "User"
    elif system == "Linux":
        return Path.home() / ".config" / "Cursor" / "User"
    elif system == "Windows":
        appdata = Path.home() / "AppData" / "Roaming"
        return appdata / "Cursor" / "User"
    else:
        # Fallback
        return Path.home() / ".cursor" / "User"


def _find_cursor_db_files(storage_root: Path) -> list[Path]:
    """
    Glob for all state.vscdb files under the Cursor workspaceStorage directory.
    Falls back to looking for legacy history.db files.
    """
    db_files: list[Path] = []

    workspace_storage = storage_root / "workspaceStorage"
    if workspace_storage.exists():
        # Modern format: state.vscdb
        db_files.extend(workspace_storage.glob("*/state.vscdb"))

    # Also check globalStorage for the global state.vscdb
    global_db = storage_root / "globalStorage" / "state.vscdb"
    if global_db.exists():
        db_files.append(global_db)

    return db_files


def parse_cursor_sessions(
    workspace_path: Path | None = None,
) -> Iterator[Session]:
    """
    Read Cursor's local session history from its SQLite workspace databases.

    Cursor stores conversation history in state.vscdb files using either:
      - Modern: `cursorDiskKV` table (keys: composerData:*, bubbleId:*)
      - Legacy: `ItemTable` (keys: %aichat%, %aiService%)

    Args:
        workspace_path: Override path to a specific state.vscdb file,
                        or to the Cursor User directory.
                        Defaults to platform-specific Cursor storage.

    Yields:
        Session objects, newest first.
    """
    if workspace_path and workspace_path.is_file():
        # Direct path to a single DB file
        db_files = [workspace_path]
    elif workspace_path and workspace_path.is_dir():
        db_files = _find_cursor_db_files(workspace_path)
    else:
        storage_root = _get_cursor_storage_root()
        db_files = _find_cursor_db_files(storage_root)

    if not db_files:
        logger.warning("No Cursor database files found.")
        return

    sessions: list[Session] = []

    for db_path in db_files:
        try:
            parsed = list(_parse_cursor_db(db_path))
            sessions.extend(parsed)
        except Exception as e:
            logger.warning("Failed to parse Cursor DB %s: %s", db_path, e)
            continue

    # Sort newest first by start_time
    sessions.sort(key=lambda s: s.start_time, reverse=True)
    yield from sessions


def _parse_cursor_db(db_path: Path) -> Iterator[Session]:
    """Parse a single Cursor state.vscdb file."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

    try:
        cursor = conn.cursor()

        # Detect which table format we're dealing with
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('cursorDiskKV', 'ItemTable')"
        )
        tables = [row[0] for row in cursor.fetchall()]

        if "cursorDiskKV" in tables:
            yield from _parse_cursor_disk_kv(conn, db_path)
        elif "ItemTable" in tables:
            yield from _parse_cursor_item_table(conn, db_path)
        else:
            logger.debug("No recognized chat tables in %s", db_path)

    except sqlite3.OperationalError as e:
        logger.warning("Database error for %s: %s", db_path, e)
    finally:
        conn.close()


def _parse_cursor_disk_kv(conn: sqlite3.Connection, db_path: Path) -> Iterator[Session]:
    """Parse the modern cursorDiskKV format."""
    cursor = conn.cursor()

    # Get all composerData entries (session metadata)
    cursor.execute(
        "SELECT key, value FROM cursorDiskKV WHERE key LIKE 'composerData:%'"
    )
    composer_rows = cursor.fetchall()

    for key, value in composer_rows:
        try:
            composer_id = key.split(":", 1)[1] if ":" in key else key
            data = json.loads(value) if isinstance(value, str) else json.loads(
                value.decode("utf-8") if isinstance(value, bytes) else str(value)
            )

            # Fetch associated bubble messages
            cursor.execute(
                "SELECT key, value FROM cursorDiskKV WHERE key LIKE ?",
                (f"bubbleId:{composer_id}:%",),
            )
            bubble_rows = cursor.fetchall()

            messages: list[dict] = []
            for bkey, bvalue in bubble_rows:
                try:
                    bdata = json.loads(bvalue) if isinstance(bvalue, str) else json.loads(
                        bvalue.decode("utf-8") if isinstance(bvalue, bytes) else str(bvalue)
                    )
                    messages.append(bdata)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

            if not messages:
                continue

            session = _build_session_from_cursor_messages(
                composer_id, data, messages, db_path
            )
            if session:
                yield session

        except (json.JSONDecodeError, UnicodeDecodeError, KeyError) as e:
            logger.debug("Skipping composer entry %s: %s", key, e)
            continue


def _parse_cursor_item_table(conn: sqlite3.Connection, db_path: Path) -> Iterator[Session]:
    """Parse the legacy ItemTable format."""
    cursor = conn.cursor()

    cursor.execute(
        """SELECT "key", "value" FROM ItemTable
           WHERE "key" LIKE '%aichat%' OR "key" LIKE '%aiService%'"""
    )
    rows = cursor.fetchall()

    for key, value in rows:
        try:
            data = json.loads(value) if isinstance(value, str) else json.loads(
                value.decode("utf-8") if isinstance(value, bytes) else str(value)
            )
            session = _parse_cursor_row({"key": key, "data": data, "db_path": db_path})
            if session:
                yield session
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.debug("Skipping ItemTable entry %s: %s", key, e)
            continue


def _build_session_from_cursor_messages(
    composer_id: str,
    metadata: dict,
    messages: list[dict],
    db_path: Path,
) -> Session | None:
    """Build a Session from Cursor composer metadata and bubble messages."""
    # Build transcript from messages
    transcript_parts: list[str] = []
    timestamps: list[float] = []

    for msg in messages:
        role = msg.get("role", msg.get("type", "unknown"))
        content = msg.get("content", msg.get("text", ""))
        ts = msg.get("timestamp", msg.get("created_at"))

        if ts:
            if isinstance(ts, (int, float)):
                timestamps.append(ts / 1000 if ts > 1e12 else ts)
            elif isinstance(ts, str):
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    timestamps.append(dt.timestamp())
                except ValueError:
                    pass

        if isinstance(content, list):
            # Handle structured content blocks
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    text_parts.append(block.get("text", str(block)))
                else:
                    text_parts.append(str(block))
            content = "\n".join(text_parts)

        if not content or not content.strip():
            continue

        if role in ("user", "human", "Human"):
            transcript_parts.append(f"Human: {content}")
        else:
            transcript_parts.append(f"Assistant: {content}")

    if not transcript_parts:
        return None

    raw_transcript = "\n\n".join(transcript_parts)
    files = extract_files_mentioned(raw_transcript)

    # Determine timestamps
    if timestamps:
        start_ts = min(timestamps)
        end_ts = max(timestamps)
    else:
        # Use file modification time as fallback
        mtime = db_path.stat().st_mtime
        start_ts = mtime - 3600
        end_ts = mtime

    session_id = f"cursor-{composer_id[:12]}"

    return Session(
        session_id=session_id,
        source=SessionSource.CURSOR,
        start_time=datetime.fromtimestamp(start_ts, tz=timezone.utc),
        end_time=datetime.fromtimestamp(end_ts, tz=timezone.utc),
        raw_transcript=raw_transcript,
        files_mentioned=files,
    )


def _parse_cursor_row(row: dict) -> Session | None:
    """
    Convert one row from Cursor's ItemTable into a Session.

    The data may be a JSON object with messages or conversation data.
    Returns None if the row doesn't contain useful content.
    """
    data = row.get("data", {})
    db_path = row.get("db_path", Path("unknown"))
    key = row.get("key", "")

    # Try to extract messages from various possible structures
    messages = None
    if isinstance(data, dict):
        messages = data.get("messages", data.get("tabs", []))
    elif isinstance(data, list):
        messages = data

    if not messages:
        return None

    # Build transcript
    transcript_parts: list[str] = []
    for msg in messages if isinstance(messages, list) else [messages]:
        if isinstance(msg, dict):
            role = msg.get("role", "assistant")
            content = msg.get("content", msg.get("text", ""))
            if content:
                label = "Human" if role in ("user", "human") else "Assistant"
                transcript_parts.append(f"{label}: {content}")

    if not transcript_parts:
        return None

    raw_transcript = "\n\n".join(transcript_parts)
    files = extract_files_mentioned(raw_transcript)

    # Generate a stable session ID from the key
    session_id = f"cursor-{hashlib.sha256(key.encode()).hexdigest()[:12]}"

    mtime = db_path.stat().st_mtime if isinstance(db_path, Path) and db_path.exists() else datetime.now(tz=timezone.utc).timestamp()

    return Session(
        session_id=session_id,
        source=SessionSource.CURSOR,
        start_time=datetime.fromtimestamp(mtime - 3600, tz=timezone.utc),
        end_time=datetime.fromtimestamp(mtime, tz=timezone.utc),
        raw_transcript=raw_transcript,
        files_mentioned=files,
    )


# ── Claude ─────────────────────────────────────────────────────────────────────


def parse_claude_export(json_path: Path) -> Iterator[Session]:
    """
    Parse a Claude Projects conversation export (JSON format).

    Supports the official Anthropic export format:
        conversations.json → array of {uuid, name, created_at, updated_at, chat_messages}

    Also handles single-conversation exports and nested structures.

    Args:
        json_path: Path to the exported JSON file.

    Yields:
        Session objects.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Handle both array of conversations and single conversation
    conversations: list[dict] = []
    if isinstance(data, list):
        conversations = data
    elif isinstance(data, dict):
        # Could be a single conversation or a wrapper object
        if "chat_messages" in data or "messages" in data:
            conversations = [data]
        elif "conversations" in data:
            conversations = data["conversations"]
        else:
            conversations = [data]

    for conv in conversations:
        try:
            session = _build_session_from_claude_conv(conv)
            if session:
                yield session
        except Exception as e:
            logger.warning("Failed to parse Claude conversation: %s", e)
            continue


def _build_session_from_claude_conv(conv: dict) -> Session | None:
    """Build a Session from a single Claude conversation object."""
    session_id = f"claude-{conv.get('uuid', conv.get('id', hashlib.sha256(json.dumps(conv, default=str).encode()).hexdigest()[:12]))}"

    # Extract messages
    messages = conv.get("chat_messages", conv.get("messages", []))
    if not messages:
        return None

    # Build transcript
    transcript_parts: list[str] = []
    for msg in messages:
        sender = msg.get("sender", msg.get("role", "unknown"))
        text = msg.get("text", msg.get("content", ""))

        if isinstance(text, list):
            # Handle structured content blocks
            text_parts = []
            for block in text:
                if isinstance(block, dict):
                    text_parts.append(block.get("text", str(block)))
                else:
                    text_parts.append(str(block))
            text = "\n".join(text_parts)

        if not text or not text.strip():
            continue

        if sender in ("human", "user", "Human"):
            transcript_parts.append(f"Human: {text}")
        else:
            transcript_parts.append(f"Assistant: {text}")

    if not transcript_parts:
        return None

    raw_transcript = "\n\n".join(transcript_parts)
    files = extract_files_mentioned(raw_transcript)

    # Parse timestamps
    created_at = conv.get("created_at", conv.get("create_time"))
    updated_at = conv.get("updated_at", conv.get("update_time"))

    start_time = _parse_timestamp(created_at) if created_at else datetime.now(tz=timezone.utc)
    end_time = _parse_timestamp(updated_at) if updated_at else start_time

    return Session(
        session_id=session_id,
        source=SessionSource.CLAUDE,
        start_time=start_time,
        end_time=end_time,
        raw_transcript=raw_transcript,
        files_mentioned=files,
    )


def _parse_timestamp(ts) -> datetime:
    """Parse a timestamp from various formats."""
    if isinstance(ts, (int, float)):
        # Unix timestamp — handle milliseconds
        if ts > 1e12:
            ts = ts / 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    elif isinstance(ts, str):
        # ISO 8601 format
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            pass
        # Try other common formats
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(ts, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return datetime.now(tz=timezone.utc)


# ── Manual / Markdown ──────────────────────────────────────────────────────────


def parse_manual_transcript(file_path: Path) -> Session:
    """
    Parse a manually exported transcript (plain text or markdown).

    Handles common paste formats:
        Human: <message>
        Assistant: <message>
    or:
        You: <message>
        Claude/ChatGPT/Cursor: <message>
    or:
        User: <message>
        AI: <message>

    Args:
        file_path: Path to the transcript file.

    Returns:
        A Session object with the parsed content.
    """
    content = file_path.read_text(encoding="utf-8")
    files = extract_files_mentioned(content)

    # Normalize various turn formats to Human:/Assistant:
    normalized = content
    # Replace common user labels
    normalized = re.sub(
        r"^(You|User)\s*:", "Human:", normalized, flags=re.MULTILINE | re.IGNORECASE
    )
    # Replace common assistant labels
    normalized = re.sub(
        r"^(Claude|ChatGPT|Cursor|AI|GPT-4|GPT)\s*:",
        "Assistant:",
        normalized,
        flags=re.MULTILINE | re.IGNORECASE,
    )

    # Generate a stable session ID from the file path
    session_id = f"manual-{hashlib.sha256(str(file_path.resolve()).encode()).hexdigest()[:12]}"

    # Use file modification time for timestamps
    mtime = file_path.stat().st_mtime
    ctime = file_path.stat().st_ctime

    return Session(
        session_id=session_id,
        source=SessionSource.MANUAL,
        start_time=datetime.fromtimestamp(min(ctime, mtime), tz=timezone.utc),
        end_time=datetime.fromtimestamp(max(ctime, mtime), tz=timezone.utc),
        raw_transcript=normalized,
        files_mentioned=files,
    )


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
    """
    # Split at "Human:" boundaries to get turn pairs
    # Each segment starts with the human message and includes the assistant response
    raw = session.raw_transcript
    segments = re.split(r"(?=Human:)", raw)

    chunks: list[SessionChunk] = []
    count = 1

    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue

        word_count = len(segment.split())

        if word_count > MAX_CHUNK_TOKENS:
            # Split large segments at sentence boundaries
            sentences = re.split(r"(?<=[.!?])\s+", segment)
            current_chunk: list[str] = []
            current_words = 0

            for sentence in sentences:
                sentence_words = len(sentence.split())
                if current_words + sentence_words > MAX_CHUNK_TOKENS and current_chunk:
                    # Emit current chunk
                    chunk_text = " ".join(current_chunk)
                    chunks.append(
                        SessionChunk(
                            chunk_id=f"{session.session_id}::chunk_{count}",
                            session_id=session.session_id,
                            text=chunk_text,
                            turn_index=len(chunks),
                            files_mentioned=extract_files_mentioned(chunk_text),
                        )
                    )
                    count += 1
                    current_chunk = []
                    current_words = 0

                current_chunk.append(sentence)
                current_words += sentence_words

            # Emit remainder
            if current_chunk:
                chunk_text = " ".join(current_chunk)
                chunks.append(
                    SessionChunk(
                        chunk_id=f"{session.session_id}::chunk_{count}",
                        session_id=session.session_id,
                        text=chunk_text,
                        turn_index=len(chunks),
                        files_mentioned=extract_files_mentioned(chunk_text),
                    )
                )
                count += 1
        else:
            chunks.append(
                SessionChunk(
                    chunk_id=f"{session.session_id}::chunk_{count}",
                    session_id=session.session_id,
                    text=segment,
                    turn_index=len(chunks),
                    files_mentioned=extract_files_mentioned(segment),
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
    """
    return sorted(set(re.findall(_FILEPATH_PATTERN, text)))
