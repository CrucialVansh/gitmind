"""
Pydantic data models — the shared vocabulary of GitMind.

These are the core data structures that flow through every part of the pipeline:
  git_parser    → Commit
  session_parser → Session
  linker        → CommitSessionPair
  retrieval     → Chunk, QueryResult
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class SessionSource(str, Enum):
    """Where did this AI session transcript come from?"""
    CURSOR = "cursor"
    CLAUDE = "claude"
    COPILOT = "copilot"
    MANUAL = "manual"  # user-imported transcript


class QueryIntent(str, Enum):
    """
    The intent router classifies every user query into one of these.
    Each intent maps to a different retrieval strategy.
    """
    STRUCTURAL = "structural"   # "where does X happen?" → BM25 over AST
    RATIONALE  = "rationale"    # "why did we do X?"    → Decision Synthesizer
    EPISODE    = "episode"      # "what did we decide?" → Confidence-gated FAISS


# ── Core Data Models ──────────────────────────────────────────────────────────

class Commit(BaseModel):
    """
    A single git commit, parsed from `git log --follow -p`.

    Week 1 task: git_parser.py populates this.
    """
    hash: str
    short_hash: str
    message: str
    author: str
    timestamp: datetime
    diff: str                       # raw unified diff text
    files_changed: list[str]        # ["src/api.py", "tests/test_api.py"]
    functions_touched: list[str]    # ["fetchUserWithRetry", "handleRateLimit"]
                                    # populated by tree-sitter in Week 2


class SessionChunk(BaseModel):
    """
    A meaningful excerpt from an AI session transcript.

    Sessions are split into chunks so we can retrieve specific
    parts rather than injecting entire 10,000-token conversations.
    """
    chunk_id: str                   # "{session_id}::chunk_{n}"
    session_id: str
    text: str                       # the actual text of this chunk
    turn_index: int                 # which turn in the session this came from
    files_mentioned: list[str]      # filepaths mentioned in this chunk
    embedding: Optional[list[float]] = None  # populated in Week 2


class Session(BaseModel):
    """
    A full AI coding session transcript (Cursor, Claude, etc.).

    Week 1 task: session_parser.py populates this.
    """
    session_id: str
    source: SessionSource
    start_time: datetime
    end_time: datetime
    raw_transcript: str
    files_mentioned: list[str]      # union of all files across all chunks
    chunks: list[SessionChunk] = Field(default_factory=list)


class CommitSessionPair(BaseModel):
    """
    The core unit of GitMind's knowledge corpus.

    A commit linked to one or more session chunks that contain
    the reasoning behind the changes in that commit.

    Week 1 task: linker.py produces these.
    The paper shows this can be done with ZERO human annotation
    using timestamp + filepath overlap as the linking signal.
    """
    pair_id: str                    # "{commit_hash}::{session_id}"
    commit: Commit
    session_id: str
    relevance_score: float          # confidence in the link (0.0–1.0)
    session_chunks: list[SessionChunk]  # extracted relevant chunks only


# ── Retrieval Models ──────────────────────────────────────────────────────────

class RetrievedChunk(BaseModel):
    """A session chunk returned from the episode store, with its retrieval score."""
    chunk: SessionChunk
    score: float                    # cosine similarity (0.0–1.0)
    passed_gate: bool               # True if score >= settings.episode_gate_threshold


class DecisionArcEntry(BaseModel):
    """
    One entry in the chronological decision timeline reconstructed
    by the Decision Synthesizer.
    """
    date: datetime
    commit_hash: str
    rationale_summary: str          # LLM-extracted "why" from the session chunk
    source_chunk_id: str


class QueryResult(BaseModel):
    """
    The final structured result returned to the CLI / VS Code extension.
    """
    query: str
    intent: QueryIntent
    answer: str                     # natural language answer
    decision_arc: list[DecisionArcEntry] = Field(default_factory=list)
    source_commits: list[str] = Field(default_factory=list)
    source_sessions: list[str] = Field(default_factory=list)
    token_count: int = 0
